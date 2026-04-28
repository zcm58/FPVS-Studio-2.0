"""Runtime helpers for trigger backend wiring and logging. It wraps trigger backends so
runtime execution can record neutral TriggerRecord data while keeping hardware-specific
behavior behind backend interfaces. The module owns runtime trigger selection and
logging, not core trigger schemas, session planning, or engine presentation."""

from __future__ import annotations

from collections.abc import Mapping

from fpvs_studio.core.execution import TriggerRecord, TriggerStatus
from fpvs_studio.triggers.base import TriggerBackend
from fpvs_studio.triggers.null_backend import NullBackend


class LoggedTriggerBackend(TriggerBackend):
    """Wrap a trigger backend and retain execution-time trigger records."""

    def __init__(
        self, backend: TriggerBackend | None = None, *, backend_name: str = "null"
    ) -> None:
        self._backend = backend or NullBackend()
        self._backend_name = backend_name
        self._records: list[TriggerRecord] = []

    @property
    def backend_name(self) -> str:
        """Return the logical backend identifier used in trigger logs."""

        return self._backend_name

    @property
    def records(self) -> tuple[TriggerRecord, ...]:
        """Return the recorded trigger attempts."""

        return tuple(self._records)

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
        status: TriggerStatus = "sent"
        message: str | None = None
        try:
            self._backend.send_trigger(
                code,
                frame_index=frame_index,
                label=label,
                time_s=time_s,
            )
        except NotImplementedError as exc:
            status = "skipped"
            message = str(exc)
        except Exception as exc:  # pragma: no cover - reserved for future backend failures
            status = "failed"
            message = str(exc)

        self._records.append(
            TriggerRecord(
                trigger_index=len(self._records),
                frame_index=frame_index or 0,
                time_s=time_s,
                code=code,
                label=label or "trigger",
                backend_name=self._backend_name,
                status=status,
                message=message,
            )
        )

    def reset(self) -> None:
        try:
            self._backend.reset()
        except NotImplementedError:
            return None

    def close(self) -> None:
        self._backend.close()


def build_trigger_backend(
    runtime_options: Mapping[str, object] | None = None,
) -> tuple[LoggedTriggerBackend, list[str]]:
    """Create the runtime trigger backend wrapper and any launch warnings."""

    options = runtime_options or {}
    warnings: list[str] = []
    if options.get("serial_port") and not bool(options.get("test_mode")):
        warnings.append(
            "Serial trigger I/O is not implemented yet; trigger attempts will be "
            "logged without hardware output."
        )
    return LoggedTriggerBackend(), warnings
