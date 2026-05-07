"""Compilation, preflight, and launch helpers for the GUI project document facade."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pydantic import ValidationError

from fpvs_studio.core.compiler import CompileError, compile_session_plan
from fpvs_studio.core.enums import EngineName
from fpvs_studio.core.models import ProjectFile, ProjectValidationReport
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.core.validation import (
    ConditionFixationGuidance,
    condition_fixation_guidance,
    validate_project,
)
from fpvs_studio.gui.document_support import (
    DocumentError,
    LaunchSummary,
    format_validation_report,
)
from fpvs_studio.runtime.launcher import LaunchSettings
from fpvs_studio.runtime.participant_history import find_completed_sessions_for_participant


def _document_dependency(name: str) -> Any:
    return getattr(import_module("fpvs_studio.gui.document"), name)


class DocumentRuntimeMixin:
    """Validation, compilation, preflight, and launch methods for `ProjectDocument`."""

    if TYPE_CHECKING:
        _project: ProjectFile
        _project_root: Path
        _last_session_plan: SessionPlan | None
        session_plan_changed: Any

    def validation_report(self, *, refresh_hz: float) -> ProjectValidationReport:
        """Validate the current project at a specific compile refresh rate."""

        return validate_project(self._project, refresh_hz=refresh_hz)

    def fixation_guidance(self, *, refresh_hz: float) -> list[ConditionFixationGuidance]:
        """Return condition-level fixation guidance at a specific refresh rate."""

        return condition_fixation_guidance(self._project, refresh_hz=refresh_hz)

    def compile_session(self, *, refresh_hz: float) -> SessionPlan:
        """Compile the current project into a session plan."""

        self.ensure_unused_session_seed_for_launch()
        report = self.validation_report(refresh_hz=refresh_hz)
        if not report.is_valid:
            raise DocumentError(format_validation_report(report))
        try:
            session_plan = compile_session_plan(
                self._project,
                refresh_hz=refresh_hz,
                project_root=self._project_root,
            )
        except (CompileError, ValidationError, ValueError) as exc:
            raise DocumentError(str(exc)) from exc
        self._last_session_plan = session_plan
        self.session_plan_changed.emit()
        return session_plan

    def preflight_session(
        self,
        *,
        refresh_hz: float,
        engine_name: str = EngineName.PSYCHOPY.value,
    ) -> SessionPlan:
        """Compile and preflight the current session plan."""

        session_plan = self.prepare_test_session_launch(
            refresh_hz=refresh_hz,
            engine_name=engine_name,
        )
        return session_plan

    def prepare_test_session_launch(
        self,
        *,
        refresh_hz: float,
        engine_name: str = EngineName.PSYCHOPY.value,
    ) -> SessionPlan:
        """Compile and preflight the current test-mode session launch."""

        session_plan = self.compile_session(refresh_hz=refresh_hz)
        try:
            engine = _document_dependency("create_engine")(engine_name)
            _document_dependency("preflight_session_plan")(
                self._project_root,
                session_plan,
                engine=engine,
            )
        except Exception as exc:
            raise DocumentError(str(exc)) from exc
        return session_plan

    def launch_compiled_session(
        self,
        session_plan: SessionPlan,
        *,
        participant_number: str,
        display_index: int | None,
        fullscreen: bool = True,
        engine_name: str = EngineName.PSYCHOPY.value,
        test_mode: bool = True,
    ) -> LaunchSummary:
        """Launch an already-prepared session plan through the runtime boundary."""

        try:
            summary = _document_dependency("launch_session")(
                self._project_root,
                session_plan,
                participant_number=participant_number,
                launch_settings=LaunchSettings(
                    engine_name=engine_name,
                    test_mode=test_mode,
                    fullscreen=fullscreen,
                    display_index=display_index,
                    serial_port=self._project.settings.triggers.serial_port,
                    serial_baudrate=self._project.settings.triggers.baudrate,
                    strict_timing_warmup=False if test_mode else True,
                    timing_miss_threshold_multiplier=4.0 if test_mode else 1.5,
                ),
            )
        except Exception as exc:
            raise DocumentError(str(exc)) from exc
        return cast(LaunchSummary, summary)

    def launch_test_session(
        self,
        *,
        refresh_hz: float,
        participant_number: str,
        display_index: int | None,
        fullscreen: bool = True,
        engine_name: str = EngineName.PSYCHOPY.value,
        test_mode: bool = True,
    ) -> tuple[SessionPlan, LaunchSummary]:
        """Compile and launch the current session through the runtime boundary."""

        session_plan = self.prepare_test_session_launch(
            refresh_hz=refresh_hz,
            engine_name=engine_name,
        )
        summary = self.launch_compiled_session(
            session_plan,
            participant_number=participant_number,
            display_index=display_index,
            fullscreen=fullscreen,
            engine_name=engine_name,
            test_mode=test_mode,
        )
        return session_plan, summary

    def has_completed_session_for_participant(self, participant_number: str) -> bool:
        """Return whether this project already contains completed runs for a participant."""

        return bool(
            find_completed_sessions_for_participant(
                self._project_root,
                participant_number,
            )
        )
