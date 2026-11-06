"""Brain Products TriggerBox rev.02 and TriggerBox Plus byte output."""

from __future__ import annotations

import importlib
import threading
import time
from types import ModuleType
from typing import Any

from fpvs_studio.core.trigger_codes import validate_event_trigger_code
from fpvs_studio.triggers.base import TriggerBackend
from fpvs_studio.triggers.brainproducts_errors import (
    triggerbox_failure_reason,
    triggerbox_port_error_message,
)
from fpvs_studio.triggers.brainproducts_windows import WindowsSerialWrite, windows_serial_write
from fpvs_studio.triggers.serial_backend import resolve_serial_port

_WRITE_TIMEOUT_S = 1.0
_WRITE_POLL_S = 0.001


class BrainProductsTriggerBoxError(RuntimeError):
    """Raised when a TriggerBox event or its required zero reset fails."""


class BrainProductsTriggerBoxBackend(TriggerBackend):
    """Write events at the flip, then clear latched outputs on an owned worker.

    Each event requires a high pulse and a low interval of ``pulse_width_ms``.
    Sends never wait for either interval or queue overlapping events. Software
    timer completion is not evidence of physical pulse width or EEG receipt.
    """

    def __init__(
        self,
        port: str | None = "COM3",
        *,
        pulse_width_ms: int = 10,
        serial_module: ModuleType | Any | None = None,
    ) -> None:
        if (
            not isinstance(pulse_width_ms, int)
            or isinstance(pulse_width_ms, bool)
            or not 1 <= pulse_width_ms <= 1000
        ):
            raise ValueError(
                "Enter a whole number from 1 to 1000 ms for the TriggerBox pulse width."
            )
        self._port = resolve_serial_port(port)
        self._pulse_s = pulse_width_ms / 1000.0
        self._serial_module = serial_module
        self._condition = threading.Condition()
        self._connection: Any | None = None
        self._native_write: WindowsSerialWrite | None = None
        self._pending_write: tuple[int, str, float] | None = None
        self._worker: threading.Thread | None = None
        self._pulse_active = False
        self._reset_at: float | None = None
        self._ready_at = 0.0
        self._stopping = False
        self._failure: BrainProductsTriggerBoxError | None = None

    @property
    def backend_name(self) -> str:
        return "brainproducts_triggerbox"

    @property
    def emits_hardware_triggers(self) -> bool:
        return True

    @property
    def emits_external_markers(self) -> bool:
        return True

    def connect(self) -> None:
        with self._condition:
            if self._connection is not None:
                self._raise_failure()
                return
            serial_module = self._serial_module or _load_serial_module()
            try:
                connection = serial_module.Serial(
                    port=self._port,
                    baudrate=2_000_000,
                    bytesize=serial_module.EIGHTBITS,
                    parity=serial_module.PARITY_NONE,
                    stopbits=serial_module.STOPBITS_ONE,
                    timeout=0,
                    write_timeout=0,
                    rtscts=False,
                    dsrdtr=False,
                    xonxoff=False,
                )
            except Exception as exc:
                raise BrainProductsTriggerBoxError(
                    f"{triggerbox_port_error_message(self._port, exc)} "
                    f"Details: Unable to open Brain Products TriggerBox on {self._port!r}: "
                    f"{exc}"
                ) from exc
            try:
                self._native_write = windows_serial_write(connection)
                self._write(connection, 0, action="initialize zero idle")
                self._drain_write()
            except Exception as exc:
                failure = (
                    exc if isinstance(exc, BrainProductsTriggerBoxError)
                    else self._write_failure(0, "initialize zero idle", exc)
                )
                cleanup = self._release_connection(connection, clear=False)
                if cleanup:
                    raise BrainProductsTriggerBoxError(
                        f"{failure} Closing the TriggerBox port also failed. Restart FPVS Studio "
                        f"before retrying. Details: {' '.join(str(error) for error in cleanup)}"
                    ) from exc
                if failure is exc:
                    raise
                raise failure from exc
            self._connection = connection
            self._failure = None
            self._stopping = False
            self._reset_at = None
            self._pulse_active = False
            self._ready_at = time.monotonic() + self._pulse_s
            self._worker = threading.Thread(
                target=self._reset_loop,
                name="FPVS TriggerBox reset",
                daemon=True,
            )
            try:
                self._worker.start()
            except Exception as exc:
                self._connection = None
                self._worker = None
                cleanup = self._release_connection(connection, clear=False)
                if cleanup:
                    raise BrainProductsTriggerBoxError(
                        "TriggerBox could not start its automatic trigger reset, and its port "
                        "could not be closed. Restart FPVS Studio before retrying. Details: "
                        f"Unable to start TriggerBox reset worker: {exc}. "
                        f"Closing the port also failed: {' '.join(str(error) for error in cleanup)}"
                    ) from exc
                raise BrainProductsTriggerBoxError(
                    "TriggerBox could not start its automatic trigger reset. Restart FPVS "
                    "Studio before retrying. Details: Unable to start TriggerBox reset worker: "
                    f"{exc}"
                ) from exc
            self._wait_until_ready()

    def send(self, code: int) -> None:
        self.send_trigger(code)

    def send_trigger(
        self,
        code: int,
        *,
        frame_index: int | None = None,
        label: str | None = None,
        time_s: float | None = None,
    ) -> None:
        self.send_prevalidated_trigger(
            validate_event_trigger_code(code),
            frame_index=frame_index,
            label=label,
            time_s=time_s,
        )

    def send_prevalidated_trigger(
        self,
        code: int,
        *,
        frame_index: int | None = None,
        label: str | None = None,
        time_s: float | None = None,
    ) -> None:
        """Submit one byte without waiting for OS completion or queueing an event."""

        del frame_index, label, time_s
        with self._condition:
            connection = self._require_connection()
            self._raise_failure()
            if self._stopping:
                raise BrainProductsTriggerBoxError(
                    "TriggerBox is still closing. Wait for it to finish before trying again."
                )
            self._require_worker()
            if self._pulse_active:
                raise BrainProductsTriggerBoxError(
                    "Two triggers are too close together. Increase their spacing, or shorten "
                    "the pulse only if it meets your amplifier's minimum at the chosen sampling "
                    "rate. Details: TriggerBox pulse overlaps the previous event."
                )
            if time.monotonic() < self._ready_at:
                raise BrainProductsTriggerBoxError(
                    "Two triggers are too close together. Increase their spacing, or shorten "
                    "the pulse only if it meets your amplifier's minimum at the chosen sampling "
                    "rate. Details: TriggerBox low interval is shorter than the configured "
                    "pulse width."
                )
            try:
                self._write(connection, code, action="send trigger")
            except BrainProductsTriggerBoxError as exc:
                self._failure = exc
                raise
            self._pulse_active = True
            self._reset_at = (
                None if self._pending_write else time.monotonic() + self._pulse_s
            )
            self._condition.notify_all()

    def reset(self) -> None:
        """Finish the current pulse and establish zero idle outside playback."""

        with self._condition:
            connection = self._require_connection()
            self._raise_failure()
            self._require_worker()
            deadline = time.monotonic() + self._pulse_s + 2 * _WRITE_TIMEOUT_S + 1.0
            while self._pulse_active:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._failure = BrainProductsTriggerBoxError(
                        "TriggerBox did not clear the last trigger in time. Reconnect TriggerBox "
                        "and check any saved EEG markers before retrying. Details: TriggerBox "
                        "reset worker did not finish the pending pulse."
                    )
                    raise self._failure
                self._condition.wait(timeout=remaining)
                self._raise_failure()
                self._require_worker()
            try:
                self._write(connection, 0, action="reset trigger lines")
                self._drain_write()
            except BrainProductsTriggerBoxError as exc:
                self._failure = exc
                raise
            self._ready_at = time.monotonic() + self._pulse_s
            self._wait_until_ready()

    def close(self) -> None:
        """Stop the worker and release the port even when a reset has failed."""

        with self._condition:
            if self._connection is None:
                return
        errors: list[Exception] = []
        try:
            self.reset()
        except Exception as exc:
            errors.append(exc)
        with self._condition:
            self._stopping = True
            self._condition.notify_all()
            worker = self._worker
        if worker is not None:
            try:
                worker.join(timeout=1.0)
                if worker.is_alive():
                    errors.append(
                        BrainProductsTriggerBoxError(
                            "TriggerBox could not finish shutting down. Restart FPVS Studio "
                            "before retrying. Details: TriggerBox reset worker did not stop."
                        )
                    )
            except Exception as exc:
                errors.append(
                    BrainProductsTriggerBoxError(
                        "TriggerBox could not finish shutting down. Restart FPVS Studio before "
                        f"retrying. Details: Unable to join TriggerBox reset worker: {exc}"
                    )
                )
        with self._condition:
            connection = self._connection
            self._connection = None
            self._worker = None
            self._reset_at = None
            self._pulse_active = False
            if connection is not None:
                errors.extend(self._release_connection(connection, clear=True))
        if len(errors) == 1:
            raise errors[0]
        if errors:
            raise BrainProductsTriggerBoxError(
                "TriggerBox cleanup did not finish. Restart FPVS Studio and reconnect "
                "TriggerBox before retrying. Details: " + " ".join(str(error) for error in errors)
            ) from errors[0]

    def _reset_loop(self) -> None:
        with self._condition:
            while not self._stopping:
                if not self._pulse_active or self._failure is not None:
                    self._condition.wait()
                    continue
                if self._pending_write is not None:
                    code = self._pending_write[0]
                    try:
                        if not self._poll_write():
                            self._condition.wait(timeout=_WRITE_POLL_S)
                            continue
                    except BrainProductsTriggerBoxError as exc:
                        self._failure = exc
                        self._condition.notify_all()
                        continue
                    if code:
                        self._reset_at = time.monotonic() + self._pulse_s
                    else:
                        self._pulse_active = False
                        self._ready_at = time.monotonic() + self._pulse_s
                    self._condition.notify_all()
                    continue
                assert self._reset_at is not None
                remaining = self._reset_at - time.monotonic()
                if remaining > 0:
                    self._condition.wait(timeout=remaining)
                    continue
                try:
                    self._write(self._require_connection(), 0, action="reset trigger lines")
                except BrainProductsTriggerBoxError as exc:
                    self._failure = exc
                self._reset_at = None
                if self._pending_write is None:
                    self._pulse_active = False
                    self._ready_at = time.monotonic() + self._pulse_s
                self._condition.notify_all()

    def _poll_write(self) -> bool:
        """Bound waiting while pending; completion is not a timing measurement."""

        if self._pending_write is None:
            return True
        assert self._native_write is not None
        code, action, deadline = self._pending_write
        try:
            if self._native_write.poll():
                self._pending_write = None
                return True
            if time.monotonic() >= deadline:
                raise TimeoutError("Windows serial write did not complete before its deadline.")
        except Exception as exc:
            if not self._native_write.pending:
                self._pending_write = None
            raise self._write_failure(code, action, exc) from exc
        return False

    def _drain_write(self) -> None:
        while not self._poll_write():
            self._condition.wait(timeout=_WRITE_POLL_S)

    def _cancel_write(self) -> None:
        native = self._native_write
        if native is None or not native.pending:
            return
        cancel_error: Exception | None = None
        try:
            native.cancel()
        except Exception as exc:
            cancel_error = exc
        deadline = time.monotonic() + _WRITE_TIMEOUT_S
        while native.pending:
            try:
                if native.poll():
                    break
            except OSError as exc:
                # Cancellation is terminal only after the OS reports it.
                if getattr(exc, "winerror", None) != 995:
                    cancel_error = exc
                break
            if time.monotonic() >= deadline:
                break
            self._condition.wait(timeout=_WRITE_POLL_S)
        if native.pending:
            native.retain_until_exit()
            detail = f" Cancellation error: {cancel_error}" if cancel_error else ""
            raise BrainProductsTriggerBoxError(
                "TriggerBox could not finish shutting down. Restart FPVS Studio before "
                "retrying. Details: Windows did not confirm completion of a serial write; "
                f"its port and pending write storage are retained until process exit.{detail}"
            ) from cancel_error
        self._pending_write = None
        if cancel_error is not None:
            raise BrainProductsTriggerBoxError(
                "TriggerBox could not finish shutting down. Restart FPVS Studio before "
                f"retrying. Details: Windows serial cancellation failed: {cancel_error}"
            ) from cancel_error

    def _release_connection(self, connection: Any, *, clear: bool) -> list[Exception]:
        """Bounded cleanup; never free or reuse storage still owned by Windows."""

        errors: list[Exception] = []
        try:
            self._cancel_write()
        except Exception as exc:
            errors.append(exc)
        native = self._native_write
        if clear and not (native is not None and native.pending):
            try:
                self._write(connection, 0, action="clear trigger lines during close")
                self._drain_write()
            except Exception as exc:
                errors.append(exc)
            try:
                self._cancel_write()
            except Exception as exc:
                errors.append(exc)
        if native is None or not native.pending:
            try:
                connection.close()
            except Exception as exc:
                errors.append(BrainProductsTriggerBoxError(
                    f"TriggerBox port {self._port} could not be closed. Restart FPVS Studio "
                    "before retrying. Details: Unable to close TriggerBox port "
                    f"{self._port!r}: {exc}"
                ))
        else:
            # Preserve ownership even if an unexpected polling/cancel error
            # interrupted the normal bounded cancellation path.
            if native.retain_until_exit():
                errors.append(BrainProductsTriggerBoxError(
                    "TriggerBox could not finish shutting down. Restart FPVS Studio before "
                    "retrying. Details: Unconfirmed Windows serial write storage and its port "
                    "are retained until process exit."
                ))
        self._native_write = None
        self._pending_write = None
        return errors

    def _wait_until_ready(self) -> None:
        while (remaining := self._ready_at - time.monotonic()) > 0:
            self._condition.wait(timeout=remaining)
            self._raise_failure()

    def _raise_failure(self) -> None:
        if self._failure is not None:
            raise self._failure

    def _require_connection(self) -> Any:
        if self._connection is None:
            raise BrainProductsTriggerBoxError(
                "TriggerBox is not connected. Check the USB cable and selected port, then "
                "reconnect before retrying."
            )
        return self._connection

    def _require_worker(self) -> None:
        if self._worker is None or not self._worker.is_alive():
            self._failure = BrainProductsTriggerBoxError(
                "TriggerBox can no longer clear trigger signals automatically. Restart FPVS "
                "Studio and check any saved EEG markers before retrying. Details: TriggerBox "
                "reset worker has stopped."
            )
            raise self._failure

    def _write(self, connection: Any, code: int, *, action: str) -> None:
        try:
            if self._native_write is None:
                bytes_written = connection.write(bytes([code]))
            else:
                bytes_written = self._native_write.write(bytes([code]))
                if bytes_written == 1:
                    self._pending_write = (code, action, time.monotonic() + _WRITE_TIMEOUT_S)
                    self._poll_write()
        except BrainProductsTriggerBoxError:
            raise
        except Exception as exc:
            raise self._write_failure(code, action, exc) from exc
        if bytes_written != 1:
            problem = (
                "TriggerBox did not finish clearing the trigger signal."
                if code == 0 else "TriggerBox did not finish sending the marker."
            )
            raise BrainProductsTriggerBoxError(
                f"{problem} The USB connection may have been interrupted. "
                "Reconnect TriggerBox and check any saved EEG markers before "
                f"retrying. Details: Unable to {action} code {code} on TriggerBox {self._port!r}: "
                f"serial write returned {bytes_written!r}, expected 1."
            )

    def _write_failure(
        self, code: int, action: str, exc: Exception,
    ) -> BrainProductsTriggerBoxError:
        problem = (
            "TriggerBox could not clear the trigger signal."
            if code == 0 else "TriggerBox could not send a marker."
        )
        reason = triggerbox_failure_reason(exc)
        if reason == "timeout":
            problem = (
                "TriggerBox timed out while clearing the trigger signal."
                if code == 0 else "TriggerBox timed out while sending a marker."
            )
        elif reason == "device_io":
            problem += " USB communication failed."
        if reason != "device_io":
            problem += " The USB connection may have been interrupted."
        return BrainProductsTriggerBoxError(
            f"{problem} Reconnect TriggerBox and check any saved EEG markers before "
            f"retrying. Details: Unable to {action} code {code} on TriggerBox "
            f"{self._port!r}: {exc}"
        )


def _load_serial_module() -> ModuleType:
    try:
        return importlib.import_module("serial")
    except ImportError as exc:
        raise BrainProductsTriggerBoxError(
            "TriggerBox could not load its connection component. The Studio installation "
            "may be incomplete. Repair or reinstall FPVS Studio, then try again. "
            "Details: pyserial is required for Brain "
            "Products TriggerBox output but is not installed."
        ) from exc
