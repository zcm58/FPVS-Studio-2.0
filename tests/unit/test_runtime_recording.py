"""Local recording selection and durable acquisition evidence with fake output only."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from tests.platform_adapters import set_module_platform, windows_runtime
from tests.unit.runtime_launcher_helpers import StubEngine
from tests.unit.test_brainproducts_windows_writes import native_driver as native_driver

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.execution import AcquisitionEvidence, ParticipantMetadata, RunExecutionSummary
from fpvs_studio.core.models import ProjectRecordingSettings
from fpvs_studio.core.project_config import (
    ProjectConfigError,
    completed_toolbox_config,
    export_project_config,
    read_project_config,
)
from fpvs_studio.core.run_spec import TriggerEvent
from fpvs_studio.core.serialization import read_json_file
from fpvs_studio.gui import document_runtime
from fpvs_studio.gui.document_runtime import DocumentRuntimeMixin
from fpvs_studio.gui.document_support import DocumentError
from fpvs_studio.runtime import launcher, run_worker, triggers
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
from fpvs_studio.runtime.run_worker import (
    RuntimeWorker,
    _build_and_connect_trigger_backend,
    _execution_error_details,
)
from fpvs_studio.runtime.unicorn_recorder import RecorderReadinessError
from fpvs_studio.triggers import brainproducts_backend, serial_backend
from fpvs_studio.triggers.null_backend import NullBackend
from fpvs_studio.triggers.serial_port_access import check_serial_port_access


@pytest.fixture(autouse=True)
def _windows_acquisition_contract(monkeypatch):
    windows_runtime(monkeypatch)


@pytest.mark.parametrize("backend", ["brainproducts_triggerbox", "brainproducts_parallel"])
@pytest.mark.parametrize("mode", ["inherited", "incomplete", "saved", "test", "pilot"])
def test_project_brainproducts_confirmation_is_required_for_normal_launch(
    monkeypatch, backend, mode,
):
    set_module_platform(monkeypatch, document_runtime, "win32")
    configuration = ProjectRecordingSettings(
        recording_backend=backend,
        brainproducts_parallel_address=0x378 if backend == "brainproducts_parallel" else None,
        brainproducts_amplifier="actichamp",
        brainproducts_sampling_rate_hz=None if mode in ("incomplete", "test", "pilot") else 500,
    ).model_dump(mode="json")
    document = SimpleNamespace(
        local_testing_enabled=mode in ("test", "pilot"),
        uses_default_recording_configuration=mode in ("inherited", "test", "pilot"),
        recording_configuration=configuration,
        recording_launch_options=lambda: {
            **configuration, "experiment_test_mode": mode == "test", "pilot_mode": mode == "pilot",
        },
    )
    needs_setup = mode in ("inherited", "incomplete")
    assert DocumentRuntimeMixin.needs_project_brainproducts_setup(document) is needs_setup
    if needs_setup:
        expected = "Confirm this project's" if mode == "inherited" else "sampling rate"
        with pytest.raises(DocumentError, match=expected):
            DocumentRuntimeMixin.validate_recording_launch(document)
    else:
        expected = backend if mode == "saved" else "null"
        assert DocumentRuntimeMixin.validate_recording_launch(document) == expected


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


class FakeParallel(FakeTriggerBox):
    @property
    def backend_name(self):
        return "brainproducts_parallel"


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


@pytest.mark.parametrize("backend_name", ["unicorn_udp", "brainproducts_triggerbox"])
def test_failed_send_is_evidence_not_a_success(execution, monkeypatch, backend_name):
    root, plan = execution
    backend = (FakeTriggerBox if backend_name == "brainproducts_triggerbox" else FakeUnicorn)(
        fail_send=True,
    )
    adapter_name = (
        "BrainProductsTriggerBoxBackend" if backend_name == "brainproducts_triggerbox"
        else "UnicornUDPBackend"
    )
    monkeypatch.setattr(triggers, adapter_name, lambda *_args, **_kwargs: backend)
    summary = _execute(
        root, plan, RuntimeWorker(StubEngine({})), recording_backend=backend_name,
        brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
    )
    evidence = _evidence(root)
    assert summary.aborted and evidence.state == "aborted"
    assert [attempt.status for attempt in evidence.runs[0].attempted_events] == ["sent", "error"]
    assert evidence.runs[0].attempted_events[-1].message == "would block"
    assert all(
        attempt.backend_name == backend_name for attempt in evidence.runs[0].attempted_events
    )
    assert all(run.state == "not_started" for run in evidence.runs[1:])
    assert backend.closed


@pytest.mark.parametrize("failure", ["connect", "cleanup", "presentation", "export"])
@pytest.mark.parametrize("backend_name", ["unicorn_udp", "brainproducts_triggerbox"])
def test_partial_evidence_survives_failure(execution, monkeypatch, failure, backend_name):
    root, plan = execution
    backend = (FakeTriggerBox if backend_name == "brainproducts_triggerbox" else FakeUnicorn)(
        fail_connect=failure == "connect", fail_close=failure == "cleanup",
    )
    adapter_name = (
        "BrainProductsTriggerBoxBackend" if backend_name == "brainproducts_triggerbox"
        else "UnicornUDPBackend"
    )
    monkeypatch.setattr(triggers, adapter_name, lambda *_args, **_kwargs: backend)
    captures = {}
    engine = StubEngine(captures)
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
        _execute(
            root, plan, RuntimeWorker(engine), recording_backend=backend_name,
            brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
        )
    evidence = _evidence(root)
    assert evidence.state == "interrupted"
    assert bool(evidence.runs[0].attempted_events) == (failure != "connect")
    assert evidence.recording.effective_backend == backend_name
    if failure == "connect":
        assert captures.get("open_count", 0) == 0
        assert backend.count == 0
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


@pytest.mark.parametrize("mode,fail_export", [
    ("single", False), ("full", False), ("compact", False), ("full", True), ("compact", True),
])
@pytest.mark.parametrize("failure", ["presentation", "trigger"])
def test_triggerbox_cleanup_failure_remains_in_evidence_after_primary_failure(
    execution, sample_project, monkeypatch, caplog, mode, fail_export, failure,
):
    root, plan = execution
    sample_project.settings.recording = ProjectRecordingSettings(
        recording_backend="brainproducts_triggerbox", brainproducts_amplifier="actichamp",
        brainproducts_sampling_rate_hz=500,
    )
    config = export_project_config(sample_project, root)
    output = FakeTriggerBox()
    cleanup_error = OSError("TriggerBox reset worker did not stop; restart FPVS Studio.")
    output.close = Mock(side_effect=cleanup_error)
    monkeypatch.setattr(triggers, "BrainProductsTriggerBoxBackend", lambda **_kwargs: output)
    engine = StubEngine({})
    original_playback = engine.run_condition
    original_error = (
        triggers.TriggerEmissionError("TriggerBox event write failed")
        if failure == "trigger" else RuntimeError("presentation failed")
    )

    def fail_after_markers(*args, **kwargs):
        original_playback(*args, **kwargs)
        raise original_error

    monkeypatch.setattr(engine, "run_condition", fail_after_markers)
    if fail_export:
        monkeypatch.setattr(
            "fpvs_studio.runtime.run_worker.write_participant_summary",
            Mock(side_effect=PermissionError("workbook locked")),
        )
    options = {
        "recording_backend": "brainproducts_triggerbox", "brainproducts_amplifier": "actichamp",
        "brainproducts_sampling_rate_hz": 500,
        "toolbox_handoff_config": config.model_dump(mode="json"),
    }
    worker = RuntimeWorker(engine)
    with pytest.raises(type(original_error)) as caught:
        if mode == "single":
            spec = plan.ordered_entries()[0].run_spec
            worker.execute(
                root, spec, root / "runs" / spec.run_id, participant_number="007",
                runtime_options=options,
            )
        else:
            _execute(root, plan, worker, export_mode=mode, **options)

    assert caught.value is original_error
    evidence = _evidence(root)
    assert evidence.state == "interrupted"
    assert str(original_error) in evidence.abort_reason
    assert str(cleanup_error) in evidence.abort_reason
    if fail_export:
        assert evidence.export_error == "workbook locked"
    assert str(cleanup_error) in caplog.text
    assert evidence.runs[0].attempted_events
    assert not list((root / "logs" / "acquisition").glob("*-completed.fpvsconfig"))


@pytest.mark.parametrize("fail_close", [False, True])
def test_triggerbox_retained_write_cause_is_not_a_second_cleanup_failure(
    fail_close,
):
    port = SimpleNamespace(
        write=Mock(side_effect=[1, OSError("event USB write failed"), 1]),
        close=Mock(side_effect=OSError("port close failed") if fail_close else None),
    )
    serial_module = SimpleNamespace(
        Serial=lambda **_kwargs: port, EIGHTBITS=8, PARITY_NONE="N", STOPBITS_ONE=1,
    )
    output = brainproducts_backend.BrainProductsTriggerBoxBackend(
        "COM4", pulse_width_ms=1, serial_module=serial_module,
    )
    backend = triggers.LoggedTriggerBackend(output, backend_name="brainproducts_triggerbox")
    backend.connect()
    with pytest.raises(triggers.TriggerEmissionError) as primary:
        backend.send_trigger(55)
    with pytest.raises(brainproducts_backend.BrainProductsTriggerBoxError) as cleanup:
        backend.close()

    error = primary.value
    details = _execution_error_details(error, cleanup.value)
    port.close.assert_called_once()
    assert [call.args[0] for call in port.write.call_args_list] == [b"\x00", b"7", b"\x00"]
    if fail_close:
        assert cleanup.value is not primary.value.__cause__
        assert "Trigger cleanup also failed" in details
        assert "port close failed" in details
    else:
        assert cleanup.value is primary.value.__cause__
        assert details == f"{type(error).__name__}: {error}"


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
        "brainproducts_amplifier": "actichamp", "brainproducts_sampling_rate_hz": 100,
        "serial_port": "COM99", "serial_baudrate": 9600, "serial_enabled": False,
    }
    backend, _ = triggers.build_trigger_backend(options)
    adapter.assert_called_once_with(port="COM9", pulse_width_ms=20)
    assert backend.backend_name == "brainproducts_triggerbox"
    snapshot = recording_snapshot(options)
    assert snapshot.serial_port == "COM9"
    assert snapshot.serial_baudrate == 2_000_000
    assert snapshot.trigger_pulse_width_ms == 20
    assert snapshot.brainproducts_amplifier == "actichamp"
    assert snapshot.brainproducts_sampling_rate_hz == 100
    assert snapshot.acquisition_profile is None


def test_triggerbox_occupied_com4_aborts_before_presentation_with_recovery(execution, monkeypatch):
    root, plan = execution
    failure = OSError(
        "could not open port 'COM4': PermissionError(13, 'Access is denied.', None, 5)"
    )
    serial_module = SimpleNamespace(
        Serial=Mock(side_effect=failure), EIGHTBITS=8, PARITY_NONE="N", STOPBITS_ONE=1,
    )
    monkeypatch.setattr(brainproducts_backend, "_load_serial_module", lambda: serial_module)
    captures = {}
    with pytest.raises(PreflightError) as caught:
        _execute(
            root, plan, RuntimeWorker(StubEngine(captures)),
            recording_backend="brainproducts_triggerbox", brainproducts_serial_port="COM4",
            brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
        )

    assert "The COM4 port is occupied or access was denied." in str(caught.value)
    assert "Fully exit the TriggerBox software (Configuration/Test IO)" in str(caught.value)
    assert "Pressing Stop can leave the port occupied." in str(caught.value)
    assert str(failure) in str(caught.value)
    serial_module.Serial.assert_called_once()
    assert serial_module.Serial.call_args.kwargs["port"] == "COM4"
    assert captures.get("open_count", 0) == 0
    evidence = _evidence(root)
    assert evidence.state == "interrupted"
    assert all(not run.attempted_events for run in evidence.runs)


@pytest.mark.skipif(sys.platform != "win32", reason="Native pySerial Win32 error replay")
@pytest.mark.parametrize("error_code, expected, recovery", [
    (5, "The COM4 port is occupied or access was denied.", "Fully exit the TriggerBox software"),
    (2, "TriggerBox port COM4 was not found.", "Device Manager"),
])
def test_triggerbox_native_pyserial_open_failure_reaches_access_check_and_runtime(
    execution, monkeypatch, error_code, expected, recovery,
):
    import ctypes

    import serial
    from serial import serialwin32

    assert serial.Serial is serialwin32.Serial
    native_error = ctypes.WinError(error_code)
    raw_error = f"could not open port 'COM4': {native_error!r}"
    open_port = Mock(return_value=serialwin32.win32.INVALID_HANDLE_VALUE)
    write = Mock(side_effect=AssertionError("A failed open must not write markers"))
    # Intercept the OS boundary: the real Serial.open runs, but never opens a device.
    monkeypatch.setattr(serialwin32.win32, "CreateFile", open_port)
    monkeypatch.setattr(serialwin32.win32, "WriteFile", write)
    monkeypatch.setattr(serialwin32, "ctypes", SimpleNamespace(WinError=lambda: native_error))
    open_arguments = (
        "COM4", serialwin32.win32.GENERIC_READ | serialwin32.win32.GENERIC_WRITE,
        0, None, serialwin32.win32.OPEN_EXISTING,
        serialwin32.win32.FILE_ATTRIBUTE_NORMAL | serialwin32.win32.FILE_FLAG_OVERLAPPED, 0,
    )

    access = check_serial_port_access("COM4", baudrate=2_000_000)
    assert not access.accessible and access.access_error == raw_error
    open_port.assert_called_once_with(*open_arguments)
    open_port.reset_mock()

    root, plan = execution
    captures = {}
    with pytest.raises(PreflightError) as caught:
        _execute(
            root, plan, RuntimeWorker(StubEngine(captures)),
            recording_backend="brainproducts_triggerbox", brainproducts_serial_port="COM4",
            brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
        )

    assert expected in str(caught.value) and recovery in str(caught.value)
    assert raw_error in str(caught.value)
    serial_failure = caught.value.__cause__.__cause__
    assert isinstance(serial_failure, serial.SerialException)
    assert str(serial_failure) == raw_error
    open_port.assert_called_once_with(*open_arguments)
    write.assert_not_called()
    assert captures.get("open_count", 0) == 0
    evidence = _evidence(root)
    assert evidence.state == "interrupted"
    assert all(not run.attempted_events for run in evidence.runs)


@pytest.mark.skipif(sys.platform != "win32", reason="Native pySerial Win32 error replay")
@pytest.mark.parametrize("selected", ["serial", "biosemi_active_three"])
@pytest.mark.parametrize("code, summary, action", [
    (5, "BioSemi trigger port COM3 is occupied or access was denied", "Fully exit"),
    (2, "BioSemi trigger port COM3 was not found", "Device Manager"),
    (121, "BioSemi trigger port COM3 did not respond in time", "Reconnect"),
    (1117, "BioSemi USB communication on COM3 failed", "USB Trigger Interface"),
])
def test_biosemi_native_open_failure_preserves_recovery_and_interrupted_evidence(
    execution, monkeypatch, selected, code, summary, action,
):
    import ctypes

    from serial import serialwin32

    native_error = ctypes.WinError(code)
    open_port = Mock(return_value=serialwin32.win32.INVALID_HANDLE_VALUE)
    write = Mock(side_effect=AssertionError("A denied open must never send a marker"))
    monkeypatch.setattr(serialwin32.win32, "CreateFile", open_port)
    monkeypatch.setattr(serialwin32.win32, "WriteFile", write)
    monkeypatch.setattr(serialwin32, "ctypes", SimpleNamespace(WinError=lambda: native_error))
    root, plan = execution
    captures = {}
    with pytest.raises(PreflightError) as caught:
        _execute(
            root, plan, RuntimeWorker(StubEngine(captures)),
            recording_backend=selected, serial_port="COM3", serial_baudrate=115200,
        )

    message = str(caught.value)
    assert summary in message and action in message
    assert repr(native_error) in message.partition("Details:")[2]
    assert "TriggerBox" not in message and "BrainVision" not in message
    open_port.assert_called_once()
    assert open_port.call_args.args[0] == "COM3"
    assert open_port.call_args.args[2] == 0  # Exclusive ownership remains required.
    write.assert_not_called()
    assert captures.get("open_count", 0) == 0
    evidence = _evidence(root)
    assert evidence.state == "interrupted"
    assert all(not run.attempted_events for run in evidence.runs)


@pytest.mark.parametrize("selected", ["serial", "biosemi_active_three"])
@pytest.mark.parametrize("mode", ["full", "compact"])
def test_biosemi_close_failure_retains_marker_evidence_and_blocks_completed_handoff(
    execution, sample_project, monkeypatch, selected, mode,
):
    root, plan = execution
    sample_project.settings.recording = ProjectRecordingSettings(recording_backend=selected)
    config = export_project_config(sample_project, root)
    port = SimpleNamespace(
        write=Mock(return_value=1), close=Mock(side_effect=OSError("close denied")),
    )
    serial_module = SimpleNamespace(
        Serial=Mock(return_value=port), EIGHTBITS=8, PARITY_NONE="N", STOPBITS_ONE=1,
    )
    monkeypatch.setattr(serial_backend, "_load_serial_module", lambda: serial_module)

    with pytest.raises(serial_backend.SerialBackendError) as caught:
        _execute(
            root, plan, RuntimeWorker(StubEngine({})), recording_backend=selected,
            serial_port="COM3", export_mode=mode,
            toolbox_handoff_config=config.model_dump(mode="json"),
        )

    assert "BioSemi trigger port COM3 could not be closed" in str(caught.value)
    assert "Restart Studio" in str(caught.value)
    assert "close denied" in str(caught.value).partition("Details:")[2]
    assert port.write.call_count > 0 and port.close.call_count == 1
    evidence = _evidence(root)
    assert evidence.state == "interrupted" and evidence.runs[0].attempted_events
    assert all(
        attempt.status == "sent" for run in evidence.runs for attempt in run.attempted_events
    )
    assert "close denied" in evidence.abort_reason
    assert not list((root / "logs" / "acquisition").glob("*-completed.fpvsconfig"))


@pytest.mark.skipif(sys.platform != "win32", reason="Native pySerial Win32 completion replay")
@pytest.mark.parametrize("selected", ["serial", "biosemi_active_three"])
@pytest.mark.parametrize("launch_kind", ["run", "session"])
@pytest.mark.parametrize("mode", ["compact", "full"])
def test_biosemi_deferred_final_marker_failure_stops_before_tasks_and_feedback(
    execution, monkeypatch, native_driver, selected, launch_kind, mode,
):
    root, plan = execution
    spec = plan.ordered_entries()[0].run_spec
    driver = native_driver
    final_index = len(spec.trigger_events)
    driver.blocked.add(final_index)
    monkeypatch.setattr(serial_backend, "_load_serial_module", lambda: driver.module)
    captures = {}
    engine = StubEngine(captures)
    play = engine.run_condition

    def fail_final_completion(*args, **kwargs):
        summary = play(*args, **kwargs)
        driver.blocked.clear()
        driver.errors[final_index] = 1117
        return summary

    monkeypatch.setattr(engine, "run_condition", fail_final_completion)
    completion = Mock(return_value=False)
    monkeypatch.setattr(engine, "show_completion_screen", completion)
    worker = RuntimeWorker(engine)
    feedback = Mock(return_value=False)
    monkeypatch.setattr(worker, "_show_condition_feedback", feedback)
    tasks = Mock(wraps=run_worker.run_task_modules)
    monkeypatch.setattr(run_worker, "run_task_modules", tasks)
    options = {"recording_backend": selected, "serial_reset_code": 0, "export_mode": mode}

    with pytest.raises(RuntimeError, match="1117") as failure:
        if launch_kind == "session":
            _execute(root, plan, worker, **options)
        else:
            worker.execute(
                root, spec, root / "runs" / "single", participant_number="007",
                runtime_options=options,
            )

    assert isinstance(failure.value, triggers.TriggerEmissionError)
    assert failure.value.__cause__.__cause__.winerror == 1117
    feedback.assert_not_called()
    completion.assert_not_called()
    assert tasks.call_count == (1 if launch_kind == "session" else 0)
    assert not any("on_module_start" in call.kwargs for call in tasks.call_args_list)
    assert captures["run_ids"] == [spec.run_id]
    assert [payload for payload, _when in driver.writes] == [
        bytes([event.code]) for event in spec.trigger_events
    ]
    assert driver.closed and not driver.reused_pending
    evidence = _evidence(root)
    assert evidence.state == "interrupted"
    assert "1117" in evidence.abort_reason
    attempts = evidence.runs[0].attempted_events
    assert len(attempts) == final_index
    assert all(attempt.status == "sent" for attempt in attempts[:-1])
    last = attempts[-1]
    event = spec.trigger_events[-1]
    assert (last.code, last.label, last.frame_index) == (event.code, event.label, event.frame_index)
    assert last.status == "error" and "1117" in last.message
    assert all(not run.attempted_events for run in evidence.runs[1:])
    assert not list((root / "logs" / "acquisition").glob("*-completed.fpvsconfig"))
    if mode == "full":
        folder = root / "runs" / (
            f"P007_session01/{spec.run_id}" if launch_kind == "session" else "single"
        )
        saved = read_json_file(folder / "run_summary.json", RunExecutionSummary)
        assert saved.aborted and saved.completed_frames == spec.display.total_frames
        assert saved.trigger_log[-1].status == "error"
        assert saved.trigger_log[-1].frame_index == event.frame_index


@pytest.mark.skipif(sys.platform != "win32", reason="Native pySerial Win32 completion replay")
@pytest.mark.parametrize("next_code", [55, 128])
def test_biosemi_deferred_failure_marks_previous_and_unsent_attempts(native_driver, next_code):
    driver = native_driver
    driver.blocked.add(1)
    output = serial_backend.SerialBackend("COM3", serial_module=driver.module)
    backend = triggers.LoggedTriggerBackend(output, backend_name="serial")
    backend.connect()
    backend.send_prevalidated_trigger(55, frame_index=7, label="first", time_s=.125)
    driver.blocked.clear()
    driver.errors[1] = 1117
    with pytest.raises(triggers.TriggerEmissionError, match="1117"):
        backend.send_prevalidated_trigger(next_code, frame_index=8, label="next", time_s=.25)
    with pytest.raises(serial_backend.SerialBackendError):
        backend.close()

    first, second = backend.records
    assert (first.code, first.frame_index, first.label, first.time_s) == (55, 7, "first", .125)
    assert (second.code, second.frame_index, second.label, second.time_s) == (
        next_code, 8, "next", .25,
    )
    assert first.status == second.status == "error"
    assert "1117" in first.message and "1117" in second.message
    assert "not sent because the previous marker failed" in second.message
    assert len(driver.writes) == 1
    assert driver.closed and not driver.reused_pending


@pytest.mark.skipif(sys.platform != "win32", reason="Native pySerial Win32 completion replay")
@pytest.mark.parametrize("next_attempt", [False, True])
@pytest.mark.parametrize("failure_kind", ["native", "timeout"])
def test_biosemi_close_failure_updates_the_pending_marker_record(
    native_driver, monkeypatch, next_attempt, failure_kind,
):
    driver = native_driver
    driver.blocked.add(1)
    monkeypatch.setattr(serial_backend, "_WRITE_TIMEOUT_S", .01)
    output = serial_backend.SerialBackend("COM3", serial_module=driver.module)
    backend = triggers.LoggedTriggerBackend(output, backend_name="serial")
    backend.connect()
    backend.send_prevalidated_trigger(55, frame_index=7, label="pending", time_s=.125)
    if next_attempt:
        with pytest.raises(triggers.TriggerEmissionError, match="previous marker"):
            backend.send_prevalidated_trigger(55, frame_index=8, label="unsent", time_s=.25)
    if failure_kind == "native":
        driver.blocked.clear()
        driver.errors[1] = 1117
    with pytest.raises(serial_backend.SerialBackendError):
        backend.close()

    records = backend.records
    assert len(records) == (2 if next_attempt else 1)
    assert all(record.status == "error" for record in records)
    assert (records[0].frame_index, records[0].label, records[0].time_s) == (7, "pending", .125)
    assert ("1117" if failure_kind == "native" else "timed out") in records[0].message
    assert len(driver.writes) == 1 and driver.closed


@pytest.mark.skipif(sys.platform != "win32", reason="Native pySerial Win32 completion replay")
def test_biosemi_successful_close_drain_keeps_submitted_marker_sent(native_driver):
    driver = native_driver
    driver.blocked.add(1)
    output = serial_backend.SerialBackend("COM3", serial_module=driver.module)
    backend = triggers.LoggedTriggerBackend(output, backend_name="serial")
    backend.connect()
    backend.send_prevalidated_trigger(55)
    with pytest.raises(triggers.TriggerEmissionError, match="previous marker"):
        backend.send_prevalidated_trigger(55)
    driver.blocked.clear()
    with pytest.raises(serial_backend.SerialBackendError, match="previous marker"):
        backend.close()
    assert [record.status for record in backend.records] == ["sent", "error"]
    assert len(driver.writes) == 1 and driver.closed


@pytest.mark.skipif(sys.platform != "win32", reason="Native pySerial Win32 completion replay")
@pytest.mark.parametrize("query_error", [6, 87])
def test_biosemi_failed_new_write_never_relabels_earlier_success(
    native_driver, monkeypatch, query_error,
):
    driver = native_driver
    monkeypatch.setattr("fpvs_studio.triggers.brainproducts_windows._RETAINED_WRITES", [])
    output = serial_backend.SerialBackend("COM3", serial_module=driver.module)
    backend = triggers.LoggedTriggerBackend(output, backend_name="serial")
    backend.connect()
    backend.send_prevalidated_trigger(55, label="completed")
    driver.query_error = query_error
    with pytest.raises(triggers.TriggerEmissionError):
        backend.send_prevalidated_trigger(55, label="failed")
    with pytest.raises(serial_backend.SerialBackendError):
        backend.close()
    assert [record.status for record in backend.records] == ["sent", "error"]
    assert len(driver.writes) == 2 and not driver.closed


@pytest.mark.skipif(sys.platform != "win32", reason="Native pySerial Win32 completion replay")
@pytest.mark.parametrize("operation", ["finish", "close"])
def test_biosemi_manual_reset_failure_never_relabels_an_event(native_driver, operation):
    driver = native_driver
    output = serial_backend.SerialBackend("COM3", reset_code=0, serial_module=driver.module)
    backend = triggers.LoggedTriggerBackend(output, backend_name="serial")
    backend.connect()
    backend.send_prevalidated_trigger(55)
    driver.blocked.add(2)
    backend.reset()
    driver.blocked.clear()
    driver.errors[2] = 1117
    if operation == "finish":
        with pytest.raises(triggers.TriggerEmissionError, match="1117"):
            backend.finish_pending_output()
    with pytest.raises(serial_backend.SerialBackendError, match="1117"):
        backend.close()
    assert [record.status for record in backend.records] == ["sent"]
    assert [payload for payload, _when in driver.writes] == [b"7", b"\x00"]
    assert driver.closed


@pytest.mark.skipif(sys.platform != "win32", reason="Native pySerial Win32 completion replay")
@pytest.mark.parametrize("selected", ["serial", "biosemi_active_three"])
def test_biosemi_engine_abort_retains_late_marker_failure_in_acquisition(
    execution, monkeypatch, native_driver, selected,
):
    root, plan = execution
    spec = plan.ordered_entries()[0].run_spec
    driver = native_driver
    final_index = len(spec.trigger_events)
    driver.blocked.add(final_index)
    monkeypatch.setattr(serial_backend, "_load_serial_module", lambda: driver.module)
    captures = {}
    engine = StubEngine(captures)
    play = engine.run_condition

    def interrupt_playback(*args, **kwargs):
        play(*args, **kwargs)
        driver.blocked.clear()
        driver.errors[final_index] = 1117
        raise RuntimeError("Presentation interrupted")

    monkeypatch.setattr(engine, "run_condition", interrupt_playback)
    with pytest.raises(RuntimeError, match="Presentation interrupted"):
        _execute(root, plan, RuntimeWorker(engine), recording_backend=selected)
    evidence = _evidence(root)
    assert evidence.state == "interrupted"
    assert "Presentation interrupted" in evidence.abort_reason and "1117" in evidence.abort_reason
    attempts = evidence.runs[0].attempted_events
    assert len(attempts) == final_index
    assert attempts[-1].status == "error" and "1117" in attempts[-1].message
    assert all(record.status == "sent" for record in attempts[:-1])
    assert all(not run.attempted_events for run in evidence.runs[1:])
    assert not captures.get("completion_screens") and not captures.get("condition_feedback")
    assert driver.closed


@pytest.mark.skipif(sys.platform != "win32", reason="Native pySerial Win32 completion replay")
@pytest.mark.parametrize("launch_kind, refresh_failure, journal_error", [
    ("run", False, None), ("session", False, None),
    ("run", True, None), ("session", True, None),
    ("session", False, PermissionError), ("session", False, ValueError),
])
def test_biosemi_late_close_refreshes_full_marker_exports_without_hiding_original_error(
    execution, monkeypatch, native_driver, launch_kind, refresh_failure, journal_error,
):
    root, plan = execution
    spec = plan.ordered_entries()[0].run_spec
    driver = native_driver
    driver.blocked.add(1)
    monkeypatch.setattr(serial_backend, "_load_serial_module", lambda: driver.module)
    close = serial_backend.SerialBackend.close

    def fail_at_close(self):
        driver.blocked.clear()
        driver.errors[1] = 1117
        return close(self)

    monkeypatch.setattr(serial_backend.SerialBackend, "close", fail_at_close)
    write = run_worker.write_run_artifacts
    snapshots = []

    def write_or_fail(folder, run_spec, summary):
        snapshots.append(summary)
        if refresh_failure and summary.trigger_log[0].status == "error":
            raise PermissionError("Trigger evidence file locked")
        return write(folder, run_spec, summary)

    monkeypatch.setattr(run_worker, "write_run_artifacts", write_or_fail)
    if journal_error is not None:
        monkeypatch.setattr(
            run_worker.TaskResponseCheckpoint, "reconcile_run_responses",
            Mock(side_effect=journal_error("Task journal unavailable")),
        )
    worker = RuntimeWorker(StubEngine({}))
    with pytest.raises(triggers.TriggerEmissionError, match="previous marker"):
        if launch_kind == "session":
            _execute(root, plan, worker, recording_backend="serial", export_mode="full")
        else:
            worker.execute(
                root, spec, root / "runs" / "single", participant_number="007",
                runtime_options={"recording_backend": "serial"},
            )
    evidence = _evidence(root)
    assert evidence.state == "interrupted" and "1117" in evidence.abort_reason
    assert [attempt.status for attempt in evidence.runs[0].attempted_events] == ["error", "error"]
    assert evidence.export_error == ("Trigger evidence file locked" if refresh_failure else None)
    folder = root / "runs" / (
        f"P007_session01/{spec.run_id}" if launch_kind == "session" else "single"
    )
    saved = read_json_file(folder / "run_summary.json", RunExecutionSummary)
    expected = ["sent", "error"] if refresh_failure else ["error", "error"]
    assert [record.status for record in saved.trigger_log] == expected
    with (folder / "trigger_log.csv").open(newline="", encoding="utf-8-sig") as stream:
        assert [row["status"] for row in csv.DictReader(stream)] == expected
    assert saved.aborted and saved.completed_frames == snapshots[0].completed_frames
    assert saved.frame_intervals == snapshots[0].frame_intervals
    assert saved.response_log == snapshots[0].response_log
    assert not list((root / "logs" / "acquisition").glob("*-completed.fpvsconfig"))
    assert driver.closed and len(driver.writes) == 1


def test_parallel_factory_uses_explicit_address_without_serial_configuration(monkeypatch):
    adapter = Mock(return_value=FakeParallel())
    monkeypatch.setattr(triggers, "ParallelPortBackend", adapter)
    options = {
        "recording_backend": "brainproducts_parallel", "brainproducts_parallel_address": 0xD010,
        "brainproducts_sampling_rate_hz": 100, "brainproducts_pulse_width_ms": 20,
        "serial_port": "COM99", "brainproducts_serial_port": "", "serial_baudrate": 0,
        "serial_enabled": False,
    }
    backend, _ = triggers.build_trigger_backend(options)
    adapter.assert_called_once_with(address=0xD010, pulse_width_ms=20)
    assert backend.backend_name == "brainproducts_parallel"
    snapshot = recording_snapshot(options)
    assert snapshot.parallel_port_address == 0xD010
    assert snapshot.serial_port is None and snapshot.serial_baudrate is None
    assert snapshot.brainproducts_amplifier == "actichamp"
    assert snapshot.brainproducts_sampling_rate_hz == 100
    assert snapshot.trigger_pulse_width_ms == 20
    assert snapshot.acquisition_profile is None
    assert snapshot.receiver_validation == "pending"
    assert snapshot.recorded_marker_integrity == "unknown"
    assert snapshot.physical_timing == "uncharacterized"
    settings = LaunchSettings(**options)
    launcher._validate_launch_settings(settings)
    assert settings.as_runtime_options()["brainproducts_parallel_address"] == 0xD010


def test_parallel_connect_failure_gives_address_and_driver_recovery_guidance(monkeypatch):
    output = FakeParallel()
    failure = OSError("InpOut driver is not running")
    output.connect = Mock(side_effect=failure)
    adapter = Mock(return_value=output)
    monkeypatch.setattr(triggers, "ParallelPortBackend", adapter)
    options = {
        "recording_backend": "brainproducts_parallel", "brainproducts_parallel_address": 0xD010,
        "brainproducts_sampling_rate_hz": 500,
    }

    with pytest.raises(PreflightError) as error:
        _build_and_connect_trigger_backend(options)

    message = str(error.value)
    assert "0xD010" in message
    assert "parallel-port I/O address matches this PC" in message
    assert "compatible InpOut driver is installed and running" in message
    assert "Details: InpOut driver is not running" in message
    assert "serial port" not in message
    assert error.value.__cause__ is failure
    assert output.closed
    adapter.assert_called_once_with(address=0xD010, pulse_width_ms=10)


@pytest.mark.parametrize("mode", ["experiment_test_mode", "pilot_mode"])
def test_parallel_test_modes_never_construct_hardware_and_allow_unset_endpoint(monkeypatch, mode):
    adapter = Mock(side_effect=AssertionError("hardware must not be created"))
    monkeypatch.setattr(triggers, "ParallelPortBackend", adapter)
    options = {"recording_backend": "brainproducts_parallel", mode: True}
    backend, _ = triggers.build_trigger_backend(options)
    assert backend.backend_name == "null"
    snapshot = recording_snapshot(options)
    assert snapshot.selected_backend == "brainproducts_parallel"
    assert snapshot.parallel_port_address is None
    assert snapshot.serial_port is None and snapshot.serial_baudrate is None
    assert snapshot.brainproducts_amplifier == "actichamp"
    assert snapshot.brainproducts_sampling_rate_hz is None
    adapter.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("brainproducts_parallel_address", True), ("brainproducts_parallel_address", "0x378"),
    ("brainproducts_parallel_address", 888.0), ("brainproducts_parallel_address", 0),
    ("brainproducts_parallel_address", -1), ("brainproducts_parallel_address", 65536),
    ("brainproducts_pulse_width_ms", 0), ("brainproducts_pulse_width_ms", True),
    ("brainproducts_sampling_rate_hz", "500"), ("brainproducts_sampling_rate_hz", 0),
    ("brainproducts_sampling_rate_hz", True), ("brainproducts_sampling_rate_hz", 300),
    ("brainproducts_amplifier", "liveamp"), ("brainproducts_amplifier", "brainamp"),
])
def test_parallel_rejects_malformed_or_unsupported_configuration_even_in_test(field, value):
    with pytest.raises(RecordingConfigurationError, match="Brain Products|actiCHamp"):
        validate_recording_configuration({
            "recording_backend": "brainproducts_parallel", "experiment_test_mode": True,
            field: value,
        })


@pytest.mark.parametrize("configuration,match", [
    ({}, "actual I/O address"),
    ({"brainproducts_sampling_rate_hz": 500}, "actual I/O address"),
    ({"brainproducts_parallel_address": 0x378}, "sampling rate"),
    ({"brainproducts_parallel_address": 0x378, "brainproducts_sampling_rate_hz": 100},
     "at least 20 ms"),
])
@pytest.mark.parametrize("launch_kind", ["run", "session"])
def test_parallel_missing_address_or_invalid_timing_fails_before_visit_or_output(
    execution, monkeypatch, launch_kind, configuration, match,
):
    root, plan = execution
    reserve = Mock(side_effect=AssertionError("visit must not be reserved"))
    monkeypatch.setattr(launcher, "reserve_participant_session", reserve)
    adapter = Mock(side_effect=AssertionError("hardware must not be opened"))
    monkeypatch.setattr(triggers, "ParallelPortBackend", adapter)
    with pytest.raises(LaunchSettingsError, match=match):
        _launch_at_boundary(root, plan, launch_kind, LaunchSettings(
            recording_backend="brainproducts_parallel", verify_refresh_rate=False, **configuration,
        ))
    reserve.assert_not_called()
    adapter.assert_not_called()
    assert not (root / "logs" / "acquisition").exists()


def test_parallel_schedule_reuses_actichamp_high_and_low_interval_validation(execution):
    _, plan = execution
    spec = plan.ordered_entries()[0].run_spec.model_copy(deep=True)
    spec.display.refresh_hz = 100
    spec.trigger_events = [
        TriggerEvent(frame_index=-1, code=1, label="condition_start"),
        TriggerEvent(frame_index=1, code=55, label="oddball_onset"),
    ]
    options = {
        "recording_backend": "brainproducts_parallel", "brainproducts_parallel_address": 0x378,
        "brainproducts_sampling_rate_hz": 1000, "brainproducts_pulse_width_ms": 10,
    }
    with pytest.raises(RecordingConfigurationError, match="Parallel-port output needs more than"):
        validate_recording_trigger_schedule(spec, options)
    validate_recording_trigger_schedule(spec, {**options, "brainproducts_pulse_width_ms": 2})
    validate_recording_trigger_schedule(spec, {**options, "experiment_test_mode": True})


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
    assert snapshot.brainproducts_amplifier is None
    assert snapshot.brainproducts_sampling_rate_hz is None
    adapter.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("brainproducts_serial_port", " "), ("brainproducts_serial_port", None),
    ("brainproducts_serial_port", 9), ("brainproducts_pulse_width_ms", True),
    ("brainproducts_pulse_width_ms", 0), ("brainproducts_pulse_width_ms", 1001),
    ("brainproducts_pulse_width_ms", "10"),
    ("brainproducts_amplifier", "unknown"), ("brainproducts_amplifier", []),
    ("brainproducts_sampling_rate_hz", True), ("brainproducts_sampling_rate_hz", "500"),
    ("brainproducts_sampling_rate_hz", 500.0), ("brainproducts_sampling_rate_hz", 0),
])
def test_invalid_triggerbox_configuration_rejected_even_in_test(field, value):
    with pytest.raises(RecordingConfigurationError, match="Brain Products"):
        validate_recording_configuration({
            "recording_backend": "brainproducts_triggerbox", "experiment_test_mode": True,
            field: value,
        })


@pytest.mark.parametrize("mode", ["experiment_test_mode", "pilot_mode"])
@pytest.mark.parametrize("configuration", [
    {}, {"brainproducts_amplifier": "liveamp"}, {"brainproducts_sampling_rate_hz": 500},
])
def test_triggerbox_incomplete_hardware_information_only_allowed_for_test_pilot(
    mode, configuration,
):
    options = {"recording_backend": "brainproducts_triggerbox", **configuration}
    with pytest.raises(RecordingConfigurationError, match="amplifier family and EEG sampling rate"):
        validate_production_recording(options)
    assert validate_production_recording({**options, mode: True}) == "null"


@pytest.mark.parametrize("mode", ["experiment_test_mode", "pilot_mode"])
def test_triggerbox_test_pilot_snapshots_preserve_explicit_amplifier_settings(mode):
    snapshot = recording_snapshot({
        "recording_backend": "brainproducts_triggerbox", "brainproducts_amplifier": "liveamp",
        "brainproducts_sampling_rate_hz": 500, mode: True,
    })
    assert snapshot.effective_backend == "null"
    assert snapshot.brainproducts_amplifier == "liveamp"
    assert snapshot.brainproducts_sampling_rate_hz == 500
    assert snapshot.recorded_marker_integrity == "unknown"


@pytest.mark.parametrize("amplifier,rate,pulse,minimum", [
    ("actichamp", 100, 19, 20), ("brainamp", 100, 9, 10), ("liveamp", 250, 7, 8),
])
def test_triggerbox_rejects_pulse_below_amplifier_minimum(amplifier, rate, pulse, minimum):
    options = {
        "recording_backend": "brainproducts_triggerbox", "brainproducts_amplifier": amplifier,
        "brainproducts_sampling_rate_hz": rate, "brainproducts_pulse_width_ms": pulse,
    }
    with pytest.raises(RecordingConfigurationError, match=f"at least {minimum} ms"):
        validate_production_recording(options)
    assert validate_production_recording({**options, "brainproducts_pulse_width_ms": minimum}) == (
        "brainproducts_triggerbox"
    )


@pytest.mark.parametrize("amplifier,rate", [
    ("actichamp", 300), ("brainamp", 10000), ("liveamp", 100),
])
def test_triggerbox_rejects_unsupported_amplifier_rate_even_in_test(amplifier, rate):
    with pytest.raises(RecordingConfigurationError, match="EEG sampling rates"):
        validate_recording_configuration({
            "recording_backend": "brainproducts_triggerbox", "brainproducts_amplifier": amplifier,
            "brainproducts_sampling_rate_hz": rate, "experiment_test_mode": True,
        })


def test_triggerbox_compiled_six_hz_at_sixty_hz_uses_one_point_two_hz_oddball_markers(execution):
    _, plan = execution
    spec = plan.ordered_entries()[0].run_spec
    assert spec.condition.base_hz == 6
    assert spec.condition.oddball_every_n == 5
    assert spec.condition.oddball_hz == pytest.approx(1.2)
    assert spec.display.refresh_hz == 60
    assert spec.display.frames_per_stimulus == 10
    frames = [event.frame_index for event in spec.trigger_events if event.label == "oddball_onset"]
    assert len(frames) > 1
    assert {
        current - previous for previous, current in zip(frames, frames[1:], strict=False)
    } == {50}
    assert 50 * 1000 / spec.display.refresh_hz == pytest.approx(833.333333)
    assert spec.trigger_events[0].label == "condition_start"
    assert spec.trigger_events[0].frame_index == 0
    assert frames[0] == 40
    validate_recording_trigger_schedule(spec, {
        "recording_backend": "brainproducts_triggerbox", "brainproducts_amplifier": "actichamp",
        "brainproducts_sampling_rate_hz": 500, "brainproducts_pulse_width_ms": 10,
    })


def test_triggerbox_schedule_checks_high_and_low_intervals_including_frame_minus_one(execution):
    _, plan = execution
    spec = plan.ordered_entries()[0].run_spec
    spec = spec.model_copy(update={"trigger_events": [
        TriggerEvent(frame_index=-1, code=1, label="condition_start"),
        TriggerEvent(frame_index=0, code=55, label="distractor_onset"),
    ]})
    options = {
        "recording_backend": "brainproducts_triggerbox", "brainproducts_amplifier": "actichamp",
        "brainproducts_sampling_rate_hz": 1000,
    }
    with pytest.raises(RecordingConfigurationError, match="frames -1 and 0"):
        validate_recording_trigger_schedule(spec, options)
    validate_recording_trigger_schedule(spec, {**options, "brainproducts_pulse_width_ms": 2})
    validate_recording_trigger_schedule(spec, {**options, "experiment_test_mode": True})


@pytest.mark.parametrize("pulse", [10, 11])
def test_triggerbox_schedule_requires_gap_strictly_greater_than_twice_pulse(execution, pulse):
    _, plan = execution
    spec = plan.ordered_entries()[0].run_spec.model_copy(deep=True)
    spec.display.refresh_hz = 100
    spec.trigger_events = [
        TriggerEvent(frame_index=0, code=1, label="condition_start"),
        TriggerEvent(frame_index=2, code=55, label="oddball_onset"),
    ]
    with pytest.raises(RecordingConfigurationError, match="20 ms apart"):
        validate_recording_trigger_schedule(spec, {
            "recording_backend": "brainproducts_triggerbox", "brainproducts_amplifier": "brainamp",
            "brainproducts_sampling_rate_hz": 1000, "brainproducts_pulse_width_ms": pulse,
        })


@pytest.mark.parametrize("launch_kind", ["run", "session"])
@pytest.mark.parametrize("configuration", [
    {},
    {"brainproducts_amplifier": "actichamp"},
    {"brainproducts_amplifier": "actichamp", "brainproducts_sampling_rate_hz": 100},
])
def test_triggerbox_missing_hardware_or_short_pulse_fails_before_visit_or_output(
    execution, monkeypatch, launch_kind, configuration,
):
    root, plan = execution
    reserve = Mock(side_effect=AssertionError("visit must not be reserved"))
    monkeypatch.setattr(launcher, "reserve_participant_session", reserve)
    adapter = Mock(side_effect=AssertionError("hardware must not be opened"))
    monkeypatch.setattr(triggers, "BrainProductsTriggerBoxBackend", adapter)
    with pytest.raises(LaunchSettingsError, match="Settings > Recording"):
        _launch_at_boundary(root, plan, launch_kind, LaunchSettings(
            recording_backend="brainproducts_triggerbox", verify_refresh_rate=False,
            **configuration,
        ))
    reserve.assert_not_called()
    adapter.assert_not_called()
    assert not (root / "logs" / "acquisition").exists()


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
            brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=1000,
            verify_refresh_rate=False,
        ))
    reserve.assert_not_called()
    adapter.assert_not_called()
    assert not (root / "logs" / "acquisition").exists()


@pytest.mark.parametrize("backend", ["brainproducts_triggerbox", "brainproducts_parallel"])
def test_brainproducts_reset_failure_retains_interrupted_acquisition_without_completed_handoff(
    execution, sample_project, monkeypatch, backend,
):
    root, plan = execution
    sample_project.settings.recording = ProjectRecordingSettings(
        recording_backend=backend, brainproducts_parallel_address=0xD010,
        brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
    )
    config = export_project_config(sample_project, root)
    output = FakeParallel() if backend == "brainproducts_parallel" else FakeTriggerBox()
    output.reset = Mock(side_effect=OSError("zero write failed"))
    adapter_name = "ParallelPortBackend" if backend == "brainproducts_parallel" else (
        "BrainProductsTriggerBoxBackend"
    )
    monkeypatch.setattr(triggers, adapter_name, lambda **_kwargs: output)
    summary = _execute(root, plan, RuntimeWorker(StubEngine({})),
                       recording_backend=backend, brainproducts_parallel_address=0xD010,
                       brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
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
    "brainproducts_parallel",
])
def test_completed_handoff_automatically_retains_hardware_identity_and_event_evidence(
    execution, sample_project, monkeypatch, export_mode, backend,
):
    root, plan = execution
    amplifier_options = (
        {"brainproducts_amplifier": "liveamp", "brainproducts_sampling_rate_hz": 250}
        if backend == "brainproducts_triggerbox" else (
            {"brainproducts_parallel_address": 0xD010, "brainproducts_sampling_rate_hz": 500}
            if backend == "brainproducts_parallel" else {}
        )
    )
    sample_project.settings.recording = ProjectRecordingSettings(
        recording_backend=backend, **amplifier_options,
    )
    config = export_project_config(sample_project, root)
    output = FakeSerial() if backend in ("serial", "biosemi_active_three") else FakeUnicorn()
    if backend in ("serial", "biosemi_active_three"):
        monkeypatch.setattr(triggers, "SerialBackend", lambda *_args, **_kwargs: output)
    elif backend == "brainproducts_triggerbox":
        output = FakeTriggerBox()
        monkeypatch.setattr(triggers, "BrainProductsTriggerBoxBackend",
                            lambda **_kwargs: output)
    elif backend == "brainproducts_parallel":
        output = FakeParallel()
        output.reset = Mock()
        monkeypatch.setattr(triggers, "ParallelPortBackend", lambda **_kwargs: output)
    else:
        _fake_output(monkeypatch, output)
    summary = _execute(
        root, plan, RuntimeWorker(StubEngine({})), export_mode=export_mode,
        recording_backend=backend, toolbox_handoff_config=config.model_dump(mode="json"),
        **amplifier_options,
    )
    assert not summary.aborted
    evidence = _evidence(root)
    path = root / "logs" / "acquisition" / f"{evidence.execution_id}-completed.fpvsconfig"
    completed = read_project_config(path)
    assert completed.format_version == 2
    assert completed.completed_session.ordering_policy == plan.ordering_policy
    assert completed.completed_session.randomization_mode == plan.randomization_mode
    assert completed.completed_session.randomization_seeds == plan.randomization_seeds
    assert (completed.completed_session.randomization_algorithm_version
            == plan.randomization_algorithm_version)
    assert [run.randomization for run in completed.completed_session.ordered_runs] == [
        entry.run_spec.randomization for entry in plan.ordered_entries()
    ]
    assert completed.toolbox.acquisition_profile == evidence.acquisition_profile
    assert completed.recording.recording_backend == backend
    assert evidence.recording.selected_backend == backend
    if backend == "brainproducts_triggerbox":
        assert completed.recording.brainproducts_amplifier == "liveamp"
        assert completed.recording.brainproducts_sampling_rate_hz == 250
        assert evidence.recording.brainproducts_amplifier == "liveamp"
        assert evidence.recording.brainproducts_sampling_rate_hz == 250
    if backend == "brainproducts_parallel":
        assert completed.recording.brainproducts_parallel_address == 0xD010
        assert completed.recording.brainproducts_amplifier == "actichamp"
        assert evidence.recording.parallel_port_address == 0xD010
        assert evidence.recording.serial_port is None
        assert evidence.recording.brainproducts_sampling_rate_hz == 500
        assert output.reset.call_count >= len(plan.ordered_entries())
    if backend in ("biosemi_active_three", "brainproducts_triggerbox", "brainproducts_parallel"):
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


@pytest.mark.parametrize("selection", [
    "serial", "biosemi_active_three", "brainproducts_triggerbox", "brainproducts_parallel",
    "unicorn_udp",
])
def test_inherited_default_handoff_matches_recording_evidence_without_project_edits(
    sample_project, sample_project_root, selection,
):
    from fpvs_studio.core.data_sharing import protocol_fingerprint
    from fpvs_studio.core.project_config import ProjectConfigFile
    from fpvs_studio.core.serialization import save_project_file
    from fpvs_studio.gui.document_runtime import _toolbox_handoff_config

    assert sample_project.settings.recording is None
    project_path = sample_project_root / "project.json"
    save_project_file(sample_project, project_path)
    project_before = sample_project.model_dump(mode="json")
    files_before = {
        path.relative_to(sample_project_root): path.read_bytes()
        for path in sample_project_root.rglob("*") if path.is_file()
    }
    protocol_before = protocol_fingerprint(sample_project, sample_project_root)
    effective_recording = ProjectRecordingSettings(
        recording_backend=selection, unicorn_udp_port=4567,
        brainproducts_serial_port="COM123", brainproducts_pulse_width_ms=20,
        brainproducts_parallel_address=0xD010,
        brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
    )
    options = {
        **effective_recording.model_dump(mode="json"),
        "recording_selection_source": "local_settings", "serial_port": "COM87",
    }
    snapshot = recording_snapshot(options)

    handoff = _toolbox_handoff_config(
        sample_project, sample_project_root, None,
        effective_recording.model_dump(mode="json"),
    )

    config = ProjectConfigFile.model_validate(handoff)
    assert config.recording == effective_recording
    assert config.recording.recording_backend == snapshot.selected_backend == selection
    assert config.toolbox.acquisition_profile == snapshot.acquisition_profile
    assert snapshot.selection_source == "local_settings"
    assert config.toolbox.protocol_sha256 == protocol_before
    assert protocol_fingerprint(sample_project, sample_project_root) == protocol_before
    assert sample_project.model_dump(mode="json") == project_before
    assert sample_project.settings.recording is None
    assert {
        path.relative_to(sample_project_root): path.read_bytes()
        for path in sample_project_root.rglob("*") if path.is_file()
    } == files_before
    if selection == "unicorn_udp":
        assert snapshot.udp_port == 4567
    elif selection == "brainproducts_triggerbox":
        assert snapshot.serial_port == "COM123"
        assert snapshot.trigger_pulse_width_ms == 20
        assert snapshot.brainproducts_amplifier == "actichamp"
        assert snapshot.brainproducts_sampling_rate_hz == 500
    elif selection == "brainproducts_parallel":
        assert snapshot.parallel_port_address == 0xD010
        assert snapshot.serial_port is None
        assert snapshot.brainproducts_amplifier == "actichamp"
    else:
        assert snapshot.serial_port == "COM87"

    plan = compile_session_plan(
        sample_project, project_root=sample_project_root, refresh_hz=60.0, random_seed=12,
    )
    recorder = AcquisitionEvidenceRecorder(
        sample_project_root, [entry.run_spec for entry in plan.ordered_entries()],
        project_id=plan.project_id, session_id=plan.session_id,
        participant_number="007", participant_session_number=1,
        runtime_options={**options, "toolbox_handoff_config": handoff},
    )
    assert recorder.evidence.recording == snapshot
    assert _evidence(sample_project_root).recording == snapshot
    assert sample_project.model_dump(mode="json") == project_before
    assert all(
        (sample_project_root / relative_path).read_bytes() == contents
        for relative_path, contents in files_before.items()
    )
