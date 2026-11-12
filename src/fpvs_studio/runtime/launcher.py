"""Runtime launch entrypoints for single runs and ordered sessions. It combines RunSpec or
SessionPlan artifacts with machine-specific LaunchSettings, engine selection, preflight,
and output-folder preparation. This module owns launch orchestration and runtime-only
options, not compilation of project state or engine rendering internals."""

from __future__ import annotations

import sys
import threading
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
from fpvs_studio.runtime.participant_sessions import reserve_participant_session
from fpvs_studio.runtime.preflight import preflight_run_spec, preflight_session_plan
from fpvs_studio.runtime.recording import (
    RecordingConfigurationError,
    resolve_recording_backend,
    validate_production_recording,
    validate_recording_configuration,
)
from fpvs_studio.runtime.run_worker import RuntimeWorker
from fpvs_studio.runtime.unicorn_recorder import require_unicorn_recorder_recording
from fpvs_studio.triggers.serial_backend import resolve_serial_port


class LaunchSettingsError(ValueError):
    """Raised when runtime-only launch settings are invalid for the current v1 runtime."""


@dataclass(frozen=True)
class LaunchSettings:
    """Runtime-only machine/launch options that do not belong in core models."""

    engine_name: str | EngineName = EngineName.PSYCHOPY
    fullscreen: bool = True
    display_index: int | None = None
    display_device_name: str | None = None
    serial_enabled: bool = True
    serial_port: str | None = "COM3"
    serial_baudrate: int = 115200
    serial_pulse_width_ms: int = 10
    serial_reset_code: int | None = None
    serial_reset_delay_ms: int = 5
    recording_backend: str | None = None
    recording_selection_source: str = "local_settings"
    unicorn_udp_port: int = 1000
    brainproducts_serial_port: str = "COM3"
    brainproducts_parallel_address: int | None = None
    brainproducts_pulse_width_ms: int = 10
    brainproducts_amplifier: str | None = None
    brainproducts_sampling_rate_hz: int | None = None
    recording_operator_confirmed: bool = False
    recording_association: str | None = None
    recorder_version: str | None = None
    strict_timing: bool = True
    strict_timing_warmup: bool = True
    verify_refresh_rate: bool = True
    verify_graphics_memory: bool = True
    timing_miss_threshold_multiplier: float = 1.5
    timing_warmup_frames: int = 240
    completion_screen_seconds: float = 0.5
    windowed_size_px: tuple[int, int] = (1280, 720)
    export_mode: str = EXPORT_MODE_FULL
    pilot_mode: bool = False
    experiment_test_mode: bool = False
    sharing_protocol_sha256: str | None = None
    toolbox_handoff_config: dict[str, object] | None = None

    def as_runtime_options(self) -> dict[str, object]:
        """Return a generic engine-facing runtime options mapping."""

        options = asdict(self)
        if self.display_device_name is None:
            options.pop("display_device_name")
        if self.sharing_protocol_sha256 is None:
            options.pop("sharing_protocol_sha256")
        if self.toolbox_handoff_config is None:
            options.pop("toolbox_handoff_config")
        if resolve_recording_backend(options) == "serial":
            options["serial_port"] = resolve_serial_port(self.serial_port)
        engine_name = options["engine_name"]
        if isinstance(engine_name, EngineName):
            options["engine_name"] = engine_name.value
        return options


