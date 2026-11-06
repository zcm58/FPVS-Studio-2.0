"""Serial trigger backend for BioSemi-compatible marker output."""

from __future__ import annotations

import importlib
import time
from types import ModuleType
from typing import Any

from fpvs_studio.core.trigger_codes import validate_event_trigger_code, validate_reset_trigger_code
from fpvs_studio.triggers.base import (
    TriggerBackend,
    TriggerCompletionError,
    TriggerSubmissionBlockedError,
)
from fpvs_studio.triggers.biosemi_errors import (
    BIOSEMI_SERIAL_SUPPORT_MESSAGE,
    biosemi_port_error_message,
    biosemi_write_error_message,
)
from fpvs_studio.triggers.brainproducts_windows import WindowsSerialWrite, windows_serial_write

_WRITE_TIMEOUT_S = 1.0
_WRITE_POLL_S = 0.001


class SerialBackendError(RuntimeError):
    """Raised when BioSemi serial trigger output cannot be performed."""


class SerialWriteCompletionError(SerialBackendError, TriggerCompletionError):
    """Completion of a previously submitted marker failed."""


class SerialWritePendingError(SerialBackendError, TriggerSubmissionBlockedError):
    """A pending marker prevented another marker from reaching the transport."""


def resolve_serial_port(port: object) -> str:
    """Use COM3 for an unset port; preserve explicitly configured device names."""

    if port is None:
        return "COM3"
    if not isinstance(port, str):
        raise ValueError("Serial trigger port must be a string or None.")
    return port.strip() or "COM3"


