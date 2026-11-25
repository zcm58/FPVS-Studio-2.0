"""Compilation, preflight, and launch helpers for the GUI project document facade."""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, cast

from pydantic import ValidationError

from fpvs_studio.core.compiler import CompileError, compile_session_plan
from fpvs_studio.core.data_sharing import protocol_fingerprint
from fpvs_studio.core.enums import EngineName, ValidationSeverity
from fpvs_studio.core.execution import ParticipantMetadata
from fpvs_studio.core.models import (
    DisplaySettings,
    ProjectFile,
    ProjectRecordingSettings,
    ProjectValidationReport,
)
from fpvs_studio.core.project_config import export_project_config
from fpvs_studio.core.randomization import RandomizationSeeds
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.core.validation import (
    APPROVED_MONITOR_REFRESH_RATES_HZ,
    ConditionFixationGuidance,
    condition_fixation_guidance,
    validate_project,
)
from fpvs_studio.data_sharing.errors import DataSharingError
from fpvs_studio.data_sharing.library_scope import validate_library_scope
from fpvs_studio.data_sharing.storage import SharingStorageError, load_settings
from fpvs_studio.gui.document_support import (
    DocumentError,
    LaunchSummary,
    format_validation_report,
)
from fpvs_studio.runtime.launcher import LaunchSettings
from fpvs_studio.runtime.participant_history import find_completed_sessions_for_participant
from fpvs_studio.runtime.participant_sessions import resolve_next_participant_session_number
from fpvs_studio.runtime.recording import (
    recording_backend_label,
    validate_recording_configuration,
)

if TYPE_CHECKING:
    from fpvs_studio.runtime.condition_recovery import InterruptedCondition


class _SessionLaunchRequired(TypedDict):
    participant_number: str
    launch_settings: LaunchSettings


class _SessionLaunchArguments(_SessionLaunchRequired, total=False):
    participant_metadata: ParticipantMetadata
    participant_session_number: int


def _document_dependency(name: str) -> Any:
    return getattr(import_module("fpvs_studio.gui.document"), name)


def _sharing_protocol(
    project: ProjectFile, project_root: Path, verified_digest: str | None = None,
) -> str | None:
    try:
        if load_settings(project_root).enabled:
            return verified_digest or protocol_fingerprint(project, project_root)
    except Exception:
        logging.getLogger(__name__).warning(
            "Sharing protocol could not be verified; "
            "local launch continues and uploads remain held.",
            exc_info=True,
        )
    return None


def _toolbox_handoff_config(
    project: ProjectFile, project_root: Path, protocol_sha256: str | None,
    recording_configuration: dict[str, object],
) -> dict[str, object]:
    project = project.model_copy(update={
        "settings": project.settings.model_copy(update={
            "recording": ProjectRecordingSettings.model_validate(recording_configuration),
        }),
    })
    config = export_project_config(project, project_root)
    protocol_sha256 = protocol_sha256 or protocol_fingerprint(project, project_root)
    config.toolbox = config.toolbox.model_copy(update={"protocol_sha256": protocol_sha256})
    try:
        profile = load_settings(project_root).profile
    except SharingStorageError:
        logging.getLogger(__name__).warning(
            "toolbox_handoff_sharing_settings_invalid: Review Data Sharing settings; "
            "local recording identity is retained.",
        )
        return config.model_dump(mode="json")
    if profile is not None and profile.protocol_sha256 == protocol_sha256:
        try:
            validate_library_scope(project_root, profile)
        except DataSharingError:
            logging.getLogger(__name__).warning(
                "toolbox_handoff_enrollment_scope_mismatch: Reconnect Data Sharing "
                "for the installed Library version; local recording identity is retained.",
            )
        else:
            config.toolbox = config.toolbox.model_copy(update={
                "experiment_id": profile.experiment_id,
                "experiment_version": profile.experiment_version,
                "study_id": profile.project_id,
            })
    return config.model_dump(mode="json")


