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
from fpvs_studio.runtime.launcher import launch_session
from fpvs_studio.runtime.preflight import preflight_session_plan

_SESSION_SEED_UPPER_BOUND = 2**31

__all__ = [
    "ConditionStimulusRow",
    "DocumentError",
    "LaunchSummary",
    "ProjectDocument",
    "_CONDITION_LENGTH_ERROR_MESSAGE",
    "_CONDITION_REPEAT_CYCLE_MISMATCH_PREFIX",
    "create_engine",
    "default_fixation_settings",
    "default_session_settings",
    "default_trigger_settings",
    "launch_session",
    "preflight_session_plan",
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
        self._last_session_plan: SessionPlan | None = None

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

    def generate_new_session_seed(self) -> int:
        """Generate and persist a fresh stored session seed."""

        seed = random.SystemRandom().randrange(_SESSION_SEED_UPPER_BOUND)
        self.update_session_settings(session_seed=seed)
        return seed

    def randomize_session_seed_for_app_launch(self) -> int:
        """Generate a fresh session seed for the current app launch without marking dirty."""

        seed = random.SystemRandom().randrange(_SESSION_SEED_UPPER_BOUND)
        session = _validated_copy(self._project.settings.session, session_seed=seed)
        settings = _validated_copy(self._project.settings, session=session)
        self._project = _validated_copy(self._project, settings=settings)
        self._last_session_plan = None
        self.project_changed.emit()
        return seed

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

    def _apply_project_update(self, **updates: object) -> None:
        project = _validated_copy(self._project, **updates)
        self._replace_project(project)

    def _replace_project(self, project: ProjectFile) -> None:
        self._project = project
        self._last_session_plan = None
        self._set_dirty(True)
        self.project_changed.emit()

    def _set_dirty(self, dirty: bool) -> None:
        if self._dirty == dirty:
            return
        self._dirty = dirty
        self.dirty_changed.emit(dirty)