def _validate_macos_source_launch(
    settings: LaunchSettings, *, require_main_thread: bool = False,
) -> None:
    """Keep initial macOS source execution explicit, verified and hardware-free."""
    if sys.platform != "darwin":
        return
    if getattr(sys, "frozen", False):
        raise LaunchSettingsError(
            "Packaged macOS execution is unsupported; use the source environment."
        )
    if settings.experiment_test_mode is not True and settings.pilot_mode is not True:
        raise LaunchSettingsError(
            "macOS source execution requires Experiment Test Mode or Pilot mode."
        )
    if settings.serial_enabled is not False:
        raise LaunchSettingsError(
            "macOS source execution requires external trigger output disabled."
        )
    if settings.fullscreen is not True:
        raise LaunchSettingsError("macOS source execution requires fullscreen presentation.")
    if settings.verify_refresh_rate is not True:
        raise LaunchSettingsError("macOS source execution requires refresh-rate verification.")
    if settings.display_index is not None and (
        type(settings.display_index) is not int or settings.display_index != 0
    ):
        raise LaunchSettingsError(
            "Select the Mac monitor by its native identity; numeric indices support only "
            "the primary display."
        )
    if settings.display_device_name is not None:
        from fpvs_studio.runtime.display_mode import DisplayModeError
        from fpvs_studio.runtime.macos_display import macos_display_id

        try:
            macos_display_id(settings.display_device_name)
        except (DisplayModeError, TypeError, ValueError) as exc:
            raise LaunchSettingsError("Select a valid Mac presentation monitor.") from exc
        if settings.display_index is not None:
            raise LaunchSettingsError("Select a display by device name or index, not both.")
    if require_main_thread and threading.current_thread() is not threading.main_thread():
        raise LaunchSettingsError("macOS presentation must run on the process main thread.")


def _validate_launch_settings(settings: LaunchSettings) -> None:
    _validate_macos_source_launch(settings)
    if not isinstance(settings.pilot_mode, bool):
        raise LaunchSettingsError("pilot_mode must be a boolean.")
    if not isinstance(settings.experiment_test_mode, bool):
        raise LaunchSettingsError("experiment_test_mode must be a boolean.")
    if settings.display_index is not None:
        if type(settings.display_index) is not int or settings.display_index < 0:
            raise LaunchSettingsError("display_index must be None or a non-negative integer.")
    if settings.display_device_name is not None:
        if (
            not isinstance(settings.display_device_name, str)
            or not settings.display_device_name.strip()
        ):
            raise LaunchSettingsError("display_device_name must be None or a non-empty string.")
        if sys.platform not in {"win32", "darwin"}:
            raise LaunchSettingsError("Named monitor selection is supported on Windows and macOS.")
        if settings.display_index is not None:
            raise LaunchSettingsError("Select a display by device name or index, not both.")
    if not isinstance(settings.fullscreen, bool):
        raise LaunchSettingsError("fullscreen must be a boolean.")
    if not isinstance(settings.serial_enabled, bool):
        raise LaunchSettingsError("serial_enabled must be a boolean.")
    try:
        effective_recording_backend = validate_production_recording(asdict(settings))
    except RecordingConfigurationError as exc:
        raise LaunchSettingsError(str(exc)) from exc
    if not isinstance(settings.strict_timing, bool):
        raise LaunchSettingsError("strict_timing must be a boolean.")
    if not isinstance(settings.strict_timing_warmup, bool):
        raise LaunchSettingsError("strict_timing_warmup must be a boolean.")
    if not isinstance(settings.verify_refresh_rate, bool):
        raise LaunchSettingsError("verify_refresh_rate must be a boolean.")
    if not isinstance(settings.verify_graphics_memory, bool):
        raise LaunchSettingsError("verify_graphics_memory must be a boolean.")
    if (
        not isinstance(settings.timing_miss_threshold_multiplier, (int, float))
        or settings.timing_miss_threshold_multiplier <= 1.0
    ):
        raise LaunchSettingsError(
            "timing_miss_threshold_multiplier must be a number greater than 1.0."
        )
    if not isinstance(settings.timing_warmup_frames, int) or settings.timing_warmup_frames < 0:
        raise LaunchSettingsError("timing_warmup_frames must be a non-negative integer.")
    if (
        isinstance(settings.completion_screen_seconds, bool)
        or not isinstance(settings.completion_screen_seconds, (int, float))
        or settings.completion_screen_seconds < 0
    ):
        raise LaunchSettingsError(
            "completion_screen_seconds must be a non-negative number."
        )
    if (
        not isinstance(settings.windowed_size_px, tuple)
        or len(settings.windowed_size_px) != 2
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in settings.windowed_size_px
        )
    ):
        raise LaunchSettingsError(
            "windowed_size_px must contain two positive integer dimensions."
        )
    if settings.export_mode not in VALID_EXPORT_MODES:
        valid_values = "', '".join(sorted(VALID_EXPORT_MODES))
        raise LaunchSettingsError(f"export_mode must be one of '{valid_values}'.")
    if settings.recording_backend in (
        "unicorn_udp", "brainproducts_triggerbox", "brainproducts_parallel",
    ):
        return
    if effective_recording_backend == "serial":
        try:
            resolve_serial_port(settings.serial_port)
        except ValueError as exc:
            raise LaunchSettingsError(str(exc)) from exc
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


