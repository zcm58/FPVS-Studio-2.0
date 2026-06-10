"""Versioned FPVS Studio project `.fpvsconfig` import/export contracts.

The config file is a JSON-backed interchange summary for Studio projects. It is not a
replacement for `project.json`, `stimuli/manifest.json`, or runtime `runs/` artifacts;
it collects the fields another tool needs for setup plus optional completed-session
reproducibility metadata.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field, StrictInt, ValidationError, field_validator, model_validator

from fpvs_studio import __version__
from fpvs_studio.core.display_geometry import visual_angle_width_cm, visual_angle_width_px
from fpvs_studio.core.enums import (
    DutyCycleMode,
    InterConditionMode,
    StimulusModality,
    StimulusVariant,
    TriggerBackendKind,
)
from fpvs_studio.core.models import (
    Condition,
    DisplaySettings,
    FPVSBaseModel,
    ProjectFile,
    ProjectMeta,
    ProjectSettings,
    SessionSettings,
    StimulusSet,
    TriggerSettings,
    validate_project_relative_path,
    validate_slug,
)
from fpvs_studio.core.paths import (
    cache_dir,
    logs_dir,
    project_dir,
    project_json_path,
    runs_dir,
    stimuli_dir,
    stimulus_generated_variants_root,
    stimulus_manifest_path,
    stimulus_original_images_root,
    stimulus_originals_dir,
)
from fpvs_studio.core.project_service import ProjectScaffold
from fpvs_studio.core.serialization import read_json_file, save_project_file
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.core.trigger_codes import validate_oddball_trigger_code_policy
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest
from fpvs_studio.preprocessing.models import StimulusManifest, StimulusSetManifest

CONFIG_SCHEMA_VERSION = "1.0.0"
PROJECT_CONFIG_SUFFIX = ".fpvsconfig"
_CONFIG_FILENAME_RE = re.compile(r"[^a-z0-9]+")


class ProjectConfigError(ValueError):
    """Raised when a `.fpvsconfig` file cannot be read, written, or imported safely."""


def project_config_filename(project_name: str, *, completed: bool = False) -> str:
    """Return the default user-facing config filename for a project title."""

    normalized = _CONFIG_FILENAME_RE.sub("", project_name.strip().lower())
    stem = normalized or "fpvsproject"
    if completed:
        stem = f"{stem}-completed"
    return f"{stem}{PROJECT_CONFIG_SUFFIX}"


class ProjectConfigProducer(FPVSBaseModel):
    """Application metadata for the config producer."""

    application: str = "FPVS Studio"
    version: str = __version__
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectConfigProject(FPVSBaseModel):
    """Project identity fields exported for setup handoff."""

    project_id: str
    name: str
    template_id: str
    description: str = ""

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_slug(value, field_name="project_id")


class ProjectConfigCondition(FPVSBaseModel):
    """Condition setup fields needed by Studio and downstream setup tools."""

    condition_id: str
    name: str
    trigger_code: StrictInt = Field(ge=0, le=255)
    base_stimulus_set_id: str
    oddball_stimulus_set_id: str
    stimulus_variant: StimulusVariant = StimulusVariant.ORIGINAL
    sequence_count: int = Field(gt=0)
    oddball_cycle_repeats_per_sequence: int = Field(ge=1)
    duty_cycle_mode: DutyCycleMode = DutyCycleMode.CONTINUOUS
    order_index: int = Field(ge=0)
    instructions: str = ""

    @field_validator("condition_id", "base_stimulus_set_id", "oddball_stimulus_set_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        return validate_slug(value, field_name="condition or stimulus set id")


class ProjectConfigStimulusSet(FPVSBaseModel):
    """Editable stimulus-set payload preserved for config import/export."""

    set_id: str
    name: str
    modality: StimulusModality = StimulusModality.IMAGE
    source_dir: str | None = None
    words: list[str] = Field(default_factory=list)

    @field_validator("set_id")
    @classmethod
    def validate_set_id(cls, value: str) -> str:
        return validate_slug(value, field_name="stimulus set id")

    @field_validator("source_dir")
    @classmethod
    def validate_source_dir(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_project_relative_path(value)


class ProjectConfigDisplay(FPVSBaseModel):
    """Display geometry needed to reproduce the intended visual angle."""

    fullscreen: bool = True
    background_color: str | tuple[int, int, int]
    monitor_name: str | None = None
    preferred_refresh_hz: float | None = Field(default=None, gt=0)
    stimulus_width_degrees: float = Field(gt=0)
    viewing_distance_cm: float = Field(gt=0)
    screen_width_cm: float = Field(gt=0)
    screen_width_px: int = Field(gt=0)
    screen_height_px: int = Field(gt=0)
    use_current_screen_resolution: bool = False
    stimulus_width_cm: float = Field(gt=0)
    stimulus_width_px: int = Field(gt=0)


class ProjectConfigSession(FPVSBaseModel):
    """Editable session settings exported with the config."""

    block_count: int = Field(ge=1)
    session_seed: int = Field(ge=0)
    randomize_conditions_per_block: bool = True
    inter_condition_mode: InterConditionMode = InterConditionMode.MANUAL_CONTINUE
    inter_condition_break_seconds: float = Field(ge=0)
    continue_key: str = "space"
    show_condition_title_on_screen: bool = False


class ProjectConfigTriggers(FPVSBaseModel):
    """Trigger settings needed by Studio and Toolbox setup."""

    backend: TriggerBackendKind
    enabled: bool
    serial_port: str | None = None
    baudrate: int = Field(gt=0)
    oddball_trigger_code: StrictInt = Field(ge=1, le=255)
    allow_nonstandard_oddball_trigger_code: bool = False
    pulse_width_ms: int = Field(ge=0)
    reset_code: StrictInt | None = Field(default=None, ge=0, le=0)
    reset_delay_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_locked_oddball_trigger_code(self) -> ProjectConfigTriggers:
        validate_oddball_trigger_code_policy(
            self.oddball_trigger_code,
            allow_nonstandard=self.allow_nonstandard_oddball_trigger_code,
        )
        return self


class ProjectConfigToolbox(FPVSBaseModel):
    """Toolbox-oriented setup fields kept simple for future import."""

    project_title: str
    event_map: dict[str, StrictInt] = Field(default_factory=dict)
    oddball_trigger_code: StrictInt = Field(ge=1, le=255)


class ProjectConfigTriggerEvent(FPVSBaseModel):
    """One compiled trigger event included in a completed config."""

    frame_index: int = Field(ge=0)
    code: StrictInt = Field(ge=1, le=255)
    label: str


class ProjectConfigCompletedRun(FPVSBaseModel):
    """One realized run entry from a completed session plan."""

    global_order_index: int = Field(ge=0)
    block_index: int = Field(ge=0)
    index_within_block: int = Field(ge=0)
    run_id: str
    condition_id: str
    condition_name: str
    random_seed: int = Field(ge=0)
    trigger_events: list[ProjectConfigTriggerEvent] = Field(default_factory=list)


class ProjectConfigCompletedSession(FPVSBaseModel):
    """Optional reproducibility summary for a completed session."""

    session_id: str
    session_seed: int = Field(ge=0)
    refresh_hz: float = Field(gt=0)
    block_orders: list[list[str]] = Field(default_factory=list)
    source_run_dir: str
    ordered_runs: list[ProjectConfigCompletedRun] = Field(default_factory=list)

    @field_validator("source_run_dir")
    @classmethod
    def validate_source_run_dir(cls, value: str) -> str:
        return validate_project_relative_path(value)


class ProjectConfigStimulusProvenance(FPVSBaseModel):
    """Stimulus manifest provenance copied into the config."""

    preprocessing_version: str | None = None
    generated_at: datetime | None = None
    sets: list[StimulusSetManifest] = Field(default_factory=list)


class ProjectConfigFile(FPVSBaseModel):
    """Top-level Studio `.fpvsconfig` interchange file."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    producer: ProjectConfigProducer = Field(default_factory=ProjectConfigProducer)
    project: ProjectConfigProject
    conditions: list[ProjectConfigCondition] = Field(default_factory=list)
    stimulus_sets: list[ProjectConfigStimulusSet] = Field(default_factory=list)
    display: ProjectConfigDisplay
    session: ProjectConfigSession
    triggers: ProjectConfigTriggers
    toolbox: ProjectConfigToolbox
    stimulus_provenance: ProjectConfigStimulusProvenance | None = None
    completed_session: ProjectConfigCompletedSession | None = None


