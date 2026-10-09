"""Exercise the actual GUI coordinator methods with no Qt import or network."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import ValidationError

from fpvs_studio.core.compiler import CompileError, compile_session_plan
from fpvs_studio.core.data_sharing import SharingProfile, SharingSettings, protocol_fingerprint
from fpvs_studio.core.enums import EngineName
from fpvs_studio.core.paths import filesystem_path, project_json_path
from fpvs_studio.core.project_service import discover_project_roots
from fpvs_studio.data_sharing.errors import DataSharingCancelled, DataSharingError
from fpvs_studio.data_sharing.service import ComparisonView, ConditionAggregate, SharingView


class _Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, value=None):
        for callback in self.callbacks:
            callback() if value is None else callback(value)


class _Object:
    def __init__(self, _parent):
        pass


class _Timer(_Object):
    def __init__(self, parent):
        super().__init__(parent)
        self.timeout = _Signal()
        self.interval = None

    def setSingleShot(self, _value):
        pass

    def start(self, interval):
        self.interval = interval

    def stop(self):
        self.interval = None


@dataclass
class _Result:
    value: object = None
    error: Exception | None = None
    cancelled: bool = False


class _Job:
    def __init__(self, callback):
        self.callback = callback
        self.finished = _Signal()
        self.cancel_event = Event()
        self.done = False
        self.finish_on_shutdown = False

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        assert not self.done
        self.done = True
        try:
            result = _Result(value=self.callback(lambda *_args: None, self.cancel_event))
        except Exception as error:
            result = _Result(error=error)
        self.finished.emit(result)


class _Lifecycle:
    def __init__(self):
        self.shutdown_started = _Signal()
        self.is_shutting_down = False
        self.jobs = []

    def start_task(self, callback, **kwargs):
        assert not self.is_shutting_down or kwargs.get("finish_on_shutdown")
        job = _Job(callback)
        job.finish_on_shutdown = kwargs.get("finish_on_shutdown", False)
        self.jobs.append(job)
        return job


class _Window:
    def __init__(self, root, project):
        self.document = SimpleNamespace(project_root=root, project=project)
        self.busy = False
        self.visible = True

    def isVisible(self):
        return self.visible

    def is_launch_busy(self):
        return self.busy


class _Backend:
    def __init__(self):
        self.view = SharingView(SharingSettings())
        self.calls = []

    def configured(self):
        return True

    def load_view(self, root, fingerprint, _cancel):
        self.calls.append(("load", root, fingerprint))
        return self.view

    def sync_project(
        self, root, fingerprint, _cancel, *, release_held=False,
        retry_offline=False, fetch_comparison=True,
    ):
        self.calls.append(("sync", root, fingerprint, release_held))
        return self.view

    def sync_startup_project(self, root, cancel):
        if cancel.is_set():
            raise DataSharingCancelled()
        self.calls.append(("startup", root))
        return self.view

    def set_sharing_enabled(self, root, enabled, fingerprint, _cancel):
        self.calls.append(("enable", root, enabled, fingerprint))
        self.view = replace(self.view, settings=self.view.settings.model_copy(
            update={"enabled": enabled},
        ))
        return self.view

    def enroll_project(self, *_args):
        pytest.fail("Opening a project must never enroll it")

    def archive_project(self, root, fingerprint, _cancel):
        self.calls.append(("archive", root, fingerprint))
        return self.view


def _coordinator(lifecycle, fingerprint, load_preferences):
    path = Path(__file__).resolve().parents[2] / "src/fpvs_studio/gui/data_sharing_controller.py"
    parsed = ast.parse(path.read_text(encoding="utf-8"))
    node = next(node for node in parsed.body if isinstance(node, ast.ClassDef))
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        node,
    ], type_ignores=[])
    namespace = {
        "QObject": _Object, "QTimer": _Timer, "update_lifecycle": lambda _app: lifecycle,
        "isValid": lambda _window: True, "protocol_fingerprint": fingerprint,
        "DataSharingCancelled": DataSharingCancelled, "UpdateTaskResult": _Result,
        "DataSharingError": DataSharingError, "replace": replace, "Event": Event,
        "load_settings": load_preferences,
        "SharingView": SharingView, "ConditionAggregate": ConditionAggregate,
        "ComparisonRow": lambda **values: SimpleNamespace(**values),
        "cast": cast, "_RETRY_LIMIT": 4, "_LOGGER": logging.getLogger(__name__),
        "_STOPPING_MESSAGE": "Stopping uploads…",
        "discover_project_roots": discover_project_roots,
        "filesystem_path": filesystem_path, "project_json_path": project_json_path,
        "Path": Path,
    }
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace["DataSharingController"]


@pytest.fixture
def state(sample_project, tmp_path):
    lifecycle, backend = _Lifecycle(), _Backend()
    fingerprints = []

    def fingerprint(project, root, *, cancelled):
        if cancelled():
            raise InterruptedError("Protocol hash cancelled.")
        fingerprints.append((project, root))
        return "a" * 64

    window = _Window(tmp_path, sample_project)
    current = [window]
    controller = _coordinator(lifecycle, fingerprint, lambda _root: backend.view.settings)(
        None, current_window=lambda: current[0], backend=backend,
    )
    return SimpleNamespace(
        controller=controller, lifecycle=lifecycle, backend=backend,
        window=window, current=current, fingerprints=fingerprints, root=tmp_path,
    )


def _profile():
    return SharingProfile(
        experiment_id="reviewed-study", experiment_version="1.0.0", protocol_sha256="a" * 64,
        title="Reviewed study", device_id="device-1",
    )


def _finish_jobs(state):
    for _ in range(20):
        job = next((job for job in state.lifecycle.jobs if not job.done), None)
        if job is None:
            return
        job.run()
    pytest.fail("Startup did not complete its bounded pass")


def test_startup_discovers_and_drains_unopened_projects_once(state):
    first = state.root / "study1"
    second = state.root / "group" / "study2"
    remembered = state.root.parent / "remembered"
    for root in (first, second, remembered):
        root.mkdir(parents=True)
        (root / "project.json").write_text("{}")
    state.controller.startup(state.root, (first, remembered, state.root / "missing"))
    assert not state.backend.calls and state.controller._window is None
    _finish_jobs(state)
    assert state.backend.calls == [
        ("startup", root.resolve()) for root in (second, first, remembered)
    ]
    count = len(state.lifecycle.jobs)
    state.controller.startup(state.root, ())
    assert len(state.lifecycle.jobs) == count


def test_open_project_takes_priority_and_startup_resumes_after_run(state):
    (state.root / "project.json").write_text("{}")
    state.controller.startup(state.root, ())
    discovery = state.lifecycle.jobs[-1]
    state.controller.opened(state.window)
    assert discovery.cancel_event.is_set()
    discovery.run()
    project_job = state.lifecycle.jobs[-1]
    assert project_job is not discovery
    project_job.run()
    discovery = state.lifecycle.jobs[-1]
    discovery.run()
    startup_job = state.lifecycle.jobs[-1]
    launched = []
    state.window.busy = True
    state.controller.session_started(state.window, lambda: launched.append(True))
    assert startup_job.cancel_event.is_set() and not launched
    startup_job.run()
    assert launched == [True] and state.controller._job is None
    assert not any(call[0] == "startup" for call in state.backend.calls)
    state.window.busy = False
    state.controller.session_completed(state.window)
    _finish_jobs(state)
    assert state.backend.calls[-1][0] == "load"  # Current off document uses its own guarded job.


def test_startup_for_open_project_hashes_unsaved_snapshot_without_comparison(state):
    state.backend.view = SharingView(SharingSettings(enabled=True, profile=_profile()))
    (state.root / "project.json").write_text("{}")
    state.controller.opened(state.window)
    state.lifecycle.jobs[-1].run()
    edited = state.window.document.project.model_copy(deep=True)
    edited.settings.protocol.base_hz = 7.0
    state.window.document.project = edited
    calls = []

    def sync(root, fingerprint, cancel, **options):
        calls.append(options)
        return state.backend.view

    state.backend.sync_project = sync
    state.controller.startup(state.root, ())
    _finish_jobs(state)
    assert state.fingerprints[-1][0] is not edited
    assert state.fingerprints[-1][0].settings.protocol.base_hz == 7.0
    assert calls == [{"release_held": False, "retry_offline": True, "fetch_comparison": False}]
    assert not any(call[0] == "startup" for call in state.backend.calls)


def test_shutdown_cancels_startup_and_never_starts_more_jobs(state):
    (state.root / "project.json").write_text("{}")
    state.controller.startup(state.root, ())
    state.lifecycle.is_shutting_down = True
    state.lifecycle.shutdown_started.emit()
    job = state.lifecycle.jobs[-1]
    assert job.cancel_event.is_set()
    job.run()
    assert len(state.lifecycle.jobs) == 1 and not state.backend.calls


def test_startup_error_is_nonmodal_and_other_projects_continue(state):
    for name in ("study1", "study2"):
        folder = state.root / name
        folder.mkdir()
        (folder / "project.json").write_text("{}")
    notices, calls = [], []
    state.controller._startup_status = notices.append

    def startup(root, cancel):
        calls.append(root)
        if root.name == "study1":
            raise ValueError("Malformed local report; retained for review")
        return SharingView(SharingSettings(), status="waiting_connection", pending_count=1)

    state.backend.sync_startup_project = startup
    state.controller.startup(state.root, ())
    _finish_jobs(state)
    assert [root.name for root in calls] == ["study1", "study2"]
    assert any("need attention" in notice for notice in notices)
    assert "need attention" in notices[-1]  # An offline project cannot hide a repair issue.
    assert state.controller.dialog is None


def test_opening_unenrolled_experiment_reads_without_activation(state):
    state.controller.opened(state.window)
    assert state.backend.calls == []
    state.lifecycle.jobs[-1].run()
    assert [call[0] for call in state.backend.calls] == ["load"]
    assert not state.controller._view.settings.enabled
    assert state.controller._retry_timer.interval is None
    assert state.fingerprints == []
    launched = []
    state.window.busy = True
    state.controller.session_started(state.window, lambda: launched.append(True))
    assert launched == [True]


@pytest.mark.parametrize("operation", ["load", "sync", "retry"])
def test_default_off_reads_skip_hashing_and_network(state, operation):
    state.controller.opened(state.window)
    state.lifecycle.jobs[-1].run()
    state.controller._request(operation)
    state.lifecycle.jobs[-1].run()
    assert state.fingerprints == []
    assert [call[0] for call in state.backend.calls] == ["load", "load"]
    assert all(call[2] == "" for call in state.backend.calls)


def test_explicit_connect_hashes_protocol_without_automatic_enable(state):
    state.controller.opened(state.window)
    state.lifecycle.jobs[-1].run()

    def enroll(root, code, fingerprint, _cancel, *, project_id=None):
        state.backend.calls.append(("connect", root, code, fingerprint))
        state.backend.view = SharingView(SharingSettings(profile=_profile()))
        return state.backend.view

    state.backend.enroll_project = enroll
    state.controller._request("connect", ("lab-issued-code", ""))
    state.lifecycle.jobs[-1].run()
    assert len(state.fingerprints) == 1
    assert state.backend.calls[-1] == ("connect", state.root, "lab-issued-code", "a" * 64)
    assert not state.controller._view.settings.enabled
    assert all(call[0] != "sync" for call in state.backend.calls)


def test_enabling_syncs_then_optout_cancels_and_outranks_queued_refresh(state):
    state.backend.view = SharingView(SharingSettings(profile=_profile()))
    state.controller.opened(state.window)
    state.lifecycle.jobs[-1].run()
    state.controller._enable(True)
    state.lifecycle.jobs[-1].run()
    assert [call[0] for call in state.backend.calls][-2:] == ["enable", "sync"]
    state.controller._request("sync")
    pending = state.lifecycle.jobs[-1]
    state.controller._enable(False)
    off_job = state.lifecycle.jobs[-1]
    assert pending.cancel_event.is_set()
    state.controller.session_completed(state.window)
    assert state.controller._off_job is off_job
    fingerprint_count = len(state.fingerprints)
    off_job.run()
    assert len(state.fingerprints) == fingerprint_count  # Opt-out never hashes stimuli.
    assert state.backend.calls[-1][0:3] == ("enable", state.root, False)
    assert not state.backend.view.settings.enabled
    sync_calls = sum(call[0] == "sync" for call in state.backend.calls)
    pending.run()
    state.lifecycle.jobs[-1].run()
    assert sum(call[0] == "sync" for call in state.backend.calls) == sync_calls


def test_worker_captures_project_and_rejects_old_result_after_edit(state):
    state.backend.view = SharingView(SharingSettings(profile=_profile()))
    state.controller.opened(state.window)
    original = state.window.document.project
    state.window.document.project = original.model_copy(deep=True)
    state.lifecycle.jobs[-1].run()
    captured, root = state.fingerprints[0]
    assert captured == original and captured is not original
    assert root == state.root
    assert state.controller._view is None
    assert len(state.lifecycle.jobs) == 2
    state.lifecycle.jobs[-1].run()
    assert state.controller._view is state.backend.view


def test_project_edit_cannot_replace_queued_optout_with_a_read(state):
    state.backend.view = SharingView(SharingSettings(profile=_profile(), enabled=True))
    state.controller.opened(state.window)
    state.lifecycle.jobs[-1].run()
    state.controller._request("sync")
    pending = state.lifecycle.jobs[-1]
    state.controller._enable(False)
    off_job = state.lifecycle.jobs[-1]
    state.window.document.project = state.window.document.project.model_copy(deep=True)
    pending.run()
    off_job.run()
    assert state.backend.calls[-1][0:3] == ("enable", state.root, False)
    assert not state.backend.view.settings.enabled


@pytest.mark.parametrize("busy", [False, True])
@pytest.mark.parametrize("transition", ["close", "cancel", "project_handoff", "shutdown"])
def test_requested_optout_survives_all_lifecycle_transitions(state, busy, transition):
    state.backend.view = SharingView(SharingSettings(profile=_profile(), enabled=True))
    state.controller.opened(state.window)
    state.lifecycle.jobs[-1].run()
    previous_sync_count = sum(call[0] == "sync" for call in state.backend.calls)
    if busy:
        state.controller._request("sync")
    state.controller._enable(False)
    off_job = state.lifecycle.jobs[-1]
    assert off_job.finish_on_shutdown
    if transition == "close":
        state.controller._close()
    elif transition == "cancel":
        state.controller._action("cancel")
    elif transition == "project_handoff":
        replacement = _Window(state.root / "replacement", state.window.document.project)
        state.current[0] = replacement
        state.controller.opened(replacement)
    else:
        state.lifecycle.is_shutting_down = True
        state.lifecycle.shutdown_started.emit()
    # Even general job cancellation cannot cancel the requested local settings save.
    off_job.cancel()
    off_job.run()
    assert ("enable", state.root, False, "a" * 64) in state.backend.calls
    assert not state.backend.view.settings.enabled
    for _ in range(10):
        unfinished = next((job for job in state.lifecycle.jobs if not job.done), None)
        if unfinished is None:
            break
        unfinished.run()
    assert not any(not job.done for job in state.lifecycle.jobs)
    assert sum(call[0] == "sync" for call in state.backend.calls) == previous_sync_count


@pytest.mark.parametrize("visible_dialog", [False, True])
def test_optout_write_failure_is_actionable_and_logged(state, caplog, visible_dialog):
    state.backend.view = SharingView(SharingSettings(profile=_profile(), enabled=True))
    state.controller.opened(state.window)
    state.lifecycle.jobs[-1].run()
    statuses = []
    if visible_dialog:
        state.controller.dialog = SimpleNamespace(
            set_state=lambda **values: statuses.append(values["status"]),
            set_project_url=lambda _url: None,
            set_comparison=lambda *_args, **_values: None,
            set_busy=lambda _busy, message="": statuses.append(message),
            enabled_checkbox=SimpleNamespace(setEnabled=lambda _value: None),
        )

    def fail(*_args):
        raise OSError("The settings folder is read-only.")

    state.backend.set_sharing_enabled = fail
    state.controller._enable(False)
    state.lifecycle.jobs[-1].run()
    assert "Could not finish disabling experiment sharing" in caplog.text
    assert state.backend.view.settings.enabled
    if visible_dialog:
        assert any("Could not turn sharing off" in status for status in statuses)


def test_durable_off_is_shown_when_postsave_history_read_fails(state, caplog):
    state.backend.view = SharingView(SharingSettings(profile=_profile(), enabled=True))
    state.controller.opened(state.window)
    state.lifecycle.jobs[-1].run()

    def persisted_then_failed(*_args):
        state.backend.view = replace(
            state.backend.view,
            settings=state.backend.view.settings.model_copy(update={"enabled": False}),
        )
        raise OSError("Upload history is malformed.")

    state.backend.set_sharing_enabled = persisted_then_failed
    state.controller._enable(False)
    state.lifecycle.jobs[-1].run()
    assert not state.controller._view.settings.enabled
    assert "Sharing is off, but upload history needs review" in state.controller._view.error
    assert "Could not finish disabling experiment sharing" in caplog.text


@pytest.mark.parametrize("operation", ["load", "enable"])
def test_repaired_history_clears_old_optout_error_only_for_accepted_result(state, operation):
    state.backend.view = SharingView(SharingSettings(profile=_profile(), enabled=True))
    state.controller.opened(state.window)
    state.lifecycle.jobs[-1].run()
    rendered = []
    state.controller.dialog = SimpleNamespace(
        set_state=lambda **values: rendered.append(values),
        set_project_url=lambda _url: None,
        set_comparison=lambda *_args, **_values: None,
        set_busy=lambda *_args: None,
        enabled_checkbox=SimpleNamespace(setEnabled=lambda _value: None),
    )
    set_enabled = state.backend.set_sharing_enabled

    def persisted_then_failed(*_args):
        state.backend.view = replace(
            state.backend.view,
            settings=state.backend.view.settings.model_copy(update={"enabled": False}),
        )
        raise OSError("Upload history is malformed.")

    state.backend.set_sharing_enabled = persisted_then_failed
    state.controller._enable(False)
    state.lifecycle.jobs[-1].run()
    error = state.controller._off_error
    assert "Sharing is off, but upload history needs review" in error

    state.backend.set_sharing_enabled = set_enabled
    state.backend.view = replace(
        state.backend.view, status="ready" if operation == "enable" else "off",
    )
    state.controller._request("load")
    canceled = state.lifecycle.jobs[-1]
    canceled.cancel()
    canceled.run()
    assert state.controller._off_error == error
    assert rendered[-1]["status"] == error

    state.controller._request(operation, True if operation == "enable" else None)
    state.lifecycle.jobs[-1].run()
    assert state.controller._off_error == ""
    assert rendered[-1]["enabled"] is (operation == "enable")
    assert "needs review" not in rendered[-1]["status"]
    assert rendered[-1]["status"] == (
        "Sharing is enabled. New eligible sessions will be reported automatically."
        if operation == "enable" else "Sharing is off. Unsent reports are paused."
    )


def test_launch_gate_waits_for_canceled_network_job_then_resumes(state):
    state.controller.opened(state.window)
    state.lifecycle.jobs[-1].run()
    state.controller._request("sync")
    job = state.lifecycle.jobs[-1]
    launched = []
    state.window.busy = True
    state.controller.session_started(state.window, lambda: launched.append(True))
    assert job.cancel_event.is_set()
    assert launched == []
    count = len(state.lifecycle.jobs)
    state.controller._request("sync")
    assert len(state.lifecycle.jobs) == count
    job.run()
    assert launched == [True]
    assert state.controller._job is None


def test_launch_interrupts_hash_without_upload_and_releases_gate(state):
    state.backend.view = SharingView(SharingSettings(profile=_profile(), enabled=True))
    state.controller.opened(state.window)
    launched = []

    def interrupted_hash(_project, _root, *, cancelled):
        state.window.busy = True
        state.controller.session_started(state.window, lambda: launched.append(True))
        assert cancelled()
        assert launched == []
        raise InterruptedError("Protocol verification cancelled.")

    state.controller._request.__func__.__globals__["protocol_fingerprint"] = interrupted_hash
    state.lifecycle.jobs[-1].run()
    assert launched == [True]
    assert state.backend.calls == []
    assert state.controller._job is None
    assert state.controller._view is None
    assert state.controller._retry_timer.interval is None


def test_launch_gate_is_immediate_when_idle_and_never_resumes_after_shutdown(state):
    state.controller.opened(state.window)
    state.lifecycle.jobs[-1].run()
    launched = []
    state.controller.session_started(state.window, lambda: launched.append("idle"))
    assert launched == ["idle"]
    state.controller._request("sync")
    job = state.lifecycle.jobs[-1]
    state.window.busy = True
    state.controller.session_started(state.window, lambda: launched.append("closing"))
    state.lifecycle.is_shutting_down = True
    state.lifecycle.shutdown_started.emit()
    job.run()
    assert launched == ["idle"]


def test_project_handoff_cancels_old_job_and_uses_new_root(state, tmp_path):
    state.controller.opened(state.window)
    old_job = state.lifecycle.jobs[-1]
    replacement = _Window(tmp_path / "replacement", state.window.document.project)
    state.current[0] = replacement
    state.controller.opened(replacement)
    assert old_job.cancel_event.is_set()
    old_job.run()
    assert state.backend.calls == []
    state.lifecycle.jobs[-1].run()
    assert state.backend.calls[0][1] == replacement.document.project_root


def test_launch_and_shutdown_cancel_work_and_bound_retry(state):
    state.backend.view = SharingView(
        SharingSettings(profile=_profile(), enabled=True), pending_count=1,
    )
    state.controller.opened(state.window)
    state.lifecycle.jobs[-1].run()
    assert state.controller._retry_timer.interval == 60000
    state.controller._request("sync")
    job = state.lifecycle.jobs[-1]
    state.window.busy = True
    state.controller.session_started(state.window)
    assert job.cancel_event.is_set()
    assert state.controller._retry_timer.interval is None
    count = len(state.lifecycle.jobs)
    state.controller._retry()
    assert len(state.lifecycle.jobs) == count
    job.run()
    state.window.busy = False
    state.controller._retries = 4
    state.controller._schedule_retry()
    assert state.controller._retry_timer.interval is None
    state.lifecycle.is_shutting_down = True
    state.lifecycle.shutdown_started.emit()
    state.controller.session_completed(state.window)
    assert len(state.lifecycle.jobs) == count


def test_metric_uses_backend_accuracy_and_exposes_denominators(state):
    row = ConditionAggregate("condition-1", "Condition", 100, 90, 10, 220.0, 90.0, 3)
    assert state.controller._metric(row, shared=True) == (
        "90.0%\n90 hits / 100 targets · 10 sessions · 3 enrollments"
    )
    assert state.controller._metric(replace(row, eligible=False), shared=True) == (
        "Not enough compatible reference data"
    )


def test_archiving_is_explicit_local_work_without_hashing_or_network(state):
    state.controller.opened(state.window)
    state.lifecycle.jobs[-1].run()
    fingerprint_count = len(state.fingerprints)
    state.controller._request("archive")
    state.lifecycle.jobs[-1].run()
    assert len(state.fingerprints) == fingerprint_count
    assert state.backend.calls[-1] == ("archive", state.root, "")
    assert all(call[0] != "sync" for call in state.backend.calls)


def test_archiving_keeps_comparison_for_the_retained_latest_session(state):
    remote = ComparisonView(
        "available", "reviewed-study", "1.0.0", "a" * 64, (), 10, 3, "",
    )
    state.backend.view = SharingView(
        SharingSettings(profile=_profile()), latest_completed_at="2026-10-05T15:00:00Z",
        remote=remote,
    )
    state.controller.opened(state.window)
    state.lifecycle.jobs[-1].run()
    state.backend.view = replace(state.backend.view, remote=None)
    state.controller._request("archive")
    state.lifecycle.jobs[-1].run()
    assert state.controller._view.remote is remote


@pytest.mark.parametrize("mismatch", ["experiment_id", "experiment_version", "protocol_sha256"])
def test_comparison_never_renders_unrelated_experiment_version_or_protocol(state, mismatch):
    row = ConditionAggregate("condition-1", "Condition", 100, 90, 10, 220.0, 90.0, 3)
    remote = ComparisonView(
        "available", "reviewed-study", "1.0.0", "a" * 64, (row,), 10, 3, "",
    )
    remote = replace(remote, **{mismatch: "b" * 64 if mismatch == "protocol_sha256" else "other"})
    state.controller._protocol = "a" * 64
    state.controller._view = SharingView(
        SharingSettings(profile=_profile(), enabled=True), local_conditions=(row,), remote=remote,
    )
    renders = []
    state.controller.dialog = SimpleNamespace(
        set_state=lambda **_values: None, set_busy=lambda *_values: None,
        set_project_url=lambda _url: None,
        set_comparison=lambda rows, **values: renders.append((rows, values)),
    )
    state.controller._render()
    assert renders[0][0][0].shared == "Not enough compatible reference data"
    assert "does not match" in renders[0][1]["notice"]
    assert "requires at least" not in renders[0][1]["notice"]
    assert "does not measure EEG quality" in renders[0][1]["details"]


@pytest.mark.parametrize("message", ["", "Not enough compatible reference data."])
def test_comparison_keeps_cohort_rules_separate_from_current_notice(state, message):
    row = ConditionAggregate("condition-1", "Condition", 100, 90, 10, 220.0, 90.0, 3)
    remote = ComparisonView(
        "available", "reviewed-study", "1.0.0", "a" * 64, (row,), 24, 4, message,
    )
    state.controller._protocol = "a" * 64
    state.controller._view = SharingView(
        SharingSettings(profile=_profile(), enabled=True), local_conditions=(row,), remote=remote,
        latest_completed_at="2026-10-08T15:00:00Z",
    )
    renders = []
    state.controller.dialog = SimpleNamespace(
        set_state=lambda **_values: None, set_busy=lambda *_values: None,
        set_project_url=lambda _url: None,
        set_comparison=lambda rows, **values: renders.append((rows, values)),
    )
    state.controller._render()
    rows, values = renders[0]
    assert rows[0].shared != "Not enough compatible reference data"
    assert values["notice"] == message
    assert "24 session reports from 4 device enrollments" in values["details"]
    assert "does not measure EEG quality" in values["details"]
    assert "2026-10-08T15:00:00Z" in values["scope"]
    assert "this enrollment's reports are excluded" in values["scope"]


def _document_launch_methods(namespace):
    repository = Path(__file__).resolve().parents[2]
    methods = []
    for relative, names in (
        ("src/fpvs_studio/gui/document_runtime.py", {"compile_session", "launch_compiled_session"}),
        ("src/fpvs_studio/gui/document.py", {"_replace_project"}),
    ):
        parsed = ast.parse((repository / relative).read_text(encoding="utf-8"))
        for node in ast.walk(parsed):
            if isinstance(node, ast.FunctionDef) and node.name in names:
                node.decorator_list = []
                methods.append(node)
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *methods,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), "document_launch_guard", "exec"), namespace)
    return namespace


@pytest.mark.parametrize("edited_after_compilation", [False, True])
def test_launch_hash_belongs_to_current_compiled_plan_only(
    sample_project, sample_project_root, edited_after_compilation,
):
    launches, hashed_projects = [], []

    def sharing_hash(project, root):
        hashed_projects.append(project)
        return protocol_fingerprint(project, root)

    def launch(root, plan, **kwargs):
        launches.append((root, plan, kwargs["launch_settings"]))
        return SimpleNamespace()

    namespace = _document_launch_methods({
        "cast": cast, "CompileError": CompileError, "ValidationError": ValidationError,
        "compile_session_plan": compile_session_plan, "EngineName": EngineName,
        "DocumentError": RuntimeError, "LaunchSummary": object,
        "LaunchSettings": lambda **values: SimpleNamespace(**values),
        "_sharing_protocol": sharing_hash, "_document_dependency": lambda _name: launch,
        "category_conflict_condition_ids": lambda _project: (),
    })
    document = SimpleNamespace(
        _project=sample_project, _project_root=sample_project_root, _last_session_plan=None,
        experiment_test_mode_enabled=False, local_testing_enabled=False,
        recording_configuration={"recording_backend": "serial"},
        attentional_blink_pilot_mode_enabled=False, _session_export_mode="full",
        validate_recording_launch=lambda: None, refresh_participant_summary_if_stale=lambda: None,
        ensure_unused_session_seed_for_launch=lambda: None,
        validation_report=lambda **_values: SimpleNamespace(is_valid=True),
        session_plan_changed=_Signal(), project_changed=_Signal(), _set_dirty=lambda _value: None,
    )
    plan = namespace["compile_session"](document, refresh_hz=60.0)
    if edited_after_compilation:
        changed = sample_project.model_copy(update={"conditions": [
            condition.model_copy(update={"instructions": "Different reviewed instructions."})
            for condition in sample_project.conditions
        ]})
        namespace["_replace_project"](document, changed)
        assert document._last_session_plan is None
    namespace["launch_compiled_session"](
        document, plan, participant_number="1", display_index=None,
    )
    assert len(launches) == 1 and launches[0][1] is plan  # Local launch still proceeds.
    supplied = launches[0][2].sharing_protocol_sha256
    if edited_after_compilation:
        assert supplied is None
        assert hashed_projects == []
    else:
        assert supplied == protocol_fingerprint(sample_project, sample_project_root)
        assert hashed_projects == [sample_project]
