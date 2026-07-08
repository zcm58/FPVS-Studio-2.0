"""GUI-facing document adapter over editable project and backend services. It mediates
ProjectFile editing, preprocessing, compilation, preflight preparation, and launch
requests so widgets do not duplicate domain logic. This module owns authoring-session
coordination, not widget layout and not runtime playback or engine implementation."""

from __future__ import annotations

import random
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from fpvs_studio.core.models import (
    ConditionTemplateProfile,
    ProjectFile,
    ProjectValidationReport,
    utc_now,
)
from fpvs_studio.core.paths import (
    project_json_path,
    stimulus_manifest_path,
)
from fpvs_studio.core.project_bundle import export_project_bundle
from fpvs_studio.core.project_config import (
    ProjectConfigError,
    export_project_config,
    find_latest_completed_session_dir,
    write_project_config,
)
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.core.validation import validate_condition_repeat_cycle_consistency
from fpvs_studio.engines.registry import create_engine
from fpvs_studio.gui.document_conditions import DocumentConditionMixin
from fpvs_studio.gui.document_runtime import DocumentRuntimeMixin
from fpvs_studio.gui.document_stimuli import DocumentStimulusMixin
from fpvs_studio.gui.document_support import (
    _CONDITION_LENGTH_ERROR_MESSAGE,
    _CONDITION_REPEAT_CYCLE_MISMATCH_PREFIX,
    ConditionStimulusRow,
    DocumentError,
    LaunchSummary,
    default_fixation_settings,
    default_session_settings,
    default_trigger_settings,
    resolve_project_location,
)
from fpvs_studio.gui.document_support import (
    format_validation_report as _format_validation_report,
)
from fpvs_studio.gui.document_support import (
    validated_copy as _validated_copy,
)
from fpvs_studio.preprocessing.manifest import (
    create_empty_manifest,
    read_stimulus_manifest,
)
from fpvs_studio.preprocessing.models import StimulusManifest
from fpvs_studio.preprocessing.normalization import ImageNormalizationScan
from fpvs_studio.runtime.export_modes import EXPORT_MODE_FULL, VALID_EXPORT_MODES
from fpvs_studio.runtime.launcher import launch_session
from fpvs_studio.runtime.participant_history import (
    completed_session_seeds,
    generate_unused_session_seed,
)
from fpvs_studio.runtime.preflight import preflight_session_plan
from fpvs_studio.runtime.session_export import (
    refresh_participant_summary_if_stale,
    write_group_summary,
)

_SESSION_SEED_UPPER_BOUND = 2**31

__all__ = [
    "ConditionStimulusRow",
    "DocumentError",
    "LaunchSummary",
    "ProjectDocument",
    "ProjectConfigError",
    "_CONDITION_LENGTH_ERROR_MESSAGE",
    "_CONDITION_REPEAT_CYCLE_MISMATCH_PREFIX",
    "create_engine",
    "default_fixation_settings",
    "default_session_settings",
    "default_trigger_settings",
    "launch_session",
    "preflight_session_plan",
    "refresh_participant_summary_if_stale",
    "resolve_project_location",
]