def export_project_config(
    project: ProjectFile,
    project_root: Path | None,
    *,
    manifest: StimulusManifest | None = None,
    completed_session_dir: Path | None = None,
) -> ProjectConfigFile:
    """Build a setup or completed project config without mutating project state."""

    resolved_manifest = _resolve_manifest(project_root, manifest)
    session_plan = (
        _read_completed_session_plan(completed_session_dir) if completed_session_dir else None
    )
    return ProjectConfigFile(
        project=ProjectConfigProject(
            project_id=project.meta.project_id,
            name=project.meta.name,
            template_id=project.meta.template_id,
            description=project.meta.description,
        ),
        conditions=[
            ProjectConfigCondition(
                condition_id=condition.condition_id,
                name=condition.name,
                trigger_code=condition.trigger_code,
                base_stimulus_set_id=condition.base_stimulus_set_id,
                oddball_stimulus_set_id=condition.oddball_stimulus_set_id,
                stimulus_variant=condition.stimulus_variant,
                sequence_count=condition.sequence_count,
                oddball_cycle_repeats_per_sequence=(
                    condition.oddball_cycle_repeats_per_sequence
                ),
                duty_cycle_mode=condition.duty_cycle_mode,
                order_index=condition.order_index,
                instructions=condition.instructions,
            )
            for condition in sorted(project.conditions, key=lambda item: item.order_index)
        ],
        stimulus_sets=[
            ProjectConfigStimulusSet(
                set_id=stimulus_set.set_id,
                name=stimulus_set.name,
                modality=stimulus_set.modality,
                source_dir=stimulus_set.source_dir,
                words=stimulus_set.words,
            )
            for stimulus_set in project.stimulus_sets
        ],
        display=_display_config(project.settings.display),
        session=_session_config(project.settings.session),
        triggers=_trigger_config(project.settings.triggers),
        toolbox=_toolbox_config(project),
        stimulus_provenance=_stimulus_provenance(resolved_manifest),
        completed_session=(
            _completed_session_config(project_root, completed_session_dir, session_plan)
            if completed_session_dir is not None and session_plan is not None
            else None
        ),
    )


