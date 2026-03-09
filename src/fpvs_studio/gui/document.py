"""GUI-facing project document and backend service adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random

from PySide6.QtCore import QObject, Signal
from pydantic import ValidationError

from fpvs_studio.core.compiler import CompileError, compile_session_plan
from fpvs_studio.core.enums import EngineName, StimulusVariant
from fpvs_studio.core.models import (
    Condition,
    FixationTaskSettings,
    ProjectFile,
    ProjectValidationReport,
    SessionSettings,
    StimulusSet,
    TriggerSettings,
    utc_now,
)
from fpvs_studio.core.paths import (
    project_json_path,
    slugify_project_name,
    stimulus_originals_dir,
    stimulus_manifest_path,
    to_project_relative_posix,
)
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.validation import (
    condition_fixation_guidance,
    validate_condition_repeat_cycle_consistency,
    validate_project,
)
from fpvs_studio.preprocessing.importer import (
    import_stimulus_source_directory,
    materialize_project_assets,
)
from fpvs_studio.preprocessing.inspection import inspect_source_directory, summary_to_stimulus_set
from fpvs_studio.preprocessing.manifest import (
    create_empty_manifest,
    inspection_summary_to_manifest_set,
    read_stimulus_manifest,
    upsert_manifest_set,
    write_stimulus_manifest,
)
from fpvs_studio.preprocessing.models import StimulusManifest
from fpvs_studio.runtime.launcher import LaunchSettings, launch_session
from fpvs_studio.runtime.participant_history import find_completed_sessions_for_participant
from fpvs_studio.runtime.preflight import preflight_session_plan
from fpvs_studio.engines.registry import create_engine

_SESSION_SEED_UPPER_BOUND = 2**31
_CONDITION_REPEAT_CYCLE_MISMATCH_PREFIX = (
    "Condition repeat/cycle settings must match across all conditions."
)
_CONDITION_LENGTH_ERROR_MESSAGE = (
    "Error: All of your conditions must be the same length. Please ensure each condition "
    "contains the same number of oddball cycles before continuing."
)


class DocumentError(ValueError):
    """Raised when a GUI-facing document action cannot complete."""


@dataclass(frozen=True)
class ConditionStimulusRow:
    """One condition-role row shown on the assets page."""

    condition_id: str
    condition_name: str
    role: str
    stimulus_set: StimulusSet


def _validated_copy(model: object, **updates: object) -> object:
    data = model.model_dump(mode="python")
    data.update(updates)
    return type(model).model_validate(data)


def _format_validation_report(report: ProjectValidationReport) -> str:
    error_issues = [issue for issue in report.issues if issue.severity.value == "error"]
    if not error_issues:
        return ""

    has_condition_repeat_cycle_mismatch = any(
        issue.message.startswith(_CONDITION_REPEAT_CYCLE_MISMATCH_PREFIX)
        for issue in error_issues
    )
    if not has_condition_repeat_cycle_mismatch:
        return "\n".join(
            f"[{issue.severity.value}] {issue.location}: {issue.message}" for issue in error_issues
        )

    issues = [_CONDITION_LENGTH_ERROR_MESSAGE]
    issues.extend(
        f"[{issue.severity.value}] {issue.location}: {issue.message}"
        for issue in error_issues
        if not issue.message.startswith(_CONDITION_REPEAT_CYCLE_MISMATCH_PREFIX)
    )
    if not issues:
        return ""
    return "\n".join(issues)


def resolve_project_location(project_location: Path) -> Path:
    """Resolve a directory or `project.json` path to the canonical JSON path."""

    candidate = Path(project_location)
    if candidate.is_dir():
        candidate = project_json_path(candidate)
    if candidate.name != "project.json":
        raise DocumentError("Select a project directory or a project.json file.")
    if not candidate.is_file():
        raise DocumentError(f"Project file was not found: {candidate}")
    return candidate


class ProjectDocument(QObject):
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
        self._last_session_plan = None

    @classmethod
    def create_new(cls, *, parent_dir: Path, project_name: str) -> "ProjectDocument":
        """Scaffold a new project and open it as a live document."""

        scaffold = create_project(parent_dir, project_name)
        manifest = create_empty_manifest(scaffold.project.meta.project_id)
        return cls(
            project_root=scaffold.project_root,
            project=scaffold.project,
            manifest=manifest,
        )

    @classmethod
    def open_existing(cls, project_location: Path) -> "ProjectDocument":
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
    def last_session_plan(self):  # noqa: ANN201 - concrete type adds import churn
        """Return the most recently compiled session plan."""

        return self._last_session_plan

    def condition_rows(self) -> list[ConditionStimulusRow]:
        """Return condition-role rows for the assets page."""

        rows: list[ConditionStimulusRow] = []
        for condition in self.ordered_conditions():
            base_set = self.get_stimulus_set(condition.base_stimulus_set_id)
            oddball_set = self.get_stimulus_set(condition.oddball_stimulus_set_id)
            if base_set is not None:
                rows.append(
                    ConditionStimulusRow(
                        condition_id=condition.condition_id,
                        condition_name=condition.name,
                        role="base",
                        stimulus_set=base_set,
                    )
                )
            if oddball_set is not None:
                rows.append(
                    ConditionStimulusRow(
                        condition_id=condition.condition_id,
                        condition_name=condition.name,
                        role="oddball",
                        stimulus_set=oddball_set,
                    )
                )
        return rows

    def ordered_conditions(self) -> list[Condition]:
        """Return conditions in stored project order."""

        return sorted(self._project.conditions, key=lambda item: item.order_index)

    def get_condition(self, condition_id: str) -> Condition | None:
        """Return one condition by id."""

        for condition in self._project.conditions:
            if condition.condition_id == condition_id:
                return condition
        return None

    def get_stimulus_set(self, set_id: str) -> StimulusSet | None:
        """Return one stimulus set by id."""

        for stimulus_set in self._project.stimulus_sets:
            if stimulus_set.set_id == set_id:
                return stimulus_set
        return None

    def get_condition_stimulus_set(self, condition_id: str, role: str) -> StimulusSet:
        """Return the base or oddball stimulus set for one condition."""

        condition = self.get_condition(condition_id)
        if condition is None:
            raise DocumentError(f"Unknown condition '{condition_id}'.")
        set_id = (
            condition.base_stimulus_set_id if role == "base" else condition.oddball_stimulus_set_id
        )
        stimulus_set = self.get_stimulus_set(set_id)
        if stimulus_set is None:
            raise DocumentError(f"Condition '{condition.name}' is missing its {role} stimulus set.")
        return stimulus_set

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

    def set_supported_variants(self, variants: list[StimulusVariant]) -> None:
        """Persist the project-level supported materialization variants."""

        ordered_variants = list(dict.fromkeys([StimulusVariant.ORIGINAL, *variants]))
        settings = _validated_copy(self._project.settings, supported_variants=ordered_variants)
        self._apply_project_update(settings=settings)

    def create_condition(self, *, name: str | None = None) -> str:
        """Create one new condition plus dedicated base/oddball stimulus sets."""

        ordered_conditions = self.ordered_conditions()
        display_name = name or f"Condition {len(ordered_conditions) + 1}"
        existing_condition_ids = {condition.condition_id for condition in self._project.conditions}
        existing_set_ids = {stimulus_set.set_id for stimulus_set in self._project.stimulus_sets}
        condition_id = self._unique_slug(display_name, existing_condition_ids)
        base_set_id = self._unique_slug(f"{condition_id}-base", existing_set_ids)
        oddball_set_id = self._unique_slug(f"{condition_id}-oddball", existing_set_ids | {base_set_id})
        sequence_count = 1
        oddball_cycle_repeats_per_sequence = 146
        if ordered_conditions:
            first_ordered_condition = ordered_conditions[0]
            sequence_count = first_ordered_condition.sequence_count
            oddball_cycle_repeats_per_sequence = (
                first_ordered_condition.oddball_cycle_repeats_per_sequence
            )

        new_condition = Condition(
            condition_id=condition_id,
            name=display_name,
            base_stimulus_set_id=base_set_id,
            oddball_stimulus_set_id=oddball_set_id,
            sequence_count=sequence_count,
            oddball_cycle_repeats_per_sequence=oddball_cycle_repeats_per_sequence,
            trigger_code=len(ordered_conditions) + 1,
            order_index=len(ordered_conditions),
        )
        new_sets = [
            self._make_empty_stimulus_set(base_set_id, f"{display_name} Base"),
            self._make_empty_stimulus_set(oddball_set_id, f"{display_name} Oddball"),
        ]
        conditions = [*ordered_conditions, new_condition]
        project = _validated_copy(
            self._project,
            conditions=self._reindex_conditions(conditions),
            stimulus_sets=[*self._project.stimulus_sets, *new_sets],
        )
        self._replace_project(project)
        return condition_id

    def remove_condition(self, condition_id: str) -> None:
        """Remove one condition and any unreferenced stimulus sets."""

        condition = self.get_condition(condition_id)
        if condition is None:
            raise DocumentError(f"Unknown condition '{condition_id}'.")
        remaining_conditions = [
            item for item in self.ordered_conditions() if item.condition_id != condition_id
        ]
        referenced_set_ids = {
            set_id
            for item in remaining_conditions
            for set_id in (item.base_stimulus_set_id, item.oddball_stimulus_set_id)
        }
        remaining_sets = [
            stimulus_set
            for stimulus_set in self._project.stimulus_sets
            if stimulus_set.set_id in referenced_set_ids
        ]
        project = _validated_copy(
            self._project,
            conditions=self._reindex_conditions(remaining_conditions),
            stimulus_sets=remaining_sets,
        )
        self._replace_project(project)

    def move_condition(self, condition_id: str, *, offset: int) -> None:
        """Move one condition up or down within the ordered condition list."""

        ordered_conditions = self.ordered_conditions()
        current_index = next(
            (index for index, item in enumerate(ordered_conditions) if item.condition_id == condition_id),
            None,
        )
        if current_index is None:
            raise DocumentError(f"Unknown condition '{condition_id}'.")
        target_index = current_index + offset
        if target_index < 0 or target_index >= len(ordered_conditions):
            return
        ordered_conditions[current_index], ordered_conditions[target_index] = (
            ordered_conditions[target_index],
            ordered_conditions[current_index],
        )
        project = _validated_copy(
            self._project,
            conditions=self._reindex_conditions(ordered_conditions),
        )
        self._replace_project(project)

    def update_condition(self, condition_id: str, **updates: object) -> None:
        """Update one condition by id through Pydantic validation."""

        conditions: list[Condition] = []
        found = False
        for condition in self.ordered_conditions():
            if condition.condition_id == condition_id:
                condition = _validated_copy(condition, **updates)
                found = True
            conditions.append(condition)
        if not found:
            raise DocumentError(f"Unknown condition '{condition_id}'.")
        project = _validated_copy(
            self._project,
            conditions=self._reindex_conditions(conditions),
        )
        self._replace_project(project)

    def import_condition_stimulus_folder(
        self,
        condition_id: str,
        *,
        role: str,
        source_dir: Path,
    ) -> StimulusSet:
        """Import one base or oddball source folder directly into the project."""

        stimulus_set = self.get_condition_stimulus_set(condition_id, role)
        _, imported_set = import_stimulus_source_directory(
            source_dir=Path(source_dir),
            project_root=self._project_root,
            set_id=stimulus_set.set_id,
            set_name=stimulus_set.name,
        )
        updated_sets = [
            imported_set if item.set_id == imported_set.set_id else item
            for item in self._project.stimulus_sets
        ]
        project = _validated_copy(self._project, stimulus_sets=updated_sets)
        self._replace_project(project)
        self._update_manifest_for_stimulus_set(imported_set.set_id)
        return imported_set

    def refresh_stimulus_inspection(self) -> None:
        """Re-inspect all imported source folders and refresh project metadata."""

        updated_sets: list[StimulusSet] = []
        manifest = self._manifest or create_empty_manifest(self._project.meta.project_id)

        for stimulus_set in self._project.stimulus_sets:
            source_dir = self._project_root / Path(stimulus_set.source_dir)
            summary = inspect_source_directory(
                source_dir,
                relative_prefix=stimulus_set.source_dir,
                strict=True,
            )
            refreshed_set = summary_to_stimulus_set(
                set_id=stimulus_set.set_id,
                name=stimulus_set.name,
                summary=summary,
            )
            refreshed_set = refreshed_set.model_copy(
                update={"available_variants": stimulus_set.available_variants}
            )
            updated_sets.append(refreshed_set)
            manifest = upsert_manifest_set(
                manifest,
                inspection_summary_to_manifest_set(
                    set_id=stimulus_set.set_id,
                    summary=summary,
                ),
            )

        project = _validated_copy(self._project, stimulus_sets=updated_sets)
        self._replace_project(project)
        self._manifest = manifest
        write_stimulus_manifest(self._project_root, manifest)
        self.manifest_changed.emit()

    def materialize_assets(self) -> StimulusManifest:
        """Materialize configured stimulus variants via the preprocessing pipeline."""

        manifest = materialize_project_assets(self._project, project_root=self._project_root)
        self._manifest = manifest
        synced_sets = self._sync_stimulus_sets_from_manifest(manifest)
        project = _validated_copy(self._project, stimulus_sets=synced_sets)
        self._replace_project(project)
        self.manifest_changed.emit()
        return manifest

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

    def validation_report(self, *, refresh_hz: float) -> ProjectValidationReport:
        """Validate the current project at a specific compile refresh rate."""

        return validate_project(self._project, refresh_hz=refresh_hz)

    def fixation_guidance(self, *, refresh_hz: float):
        """Return condition-level fixation guidance at a specific refresh rate."""

        return condition_fixation_guidance(self._project, refresh_hz=refresh_hz)

    def compile_session(self, *, refresh_hz: float):
        """Compile the current project into a session plan."""

        report = self.validation_report(refresh_hz=refresh_hz)
        if not report.is_valid:
            raise DocumentError(_format_validation_report(report))
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
    ):
        """Compile and preflight the current session plan."""

        session_plan = self.compile_session(refresh_hz=refresh_hz)
        try:
            engine = create_engine(engine_name)
            preflight_session_plan(self._project_root, session_plan, engine=engine)
        except Exception as exc:
            raise DocumentError(str(exc)) from exc
        return session_plan

    def launch_test_session(
        self,
        *,
        refresh_hz: float,
        participant_number: str,
        display_index: int | None,
        fullscreen: bool = True,
        engine_name: str = EngineName.PSYCHOPY.value,
        test_mode: bool = True,
    ):
        """Compile and launch the current session through the runtime boundary."""

        session_plan = self.compile_session(refresh_hz=refresh_hz)
        try:
            summary = launch_session(
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
                ),
            )
        except Exception as exc:
            raise DocumentError(str(exc)) from exc
        return session_plan, summary

    def has_completed_session_for_participant(self, participant_number: str) -> bool:
        """Return whether this project already contains completed runs for a participant."""

        return bool(
            find_completed_sessions_for_participant(
                self._project_root,
                participant_number,
            )
        )

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

    def _make_empty_stimulus_set(self, set_id: str, name: str) -> StimulusSet:
        source_dir = to_project_relative_posix(
            self._project_root,
            stimulus_originals_dir(self._project_root, set_id),
        )
        return StimulusSet(
            set_id=set_id,
            name=name,
            source_dir=source_dir,
            image_count=0,
        )

    def _reindex_conditions(self, conditions: list[Condition]) -> list[Condition]:
        return [
            condition.model_copy(update={"order_index": index})
            for index, condition in enumerate(conditions)
        ]

    def _unique_slug(self, preferred_name: str, existing_ids: set[str]) -> str:
        base = slugify_project_name(preferred_name)
        candidate = base
        suffix = 2
        while candidate in existing_ids:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def _update_manifest_for_stimulus_set(self, set_id: str) -> None:
        stimulus_set = self.get_stimulus_set(set_id)
        if stimulus_set is None:
            return
        source_dir = self._project_root / Path(stimulus_set.source_dir)
        summary = inspect_source_directory(
            source_dir,
            relative_prefix=stimulus_set.source_dir,
            strict=True,
        )
        manifest = self._manifest or create_empty_manifest(self._project.meta.project_id)
        manifest = upsert_manifest_set(
            manifest,
            inspection_summary_to_manifest_set(
                set_id=set_id,
                summary=summary,
            ),
        )
        self._manifest = manifest
        write_stimulus_manifest(self._project_root, manifest)
        self.manifest_changed.emit()

    def _sync_stimulus_sets_from_manifest(
        self,
        manifest: StimulusManifest,
    ) -> list[StimulusSet]:
        manifest_sets = {manifest_set.set_id: manifest_set for manifest_set in manifest.sets}
        synced_sets: list[StimulusSet] = []
        for stimulus_set in self._project.stimulus_sets:
            manifest_set = manifest_sets.get(stimulus_set.set_id)
            if manifest_set is None:
                synced_sets.append(stimulus_set)
                continue
            resolution = (
                manifest_set.assets[0].source.resolution if manifest_set.assets else stimulus_set.resolution
            )
            synced_sets.append(
                stimulus_set.model_copy(
                    update={
                        "image_count": len(manifest_set.assets),
                        "resolution": resolution,
                        "available_variants": manifest_set.available_variants,
                    }
                )
            )
        return synced_sets


def default_session_settings() -> SessionSettings:
    """Return a fresh validated copy of session settings."""

    return SessionSettings()


def default_fixation_settings() -> FixationTaskSettings:
    """Return a fresh validated copy of fixation settings."""

    return FixationTaskSettings()


def default_trigger_settings() -> TriggerSettings:
    """Return a fresh validated copy of trigger settings."""

    return TriggerSettings()