class ProjectDocument(
    QObject,
    DocumentConditionMixin,
    DocumentStimulusMixin,
    DocumentRuntimeMixin,
):
    """Live project document used by the Phase 5 authoring GUI."""

    project_changed = Signal()
    dirty_changed = Signal(bool)
    manifest_changed = Signal()
    session_plan_changed = Signal()
    saved = Signal()

    def __init__(
        self,
        *,
        project_root: Path,
        project: ProjectFile,
        manifest: StimulusManifest | None = None,
    ) -> None:
        super().__init__()
        self._project_root = Path(project_root)
        self._project = project
        self._manifest = manifest
        self._dirty = False
        self._session_export_mode = EXPORT_MODE_FULL
        self._require_biosemi_recording_confirmation = True
        self._show_sophia_mode_ticker = True
        self._last_session_plan: SessionPlan | None = None
        self._image_normalization_scan_cache: tuple[
            tuple[object, ...],
            ImageNormalizationScan,
        ] | None = None

    @classmethod
    def create_new(
        cls,
        *,
        parent_dir: Path,
        project_name: str,
        condition_template_profile: ConditionTemplateProfile | None = None,
    ) -> ProjectDocument:
        """Scaffold a new project and open it as a live document."""

        scaffold = create_project(
            parent_dir,
            project_name,
            condition_template_profile=condition_template_profile,
        )
        manifest = create_empty_manifest(scaffold.project.meta.project_id)
        return cls(
            project_root=scaffold.project_root,
            project=scaffold.project,
            manifest=manifest,
        )

    @classmethod
    def open_existing(cls, project_location: Path) -> ProjectDocument:
        """Load an existing project directory or `project.json` file."""

        project_file_path = resolve_project_location(project_location)
        project = load_project_file(project_file_path)
        project_root = project_file_path.parent
        manifest_path = stimulus_manifest_path(project_root)
        manifest = read_stimulus_manifest(project_root) if manifest_path.is_file() else None
        return cls(project_root=project_root, project=project, manifest=manifest)

    @property
    def project(self) -> ProjectFile:
        """Return the live editable project model."""

        return self._project

    @property
    def project_root(self) -> Path:
        """Return the current project root path."""

        return self._project_root

    @property
    def project_file_path(self) -> Path:
        """Return the canonical `project.json` path for the live document."""

        return project_json_path(self._project_root)

    @property
    def manifest(self) -> StimulusManifest | None:
        """Return the current preprocessing manifest when available."""

        return self._manifest

    @property
    def dirty(self) -> bool:
        """Return whether the document has unsaved changes."""

        return self._dirty

    @property
    def session_export_mode(self) -> str:
        """Return the runtime export mode used for launches from this document."""

        return self._session_export_mode

    @property
    def require_biosemi_recording_confirmation(self) -> bool:
        """Return whether GUI launches require the BioSemi recording safety check."""

        return self._require_biosemi_recording_confirmation

    @property
    def show_sophia_mode_ticker(self) -> bool:
        """Return whether Home should show the Sophia Mode ticker."""

        return self._show_sophia_mode_ticker

    @property
    def last_session_plan(self) -> SessionPlan | None:
        """Return the most recently compiled session plan."""

        return self._last_session_plan

    def update_project_name(self, name: str) -> None:
        """Update the project display name."""

        meta = _validated_copy(self._project.meta, name=name)
        self._apply_project_update(meta=meta)

    def update_project_description(self, description: str) -> None:
        """Update the optional project description."""

        meta = _validated_copy(self._project.meta, description=description)
        self._apply_project_update(meta=meta)

    def update_display_settings(self, **updates: object) -> None:
        """Update project display settings through Pydantic validation."""

        display = _validated_copy(self._project.settings.display, **updates)
        settings = _validated_copy(self._project.settings, display=display)
        self._apply_project_update(settings=settings)

    def update_session_settings(self, **updates: object) -> None:
        """Update session settings through Pydantic validation."""

        session = _validated_copy(self._project.settings.session, **updates)
        settings = _validated_copy(self._project.settings, session=session)
        self._apply_project_update(settings=settings)

    def update_condition_defaults(self, **updates: object) -> None:
        """Update project-wide condition defaults through Pydantic validation."""

        condition_defaults = _validated_copy(self._project.settings.condition_defaults, **updates)
        settings = _validated_copy(self._project.settings, condition_defaults=condition_defaults)
        self._apply_project_update(settings=settings)

    def generate_new_session_seed(self) -> int:
        """Generate and persist a fresh stored random order seed."""

        seed = self._generate_unused_session_seed()
        self.update_session_settings(session_seed=seed)
        return seed

    def randomize_session_seed_for_app_launch(self) -> int:
        """Generate a fresh random order seed for the current app launch without marking dirty."""

        seed = self.generate_session_seed_for_app_launch()
        self.apply_session_seed_for_app_launch(seed)
        return seed

    def generate_session_seed_for_app_launch(self) -> int:
        """Generate a fresh random order seed without mutating the live document."""

        return self._generate_unused_session_seed()

    def apply_session_seed_for_app_launch(self, seed: int) -> None:
        """Apply an app-launch random order seed without marking the document dirty."""

        self._replace_session_seed_without_dirty(seed)

    def ensure_unused_session_seed_for_launch(self) -> int:
        """Ensure the current launch seed has not been consumed by a prior session."""

        seed = self._project.settings.session.session_seed
        if seed in completed_session_seeds(self._project_root):
            seed = self._generate_unused_session_seed()
            self._replace_session_seed_without_dirty(seed)
        return seed

    def set_session_export_mode(self, export_mode: str) -> None:
        """Set the app-level run export mode used for future launches."""

        if export_mode not in VALID_EXPORT_MODES:
            valid_values = "', '".join(sorted(VALID_EXPORT_MODES))
            raise DocumentError(f"Run export mode must be one of '{valid_values}'.")
        self._session_export_mode = export_mode

    def set_require_biosemi_recording_confirmation(self, required: bool) -> None:
        """Set whether GUI launches require the BioSemi recording safety check."""

        required = bool(required)
        if self._require_biosemi_recording_confirmation == required:
            return
        self._require_biosemi_recording_confirmation = required
        self.project_changed.emit()

    def set_show_sophia_mode_ticker(self, enabled: bool) -> None:
        """Set whether Home shows the Sophia Mode ticker when Sophia Mode is enabled."""

        enabled = bool(enabled)
        if self._show_sophia_mode_ticker == enabled:
            return
        self._show_sophia_mode_ticker = enabled
        self.project_changed.emit()

    def _generate_unused_session_seed(self) -> int:
        try:
            return generate_unused_session_seed(
                self._project_root,
                rng=random.SystemRandom(),
                upper_bound=_SESSION_SEED_UPPER_BOUND,
            )
        except RuntimeError as exc:
            raise DocumentError(str(exc)) from exc

    def _replace_session_seed_without_dirty(self, seed: int) -> None:
        session = _validated_copy(self._project.settings.session, session_seed=seed)
        settings = _validated_copy(self._project.settings, session=session)
        self._project = _validated_copy(self._project, settings=settings)
        self._last_session_plan = None

    def update_fixation_settings(self, **updates: object) -> None:
        """Update fixation settings through Pydantic validation."""

        fixation = _validated_copy(self._project.settings.fixation_task, **updates)
        settings = _validated_copy(self._project.settings, fixation_task=fixation)
        self._apply_project_update(settings=settings)

    def update_trigger_settings(self, **updates: object) -> None:
        """Update trigger settings through Pydantic validation."""

        triggers = _validated_copy(self._project.settings.triggers, **updates)
        settings = _validated_copy(self._project.settings, triggers=triggers)
        self._apply_project_update(settings=settings)

    def save(self) -> None:
        """Persist the current project to `project.json`."""

        consistency_issues = validate_condition_repeat_cycle_consistency(self._project)
        if consistency_issues:
            raise DocumentError(
                _format_validation_report(ProjectValidationReport(issues=consistency_issues))
            )

        meta = _validated_copy(self._project.meta, updated_at=utc_now())
        project = _validated_copy(self._project, meta=meta)
        save_project_file(project, self.project_file_path)
        self._project = project
        self._set_dirty(False)
        self.saved.emit()
        self.project_changed.emit()

    def export_config_file(self, path: Path, *, include_completed: bool = False) -> None:
        """Export the current project as a Studio `.fpvsconfig` file."""

        completed_session_dir = None
        if include_completed:
            completed_session_dir = find_latest_completed_session_dir(self._project_root)
            if completed_session_dir is None:
                raise DocumentError("No completed session exports were found for this project.")
        config = export_project_config(
            self._project,
            self._project_root,
            manifest=self._manifest,
            completed_session_dir=completed_session_dir,
        )
        write_project_config(path, config)

    def export_bundle_file(self, path: Path) -> None:
        """Export the saved project as a portable Studio `.fpvsbundle` file."""

        export_project_bundle(self._project_root, path)

    def export_group_summary_file(self, path: Path) -> Path:
        """Export the project-level group summary workbook to the selected path."""

        try:
            return write_group_summary(self._project_root, path)
        except ValueError as exc:
            raise DocumentError(str(exc)) from exc

    def refresh_participant_summary_if_stale(self) -> Path | None:
        """Refresh compact participant summaries when project logs are newer."""

        try:
            return refresh_participant_summary_if_stale(self._project_root)
        except PermissionError as exc:
            raise DocumentError(
                "Participant summary logs are out of date, but FPVS Studio could not "
                "refresh them. Close participant_summary.xlsx if it is open in Excel "
                "and try again."
            ) from exc
        except OSError as exc:
            raise DocumentError(
                "Participant summary logs are out of date, but FPVS Studio could not "
                f"refresh them: {exc}"
            ) from exc

    def _apply_project_update(self, **updates: object) -> None:
        project = _validated_copy(self._project, **updates)
        self._replace_project(project)

    def _replace_project(self, project: ProjectFile) -> None:
        self._project = project
        self._last_session_plan = None
        self._image_normalization_scan_cache = None
        self._set_dirty(True)
        self.project_changed.emit()

    def _set_dirty(self, dirty: bool) -> None:
        if self._dirty == dirty:
            return
        self._dirty = dirty
        self.dirty_changed.emit(dirty)

