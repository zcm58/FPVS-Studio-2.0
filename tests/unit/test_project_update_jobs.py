"""Run the real update coordinator with worker fakes and no Qt imports."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from types import MethodType, SimpleNamespace
from typing import cast

import pytest

from fpvs_studio.core.library_origin import LibraryOriginError, LibraryProjectOrigin
from fpvs_studio.core.project_bundle import ProjectBundleCancelled
from fpvs_studio.core.project_bundle_update import (
    ProjectBundleRecoveryError,
    ProjectBundleUpdateResult,
)
from fpvs_studio.data_sharing.errors import DataSharingCancelled, DataSharingError
from fpvs_studio.library.errors import LibraryCancelled
from fpvs_studio.library.models import LibraryItem
from fpvs_studio.library.project_updates import ProjectUpdateResult


class Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback, *_args):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in self.callbacks:
            callback(*args)


class Bridge:
    def __init__(self, _parent):
        self.stage_changed = Signal()
        self.deleted = False

    def deleteLater(self):
        self.deleted = True


class Job:
    def __init__(self, callback):
        self.callback = callback
        self.cancel_event = Event()
        self.finished = Signal()

    def cancel(self):
        self.cancel_event.set()

    def run(self, *, late_cancel=False):
        try:
            value = self.callback(lambda *_args: None, self.cancel_event)
            outcome = SimpleNamespace(value=value, error=None, cancelled=False)
        except Exception as error:
            outcome = SimpleNamespace(value=None, error=error, cancelled=False)
        if late_cancel:
            self.cancel_event.set()
            outcome.cancelled = True
        self.finished.emit(outcome)


@dataclass
class Checked:
    result: ProjectUpdateResult
    catalog: object = None
    can_download_separately: bool = True
    reporting_error: str = ""
    reporting_notice: str = ""


@dataclass
class Updated:
    result: ProjectBundleUpdateResult
    reconnect_required: bool


@pytest.fixture
def update_job(tmp_path):
    source = Path(__file__).parents[2] / "src/fpvs_studio/gui/project_update_controller.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == "ProjectUpdateController")
    names = {"_current", "_update_current", "_action", "_run_pending", "_queue_check",
             "_save_origin", "_invalidate_failed_update_candidate"}
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    calls, jobs, applied, messages = [], [], [], []
    origin = LibraryProjectOrigin(
        service_url="https://library.example.test", item_id="study", installed_version="1.0.0",
        bundle_sha256="b" * 64, local_project_id="local-study",
    )
    item = LibraryItem(
        item_id="study", version="2.0.0", title="Study", description="New protocol",
        experiment_category="fpvs_oddball", filename="study-2.0.0.fpvsbundle",
        size_bytes=100, uncompressed_size_bytes=200, file_count=2,
        sha256="a" * 64, min_studio_version="1.0.0",
    )
    flags = SimpleNamespace(save=True, fixation=True, busy=False, source_changed=False,
                            fail=False, current=True, apply_fail=False, pending=False,
                            pending_late=False, report_checks=0, locked=False)
    project = SimpleNamespace(meta=SimpleNamespace(project_id="local-study", name="Local study"))
    document = SimpleNamespace(project_root=tmp_path, project=project)

    def fail_window():
        flags.locked = True
        window._project_update_reload_failed = True

    window = SimpleNamespace(
        document=document, isVisible=lambda: True, is_launch_busy=lambda: flags.busy,
        _project_update_reload_failed=False,
        _allow_project_handoff_during_fixation_load=lambda: flags.fixation,
        prepare_project_handoff=lambda: flags.save,
        start_bundle_import_processing=lambda **kw: calls.append(("freeze", kw)),
        finish_bundle_import_processing=lambda **kw: calls.append(("unfreeze", kw)),
        show_home=lambda: calls.append("home"),
        fail_library_project_update=fail_window,
    )
    result = ProjectUpdateResult("update_available", origin, item)
    committed = ProjectBundleUpdateResult(
        scaffold=SimpleNamespace(project_root=tmp_path, project=project),
        backup_path=tmp_path / "backup", manifest=SimpleNamespace(project_id="local-study"),
    )

    def snapshot(_root, **_kwargs):
        calls.append("snapshot")
        return SimpleNamespace(origin=origin.model_copy(update={"installed_version": "1.5.0"})
                               if flags.source_changed else origin)

    def download(_item, **_kwargs):
        calls.append("download")
        return tmp_path / item.filename

    def reporting(*_args, **_kwargs):
        flags.report_checks += 1
        if flags.pending or (flags.pending_late and flags.report_checks == 2):
            raise DataSharingError("Resolve saved Results reports first", code="pending_results")
        return SimpleNamespace(reconnect_required=False)

    def apply(value):
        if flags.apply_fail:
            raise RuntimeError("Cannot refresh the window")
        calls.append("adopt")
        applied.append(value)

    def commit(*_args, **_kwargs):
        _kwargs["precommit_check"]()
        calls.append("commit")
        if flags.fail:
            raise OSError("Disk is full")
        return committed

    def start(callback, **kwargs):
        calls.append(("start", kwargs))
        job = Job(callback)
        jobs.append(job)
        return job

    namespace = {
        "Path": Path, "Event": Event, "cast": cast, "_Checked": Checked,
        "LibraryProjectOrigin": LibraryProjectOrigin, "LibraryOriginError": LibraryOriginError,
        "LibraryCancelled": LibraryCancelled, "ProjectBundleCancelled": ProjectBundleCancelled,
        "ProjectBundleUpdateResult": ProjectBundleUpdateResult,
        "UpdateTaskResult": SimpleNamespace, "_Updated": Updated,
        "ProjectBundleRecoveryError": ProjectBundleRecoveryError,
        "DataSharingError": DataSharingError, "DataSharingCancelled": DataSharingCancelled,
        "inspect_project_update_reporting": reporting,
        "ensure_project_update_recovery_ready": lambda *_args, **_kwargs: None,
        "Qt": SimpleNamespace(ConnectionType=SimpleNamespace(QueuedConnection=1)),
        "ProjectUpdateResult": ProjectUpdateResult, "ProgressSignalBridge": Bridge,
        "isValid": lambda _widget: True, "capture_project_update_snapshot": snapshot,
        "update_project_bundle": commit, "_LOGGER": logging.getLogger(__name__),
        "load_library_origin": lambda _root: origin,
        "check_project_update": lambda *_args, **_kwargs: result,
        "check_library_install": lambda *_args, **_kwargs: SimpleNamespace(
            state="installed", message="Already installed elsewhere",
        ),
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *methods,
    ], type_ignores=[])), str(source), "exec"), namespace)
    context = SimpleNamespace(
        _result=result, _window=window, _current_window=lambda: window if flags.current else None,
        _lifecycle=SimpleNamespace(is_shutting_down=False, start_task=start),
        _job=None, _generation=1, _importing=False, _pending_check=None, _last_backup=None,
        _update_bridge=None, _studio_root=lambda: tmp_path,
        _apply_update=apply, _error=str,
        _poll_timer=SimpleNamespace(stop=lambda: None),
        _offer_timer=SimpleNamespace(stop=lambda: None),
        dialog=SimpleNamespace(
            set_busy=lambda *args: messages.append(args), clear_install_candidate=lambda: None,
            check_button=SimpleNamespace(setEnabled=lambda _enabled: None),
            relink_button=SimpleNamespace(setEnabled=lambda _enabled: None),
            auto_check_checkbox=SimpleNamespace(setEnabled=lambda _enabled: None),
            link_panel=SimpleNamespace(setEnabled=lambda _enabled: None),
        ),
        client=SimpleNamespace(service_url=origin.service_url, download=download,
                               release_download=lambda: calls.append("release")),
    )
    context._checked = lambda value, **_kwargs: setattr(context, "_result", value.result)
    for name in names:
        setattr(context, name, MethodType(namespace[name], context))
    return SimpleNamespace(controller=context, flags=flags, jobs=jobs, calls=calls,
                           applied=applied, messages=messages, result=committed)


@pytest.mark.parametrize("blocked", ["save", "fixation", "unknown-version"])
def test_current_update_waits_for_authorized_saved_project(update_job, blocked):
    s = update_job
    if blocked == "unknown-version":
        s.controller._result = ProjectUpdateResult(
            "version_unknown", s.controller._result.origin, s.controller._result.latest_item,
        )
    else:
        setattr(s.flags, blocked, False)
    s.controller._update_current()
    assert s.jobs == []
    assert s.calls == []


def test_update_snapshots_before_transfer_and_applies_only_worker_success(update_job):
    s = update_job
    s.controller._update_current()
    assert s.calls[0][0] == "freeze"
    assert "download" not in s.calls
    assert s.controller._importing
    s.jobs[0].run()
    assert [x for x in s.calls if isinstance(x, str)] == [
        "snapshot", "download", "commit", "adopt", "home", "release",
    ]
    assert s.applied == [s.result]
    assert s.controller._last_backup[1] == s.result.backup_path
    assert not s.controller._importing and s.controller._job is None
    assert any(isinstance(x, tuple) and x[0] == "unfreeze" for x in s.calls)


def test_late_cancel_preserves_committed_result(update_job):
    s = update_job
    s.controller._update_current()
    s.jobs[0].run(late_cancel=True)
    assert s.applied == [s.result]
    assert s.calls.count("release") == 1


@pytest.mark.parametrize("failure", ["source_changed", "fail"])
def test_failure_does_not_replace_open_document_and_releases_lease(update_job, failure):
    s = update_job
    setattr(s.flags, failure, True)
    s.controller._update_current()
    s.jobs[0].run()
    assert not s.applied
    assert s.calls.count("release") == 1
    assert not s.controller._importing
    assert s.messages[-1][0] is False
    if failure == "source_changed":
        assert "download" not in s.calls
        assert "changed" in s.messages[-1][1]
    else:
        assert "Disk is full" in s.messages[-1][1]


def test_replaced_window_never_receives_old_committed_document(update_job):
    s = update_job
    s.controller._update_current()
    s.flags.current = False
    s.jobs[0].run()
    assert not s.applied
    assert s.calls.count("release") == 1
    assert not s.controller._importing


def test_another_installed_copy_only_disables_separate_download(update_job):
    s = update_job
    checked = []
    s.controller._checked = lambda value, **_kwargs: checked.append(value)
    s.controller._start = lambda callback, completed, *_args: completed(callback(None, Event()))
    s.controller._queue_check(s.controller._window, automatic=True)
    assert checked[0].result.status == "update_available"
    assert checked[0].result.can_install
    assert not checked[0].can_download_separately


@pytest.mark.parametrize("late", [False, True])
def test_unresolved_results_block_before_transfer_or_before_commit(update_job, late):
    s = update_job
    s.flags.pending_late = late
    s.flags.pending = not late
    s.controller._update_current()
    s.jobs[0].run()
    assert not s.applied
    assert "commit" not in s.calls
    assert ("download" in s.calls) == late
    assert "Results" in s.messages[-1][1]
    assert s.calls.count("release") == 1


def test_committed_model_must_be_adopted_before_editing_is_unlocked(update_job):
    s = update_job
    s.controller._update_current()
    s.jobs[0].run()
    adopted = s.calls.index("adopt")
    unlocked = next(i for i, x in enumerate(s.calls) if isinstance(x, tuple)
                    and x[0] == "unfreeze")
    assert adopted < unlocked


def test_failed_reload_locks_stale_model_instead_of_reenabling_save(update_job):
    s = update_job
    s.flags.apply_fail = True
    s.controller._update_current()
    s.jobs[0].run()
    assert s.flags.locked
    assert not any(isinstance(x, tuple) and x[0] == "unfreeze" for x in s.calls)
    assert s.calls.count("release") == 1
    assert not s.controller._importing


@pytest.mark.parametrize("failure", ["adoption", "rollback"])
def test_failed_update_clears_candidate_and_blocks_update_relink_and_check(update_job, failure):
    s = update_job
    s.controller._checked_result = Checked(s.controller._result)
    s.controller._separate_download_allowed = True
    s.controller._update_current()
    if failure == "adoption":
        s.flags.apply_fail = True
        s.jobs[0].run()
    else:
        s.jobs[0].finished.emit(SimpleNamespace(
            value=None, error=ProjectBundleRecoveryError(s.result.backup_path), cancelled=False,
        ))
    assert s.controller._window._project_update_reload_failed
    assert s.controller._result is None
    assert s.controller._checked_result is None
    assert not s.controller._separate_download_allowed
    assert "reopen" in s.messages[-1][1].lower() or "restore" in s.messages[-1][1].lower()
    previous_calls, previous_messages = list(s.calls), list(s.messages)
    for action in ("update", "install", "relink", "check", "link", "set_auto"):
        s.controller._action(action)
    s.controller._update_current()
    s.controller._save_origin(link=True)
    s.controller._queue_check(s.controller._window, automatic=False)
    assert len(s.jobs) == 1
    assert s.calls == previous_calls and s.messages == previous_messages


def test_cache_release_failure_does_not_leave_update_controller_busy(update_job):
    s = update_job
    def fail_release():
        raise OSError("Cache unlock failed")
    s.controller.client.release_download = fail_release
    s.controller._update_current()
    s.jobs[0].run()
    assert s.applied == [s.result]
    assert not s.controller._importing and s.controller._job is None


@pytest.mark.parametrize("failed_reload", [False, True])
def test_main_window_direct_recovery_launch_cannot_bypass_update_lock(failed_reload):
    source = Path(__file__).parents[2] / "src/fpvs_studio/gui/main_window.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "StudioMainWindow")
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                  and node.name == "_launch_recovered_condition")
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        method,
    ], type_ignores=[])), str(source), "exec"), namespace)
    window = SimpleNamespace(
        isVisible=lambda: True, is_launch_busy=lambda: False,
        _bundle_import_processing_active=not failed_reload,
        _project_update_reload_failed=failed_reload,
    )
    # No document/runtime dependency exists on this fake: reaching either would fail.
    namespace["_launch_recovered_condition"](window, object())


@pytest.mark.parametrize("method_name", ["save_project", "launch_session"])
@pytest.mark.parametrize("failed_reload", [False, True])
def test_direct_save_and_launch_stop_before_model_access_during_update(method_name, failed_reload):
    source = Path(__file__).parents[2] / "src/fpvs_studio/gui/main_window.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "StudioMainWindow")
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                  and node.name == method_name)
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        method,
    ], type_ignores=[])), str(source), "exec"), namespace)
    window = SimpleNamespace(
        _bundle_import_processing_active=not failed_reload,
        _project_update_reload_failed=failed_reload,
    )
    result = namespace[method_name](window)
    assert result is (False if method_name == "save_project" else None)