def _launch_runtime_options(settings: LaunchSettings) -> dict[str, object]:
    """Pin native display identity so preflight and playback share one monitor."""
    options = settings.as_runtime_options()
    if sys.platform == "win32" and settings.display_index is not None:
        from fpvs_studio.runtime.windows_display import (
            WindowsDisplayModeError,
            query_windows_monitors,
        )

        try:
            monitors = query_windows_monitors()
        except WindowsDisplayModeError as exc:
            raise LaunchSettingsError(str(exc)) from exc
        if not 0 <= settings.display_index < len(monitors):
            raise LaunchSettingsError("The selected display index is no longer available.")
        options["display_device_name"] = monitors[settings.display_index].device_name
        options["display_index"] = None
    elif sys.platform == "darwin" and settings.display_device_name is None:
        from fpvs_studio.runtime.display_mode import DisplayModeError
        from fpvs_studio.runtime.macos_display import query_macos_monitors

        try:
            primary = [monitor for monitor in query_macos_monitors() if monitor.primary]
        except DisplayModeError as exc:
            raise LaunchSettingsError(str(exc)) from exc
        if len(primary) != 1:
            raise LaunchSettingsError("macOS did not identify one active primary display.")
        options["display_device_name"] = primary[0].device_name
        options["display_index"] = None
    return options


def _check_recorder_before_launch(settings: LaunchSettings) -> None:
    """Check live Recorder state outside the GUI thread before presentation.

    Pending receiver/timing qualification is recorded as metadata, not a blanket
    launch block. A normal Unicorn launch still requires fresh raw recording data.
    """

    try:
        backend = validate_recording_configuration(asdict(settings))
    except RecordingConfigurationError as exc:
        raise LaunchSettingsError(str(exc)) from exc
    if backend == "unicorn_udp":
        require_unicorn_recorder_recording()


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
    _validate_macos_source_launch(settings, require_main_thread=True)
    _check_recorder_before_launch(settings)
    _validate_launch_settings(settings)
    if settings.export_mode != EXPORT_MODE_FULL:
        raise LaunchSettingsError(
            "launch_run only supports full export mode; use launch_session for compact "
            "summary exports."
        )
    runtime_options = _launch_runtime_options(settings)
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
    participant_session_number: int | None = None,
    participant_metadata: ParticipantMetadata | Mapping[str, object] | None = None,
    launch_settings: LaunchSettings | None = None,
) -> SessionExecutionSummary:
    """Launch an ordered session plan into the selected presentation engine."""

    settings = launch_settings or LaunchSettings()
    _validate_macos_source_launch(settings, require_main_thread=True)
    _check_recorder_before_launch(settings)
    _validate_launch_settings(settings)
    runtime_options = _launch_runtime_options(settings)
    cleaned_participant_number = _validate_participant_number(participant_number)
    cleaned_participant_metadata = _validate_participant_metadata(participant_metadata)
    engine = create_engine(settings.engine_name)
    preflight_session_plan(
        project_root,
        session_plan,
        engine=engine,
        runtime_options=runtime_options,
    )
    reservation = reserve_participant_session(
        project_root,
        cleaned_participant_number,
        session_id=session_plan.session_id,
        participant_session_number=participant_session_number,
        create_output_directory=settings.export_mode == EXPORT_MODE_FULL,
    )
    output_dir = runs_dir(project_root) / reservation.output_label
    relative_output_dir = to_project_relative_posix(project_root, output_dir)
    worker = RuntimeWorker(engine)
    return worker.execute_session(
        project_root,
        session_plan,
        output_dir,
        runtime_options=runtime_options,
        relative_output_dir=relative_output_dir,
        participant_number=cleaned_participant_number,
        participant_session_number=reservation.participant_session_number,
        participant_metadata=cleaned_participant_metadata,
    )
