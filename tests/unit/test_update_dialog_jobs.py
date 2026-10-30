"""Run the actual update orchestration with fake jobs and no Qt import."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from fpvs_studio.updates.models import (
    DownloadedInstaller,
    InstallerAsset,
    UpdateCancelled,
    UpdateCheckResult,
    UpdatePhase,
)


class _Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in tuple(self.callbacks):
            callback(*args)


class _Widget:
    def __init__(self):
        self.text = ""
        self.enabled = True
        self.visible = True
        self.value = 0
        self.range = (0, 1000)

    def setText(self, text):
        self.text = text

    def setEnabled(self, enabled):
        self.enabled = enabled

    def setVisible(self, visible):
        self.visible = visible

    def setRange(self, minimum, maximum):
        self.range = (minimum, maximum)

    def setValue(self, value):
        self.value = value


class _DialogBase:
    class DialogCode(IntEnum):
        Rejected = 0
        Accepted = 1

    def done(self, result):
        self.result = result
        self.visible = False

    def accept(self):
        self.done(int(self.DialogCode.Accepted))

    def _fit_action_buttons(self):
        pass

    def _set_notes_text(self, text):
        self.notes_label.setText(text)


_UNSET = object()


class _Job:
    def __init__(self, callback, result_type, *, keep_success_on_cancel=False):
        self.callback = callback
        self.result_type = result_type
        self.keep_success_on_cancel = keep_success_on_cancel
        self.finished = _Signal()
        self.progress_changed = _Signal()
        self.cancel_event = Event()
        self.value = None
        self.error = None

    def cancel(self):
        self.cancel_event.set()

    def run_callback(self):
        try:
            if self.cancel_event.is_set():
                raise UpdateCancelled("Canceled before callback")
            self.value = self.callback(self.progress_changed.emit, self.cancel_event)
        except Exception as error:
            self.error = error

    def finish(self, *, value=_UNSET, error=None):
        if value is not _UNSET:
            self.value = value
        if error is not None:
            self.error = error
        cancelled = isinstance(self.error, UpdateCancelled) or (
            self.cancel_event.is_set()
            and not (self.keep_success_on_cancel and self.error is None)
        )
        self.finished.emit(self.result_type(self.value, self.error, cancelled))


@pytest.fixture
def update_flow(tmp_path):
    gui = Path(__file__).resolve().parents[2] / "src/fpvs_studio/gui"
    source = gui / "update_dialog.py"
    parsed = ast.parse(source.read_text(encoding="utf-8"))
    dialog = next(
        node for node in parsed.body
        if isinstance(node, ast.ClassDef) and node.name == "UpdateDialog"
    )
    methods = {
        "start_update_check", "start_download", "install_and_restart", "_start_task",
        "_handle_task_finished", "_handle_download_result", "_handle_task_error",
        "_handle_download_progress", "_handle_task_cancelled", "_download_available",
        "_set_busy_state", "_set_close_button_text", "reject", "done", "_request_close",
        "_handle_application_shutdown",
    }
    dialog.body = [
        node for node in dialog.body if isinstance(node, ast.FunctionDef) and node.name in methods
    ]
    for method in dialog.body:
        method.decorator_list = []
    lifecycle = ast.parse((gui / "update_lifecycle.py").read_text(encoding="utf-8"))
    result = next(
        node for node in lifecycle.body
        if isinstance(node, ast.ClassDef) and node.name == "UpdateTaskResult"
    )
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        result, dialog,
    ], type_ignores=[])
    namespace = {
        "__name__": __name__, "dataclass": dataclass, "QDialog": _DialogBase,
        "DownloadedInstaller": DownloadedInstaller, "UpdatePhase": UpdatePhase,
        "_PROGRESS_MAXIMUM": 1000, "_LOGGER": logging.getLogger(__name__),
    }
    exec(compile(ast.fix_missing_locations(module), str(source), "exec"), namespace)
    jobs, events = [], []
    lifecycle = SimpleNamespace(is_shutting_down=False, manual_check_requested=_Signal())

    def start_task(callback, *, keep_success_on_cancel=False, on_committed_success=None):
        job = _Job(
            callback, namespace["UpdateTaskResult"], keep_success_on_cancel=keep_success_on_cancel,
        )
        if on_committed_success is not None:
            job.finished.connect(lambda outcome: (
                on_committed_success() if outcome.error is None and not outcome.cancelled else None
            ))
        jobs.append(job)
        return job

    lifecycle.start_task = start_task
    asset = InstallerAsset("update.exe", "https://example.invalid/update.exe", 9, "a" * 64)
    downloaded = DownloadedInstaller(tmp_path / "update.exe", 9, asset.sha256, asset)
    instance = namespace["UpdateDialog"]()
    instance._result = UpdateCheckResult("1.0", "2.0", True, None, "", asset, False)
    instance._downloaded_installer = None
    instance._preparing_install = False
    instance._disposed = Event()
    instance.destroyed = _Signal()
    instance._job = None
    instance._task_kind = None
    instance._close_pending = False
    instance._close_result = 0
    instance._lifecycle = lifecycle
    instance.result = None
    instance.visible = True
    for name in ("check_button", "download_button", "close_button", "progress_bar",
                 "status_label", "notes_label"):
        setattr(instance, name, _Widget())
    instance._download_callback = lambda *_args: events.append("download") or downloaded
    instance._installer_launcher = lambda *_args: events.append("launch")
    instance._on_before_install = lambda: events.append("save") or True
    instance._quit_app = lambda: events.append("quit")
    return SimpleNamespace(
        dialog=instance, jobs=jobs, events=events, downloaded=downloaded, lifecycle=lifecycle,
    )


def test_single_action_waits_for_download_and_install_worker_finish(update_flow):
    flow = update_flow
    dialog = flow.dialog
    dialog.start_download()
    download = flow.jobs[0]
    download.run_callback()
    assert flow.events == ["download"]
    assert dialog._downloaded_installer is None
    assert not dialog.download_button.enabled
    dialog.start_download()
    assert len(flow.jobs) == 1

    download.finish()
    assert flow.events == ["download", "save"]
    assert len(flow.jobs) == 2
    assert dialog._task_kind == "install"
    assert dialog._downloaded_installer is flow.downloaded
    install = flow.jobs[1]
    install.run_callback()
    assert flow.events == ["download", "save", "launch"]
    assert dialog.visible
    install.finish()
    assert flow.events == ["download", "save", "launch", "quit"]
    assert dialog.result == dialog.DialogCode.Accepted
    assert not dialog.visible


@pytest.mark.parametrize("interruption", ["cancel", "close", "shutdown", "disposed", "error",
                                        "invalid-result"])
def test_download_interruption_never_starts_install(update_flow, interruption):
    flow = update_flow
    dialog = flow.dialog
    dialog.start_download()
    job = flow.jobs[0]
    job.run_callback()
    if interruption == "cancel":
        job.cancel()
    elif interruption == "close":
        dialog.reject()
    elif interruption == "shutdown":
        flow.lifecycle.is_shutting_down = True
        dialog._handle_application_shutdown()
    elif interruption == "disposed":
        dialog._disposed.set()
        dialog.destroyed.emit()
    if interruption == "error":
        job.finish(error=RuntimeError("Download failed"))
    elif interruption == "invalid-result":
        job.finish(value=object())
    else:
        job.finish()
    assert len(flow.jobs) == 1
    assert flow.events == ["download"]
    assert dialog._job is None


def test_canceled_save_keeps_verified_download_for_the_same_action_to_retry(update_flow):
    flow = update_flow
    answers = iter((False, True))
    flow.dialog._on_before_install = lambda: flow.events.append("save") or next(answers)
    flow.dialog.start_download()
    flow.jobs[0].run_callback()
    flow.jobs[0].finish()
    assert flow.events == ["download", "save"]
    assert len(flow.jobs) == 1
    assert flow.dialog._downloaded_installer is flow.downloaded
    assert flow.dialog.download_button.enabled

    flow.dialog.start_download()
    assert flow.events == ["download", "save", "save"]
    assert len(flow.jobs) == 2
    assert flow.dialog._task_kind == "install"
    flow.jobs[1].run_callback()
    flow.jobs[1].finish()
    assert flow.events == ["download", "save", "save", "launch", "quit"]


@pytest.mark.parametrize("save_accepted", [False, True])
def test_save_hook_cannot_reenter_the_update_action(update_flow, save_accepted):
    flow = update_flow

    def save():
        flow.dialog.start_download()
        flow.dialog.start_update_check()
        flow.dialog.install_and_restart()
        assert len(flow.jobs) == 1
        return save_accepted

    flow.dialog._on_before_install = save
    flow.dialog.start_download()
    flow.jobs[0].run_callback()
    flow.jobs[0].finish()
    assert len(flow.jobs) == (2 if save_accepted else 1)
    assert flow.dialog._task_kind == ("install" if save_accepted else None)
    assert not flow.dialog._preparing_install


def test_cached_download_state_does_not_start_install_without_the_action(update_flow):
    flow = update_flow
    flow.dialog._handle_download_result(flow.downloaded)
    assert flow.jobs == []
    assert flow.events == []
    assert flow.dialog.download_button.enabled
    flow.dialog.start_download()
    assert len(flow.jobs) == 1
    assert flow.dialog._task_kind == "install"
    assert flow.events == ["save"]


@pytest.mark.parametrize("interruption", ["close", "disposed", "shutdown"])
def test_interrupted_save_hook_cannot_start_an_installer(update_flow, interruption):
    flow = update_flow

    def save():
        if interruption == "close":
            flow.dialog.reject()
        elif interruption == "disposed":
            flow.dialog._disposed.set()
            flow.dialog.destroyed.emit()
        else:
            flow.lifecycle.is_shutting_down = True
            flow.dialog._handle_application_shutdown()
        return True

    flow.dialog._on_before_install = save
    flow.dialog.start_download()
    flow.jobs[0].run_callback()
    flow.jobs[0].finish()
    assert len(flow.jobs) == 1
    assert flow.events == ["download"]
    assert flow.dialog._job is None


def test_install_failure_invalidates_cached_download_before_retry(update_flow):
    flow = update_flow
    flow.dialog.start_download()
    flow.jobs[0].run_callback()
    flow.jobs[0].finish()
    flow.jobs[1].finish(error=RuntimeError("Installer verification failed"))
    assert flow.events == ["download", "save"]
    assert flow.dialog._downloaded_installer is None
    assert flow.dialog.download_button.enabled
    assert flow.dialog.visible
    flow.dialog.start_download()
    assert len(flow.jobs) == 3
    assert flow.dialog._task_kind == "download"


def test_committed_launch_survives_late_cancel_and_quits_after_finish(update_flow):
    flow = update_flow
    flow.dialog.start_download()
    flow.jobs[0].run_callback()
    flow.jobs[0].finish()
    install = flow.jobs[1]
    install.run_callback()
    flow.dialog.reject()
    assert flow.events == ["download", "save", "launch"]
    install.finish()
    assert flow.events == ["download", "save", "launch", "quit"]
    assert flow.dialog.result == flow.dialog.DialogCode.Accepted
