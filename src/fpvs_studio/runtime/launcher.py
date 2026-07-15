"""Runtime launch entrypoints for single runs and ordered sessions. It combines RunSpec or
SessionPlan artifacts with machine-specific LaunchSettings, engine selection, preflight,
and output-folder preparation. This module owns launch orchestration and runtime-only
options, not compilation of project state or engine rendering internals."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from pydantic import ValidationError

from fpvs_studio.core.enums import EngineName
from fpvs_studio.core.execution import (
    ParticipantMetadata,
    RunExecutionSummary,
    SessionExecutionSummary,
)
from fpvs_studio.core.paths import runs_dir, to_project_relative_posix
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.engines.registry import create_engine
from fpvs_studio.runtime.export_modes import EXPORT_MODE_FULL, VALID_EXPORT_MODES
from fpvs_studio.runtime.participant_history import resolve_next_participant_output_label
from fpvs_studio.runtime.preflight import preflight_run_spec, preflight_session_plan
from fpvs_studio.runtime.run_worker import RuntimeWorker


class LaunchSettingsError(ValueError):
    """Raised when runtime-only launch settings are invalid for the current v1 runtime."""


@dataclass(frozen=True)
class LaunchSettings:
    """Runtime-only machine/launch options that do not belong in core models."""

    engine_name: str | EngineName = EngineName.PSYCHOPY
    test_mode: bool = True
    fullscreen: bool = True
    display_index: int | None = None
    serial_enabled: bool = False
    serial_port: str | None = "COM3"
    serial_baudrate: int = 115200
    serial_pulse_width_ms: int = 10
    serial_reset_code: int | None = None
    serial_reset_delay_ms: int = 5
    strict_timing: bool = True
    strict_timing_warmup: bool = True
    timing_miss_threshold_multiplier: float = 1.5
    timing_warmup_frames: int = 240
    export_mode: str = EXPORT_MODE_FULL

    def as_runtime_options(self) -> dict[str, object]:
        """Return a generic engine-facing runtime options mapping."""

        options = asdict(self)
        engine_name = options["engine_name"]
        if isinstance(engine_name, EngineName):
            options["engine_name"] = engine_name.value
        options["verify_refresh_rate"] = True
        return options


def _validate_launch_settings(settings: LaunchSettings) -> None:
    if not settings.test_mode:
        raise LaunchSettingsError(
            "FPVS Studio Phase 4 currently requires test_mode=True. "
            "Non-test launch validation remains deferred."
        )
    if settings.display_index is not None:
        if not isinstance(settings.display_index, int) or settings.display_index < 0:
            raise LaunchSettingsError("display_index must be None or a non-negative integer.")
    if not isinstance(settings.fullscreen, bool):
        raise LaunchSettingsError("fullscreen must be a boolean.")
    if not isinstance(settings.serial_enabled, bool):
        raise LaunchSettingsError("serial_enabled must be a boolean.")
    if not isinstance(settings.strict_timing, bool):
        raise LaunchSettingsError("strict_timing must be a boolean.")
    if not isinstance(settings.strict_timing_warmup, bool):
        raise LaunchSettingsError("strict_timing_warmup must be a boolean.")
    if (
        not isinstance(settings.timing_miss_threshold_multiplier, (int, float))
        or settings.timing_miss_threshold_multiplier <= 1.0
    ):
        raise LaunchSettingsError(
            "timing_miss_threshold_multiplier must be a number greater than 1.0."
        )
    if not isinstance(settings.timing_warmup_frames, int) or settings.timing_warmup_frames < 0:
        raise LaunchSettingsError("timing_warmup_frames must be a non-negative integer.")
    if settings.export_mode not in VALID_EXPORT_MODES:
        valid_values = "', '".join(sorted(VALID_EXPORT_MODES))
        raise LaunchSettingsError(f"export_mode must be one of '{valid_values}'.")
    if settings.serial_port is not None and not settings.serial_port.strip():
        raise LaunchSettingsError("serial_port may not be blank when provided.")
    if not isinstance(settings.serial_baudrate, int) or settings.serial_baudrate <= 0:
        raise LaunchSettingsError("serial_baudrate must be a positive integer.")
    if (
        not isinstance(settings.serial_pulse_width_ms, int)
        or settings.serial_pulse_width_ms < 0
    ):
        raise LaunchSettingsError("serial_pulse_width_ms must be a non-negative integer.")
    if settings.serial_reset_code is not None:
        if (
            not isinstance(settings.serial_reset_code, int)
            or settings.serial_reset_code != 0
        ):
            raise LaunchSettingsError("serial_reset_code must be None or the integer 0.")
    if (
        not isinstance(settings.serial_reset_delay_ms, int)
        or settings.serial_reset_delay_ms < 0
    ):
        raise LaunchSettingsError("serial_reset_delay_ms must be a non-negative integer.")


def _validate_participant_number(participant_number: str) -> str:
    if not isinstance(participant_number, str):
        raise LaunchSettingsError("participant_number must be a string.")
    cleaned = participant_number.strip()
    if not cleaned:
        raise LaunchSettingsError("participant_number is required.")
    if not cleaned.isdigit():
        raise LaunchSettingsError("participant_number must contain digits only.")
    return cleaned


def _validate_participant_metadata(
    participant_metadata: ParticipantMetadata | Mapping[str, object] | None,
) -> ParticipantMetadata:
    if participant_metadata is None:
        return ParticipantMetadata()
    if isinstance(participant_metadata, ParticipantMetadata):
        return participant_metadata
    try:
        return ParticipantMetadata.model_validate(participant_metadata)
    except ValidationError as exc:
        raise LaunchSettingsError(str(exc)) from exc


def launch_run(
    project_root: Path,
    run_spec: RunSpec,
    *,
    participant_number: str,
    participant_metadata: ParticipantMetadata | Mapping[str, object] | None = None,
    launch_settings: LaunchSettings | None = None,
) -> RunExecutionSummary:
    """Launch one compiled RunSpec into the selected presentation engine."""

    settings = launch_settings or LaunchSettings()
    _validate_launch_settings(settings)
    if settings.export_mode != EXPORT_MODE_FULL:
        raise LaunchSettingsError(
            "launch_run only supports full export mode; use launch_session for compact "
            "summary exports."
        )
    runtime_options = settings.as_runtime_options()
    cleaned_participant_number = _validate_participant_number(participant_number)
    cleaned_participant_metadata = _validate_participant_metadata(participant_metadata)
    output_dir = runs_dir(project_root) / run_spec.run_id
    relative_output_dir = to_project_relative_posix(project_root, output_dir)
    engine = create_engine(settings.engine_name)
    preflight_run_spec(project_root, run_spec, engine=engine, runtime_options=runtime_options)
    worker = RuntimeWorker(engine)
    return worker.execute(
        project_root,
        run_spec,
        output_dir,
        runtime_options=runtime_options,
        relative_output_dir=relative_output_dir,
        participant_number=cleaned_participant_number,
        participant_metadata=cleaned_participant_metadata,
    )


def launch_session(
    project_root: Path,
    session_plan: SessionPlan,
    *,
    participant_number: str,
    participant_metadata: ParticipantMetadata | Mapping[str, object] | None = None,
    launch_settings: LaunchSettings | None = None,
) -> SessionExecutionSummary:
    """Launch an ordered session plan into the selected presentation engine."""

    settings = launch_settings or LaunchSettings()
    _validate_launch_settings(settings)
    runtime_options = settings.as_runtime_options()
    cleaned_participant_number = _validate_participant_number(participant_number)
    cleaned_participant_metadata = _validate_participant_metadata(participant_metadata)
    output_label = resolve_next_participant_output_label(project_root, cleaned_participant_number)
    output_dir = runs_dir(project_root) / output_label
    relative_output_dir = to_project_relative_posix(project_root, output_dir)
    engine = create_engine(settings.engine_name)
    preflight_session_plan(
        project_root,
        session_plan,
        engine=engine,
        runtime_options=runtime_options,
    )
    worker = RuntimeWorker(engine)
    return worker.execute_session(
        project_root,
        session_plan,
        output_dir,
        runtime_options=runtime_options,
        relative_output_dir=relative_output_dir,
        participant_number=cleaned_participant_number,
        participant_metadata=cleaned_participant_metadata,
    )
