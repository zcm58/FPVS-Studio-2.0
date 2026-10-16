"""Local recording selection and durable acquisition evidence with fake output only."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from tests.unit.runtime_launcher_helpers import StubEngine

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.execution import AcquisitionEvidence, ParticipantMetadata
from fpvs_studio.core.models import ProjectRecordingSettings
from fpvs_studio.core.project_config import (
    ProjectConfigError,
    completed_toolbox_config,
    export_project_config,
    read_project_config,
)
from fpvs_studio.core.run_spec import TriggerEvent
from fpvs_studio.core.serialization import read_json_file
from fpvs_studio.runtime import launcher, triggers
from fpvs_studio.runtime.acquisition_evidence import AcquisitionEvidenceRecorder
from fpvs_studio.runtime.display_mode import NativeDisplayMode
from fpvs_studio.runtime.launcher import (
    LaunchSettings,
    LaunchSettingsError,
    launch_run,
    launch_session,
)
from fpvs_studio.runtime.preflight import PreflightError
from fpvs_studio.runtime.recording import (
    RecordingConfigurationError,
    recording_snapshot,
    validate_production_recording,
    validate_recording_configuration,
    validate_recording_trigger_schedule,
)
from fpvs_studio.runtime.run_worker import RuntimeWorker
from fpvs_studio.runtime.unicorn_recorder import RecorderReadinessError
from fpvs_studio.triggers.null_backend import NullBackend


class FakeUnicorn(NullBackend):
    """In-memory transport; never creates a socket or accesses vendor software."""

    def __init__(self, *, fail_send=False, fail_connect=False, fail_close=False):
        self.fail_send = fail_send
        self.fail_connect = fail_connect
        self.fail_close = fail_close
        self.count = 0
        self.closed = False

    @property
    def backend_name(self):
        return "unicorn_udp"

    @property
    def emits_external_markers(self):
        return True

    def connect(self):
        if self.fail_connect:
            raise OSError("socket unavailable")

    def send_trigger(self, code, **kwargs):
        self.count += 1
        if self.fail_send and self.count == 2:
            raise BlockingIOError("would block")

    def close(self):
        self.closed = True
        if self.fail_close:
            raise OSError("socket cleanup failed")


class FakeSerial(FakeUnicorn):
    @property
    def backend_name(self):
        return "serial"


class FakeTriggerBox(FakeUnicorn):
    @property
    def backend_name(self):
        return "brainproducts_triggerbox"


@pytest.fixture
def execution(sample_project, sample_project_root):
    plan = compile_session_plan(
        sample_project, project_root=sample_project_root, refresh_hz=60.0, random_seed=12,
    )
    return sample_project_root, plan


def _fake_output(monkeypatch, backend):
    monkeypatch.setattr(triggers, "UnicornUDPBackend", lambda port: backend)


def _execute(root, plan, worker, *, export_mode="compact", visit=1, metadata=None, **options):
    return worker.execute_session(
        root, plan, root / "runs" / f"P007_session{visit:02d}",
        participant_number="007", participant_session_number=visit,
        participant_metadata=metadata,
        relative_output_dir=f"runs/P007_session{visit:02d}",
        runtime_options={
            "recording_backend": "unicorn_udp", "unicorn_udp_port": 1000,
            "recording_operator_confirmed": True,
            "recording_association": f"007-visit-{visit}",
            "export_mode": export_mode, **options,
        },
    )


def _evidence(root):
    paths = list((root / "logs" / "acquisition").glob("*.acquisition-v1.json"))
    assert len(paths) == 1
    return read_json_file(paths[0], AcquisitionEvidence)


def test_selection_precedence_allows_explicit_unicorn_with_pending_validation():
    assert validate_production_recording({}) == "serial"
    assert validate_production_recording({
        "recording_backend": "serial", "serial_enabled": False,
    }) == "serial"
    with pytest.raises(RecordingConfigurationError, match="Null output"):
        validate_production_recording({"serial_enabled": False})
    options = {"recording_backend": "unicorn_udp", "serial_enabled": False}
    assert validate_production_recording(options) == "unicorn_udp"
    snapshot = recording_snapshot(options)
    assert snapshot.receiver_validation == "pending"
    assert snapshot.recorded_marker_integrity == "unknown"
    assert snapshot.physical_timing == "uncharacterized"
    assert not snapshot.operator_confirmed_raw_bdf_recording


@pytest.mark.parametrize("mode", ["experiment_test_mode", "pilot_mode"])
def test_test_and_pilot_always_null_even_when_serial_enabled(mode):
    for selected in (None, "serial", "unicorn_udp", "biosemi_active_three",
                     "brainproducts_triggerbox"):
        assert validate_production_recording({
            "recording_backend": selected, "serial_enabled": True, mode: True,
        }) == "null"


@pytest.mark.parametrize("port", [True, False, 0, -1, 65536, 1000.5, "1000", None])
def test_invalid_udp_port_never_normalizes_to_default(port):
    with pytest.raises(RecordingConfigurationError, match="UDP port"):
        validate_recording_configuration({
            "recording_backend": "unicorn_udp", "unicorn_udp_port": port,
            "experiment_test_mode": True,
        })


@pytest.mark.parametrize("selected", ["", "null", "future", 1, False, []])
def test_invalid_saved_choice_is_actionable_even_in_test(selected):
    with pytest.raises(RecordingConfigurationError, match="Settings > Recording"):
        validate_production_recording({"recording_backend": selected, "pilot_mode": True})


def _launch_at_boundary(root, plan, launch_kind, settings):
    if launch_kind == "run":
        return launch_run(
            root, plan.ordered_entries()[0].run_spec,
            participant_number="007", launch_settings=settings,
        )
    return launch_session(root, plan, participant_number="007", launch_settings=settings)


@pytest.mark.parametrize("launch_kind", ["run", "session"])
def test_ready_unicorn_launches_through_preflight_and_worker(
    execution, monkeypatch, launch_kind,
):
    root, plan = execution
    captures = {}
    backend = FakeUnicorn()
    _fake_output(monkeypatch, backend)
    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_native_display_mode",
        lambda: NativeDisplayMode(
            platform_name="Windows", display_name=r"\\.\DISPLAY1", refresh_hz=60.0,
            source_name="QueryDisplayConfig", exact_refresh=True, mode_reference="60/1",
        ),
    )
    engine = Mock(return_value=StubEngine(captures))
    preflight_name = "preflight_run_spec" if launch_kind == "run" else "preflight_session_plan"
    preflight = Mock(wraps=getattr(launcher, preflight_name))
    reserve = Mock(wraps=launcher.reserve_participant_session)
    worker = Mock(wraps=RuntimeWorker)
    ready = Mock()
    calls = Mock()
    calls.attach_mock(ready, "readiness")
    calls.attach_mock(engine, "engine")
    calls.attach_mock(preflight, "preflight")
    calls.attach_mock(reserve, "reserve")
    calls.attach_mock(worker, "worker")
    monkeypatch.setattr(launcher, "require_unicorn_recorder_recording", ready)
    monkeypatch.setattr(launcher, "create_engine", engine)
    monkeypatch.setattr(launcher, preflight_name, preflight)
    monkeypatch.setattr(launcher, "reserve_participant_session", reserve)
    monkeypatch.setattr(launcher, "RuntimeWorker", worker)

    summary = _launch_at_boundary(
        root, plan, launch_kind,
        LaunchSettings(recording_backend="unicorn_udp", serial_enabled=False),
    )

    expected_calls = ["readiness", "engine", "preflight"]
    if launch_kind == "session":
        expected_calls.append("reserve")
        assert summary.participant_session_number == 1
    expected_calls.append("worker")
    assert [call[0] for call in calls.mock_calls] == expected_calls
    assert not summary.aborted
    expected_specs = [entry.run_spec for entry in plan.ordered_entries()]
    if launch_kind == "run":
        expected_specs = expected_specs[:1]
    assert captures["run_ids"] == [spec.run_id for spec in expected_specs]
    assert backend.count == sum(len(spec.trigger_events) for spec in expected_specs)
    assert backend.closed
    evidence = _evidence(root)
    assert evidence.recording.effective_backend == "unicorn_udp"
    assert evidence.recording.receiver_validation == "pending"
    assert evidence.state == "completed"


@pytest.mark.parametrize("launch_kind", ["run", "session"])
def test_ready_unicorn_still_requires_preflight_before_reservation_and_output(
    execution, monkeypatch, launch_kind,
):
    root, plan = execution
    ready = Mock()
    preflight = Mock(side_effect=PreflightError("display does not match compiled timing"))
    reserve = Mock(side_effect=AssertionError("visit must not be reserved"))
    worker = Mock(side_effect=AssertionError("worker must not be created"))
    monkeypatch.setattr(launcher, "require_unicorn_recorder_recording", ready)
    monkeypatch.setattr(launcher, "create_engine", lambda _name: StubEngine({}))
    monkeypatch.setattr(
        launcher,
        "preflight_run_spec" if launch_kind == "run" else "preflight_session_plan",
        preflight,
    )
    monkeypatch.setattr(launcher, "reserve_participant_session", reserve)
    monkeypatch.setattr(launcher, "RuntimeWorker", worker)

    with pytest.raises(PreflightError, match="display does not match compiled timing"):
        _launch_at_boundary(
            root, plan, launch_kind, LaunchSettings(recording_backend="unicorn_udp"),
        )

    ready.assert_called_once_with()
    preflight.assert_called_once()
    reserve.assert_not_called()
    worker.assert_not_called()
    assert not (root / "runs").exists()
    assert not (root / "logs" / "acquisition").exists()


@pytest.mark.parametrize("launch_kind", ["run", "session"])
@pytest.mark.parametrize("state", ["closed", "idle", "unknown", "timeout"])
def test_recorder_readiness_failure_precedes_engine_reservation_and_output(
    execution, monkeypatch, launch_kind, state,
):
    root, plan = execution
    ready = Mock(side_effect=RecorderReadinessError(f"Recorder is {state}"))
    engine = Mock(side_effect=AssertionError("engine must not be created"))
    reserve = Mock(side_effect=AssertionError("visit must not be reserved"))
    monkeypatch.setattr(launcher, "require_unicorn_recorder_recording", ready)
    monkeypatch.setattr(launcher, "create_engine", engine)
    monkeypatch.setattr(launcher, "reserve_participant_session", reserve)
    with pytest.raises(RecorderReadinessError, match=f"Recorder is {state}"):
        _launch_at_boundary(
            root, plan, launch_kind, LaunchSettings(recording_backend="unicorn_udp"),
        )
    ready.assert_called_once_with()
    engine.assert_not_called()
    reserve.assert_not_called()
    assert not (root / "runs").exists()
    assert not (root / "logs" / "acquisition").exists()


@pytest.mark.parametrize("launch_kind", ["run", "session"])
@pytest.mark.parametrize("options", [
    {},
    {"recording_backend": "serial"},
    {"recording_backend": "unicorn_udp", "experiment_test_mode": True},
    {"recording_backend": "unicorn_udp", "pilot_mode": True},
])
def test_other_recording_modes_do_not_probe_recorder(
    execution, monkeypatch, launch_kind, options,
):
    root, plan = execution
    ready = Mock(side_effect=AssertionError("Recorder must not be queried"))
    engine = Mock(side_effect=RuntimeError("engine boundary reached"))
    monkeypatch.setattr(launcher, "require_unicorn_recorder_recording", ready)
    monkeypatch.setattr(launcher, "create_engine", engine)
    with pytest.raises(RuntimeError, match="engine boundary reached"):
        _launch_at_boundary(root, plan, launch_kind, LaunchSettings(**options))
    ready.assert_not_called()
    engine.assert_called_once()


@pytest.mark.parametrize("launch_kind", ["run", "session"])
def test_invalid_recording_configuration_precedes_recorder_probe(
    execution, monkeypatch, launch_kind,
):
    root, plan = execution
    ready = Mock(side_effect=AssertionError("Recorder must not be queried"))
    engine = Mock(side_effect=AssertionError("engine must not be created"))
    monkeypatch.setattr(launcher, "require_unicorn_recorder_recording", ready)
    monkeypatch.setattr(launcher, "create_engine", engine)
    with pytest.raises(LaunchSettingsError, match="UDP port"):
        _launch_at_boundary(
            root, plan, launch_kind,
            LaunchSettings(recording_backend="unicorn_udp", unicorn_udp_port=0),
        )
    ready.assert_not_called()
    engine.assert_not_called()


@pytest.mark.parametrize("export_mode", ["compact", "full"])
def test_evidence_survives_finalization_and_keeps_actual_attempt_order(
    execution, monkeypatch, export_mode,
):
    root, plan = execution
    backend = FakeUnicorn()
    _fake_output(monkeypatch, backend)
    summary = _execute(root, plan, RuntimeWorker(StubEngine({})), export_mode=export_mode)
    evidence = _evidence(root)
    assert evidence.state == "completed"
    assert evidence.participant_number == "007"
    assert evidence.participant_session_number == 1
    assert evidence.session_id == plan.session_id
    assert evidence.recording.recording_association == "007-visit-1"
    assert evidence.recording.operator_confirmed_raw_bdf_recording
    assert evidence.recording.acquisition_status == "unknown"
    assert evidence.recording.recorded_marker_integrity == "unknown"
    assert evidence.recording.physical_timing == "uncharacterized"
    assert evidence.recording.recorder_version is None
    assert evidence.recording.receiver_validation == "pending"
    assert evidence.callback_time_units == "seconds"
    assert "not EEG time" in evidence.callback_time_origin
    assert "abrupt process loss" in evidence.persistence_boundary
    for actual, entry in zip(evidence.runs, plan.ordered_entries(), strict=True):
        assert actual.state == "completed"
        assert [(r.code, r.label, r.frame_index) for r in actual.attempted_events] == [
            (r.code, r.label, r.frame_index) for r in entry.run_spec.trigger_events
        ]
        assert all(r.status == "sent" for r in actual.attempted_events)
    assert summary.runtime_metadata.recording == evidence.recording
    assert summary.run_results[0].runtime_metadata.recording == evidence.recording
    assert not list((root / "logs" / ".task-response-checkpoints").glob("*.session.json"))
    assert (root / "runs").exists() == (export_mode == "full")
    assert backend.closed


def test_failed_send_is_evidence_not_a_success(execution, monkeypatch):
    root, plan = execution
    _fake_output(monkeypatch, FakeUnicorn(fail_send=True))
    summary = _execute(root, plan, RuntimeWorker(StubEngine({})))
    evidence = _evidence(root)
    assert summary.aborted and evidence.state == "aborted"
    assert [attempt.status for attempt in evidence.runs[0].attempted_events] == ["sent", "error"]
    assert evidence.runs[0].attempted_events[-1].message == "would block"
    assert all(run.state == "not_started" for run in evidence.runs[1:])


@pytest.mark.parametrize("failure", ["connect", "cleanup", "presentation", "export"])
def test_partial_evidence_survives_failure(execution, monkeypatch, failure):
    root, plan = execution
    backend = FakeUnicorn(fail_connect=failure == "connect", fail_close=failure == "cleanup")
    _fake_output(monkeypatch, backend)
    engine = StubEngine({})
    if failure == "presentation":
        original = engine.run_condition

        def fail_after_markers(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("presentation failed")

        monkeypatch.setattr(engine, "run_condition", fail_after_markers)
    if failure == "export":
        monkeypatch.setattr(
            "fpvs_studio.runtime.run_worker.write_participant_summary",
            Mock(side_effect=PermissionError("workbook locked")),
        )
    with pytest.raises(Exception, match={
        "connect": "socket unavailable", "cleanup": "socket cleanup failed",
        "presentation": "presentation failed", "export": "workbook locked",
    }[failure]):
        _execute(root, plan, RuntimeWorker(engine))
    evidence = _evidence(root)
    assert evidence.state == "interrupted"
    assert bool(evidence.runs[0].attempted_events) == (failure != "connect")
    if failure == "export":
        assert evidence.export_error == "workbook locked"
    assert backend.closed


def test_cancel_before_presentation_preserves_association_without_attempts(execution):
    root, plan = execution
    summary = _execute(
        root, plan, RuntimeWorker(StubEngine({"abort_on_transition": True})),
        experiment_test_mode=True,
    )
    evidence = _evidence(root)
    assert summary.aborted and evidence.state == "aborted"
    assert evidence.recording.effective_backend == "null"
    assert not evidence.recording.operator_confirmed_raw_bdf_recording
    assert evidence.recording.recording_association == "007-visit-1"
    assert all(not run.attempted_events for run in evidence.runs)


def test_visits_and_repeated_direct_execution_never_overwrite_evidence(execution):
    root, plan = execution
    for visit in (1, 2, 2):
        _execute(root, plan, RuntimeWorker(StubEngine({})), visit=visit, pilot_mode=True)
    paths = list((root / "logs" / "acquisition").glob("*.acquisition-v1.json"))
    assert len(paths) == 3
    evidence = [read_json_file(path, AcquisitionEvidence) for path in paths]
    assert {item.participant_session_number for item in evidence} == {1, 2}
    assert all(not run.attempted_events for item in evidence for run in item.runs)


def test_single_run_cleanup_failure_keeps_marker_attempts(execution, monkeypatch):
    root, plan = execution
    _fake_output(monkeypatch, FakeUnicorn(fail_close=True))
    spec = plan.ordered_entries()[0].run_spec
    with pytest.raises(OSError, match="socket cleanup failed"):
        RuntimeWorker(StubEngine({})).execute(
            root, spec, root / "runs" / spec.run_id, participant_number="007",
            runtime_options={"recording_backend": "unicorn_udp"},
        )
    evidence = _evidence(root)
    assert evidence.state == "interrupted"
    assert evidence.runs[0].attempted_events


def test_evidence_write_failure_precedes_output(execution, monkeypatch):
    root, plan = execution
    backend = FakeUnicorn()
    _fake_output(monkeypatch, backend)
    monkeypatch.setattr(
        "fpvs_studio.runtime.acquisition_evidence.write_json_file",
        Mock(side_effect=PermissionError("evidence folder is read-only")),
    )
    with pytest.raises(PermissionError, match="evidence folder is read-only"):
        _execute(root, plan, RuntimeWorker(StubEngine({})))
    assert backend.count == 0
    assert not backend.closed  # The backend has not even been created/connected.


def test_legacy_snapshot_does_not_claim_vendor_recording():
    snapshot = recording_snapshot({"serial_port": "COM9"})
    assert snapshot.selected_backend == snapshot.effective_backend == "serial"
    assert snapshot.selection_source == "legacy_project"
    assert snapshot.serial_port == "COM9"
    assert not snapshot.operator_confirmed_raw_bdf_recording


def test_empty_evidence_uses_session_project_identity(tmp_path):
    recorder = AcquisitionEvidenceRecorder(
        tmp_path, [], project_id="empty-project", participant_number="007",
        runtime_options={"recording_backend": "unicorn_udp", "pilot_mode": True},
    )
    recorder.finish(abort_reason="Session cancelled before a condition.")
    evidence = _evidence(tmp_path)
    assert evidence.project_id == "empty-project"
    assert evidence.runs == []
    assert evidence.state == "aborted"


def test_evidence_path_rejects_linked_logs_escape(execution, tmp_path):
    root, plan = execution
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "logs").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Directory symlinks unavailable: {exc}")
    with pytest.raises(ValueError, match="escapes the project root"):
        AcquisitionEvidenceRecorder(
            root, [plan.ordered_entries()[0].run_spec],
            project_id=plan.project_id,
            runtime_options={"recording_backend": "unicorn_udp"}, participant_number="007",
        )
    assert list(outside.iterdir()) == []


def test_project_recording_selection_is_identified_in_export_snapshot():
    snapshot = recording_snapshot({
        "recording_backend": "unicorn_udp", "unicorn_udp_port": 2345,
        "recording_selection_source": "project_settings",
    })
    assert snapshot.selection_source == "project_settings"
    assert snapshot.udp_port == 2345


def test_triggerbox_factory_uses_project_endpoint_and_fixed_protocol(monkeypatch):
    output = FakeTriggerBox()
    adapter = Mock(return_value=output)
    monkeypatch.setattr(triggers, "BrainProductsTriggerBoxBackend", adapter)
    options = {
        "recording_backend": "brainproducts_triggerbox",
        "brainproducts_serial_port": " COM9 ", "brainproducts_pulse_width_ms": 20,
        "serial_port": "COM99", "serial_baudrate": 9600, "serial_enabled": False,
    }
    backend, _ = triggers.build_trigger_backend(options)
    adapter.assert_called_once_with(port="COM9", pulse_width_ms=20)
    assert backend.backend_name == "brainproducts_triggerbox"
    snapshot = recording_snapshot(options)
    assert snapshot.serial_port == "COM9"
    assert snapshot.serial_baudrate == 2_000_000
    assert snapshot.trigger_pulse_width_ms == 20
    assert snapshot.acquisition_profile is None


@pytest.mark.parametrize("mode", ["experiment_test_mode", "pilot_mode"])
def test_triggerbox_test_modes_never_construct_hardware(monkeypatch, mode):
    adapter = Mock(side_effect=AssertionError("hardware must not be created"))
    monkeypatch.setattr(triggers, "BrainProductsTriggerBoxBackend", adapter)
    options = {"recording_backend": "brainproducts_triggerbox", mode: True}
    backend, _ = triggers.build_trigger_backend(options)
    assert backend.backend_name == "null"
    snapshot = recording_snapshot(options)
    assert snapshot.selected_backend == "brainproducts_triggerbox"
    assert snapshot.serial_port is None
    adapter.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("brainproducts_serial_port", " "), ("brainproducts_serial_port", None),
    ("brainproducts_serial_port", 9), ("brainproducts_pulse_width_ms", True),
    ("brainproducts_pulse_width_ms", 0), ("brainproducts_pulse_width_ms", 1001),
    ("brainproducts_pulse_width_ms", "10"),
])
def test_invalid_triggerbox_configuration_rejected_even_in_test(field, value):
    with pytest.raises(RecordingConfigurationError, match="Brain Products"):
        validate_recording_configuration({
            "recording_backend": "brainproducts_triggerbox", "experiment_test_mode": True,
            field: value,
        })


def test_triggerbox_schedule_checks_high_and_low_intervals_including_frame_minus_one(execution):
    _, plan = execution
    spec = plan.ordered_entries()[0].run_spec
    spec = spec.model_copy(update={"trigger_events": [
        TriggerEvent(frame_index=-1, code=1, label="condition_start"),
        TriggerEvent(frame_index=0, code=55, label="distractor_onset"),
    ]})
    options = {"recording_backend": "brainproducts_triggerbox"}
    with pytest.raises(RecordingConfigurationError, match="frames -1 and 0"):
        validate_recording_trigger_schedule(spec, options)
    validate_recording_trigger_schedule(spec, {**options, "brainproducts_pulse_width_ms": 2})
    validate_recording_trigger_schedule(spec, {**options, "experiment_test_mode": True})


@pytest.mark.parametrize("launch_kind", ["run", "session"])
def test_triggerbox_impossible_schedule_fails_before_visit_or_output(
    execution, monkeypatch, launch_kind,
):
    root, plan = execution
    monkeypatch.setattr(launcher, "create_engine", lambda _name: StubEngine({}))
    reserve = Mock(side_effect=AssertionError("visit must not be reserved"))
    monkeypatch.setattr(launcher, "reserve_participant_session", reserve)
    adapter = Mock(side_effect=AssertionError("hardware must not be opened"))
    monkeypatch.setattr(triggers, "BrainProductsTriggerBoxBackend", adapter)
    with pytest.raises(PreflightError, match="TriggerBox needs more than"):
        _launch_at_boundary(root, plan, launch_kind, LaunchSettings(
            recording_backend="brainproducts_triggerbox", brainproducts_pulse_width_ms=1000,
            verify_refresh_rate=False,
        ))
    reserve.assert_not_called()
    adapter.assert_not_called()
    assert not (root / "logs" / "acquisition").exists()


def test_triggerbox_reset_failure_retains_interrupted_acquisition_without_completed_handoff(
    execution, sample_project, monkeypatch,
):
    root, plan = execution
    sample_project.settings.recording = ProjectRecordingSettings(
        recording_backend="brainproducts_triggerbox",
    )
    config = export_project_config(sample_project, root)
    output = FakeTriggerBox()
    output.reset = Mock(side_effect=OSError("zero write failed"))
    monkeypatch.setattr(triggers, "BrainProductsTriggerBoxBackend", lambda **_kwargs: output)
    summary = _execute(root, plan, RuntimeWorker(StubEngine({})),
                       recording_backend="brainproducts_triggerbox",
                       toolbox_handoff_config=config.model_dump(mode="json"))
    assert summary.aborted
    assert "pulse reset failed" in summary.abort_reason
    assert output.closed
    evidence = _evidence(root)
    assert evidence.state == "aborted"
    assert evidence.runs[0].attempted_events
    assert not list((root / "logs" / "acquisition").glob("*-completed.fpvsconfig"))


@pytest.mark.parametrize("export_mode", ["compact", "full"])
@pytest.mark.parametrize("backend", [
    "serial", "unicorn_udp", "biosemi_active_three", "brainproducts_triggerbox",
])
def test_completed_handoff_automatically_retains_hardware_identity_and_event_evidence(
    execution, sample_project, monkeypatch, export_mode, backend,
):
    root, plan = execution
    sample_project.settings.recording = ProjectRecordingSettings(recording_backend=backend)
    config = export_project_config(sample_project, root)
    output = FakeSerial() if backend in ("serial", "biosemi_active_three") else FakeUnicorn()
    if backend in ("serial", "biosemi_active_three"):
        monkeypatch.setattr(triggers, "SerialBackend", lambda *_args, **_kwargs: output)
    elif backend == "brainproducts_triggerbox":
        output = FakeTriggerBox()
        monkeypatch.setattr(triggers, "BrainProductsTriggerBoxBackend",
                            lambda **_kwargs: output)
    else:
        _fake_output(monkeypatch, output)
    summary = _execute(
        root, plan, RuntimeWorker(StubEngine({})), export_mode=export_mode,
        recording_backend=backend, toolbox_handoff_config=config.model_dump(mode="json"),
    )
    assert not summary.aborted
    evidence = _evidence(root)
    path = root / "logs" / "acquisition" / f"{evidence.execution_id}-completed.fpvsconfig"
    completed = read_project_config(path)
    assert completed.schema_version == config.schema_version
    assert completed.toolbox.acquisition_profile == evidence.acquisition_profile
    assert completed.recording.recording_backend == backend
    assert evidence.recording.selected_backend == backend
    if backend in ("biosemi_active_three", "brainproducts_triggerbox"):
        assert evidence.acquisition_profile is None
        assert evidence.recording.receiver_validation == "pending"
    assert completed.completed_session.execution_id == evidence.execution_id
    assert completed.completed_session.participant_number == "007"
    assert completed.completed_session.participant_session_number == 1
    assert completed.completed_session.acquisition_evidence == evidence
    assert [run.run_id for run in completed.completed_session.ordered_runs] == [
        entry.run_id for entry in plan.ordered_entries()
    ]
    assert all(run.attempted_events for run in evidence.runs)
    assert (root / "runs").exists() == (export_mode == "full")


@pytest.mark.parametrize("removed", [None, [], [" a1 ", "A1", "oz"]])
@pytest.mark.parametrize("export_mode", ["compact", "full"])
def test_completed_handoff_keeps_immutable_nullable_electrode_snapshot(
    execution, sample_project, monkeypatch, removed, export_mode,
):
    root, plan = execution
    config = export_project_config(sample_project, root)
    metadata = ParticipantMetadata(manual_removed_electrodes=removed)
    expected = None if removed is None else list(metadata.manual_removed_electrodes)
    monkeypatch.setattr(triggers, "SerialBackend", lambda *_args, **_kwargs: FakeSerial())
    original_open = StubEngine.open_session

    def open_session(engine, **kwargs):
        metadata.manual_removed_electrodes = ["C3"]
        sample_project.manual_removed_electrodes = {"007": ["B2"]}
        return original_open(engine, **kwargs)

    monkeypatch.setattr(StubEngine, "open_session", open_session)
    _execute(root, plan, RuntimeWorker(StubEngine({})), export_mode=export_mode,
             recording_backend="serial", metadata=metadata,
             toolbox_handoff_config=config.model_dump(mode="json"))
    evidence = _evidence(root)
    path = root / "logs" / "acquisition" / f"{evidence.execution_id}-completed.fpvsconfig"
    completed = read_project_config(path)
    assert json.loads(path.read_text(encoding="utf-8"))["completed_session"][
        "manual_removed_electrodes"
    ] == expected
    assert completed.completed_session.manual_removed_electrodes == expected
    assert completed.completed_session.execution_id == evidence.execution_id


def test_compact_cleanup_failure_retains_evidence_without_completed_handoff(
    execution, sample_project, monkeypatch,
):
    root, plan = execution
    sample_project.settings.recording = ProjectRecordingSettings(recording_backend="unicorn_udp")
    config = export_project_config(sample_project, root)
    _fake_output(monkeypatch, FakeUnicorn())
    unlink = Path.unlink
    failed_paths = []

    def fail_session_checkpoint_cleanup(path, *args, **kwargs):
        if path.parent.name == ".task-response-checkpoints" and path.name.endswith(".session.json"):
            failed_paths.append(path)
            raise PermissionError("session checkpoint locked")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_session_checkpoint_cleanup)
    with pytest.raises(PermissionError, match="session checkpoint locked"):
        _execute(root, plan, RuntimeWorker(StubEngine({})),
            toolbox_handoff_config=config.model_dump(mode="json"))
    evidence = _evidence(root)
    assert len(failed_paths) == 1 and failed_paths[0].exists()
    assert evidence.state == "interrupted"
    assert evidence.export_error == "session checkpoint locked"
    assert all(run.attempted_events for run in evidence.runs)
    assert not list((root / "logs" / "acquisition").glob("*-completed.fpvsconfig"))


def test_aborted_session_retains_evidence_without_completed_handoff(
    execution, sample_project, monkeypatch,
):
    root, plan = execution
    sample_project.settings.recording = ProjectRecordingSettings(recording_backend="unicorn_udp")
    config = export_project_config(sample_project, root)
    _fake_output(monkeypatch, FakeUnicorn(fail_send=True))
    summary = _execute(root, plan, RuntimeWorker(StubEngine({})),
        toolbox_handoff_config=config.model_dump(mode="json"))
    assert summary.aborted and _evidence(root).state == "aborted"
    assert not list((root / "logs" / "acquisition").glob("*-completed.fpvsconfig"))


def test_handoff_rejects_wrong_selected_hardware_before_any_marker_output(
    execution, sample_project, monkeypatch,
):
    root, plan = execution
    config = export_project_config(sample_project, root)
    output = FakeUnicorn()
    _fake_output(monkeypatch, output)
    with pytest.raises(ProjectConfigError, match="hardware selection does not match"):
        _execute(root, plan, RuntimeWorker(StubEngine({})),
            toolbox_handoff_config=config.model_dump(mode="json"))
    assert output.count == 0


def test_completed_helper_rejects_wrong_session_association(execution, sample_project, monkeypatch):
    root, plan = execution
    _fake_output(monkeypatch, FakeUnicorn())
    _execute(root, plan, RuntimeWorker(StubEngine({})))
    sample_project.settings.recording = ProjectRecordingSettings(recording_backend="unicorn_udp")
    config = export_project_config(sample_project, root)
    evidence = _evidence(root)
    evidence.session_id = "wrong-session"
    with pytest.raises(ProjectConfigError, match="session or run identity does not match"):
        completed_toolbox_config(config, root, plan, evidence)
