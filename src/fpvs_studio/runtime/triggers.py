"""Runtime helpers for trigger backend wiring and logging. It wraps trigger backends so
runtime execution can record neutral TriggerRecord data while keeping hardware-specific
behavior behind backend interfaces. The module owns runtime trigger selection and
logging, not core trigger schemas, session planning, or engine presentation."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from fpvs_studio.core.execution import TriggerRecord, TriggerStatus
from fpvs_studio.core.trigger_codes import validate_event_trigger_code
from fpvs_studio.triggers.base import TriggerBackend
from fpvs_studio.triggers.null_backend import NullBackend
from fpvs_studio.triggers.serial_backend import SerialBackend, resolve_serial_port

LOGGER = logging.getLogger(__name__)


_RawTriggerAttempt = tuple[int, float | None, int, str, TriggerStatus, str | None]


class TriggerEmissionError(RuntimeError):
    """Raised when a connected trigger backend fails during marker emission."""


class LoggedTriggerBackend(TriggerBackend):
    """Wrap a trigger backend and retain execution-time trigger records."""

    def __init__(
        self, backend: TriggerBackend, *, backend_name: str
    ) -> None:
        if backend is None:
            raise ValueError("A trigger backend must be explicitly supplied.")
        expected_name = "serial" if backend.emits_hardware_triggers else "null"
        if backend_name != expected_name:
            raise ValueError("Trigger backend name must match its actual null/serial output.")
        self._backend = backend
        self._backend_name = backend_name
        self._raw_records: list[_RawTriggerAttempt] = []

    @property
    def emits_hardware_triggers(self) -> bool:
        return self._backend.emits_hardware_triggers

    @property
    def backend_name(self) -> str:
        """Return the logical backend identifier used in trigger logs."""

        return self._backend_name

    @property
    def records(self) -> tuple[TriggerRecord, ...]:
        """Materialize neutral trigger records outside the display callback."""

        return tuple(
            TriggerRecord(
                trigger_index=index,
                frame_index=frame_index,
                time_s=time_s,
                code=code,
                label=label,
                backend_name=self._backend_name,
                status=status,
                message=message,
            )
            for index, (frame_index, time_s, code, label, status, message) in enumerate(
                self._raw_records
            )
        )

    def connect(self) -> None:
        self._backend.connect()

    def send_trigger(
        self,
        code: int,
        *,
        frame_index: int | None = None,
        label: str | None = None,
        time_s: float | None = None,
    ) -> None:
        trigger_code = validate_event_trigger_code(code, label=label or "trigger")
        self.send_prevalidated_trigger(
            trigger_code,
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
        """Perform the physical write and append only primitive callback-time data."""

        normalized_label = label or "trigger"
        normalized_frame_index = frame_index if frame_index is not None else 0
        status: TriggerStatus = "sent"
        message: str | None = None
        caught_exception: Exception | None = None
        if self._backend_name == "null":
            self._raw_records.append(
                (
                    normalized_frame_index,
                    time_s,
                    code,
                    normalized_label,
                    "skipped_disabled",
                    "Trigger output is disabled; marker was logged only.",
                )
            )
            return

        try:
            self._backend.send_prevalidated_trigger(
                code,
                frame_index=frame_index,
                label=label,
                time_s=time_s,
            )
        except Exception as exc:
            status = "error"
            message = str(exc)
            caught_exception = exc

        self._raw_records.append(
            (normalized_frame_index, time_s, code, normalized_label, status, message)
        )
        if status == "error":
            raise TriggerEmissionError(message) from caught_exception

    def reset(self) -> None:
        try:
            self._backend.reset()
        except Exception:
            LOGGER.exception(
                "Trigger backend reset failed.",
                extra={"backend_name": self._backend_name},
            )
            raise

    def close(self) -> None:
        self._backend.close()


class LoggedNullBackend(LoggedTriggerBackend):
    """Compatibility alias for explicit log-only trigger output."""

    def __init__(self) -> None:
        super().__init__(backend=NullBackend(), backend_name="null")


def _build_serial_backend(options: Mapping[str, object]) -> SerialBackend:
    return SerialBackend(
        resolve_serial_port(options.get("serial_port")),
        _positive_int_option(options, "serial_baudrate", default=115200),
        pulse_width_ms=_non_negative_int_option(
            options,
            "serial_pulse_width_ms",
            default=10,
        ),
        reset_code=_optional_reset_code_option(options, "serial_reset_code", default=None),
        reset_delay_ms=_non_negative_int_option(
            options,
            "serial_reset_delay_ms",
            default=5,
        ),
    )


def build_trigger_backend(
    runtime_options: Mapping[str, object] | None = None,
) -> tuple[LoggedTriggerBackend, list[str]]:
    """Create the runtime trigger backend wrapper and any launch warnings."""

    options = runtime_options or {}
    serial_enabled = options.get("serial_enabled", True)
    test_mode = options.get("experiment_test_mode", False)
    pilot_mode = options.get("pilot_mode", False)
    if not all(isinstance(value, bool) for value in (serial_enabled, test_mode, pilot_mode)):
        raise ValueError("Serial output and test-mode flags must be booleans.")
    if not serial_enabled and not (test_mode or pilot_mode):
        raise ValueError(
            "Serial trigger output is required for recording. Null output is only allowed "
            "in Experiment Test Mode or Pilot Study Mode."
        )
    if serial_enabled:
        return LoggedTriggerBackend(_build_serial_backend(options), backend_name="serial"), []
    return LoggedNullBackend(), []


def _positive_int_option(
    options: Mapping[str, object],
    name: str,
    *,
    default: int,
) -> int:
    value = options.get(name, default)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def _non_negative_int_option(
    options: Mapping[str, object],
    name: str,
    *,
    default: int,
) -> int:
    value = options.get(name, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return value


def _optional_reset_code_option(
    options: Mapping[str, object],
    name: str,
    *,
    default: int | None,
) -> int | None:
    value = options.get(name, default)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value != 0:
        raise ValueError(f"{name} must be None or the integer 0.")
    return value
