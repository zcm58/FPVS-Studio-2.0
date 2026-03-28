"""No-op trigger backend for environments without hardware signaling.
Runtime can use this implementation to satisfy the trigger interface while still producing neutral trigger logs and execution summaries.
The module owns fallback backend behavior only; event planning and participant-facing flow stay elsewhere."""

from __future__ import annotations

from fpvs_studio.triggers.base import TriggerBackend


class NullBackend(TriggerBackend):
    """No-op backend used when triggers are disabled."""

    def connect(self) -> None:
        return None

    def send_trigger(
        self,
        code: int,
        *,
        frame_index: int | None = None,
        label: str | None = None,
        time_s: float | None = None,
    ) -> None:
        return None

    def reset(self) -> None:
        return None

    def close(self) -> None:
        return None