class DocumentRuntimeMixin:
    """Validation, compilation, preflight, and launch methods for `ProjectDocument`."""

    if TYPE_CHECKING:
        from fpvs_studio.core.study_versions import ProtocolDraft

        _project: ProjectFile
        _project_root: Path
        _session_export_mode: str
        _last_session_plan: SessionPlan | None
        session_plan_changed: Any

        @property
        def experiment_test_mode_enabled(self) -> bool: ...
        @property
        def attentional_blink_pilot_mode_enabled(self) -> bool: ...
        @property
        def local_testing_enabled(self) -> bool: ...
        @property
        def recording_configuration(self) -> dict[str, object]: ...
        @property
        def uses_default_recording_configuration(self) -> bool: ...

        def ensure_unused_session_seed_for_launch(self) -> int: ...
        def prepare_protocol_change(
            self, project: ProjectFile, *, include_run_observations: bool = True,
        ) -> ProtocolDraft: ...
        def _save_protocol(self, project: ProjectFile) -> None: ...
        def refresh_participant_summary_if_stale(self) -> Path | None: ...
        def prepare_participant_randomization(
            self, participant_number: str, participant_session_number: int | None,
        ) -> RandomizationSeeds | None: ...
        def finish_participant_randomization(
            self, *, participant_number: str | None = None,
            resolved_seeds: RandomizationSeeds | None = None,
        ) -> None: ...

    def recording_launch_options(self) -> dict[str, object]:
        """Resolve the effective recording device into runtime-only launch options."""

        return {
            **self.recording_configuration,
            "serial_enabled": not self.local_testing_enabled,
            "serial_port": self._project.settings.triggers.serial_port,
            "experiment_test_mode": self.experiment_test_mode_enabled,
            "pilot_mode": self.attentional_blink_pilot_mode_enabled,
        }

    def recording_setup_summary(self) -> str:
        """Describe effective output before either Home or Run starts a launch."""

        options = self.recording_launch_options()
        try:
            backend = validate_recording_configuration(options)
            label = recording_backend_label(options)
        except ValueError:
            return "Recording Setup required before recording."
        if backend == "unicorn_udp":
            return f"{label} — Recorder check before launch"
        return label

    def needs_project_brainproducts_setup(self) -> bool:
        """Require project-specific EEG timing before the first normal launch."""
        if sys.platform == "darwin" or self.local_testing_enabled:
            return False
        options = self.recording_configuration
        backend = options["recording_backend"]
        if backend not in ("brainproducts_triggerbox", "brainproducts_parallel"):
            return False
        return (
            self.uses_default_recording_configuration
            or options["brainproducts_sampling_rate_hz"] is None
            or (
                backend == "brainproducts_triggerbox" and options["brainproducts_amplifier"] is None
            )
        )

    def validate_recording_launch(self) -> str:
        """Validate local settings without probing vendor software on the GUI thread.

        The launch worker checks Recorder readiness before the runtime reserves a
        visit or opens participant presentation. Validation status is informational.
        """

        if sys.platform == "darwin" and (
            getattr(sys, "frozen", False) or not self.local_testing_enabled
        ):
            raise DocumentError(
                "macOS source supports local tests only. Enable Experiment Test Mode "
                "in Settings (or Pilot Study Mode for Attentional Blink). "
                "Run EEG acquisition on the Windows lab PC."
            )
        try:
            backend = validate_recording_configuration(self.recording_launch_options())
        except ValueError as exc:
            raise DocumentError(str(exc)) from exc
        if (backend in ("brainproducts_triggerbox", "brainproducts_parallel")
                and self.uses_default_recording_configuration):
            raise DocumentError(
                "Confirm this project's Brain Products amplifier and Recorder sampling rate "
                "in Recording Setup before launching."
            )
        return backend

    def validation_report(self, *, refresh_hz: float) -> ProjectValidationReport:
        """Validate the current project at a specific compile refresh rate."""

        return validate_project(self._project, refresh_hz=refresh_hz)

    def local_display_can_resolve_validation(self) -> bool:
        """Allow Mac calibration only when refresh alone can resolve validation.

        Readiness uses the saved lab rate, while Mac Test/Pilot confirms the local
        rate at launch. These inexpensive model-only checks retain every structural
        validator; the confirmed display still has to pass compilation/preflight.
        """
        if (sys.platform != "darwin" or getattr(sys, "frozen", False)
                or not self.local_testing_enabled):
            return False
        for rate in APPROVED_MONITOR_REFRESH_RATES_HZ:
            report = validate_project(self._project, refresh_hz=rate)
            if report.is_valid and not any(
                issue.severity == ValidationSeverity.WARNING
                and issue.location == "settings.protocol.base_hz"
                for issue in report.issues
            ):
                return True
        return False

    def fixation_guidance(self, *, refresh_hz: float) -> list[ConditionFixationGuidance]:
        """Return condition-level fixation guidance at a specific refresh rate."""

        return condition_fixation_guidance(self._project, refresh_hz=refresh_hz)

    def compile_session(
        self,
        *,
        refresh_hz: float,
        condition_ids: Sequence[str] | None = None,
        resolved_seeds: RandomizationSeeds | None = None,
        local_display: DisplaySettings | None = None,
    ) -> SessionPlan:
        """Compile the current project into a session plan."""

        self.ensure_unused_session_seed_for_launch()
        project = self._project
        if local_display is not None:
            if not self.local_testing_enabled:
                raise DocumentError("Local display calibration requires Test or Pilot mode.")
            project = self._project.model_copy(deep=True)
            project.settings.display = local_display.model_copy(deep=True)
        report = (
            self.validation_report(refresh_hz=refresh_hz)
            if local_display is None else validate_project(project, refresh_hz=refresh_hz)
        )
        if not report.is_valid:
            raise DocumentError(format_validation_report(report))
        try:
            session_plan = compile_session_plan(
                project,
                refresh_hz=refresh_hz,
                project_root=self._project_root,
                condition_ids=(list(condition_ids) if condition_ids is not None else None),
                resolved_seeds=resolved_seeds,
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

        session_plan = self.prepare_session_launch(
            refresh_hz=refresh_hz,
            engine_name=engine_name,
            decode_image_assets=True,
        )
        return session_plan

    def prepare_session_launch(
        self,
        *,
        refresh_hz: float,
        engine_name: str = EngineName.PSYCHOPY.value,
        decode_image_assets: bool = False,
        resolved_seeds: RandomizationSeeds | None = None,
    ) -> SessionPlan:
        """Compile and preflight the current session launch."""

        session_plan = self.compile_session(refresh_hz=refresh_hz, resolved_seeds=resolved_seeds)
        self.preflight_compiled_session(
            session_plan,
            engine_name=engine_name,
            decode_image_assets=decode_image_assets,
        )
        return session_plan

    def preflight_compiled_session(
        self,
        session_plan: SessionPlan,
        *,
        engine_name: str = EngineName.PSYCHOPY.value,
        decode_image_assets: bool = False,
    ) -> None:
        """Preflight an already-compiled session plan."""

        try:
            self.validate_recording_launch()
            engine = _document_dependency("create_engine")(engine_name)
            preflight_session_plan = _document_dependency("preflight_session_plan")
            if decode_image_assets:
                preflight_session_plan(
                    self._project_root,
                    session_plan,
                    engine=engine,
                    decode_image_assets=True,
                )
            else:
                preflight_session_plan(
                    self._project_root,
                    session_plan,
                    engine=engine,
                )
        except Exception as exc:
            raise DocumentError(str(exc)) from exc

    def check_collection_open(self) -> None:
        from fpvs_studio.runtime.launcher import check_research_collection_open

        check_research_collection_open(self._project_root, local_testing=self.local_testing_enabled)

    def launch_compiled_session(
        self,
        session_plan: SessionPlan,
        *,
        participant_number: str,
        participant_metadata: ParticipantMetadata | None = None,
        participant_session_number: int | None = None,
        display_index: int | None,
        display_device_name: str | None = None,
        fullscreen: bool = True,
        engine_name: str = EngineName.PSYCHOPY.value,
        recording_operator_confirmed: bool = False,
        recording_association: str | None = None,
        recorder_version: str | None = None,
        replacement_source: SessionPlan | None = None,
        frozen_record: InterruptedCondition | None = None,
    ) -> LaunchSummary:
        """Launch an already-prepared session plan through the runtime boundary."""

        try:
            if (
                not self.experiment_test_mode_enabled
                and not self._project.settings.allow_repeated_participant_sessions
            ):
                if participant_session_number not in (None, 1):
                    raise DocumentError(
                        "Repeat participant sessions are disabled. Enable Allow repeat "
                        "participant sessions in Setup > Project before launching again."
                    )
                participant_session_number = 1
            self.validate_recording_launch()
            revision = None
            verified_digest = None
            if replacement_source is not None and replacement_source is not self._last_session_plan:
                raise DocumentError("The replacement protocol changed. Prepare the re-run again.")
            frozen_version_id = frozen_record.protocol_version_id if frozen_record else None
            verified_setup = (
                session_plan is self._last_session_plan
                or replacement_source is not None
                or frozen_version_id is not None
            )
            if not self.local_testing_enabled and (verified_setup or frozen_record is not None):
                from fpvs_studio.core.data_sharing import protocol_fingerprint_with_assets
                from fpvs_studio.core.run_stimulus_identity import verify_run_stimuli
                from fpvs_studio.core.study_versions import current_version, ensure_working_setup

                if not (self._project_root / "project.json").is_file():
                    self._save_protocol(self._project)
                ensure_working_setup(self._project_root)
                draft = self.prepare_protocol_change(self._project, include_run_observations=False)
                if draft.changes:
                    raise DocumentError(
                        "The protocol or stimuli changed. Review and save the experiment "
                        "before collecting data."
                    )
                revision = current_version(self._project_root)
                if revision is None or revision.version_id != draft.previous:
                    raise DocumentError("The study changed during launch. Review and launch again.")
                if frozen_version_id is not None and revision.version_id != frozen_version_id:
                    raise DocumentError(
                        "The original protocol has changed. Reopen Interrupted Sessions "
                        "to prepare a replacement using the current setup."
                    )
                verified_digest, media = protocol_fingerprint_with_assets(
                    self._project, self._project_root
                )
                verify_run_stimuli(self._project_root, revision.version_id, media)
                if not verified_setup:
                    revision = None  # An older schedule has no recorded version to attribute.
            recording_configuration = self.recording_configuration
            trigger_settings = self._project.settings.triggers
            sharing_protocol = (
                _sharing_protocol(self._project, self._project_root, verified_digest)
                if verified_setup else None
            )
            launch_kwargs: _SessionLaunchArguments = {
                "participant_number": participant_number,
                "launch_settings": LaunchSettings(
                    engine_name=engine_name,
                    fullscreen=fullscreen,
                    display_index=display_index,
                    display_device_name=display_device_name,
                    # Persisted legacy flags cannot disable EEG recording output.
                    serial_enabled=not self.local_testing_enabled,
                    recording_backend=cast(
                        str | None, recording_configuration.get("recording_backend"),
                    ),
                    electrode_montage=cast(
                        str | None, recording_configuration.get("electrode_montage"),
                    ),
                    unicorn_udp_port=cast(
                        int, recording_configuration.get("unicorn_udp_port", 1000),
                    ),
                    brainproducts_serial_port=cast(
                        str, recording_configuration.get("brainproducts_serial_port", "COM3"),
                    ),
                    brainproducts_parallel_address=cast(
                        int | None, recording_configuration.get("brainproducts_parallel_address"),
                    ),
                    brainproducts_pulse_width_ms=cast(
                        int, recording_configuration.get("brainproducts_pulse_width_ms", 10),
                    ),
                    brainproducts_amplifier=cast(
                        str | None, recording_configuration.get("brainproducts_amplifier"),
                    ),
                    brainproducts_sampling_rate_hz=cast(
                        int | None,
                        recording_configuration.get("brainproducts_sampling_rate_hz"),
                    ),
                    recording_selection_source=(
                        "local_settings" if self.uses_default_recording_configuration
                        else "project_settings"
                    ),
                    recording_operator_confirmed=recording_operator_confirmed,
                    recording_association=recording_association,
                    recorder_version=recorder_version,
                    experiment_test_mode=self.experiment_test_mode_enabled,
                    serial_port=trigger_settings.serial_port,
                    serial_baudrate=trigger_settings.baudrate,
                    serial_pulse_width_ms=trigger_settings.pulse_width_ms,
                    serial_reset_code=trigger_settings.reset_code,
                    serial_reset_delay_ms=trigger_settings.reset_delay_ms,
                    verify_refresh_rate=(
                        sys.platform == "darwin" or not self.local_testing_enabled
                    ),
                    verify_graphics_memory=not self.local_testing_enabled,
                    pilot_mode=self.attentional_blink_pilot_mode_enabled,
                    completion_screen_seconds=0.5,
                    export_mode=self._session_export_mode,
                    sharing_protocol_sha256=sharing_protocol,
                    studio_protocol_version_id=revision.version_id if revision else None,
                    studio_protocol_change_reason=revision.reason if revision else None,
                    toolbox_handoff_config=(
                        _toolbox_handoff_config(
                            self._project,
                            self._project_root,
                            verified_digest or sharing_protocol,
                            recording_configuration,
                        )
                        if verified_setup else None
                    ),
                ),
            }
            if participant_metadata is not None:
                launch_kwargs["participant_metadata"] = participant_metadata
            if participant_session_number is not None:
                launch_kwargs["participant_session_number"] = participant_session_number
            launch = _document_dependency("launch_session")
            if sys.platform == "darwin":
                from fpvs_studio.runtime.macos_session_process import launch_macos_test_session

                launch = launch_macos_test_session
            summary: LaunchSummary = launch(
                self._project_root,
                session_plan,
                **launch_kwargs,
            )
            self.refresh_participant_summary_if_stale()
        except Exception as exc:
            raise DocumentError(str(exc)) from exc
        return summary

    def launch_session(
        self,
        *,
        refresh_hz: float,
        participant_number: str,
        participant_metadata: ParticipantMetadata | None = None,
        participant_session_number: int | None = None,
        display_index: int | None,
        display_device_name: str | None = None,
        fullscreen: bool = True,
        engine_name: str = EngineName.PSYCHOPY.value,
    ) -> tuple[SessionPlan, LaunchSummary]:
        """Compile and launch the current session through the runtime boundary."""

        resolved_seeds = self.prepare_participant_randomization(
            participant_number, participant_session_number,
        )
        session_plan = self.prepare_session_launch(
            refresh_hz=refresh_hz,
            engine_name=engine_name,
            resolved_seeds=resolved_seeds,
        )
        summary = self.launch_compiled_session(
            session_plan,
            participant_number=participant_number,
            participant_metadata=participant_metadata,
            participant_session_number=participant_session_number,
            display_index=display_index,
            display_device_name=display_device_name,
            fullscreen=fullscreen,
            engine_name=engine_name,
        )
        if resolved_seeds is not None:
            self.finish_participant_randomization(
                participant_number=participant_number, resolved_seeds=resolved_seeds,
            )
        return session_plan, summary

    def next_participant_session_number(self, participant_number: str) -> int:
        """Preview the next session using runtime history; call from a GUI worker."""

        return resolve_next_participant_session_number(self._project_root, participant_number)

    def has_completed_session_for_participant(self, participant_number: str) -> bool:
        """Return whether this project already contains completed runs for a participant."""

        return bool(
            find_completed_sessions_for_participant(
                self._project_root,
                participant_number,
            )
        )