def write_project_config(path: Path, config: ProjectConfigFile) -> None:
    """Write a `.fpvsconfig` file as UTF-8 JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")


def read_project_config(path: Path) -> ProjectConfigFile:
    """Read a UTF-8 JSON `.fpvsconfig` file."""

    try:
        raw_payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProjectConfigError(f"Unable to read project config: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProjectConfigError(f"Project config is not valid JSON: {path}") from exc
    if not isinstance(raw_payload, dict):
        raise ProjectConfigError("Project config must contain a JSON object.")
    raw_version = raw_payload.get("schema_version")
    if raw_version != CONFIG_SCHEMA_VERSION:
        raise ProjectConfigError(
            "Unsupported project config schema version: "
            f"{raw_version!r}. Expected {CONFIG_SCHEMA_VERSION!r}."
        )
    try:
        return ProjectConfigFile.model_validate(raw_payload)
    except ValidationError as exc:
        raise ProjectConfigError(f"Project config failed validation: {exc}") from exc


def create_project_from_config(parent_dir: Path, config: ProjectConfigFile) -> ProjectScaffold:
    """Create a new Studio project shell from a `.fpvsconfig` file."""

    target_dir, project_id = _unique_import_project_dir(parent_dir, config.project.project_id)
    for folder in (
        target_dir,
        stimuli_dir(target_dir),
        stimulus_original_images_root(target_dir),
        stimulus_generated_variants_root(target_dir),
        runs_dir(target_dir),
        cache_dir(target_dir),
        logs_dir(target_dir),
    ):
        folder.mkdir(parents=True, exist_ok=True)

    stimulus_sets = _placeholder_stimulus_sets(config)
    for stimulus_set in stimulus_sets:
        if stimulus_set.modality == StimulusModality.IMAGE:
            stimulus_originals_dir(target_dir, stimulus_set.set_id).mkdir(
                parents=True,
                exist_ok=True,
            )

    project = ProjectFile(
        meta=ProjectMeta(
            project_id=project_id,
            name=config.project.name,
            template_id=config.project.template_id,
            description=config.project.description,
        ),
        settings=ProjectSettings(
            display=_display_settings(config.display),
            triggers=_trigger_settings(config.triggers),
            session=_session_settings(config.session),
        ),
        stimulus_sets=stimulus_sets,
        conditions=[
            Condition(
                condition_id=condition.condition_id,
                name=condition.name,
                instructions=condition.instructions,
                base_stimulus_set_id=condition.base_stimulus_set_id,
                oddball_stimulus_set_id=condition.oddball_stimulus_set_id,
                stimulus_variant=condition.stimulus_variant,
                sequence_count=condition.sequence_count,
                oddball_cycle_repeats_per_sequence=(
                    condition.oddball_cycle_repeats_per_sequence
                ),
                trigger_code=condition.trigger_code,
                duty_cycle_mode=condition.duty_cycle_mode,
                order_index=index,
            )
            for index, condition in enumerate(config.conditions)
        ],
    )
    save_project_file(project, project_json_path(target_dir))
    write_stimulus_manifest(target_dir, create_empty_manifest(project.meta.project_id))
    return ProjectScaffold(project_root=target_dir, project=project)


def find_latest_completed_session_dir(project_root: Path) -> Path | None:
    """Return the latest run directory containing a readable completed session plan."""

    root = runs_dir(project_root)
    if not root.is_dir():
        return None
    candidates = [
        candidate
        for candidate in root.iterdir()
        if candidate.is_dir() and (candidate / "session_plan.json").is_file()
    ]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        try:
            _read_completed_session_plan(candidate)
        except ProjectConfigError:
            continue
        return candidate
    return None


def _resolve_manifest(
    project_root: Path | None,
    manifest: StimulusManifest | None,
) -> StimulusManifest | None:
    if manifest is not None:
        return manifest
    if project_root is None:
        return None
    path = stimulus_manifest_path(project_root)
    if not path.is_file():
        return None
    try:
        return read_json_file(path, StimulusManifest)
    except Exception as exc:
        raise ProjectConfigError(f"Unable to read stimulus manifest: {path}") from exc


def _read_completed_session_plan(completed_session_dir: Path | None) -> SessionPlan:
    if completed_session_dir is None:
        raise ProjectConfigError("Completed session export requires a session directory.")
    path = completed_session_dir / "session_plan.json"
    if not path.is_file():
        raise ProjectConfigError(f"Completed session is missing session_plan.json: {path}")
    try:
        return read_json_file(path, SessionPlan)
    except Exception as exc:
        raise ProjectConfigError(f"Unable to read completed session plan: {path}") from exc


def _display_config(display: DisplaySettings) -> ProjectConfigDisplay:
    width_cm = visual_angle_width_cm(
        degrees=display.stimulus_width_degrees,
        viewing_distance_cm=display.viewing_distance_cm,
    )
    width_px = visual_angle_width_px(
        degrees=display.stimulus_width_degrees,
        viewing_distance_cm=display.viewing_distance_cm,
        screen_width_cm=display.screen_width_cm,
        screen_width_px=display.screen_width_px,
    )
    return ProjectConfigDisplay(
        fullscreen=display.fullscreen,
        background_color=display.background_color,
        monitor_name=display.monitor_name,
        preferred_refresh_hz=display.preferred_refresh_hz,
        stimulus_width_degrees=display.stimulus_width_degrees,
        viewing_distance_cm=display.viewing_distance_cm,
        screen_width_cm=display.screen_width_cm,
        screen_width_px=display.screen_width_px,
        screen_height_px=display.screen_height_px,
        use_current_screen_resolution=display.use_current_screen_resolution,
        stimulus_width_cm=width_cm,
        stimulus_width_px=width_px,
    )


def _session_config(session: SessionSettings) -> ProjectConfigSession:
    return ProjectConfigSession(
        block_count=session.block_count,
        session_seed=session.session_seed,
        randomize_conditions_per_block=session.randomize_conditions_per_block,
        inter_condition_mode=session.inter_condition_mode,
        inter_condition_break_seconds=session.inter_condition_break_seconds,
        continue_key=session.continue_key,
        show_condition_title_on_screen=session.show_condition_title_on_screen,
    )


def _trigger_config(triggers: TriggerSettings) -> ProjectConfigTriggers:
    oddball_trigger_code = _validated_project_oddball_trigger_code(triggers)
    return ProjectConfigTriggers(
        backend=triggers.backend,
        enabled=triggers.enabled,
        serial_port=triggers.serial_port,
        baudrate=triggers.baudrate,
        oddball_trigger_code=oddball_trigger_code,
        allow_nonstandard_oddball_trigger_code=(
            triggers.allow_nonstandard_oddball_trigger_code
        ),
        pulse_width_ms=triggers.pulse_width_ms,
        reset_code=triggers.reset_code,
        reset_delay_ms=triggers.reset_delay_ms,
    )


def _toolbox_config(project: ProjectFile) -> ProjectConfigToolbox:
    oddball_trigger_code = _validated_project_oddball_trigger_code(project.settings.triggers)
    return ProjectConfigToolbox(
        project_title=project.meta.name,
        event_map={condition.name: condition.trigger_code for condition in project.conditions},
        oddball_trigger_code=oddball_trigger_code,
    )


def _validated_project_oddball_trigger_code(triggers: TriggerSettings) -> int:
    try:
        return validate_oddball_trigger_code_policy(
            triggers.oddball_trigger_code,
            allow_nonstandard=triggers.allow_nonstandard_oddball_trigger_code,
        )
    except (TypeError, ValueError) as exc:
        raise ProjectConfigError(str(exc)) from exc


def _stimulus_provenance(
    manifest: StimulusManifest | None,
) -> ProjectConfigStimulusProvenance | None:
    if manifest is None:
        return None
    return ProjectConfigStimulusProvenance(
        preprocessing_version=manifest.preprocessing_version,
        generated_at=manifest.generated_at,
        sets=manifest.sets,
    )


def _completed_session_config(
    project_root: Path | None,
    completed_session_dir: Path,
    session_plan: SessionPlan,
) -> ProjectConfigCompletedSession:
    if project_root is None:
        raise ProjectConfigError("Completed session export requires a project root.")
    source_run_dir = completed_session_dir.resolve().relative_to(project_root.resolve()).as_posix()
    return ProjectConfigCompletedSession(
        session_id=session_plan.session_id,
        session_seed=session_plan.random_seed,
        refresh_hz=session_plan.refresh_hz,
        block_orders=[list(block.condition_order) for block in session_plan.blocks],
        source_run_dir=source_run_dir,
        ordered_runs=[
            ProjectConfigCompletedRun(
                global_order_index=entry.global_order_index,
                block_index=entry.block_index,
                index_within_block=entry.index_within_block,
                run_id=entry.run_id,
                condition_id=entry.condition_id,
                condition_name=entry.condition_name,
                random_seed=entry.run_spec.random_seed,
                trigger_events=[
                    ProjectConfigTriggerEvent(
                        frame_index=trigger.frame_index,
                        code=trigger.code,
                        label=trigger.label,
                    )
                    for trigger in entry.run_spec.trigger_events
                ],
            )
            for entry in session_plan.ordered_entries()
        ],
    )


def _unique_import_project_dir(parent_dir: Path, source_project_id: str) -> tuple[Path, str]:
    source_project_id = validate_slug(source_project_id, field_name="project_id")
    candidate_id = source_project_id
    candidate_dir = project_dir(parent_dir, candidate_id)
    if not candidate_dir.exists():
        return candidate_dir, candidate_id

    base_id = f"{source_project_id}-from-config"
    candidate_id = base_id
    candidate_dir = project_dir(parent_dir, candidate_id)
    suffix = 2
    while candidate_dir.exists():
        candidate_id = f"{base_id}-{suffix}"
        candidate_dir = project_dir(parent_dir, candidate_id)
        suffix += 1
    return candidate_dir, candidate_id


def _placeholder_stimulus_sets(config: ProjectConfigFile) -> list[StimulusSet]:
    if config.stimulus_sets:
        return [
            StimulusSet(
                set_id=stimulus_set.set_id,
                name=stimulus_set.name,
                modality=stimulus_set.modality,
                source_dir=stimulus_set.source_dir
                if stimulus_set.modality == StimulusModality.IMAGE
                else None,
                resolution=None,
                image_count=0,
                words=stimulus_set.words,
            )
            for stimulus_set in config.stimulus_sets
        ]
    set_ids: list[str] = []
    for condition in config.conditions:
        for set_id in (condition.base_stimulus_set_id, condition.oddball_stimulus_set_id):
            if set_id not in set_ids:
                set_ids.append(set_id)
    return [
        StimulusSet(
            set_id=set_id,
            name=_stimulus_set_name(config, set_id),
            source_dir=f"stimuli/original-images/{set_id}",
            resolution=None,
            image_count=0,
        )
        for set_id in set_ids
    ]


def _stimulus_set_name(config: ProjectConfigFile, set_id: str) -> str:
    if config.stimulus_provenance is not None:
        for manifest_set in config.stimulus_provenance.sets:
            if manifest_set.set_id == set_id:
                return set_id.replace("-", " ").title()
    return set_id.replace("-", " ").title()


def _display_settings(config: ProjectConfigDisplay) -> DisplaySettings:
    return DisplaySettings(
        fullscreen=config.fullscreen,
        background_color=config.background_color,
        monitor_name=config.monitor_name,
        preferred_refresh_hz=config.preferred_refresh_hz,
        stimulus_width_degrees=config.stimulus_width_degrees,
        viewing_distance_cm=config.viewing_distance_cm,
        screen_width_cm=config.screen_width_cm,
        screen_width_px=config.screen_width_px,
        screen_height_px=config.screen_height_px,
        use_current_screen_resolution=config.use_current_screen_resolution,
    )


def _trigger_settings(config: ProjectConfigTriggers) -> TriggerSettings:
    return TriggerSettings(
        backend=config.backend,
        enabled=config.enabled,
        serial_port=config.serial_port,
        baudrate=config.baudrate,
        oddball_trigger_code=config.oddball_trigger_code,
        allow_nonstandard_oddball_trigger_code=config.allow_nonstandard_oddball_trigger_code,
        pulse_width_ms=config.pulse_width_ms,
        reset_code=config.reset_code,
        reset_delay_ms=config.reset_delay_ms,
    )


def _session_settings(config: ProjectConfigSession) -> SessionSettings:
    return SessionSettings(
        block_count=config.block_count,
        session_seed=config.session_seed,
        randomize_conditions_per_block=config.randomize_conditions_per_block,
        inter_condition_mode=config.inter_condition_mode,
        inter_condition_break_seconds=config.inter_condition_break_seconds,
        continue_key=config.continue_key,
        show_condition_title_on_screen=config.show_condition_title_on_screen,
    )
