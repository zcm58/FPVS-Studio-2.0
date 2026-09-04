"""Abstract presentation-engine contract for runtime playback. Runtime calls this interface
with RunSpec, validation data, and neutral execution models so engine implementations
stay swappable. The module owns renderer-facing protocol definitions, not session
sequencing, fixation scoring, or export writing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fpvs_studio.core.execution import RunExecutionSummary
from fpvs_studio.core.models import DisplayValidationReport
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.validation import validate_display_refresh
from fpvs_studio.triggers.base import TriggerBackend


@dataclass(frozen=True)
class FixationTutorialAttemptResult:
    """Result for one participant fixation tutorial practice attempt."""

    hit: bool
    reaction_time_s: float | None = None
    aborted: bool = False


ResolvedTaskStepKind = Literal[
    "instruction",
    "study",
    "choice_grid",
    "questionnaire",
    "raw_key",
    "timed_feedback",
]
ResolvedTaskResponseKind = Literal[
    "none",
    "continue",
    "raw_key",
    "single_choice",
    "multiple_choice",
    "short_text",
    "long_text",
    "numeric",
    "rating",
]
ResolvedTaskSubmissionMode = Literal["immediate", "explicit"]


@dataclass(frozen=True)
class ResolvedTaskItem:
    """One task item after runtime has resolved its calibrated layout to pixels."""

    item_id: str
    text: str | None = None
    image_path: str | None = None
    position_px: tuple[float, float] = (0.0, 0.0)
    size_px: tuple[float, float] | None = None
    text_height_px: float = 32.0
    color: str = "white"
    selectable: bool = False


@dataclass(frozen=True)
class ResolvedTaskStep:
    """Engine-facing representation of one declarative task screen."""

    task_id: str
    step_id: str
    kind: ResolvedTaskStepKind
    response_kind: ResolvedTaskResponseKind = "none"
    heading: str | None = None
    body: str | None = None
    items: tuple[ResolvedTaskItem, ...] = ()
    allowed_keys: tuple[str, ...] = ()
    continue_key: str = "space"
    submit_key: str = "return"
    duration_s: float | None = None
    timeout_s: float | None = None
    required: bool = True
    minimum_selections: int = 1
    maximum_selections: int | None = 1
    numeric_minimum: float | None = None
    numeric_maximum: float | None = None
    maximum_text_length: int = 2000
    numeric_step: float | None = None
    submission_mode: ResolvedTaskSubmissionMode = "immediate"
    prompt: str | None = None
    prompt_position_px: tuple[float, float] | None = None
    prompt_height_px: float | None = None
    show_footer: bool = True
    repeat_index: int = 0
    question_id: str | None = None
    font_family: str = "Arial"


@dataclass(frozen=True)
class TaskEngineInput:
    """Raw input returned by an engine for one task screen."""

    aborted: bool = False
    timed_out: bool = False
    key: str | None = None
    selected_item_ids: tuple[str, ...] = ()
    text_value: str | None = None
    numeric_value: float | None = None
    mouse_position_px: tuple[float, float] | None = None
    mouse_button: int | None = None
    reaction_time_s: float | None = None
    key_reaction_time_s: float | None = None
    key_duration_s: float | None = None
    displayed_item_ids: tuple[str, ...] = ()


class PresentationEngine(ABC):
    """Stable interface for swappable presentation engines."""

    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Return the engine identifier."""

    def validate_run_spec(self, run_spec: RunSpec) -> DisplayValidationReport:
        """Validate display timing for a run spec."""

        return validate_display_refresh(
            run_spec.display.refresh_hz,
            duty_cycle_mode=run_spec.display.duty_cycle_mode,
            base_hz=run_spec.condition.base_hz,
            oddball_every_n=run_spec.condition.oddball_every_n,
        )

    def current_display_size_px(self) -> tuple[int, int] | None:
        """Return the active session window size in pixels when available."""

        return None

    def measure_refresh_hz(
        self,
        *,
        runtime_options: Mapping[str, object] | None = None,
    ) -> float:
        """Measure the connected presentation display refresh rate."""

        raise RuntimeError(f"Presentation engine '{self.engine_id}' cannot measure refresh rate.")

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
    def run_fixation_tutorial_attempt(
        self,
        run_spec: RunSpec,
        *,
        target_delay_seconds: float,
    ) -> FixationTutorialAttemptResult:
        """Run one fixation tutorial practice attempt and return hit/miss/abort state."""

    def render_task_step(
        self,
        step: ResolvedTaskStep,
        project_root: Path,
    ) -> TaskEngineInput:
        """Render a resolved modular task screen and return neutral raw input.

        This is non-abstract for compatibility with existing external engines. Runtime
        only calls it for a session entry that contains task modules and surfaces this
        error before participant input if the selected engine lacks task support.
        """

        raise RuntimeError(
            f"Presentation engine '{self.engine_id}' does not support modular tasks."
        )

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