class SerialBackend(TriggerBackend):
    """Write single-byte trigger markers to a configured serial port."""

    def __init__(
        self,
        port: str | None = "COM3",
        baudrate: int = 115200,
        *,
        pulse_width_ms: int = 10,
        reset_code: int | None = None,
        reset_delay_ms: int = 5,
        serial_module: ModuleType | Any | None = None,
    ) -> None:
        self._port = resolve_serial_port(port)
        self._baudrate = baudrate
        self._pulse_width_ms = pulse_width_ms
        self._reset_code = reset_code
        self._reset_delay_ms = reset_delay_ms
        self._serial_module = serial_module
        self._connection: Any | None = None
        self._native_write: WindowsSerialWrite | None = None
        self._pending_marker: tuple[int, str] | None = None
        self._failure: SerialBackendError | None = None
        self._quarantined = False

    @property
    def emits_hardware_triggers(self) -> bool:
        return True

    def connect(self) -> None:
        self._raise_failure()
        if self._connection is not None:
            return
        serial_module = self._serial_module or _load_serial_module()
        try:
            serial_factory = serial_module.Serial
            bytesize = serial_module.EIGHTBITS
            parity = serial_module.PARITY_NONE
            stopbits = serial_module.STOPBITS_ONE
            if not callable(serial_factory):
                raise ImportError("The serial transport is unavailable.")
        except (ImportError, AttributeError) as exc:
            raise SerialBackendError(
                f"{BIOSEMI_SERIAL_SUPPORT_MESSAGE} Details: {exc}"
            ) from exc
        try:
            self._connection = serial_factory(
                port=self._port,
                baudrate=self._baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=0,
                write_timeout=0,
                rtscts=False,
                dsrdtr=False,
                xonxoff=False,
            )
            self._native_write = windows_serial_write(self._connection)
        except Exception as exc:
            error = SerialBackendError(
                f"{biosemi_port_error_message(self._port, exc)} Details: {exc}"
            )
            error.__cause__ = exc
            if self._connection is not None:
                self._failure = error
                self.close()
            raise error from exc

    def send(self, code: int) -> None:
        """Emit one normal trigger event marker."""

        self.send_trigger(code)

    def send_trigger(
        self,
        code: int,
        *,
        frame_index: int | None = None,
        label: str | None = None,
        time_s: float | None = None,
    ) -> None:
        del frame_index, label, time_s
        self._write_marker(
            validate_event_trigger_code(code),
            action="send trigger",
        )

    def send_prevalidated_trigger(
        self,
        code: int,
        *,
        frame_index: int | None = None,
        label: str | None = None,
        time_s: float | None = None,
    ) -> None:
        """Write one already-validated marker without hot-path model work."""

        del frame_index, label, time_s
        self._write_marker(code, action="send trigger")

    def reset(self) -> None:
        if self._reset_code is None:
            return
        validate_reset_trigger_code(self._reset_code)
        self.write_idle()

    def write_idle(self) -> None:
        """Explicitly write the idle byte for a manual hardware test or reset."""

        self._write_marker(0, action="reset trigger line")

    def finish_pending_output(self) -> None:
        """Confirm the last submitted marker outside frame playback, without resetting."""

        self._raise_failure()
        pending_event = (
            self._pending_marker is not None and self._pending_marker[1] == "send trigger"
        )
        try:
            self._drain_write()
        except SerialBackendError as exc:
            if pending_event:
                self._failure = SerialWriteCompletionError(str(exc))
                raise self._failure from exc.__cause__
            self._failure = exc
            raise

    def close(self) -> None:
        """Observe the final write outside playback before releasing its storage."""

        if self._quarantined:
            self._raise_failure()
            return
        connection = self._connection
        errors = [self._failure] if self._failure is not None else []
        completion_failed = False
        pending_event = (
            self._pending_marker is not None and self._pending_marker[1] == "send trigger"
        )
        if connection is not None:
            try:
                self._drain_write()
            except SerialBackendError as exc:
                errors.append(exc)
                completion_failed = pending_event
            try:
                self._cancel_write()
            except SerialBackendError as exc:
                errors.append(exc)
                completion_failed = pending_event
            native = self._native_write
            if native is not None and native.pending:
                native.retain_until_exit()
                self._quarantined = True
            else:
                try:
                    connection.close()
                except Exception as exc:
                    message = biosemi_port_error_message(
                        self._port, f"Unable to close the port: {exc}",
                    )
                    error = SerialBackendError(f"{message} Details: {exc}")
                    error.__cause__ = exc
                    errors.append(error)
                else:
                    self._connection = None
                    self._native_write = None
                    self._pending_marker = None
        if len(errors) == 1:
            self._failure = errors[0]
            if completion_failed and not isinstance(self._failure, TriggerCompletionError):
                self._failure = SerialWriteCompletionError(str(errors[0]))
                self._failure.__cause__ = errors[0].__cause__ or errors[0]
        elif errors:
            error_type = SerialWriteCompletionError if completion_failed else SerialBackendError
            self._failure = error_type(
                "BioSemi could not finish shutting down. Restart Studio before retrying. "
                "Details: " + " ".join(str(error) for error in errors)
            )
            self._failure.__cause__ = errors[0]
        self._raise_failure()

    def _write_marker(self, code: int, *, action: str) -> None:
        self._raise_failure()
        if self._connection is None:
            raise SerialBackendError(
                f"BioSemi trigger port {self._port} is not connected. Check the USB Trigger "
                "Interface cable and selected port, then reconnect before retrying."
            )
        try:
            pending_event = (
                self._pending_marker is not None and self._pending_marker[1] == "send trigger"
            )
            try:
                previous_completed = self._poll_write()
            except SerialBackendError as exc:
                if not pending_event:
                    raise
                raise SerialWriteCompletionError(str(exc)) from exc.__cause__
            if not previous_completed:
                raise SerialWritePendingError(
                    f"BioSemi is still sending the previous marker on {self._port}. "
                    "The next marker was not sent. USB communication may be delayed. "
                    "Reconnect the USB Trigger Interface and review any saved EEG markers "
                    "before retrying."
                )
            if self._native_write is None:
                bytes_written = self._connection.write(bytes([code]))
            else:
                self._pending_marker = (code, action)
                bytes_written = self._native_write.write(bytes([code]))
                if bytes_written == 1:
                    self._poll_write()
            if bytes_written != 1:
                raise OSError(f"Serial write returned {bytes_written!r}, expected 1.")
        except SerialBackendError as exc:
            self._failure = exc
            raise
        except Exception as exc:
            self._failure = self._write_failure(code, action, exc)
            raise self._failure from exc

    def _raise_failure(self) -> None:
        if self._failure is not None:
            raise self._failure

    def _poll_write(self) -> bool:
        native = self._native_write
        if native is None or not native.pending:
            return True
        assert self._pending_marker is not None
        code, action = self._pending_marker
        try:
            return native.poll()
        except Exception as exc:
            raise self._write_failure(code, action, exc) from exc
        finally:
            if not native.pending:
                self._pending_marker = None

    def _drain_write(self) -> None:
        deadline = time.monotonic() + _WRITE_TIMEOUT_S
        while not self._poll_write():
            if time.monotonic() >= deadline:
                assert self._pending_marker is not None
                code, action = self._pending_marker
                error = TimeoutError("Windows serial write did not complete before its deadline.")
                raise self._write_failure(code, action, error) from error
            time.sleep(_WRITE_POLL_S)

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
            except Exception as exc:
                if getattr(exc, "winerror", None) != 995:
                    cancel_error = exc
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(_WRITE_POLL_S)
        if native.pending:
            detail = f" Cancellation error: {cancel_error}" if cancel_error else ""
            raise SerialBackendError(
                f"BioSemi trigger port {self._port} could not be released. Windows has not "
                "finished sending or cancelling a marker. Restart Studio before retrying. "
                "Details: The port and pending write storage are retained until process exit."
                + detail
            ) from cancel_error
        self._pending_marker = None
        if cancel_error is not None:
            raise SerialBackendError(
                "BioSemi could not finish shutting down. Restart Studio before retrying. "
                f"Details: Windows serial cancellation failed: {cancel_error}"
            ) from cancel_error

    def _write_failure(self, code: int, action: str, exc: Exception) -> SerialBackendError:
        message = biosemi_write_error_message(
            self._port, exc, reset=action == "reset trigger line",
        )
        return SerialBackendError(
            f"{message} Details: Unable to {action} code {code} on {self._port!r}: {exc}"
        )


def _load_serial_module() -> ModuleType:
    try:
        return importlib.import_module("serial")
    except ImportError as exc:
        raise SerialBackendError(
            f"{BIOSEMI_SERIAL_SUPPORT_MESSAGE} Details: {exc}"
        ) from exc
