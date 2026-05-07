"""Abstract presentation-engine contract for runtime playback. Runtime calls this interface
with RunSpec, validation data, and neutral execution models so engine implementations
stay swappable. The module owns renderer-facing protocol definitions, not session
sequencing, fixation scoring, or export writing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path

from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.execution import RunExecutionSummary
from fpvs_studio.core.models import DisplayValidationReport
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.validation import validate_display_refresh
from fpvs_studio.triggers.base import TriggerBackend


class PresentationEngine(ABC):
    """Stable interface for swappable presentation engines."""

    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Return the engine identifier."""

    def validate_run_spec(self, run_spec: RunSpec) -> DisplayValidationReport:
        """Validate display timing for a run spec."""

        duty_cycle_mode = (
            DutyCycleMode.BLANK_50 if run_spec.display.off_frames > 0 else DutyCycleMode.CONTINUOUS
        )
        return validate_display_refresh(
            run_spec.display.refresh_hz,
            duty_cycle_mode=duty_cycle_mode,
            base_hz=run_spec.condition.base_hz,
        )

    @abstractmethod
    def probe_displays(self) -> list[dict[str, object]]:
        """Return discovered display information."""

    @abstractmethod
    def open_session(
        self,
        *,
        runtime_options: Mapping[str, object] | None = None,
    ) -> None:
        """Initialize any session-scoped engine resources."""

    @abstractmethod
    def show_transition_screen(
        self,
        *,
        heading: str,
        body: str | None = None,
        countdown_seconds: float | None = None,
        continue_key: str | None = None,
        continue_prompt: str | None = None,
    ) -> bool:
        """Show a text transition screen and return whether the session was aborted."""

    @abstractmethod
    def show_block_break_screen(
        self,
        *,
        completed_block_index: int,
        total_block_count: int,
        next_block_index: int,
    ) -> bool:
        """Show a manual inter-block break screen and return whether escape aborted."""

    @abstractmethod
    def show_condition_feedback_screen(
        self,
        *,
        heading: str,
        body: str,
        continue_key: str,
    ) -> bool:
        """Show end-of-condition feedback and return whether escape aborted."""

    @abstractmethod
    def run_condition(
        self,
        run_spec: RunSpec,
        project_root: Path,
        *,
        runtime_options: Mapping[str, object] | None = None,
        trigger_backend: TriggerBackend | None = None,
    ) -> RunExecutionSummary:
        """Execute a compiled condition run."""

    @abstractmethod
    def show_completion_screen(
        self,
        *,
        completed_condition_count: int,
        total_condition_count: int,
        was_aborted: bool,
    ) -> bool:
        """Show a completion or abort screen and return whether escape was pressed."""

    @abstractmethod
    def close_session(self) -> None:
        """Release any session-scoped engine resources."""

    @abstractmethod
    def abort(self) -> None:
        """Abort an active run if possible."""
