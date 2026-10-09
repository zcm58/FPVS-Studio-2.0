"""Tests for GUI worker helpers."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from threading import Event

import pytest
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QWidget

from fpvs_studio.gui.thread_completion import ThreadCompletion
from fpvs_studio.gui.update_lifecycle import UpdateLifecycle
from fpvs_studio.gui.workers import BackgroundTask, ProgressTask


class _FakeProgressDialog:
    def __init__(self, label, cancel_text, minimum, maximum, parent) -> None:
        self.label = label
        self.cancel_text = cancel_text
        self.minimum = minimum
        self.maximum = maximum
        self.parent = parent
        self.cancel_button = object()
        self.window_modality = None
        self.minimum_duration = None
        self.shown = False
        self.closed = False

    def setWindowTitle(self, title) -> None:  # noqa: N802
        self.window_title = title

    def setCancelButton(self, button) -> None:  # noqa: N802
        self.cancel_button = button

    def setWindowModality(self, modality) -> None:  # noqa: N802
        self.window_modality = modality

    def setMinimumDuration(self, duration_ms) -> None:  # noqa: N802
        self.minimum_duration = duration_ms

    def show(self) -> None:
        self.shown = True

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def worker_lifecycle(qapp, qtbot, monkeypatch):
    quit_requests: list[bool] = []
    original_auto_quit = qapp.quitOnLastWindowClosed()
    qapp.setQuitOnLastWindowClosed(False)
    lifecycle = UpdateLifecycle(qapp, quit_callback=lambda: quit_requests.append(True))
    monkeypatch.setattr(qapp, "_fpvs_update_lifecycle", lifecycle, raising=False)
    yield lifecycle, quit_requests
    lifecycle.request_shutdown()
    qtbot.waitUntil(lambda: not lifecycle.has_active_jobs, timeout=10000)
    qapp.removeEventFilter(lifecycle)
    qapp.lastWindowClosed.disconnect(lifecycle._last_window_closed)
    qapp.aboutToQuit.disconnect(lifecycle._about_to_quit)
    lifecycle.deleteLater()
    qapp.setQuitOnLastWindowClosed(original_auto_quit)


def test_persistent_progress_task_runs_on_stable_presentation_thread(
    qtbot, worker_lifecycle
) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    thread_names: list[str] = []
    finished_labels: list[str] = []

    def _run_task(label: str) -> None:
        task = ProgressTask(
            parent_widget=parent,
            label=label,
            callback=lambda: QThread.currentThread().objectName(),
            dialog_factory=_FakeProgressDialog,
            persistent_thread=True,
        )
        task.succeeded.connect(thread_names.append)
        task.finished.connect(lambda: finished_labels.append(label))
        task.start()
        qtbot.waitUntil(lambda: label in finished_labels)

    _run_task("first")
    _run_task("second")

    assert thread_names == [
        "fpvs-studio-presentation-thread",
        "fpvs-studio-presentation-thread",
    ]


@pytest.mark.parametrize("kind", ["background", "progress", "presentation"])
@pytest.mark.parametrize("fails", [False, True])
def test_worker_survives_requester_destruction_and_shutdown(
    qtbot, worker_lifecycle, kind, fails
) -> None:
    lifecycle, quit_requests = worker_lifecycle
    parent = QWidget()
    qtbot.addWidget(parent)
    started = Event()
    release = Event()
    outcomes: list[object] = []
    heartbeats: list[bool] = []

    def callback():
        started.set()
        assert release.wait(5)
        if fails:
            raise RuntimeError("Synthetic network failure")
        return "complete"

    if kind == "background":
        task = BackgroundTask(parent_widget=parent, callback=callback)
    else:
        task = ProgressTask(
            parent_widget=parent,
            label="Synthetic task",
            callback=callback,
            persistent_thread=kind == "presentation",
            dialog_factory=_FakeProgressDialog,
        )
    task.succeeded.connect(outcomes.append)
    task.failed.connect(outcomes.append)
    task.finished.connect(lambda: outcomes.append("finished"))
    task.start()
    try:
        qtbot.waitUntil(started.is_set)
        parent.deleteLater()
        qtbot.wait(1)
        lifecycle.request_shutdown()
        QTimer.singleShot(0, lambda: heartbeats.append(True))
        qtbot.waitUntil(lambda: bool(heartbeats))
        assert lifecycle.has_active_jobs
        assert not quit_requests
    finally:
        release.set()
    qtbot.waitUntil(lambda: not lifecycle.has_active_jobs)
    qtbot.waitUntil(lambda: bool(quit_requests))
    assert outcomes == []


def test_online_job_stays_alive_until_native_cleanup_completes(
    qtbot, worker_lifecycle, monkeypatch
) -> None:
    lifecycle, quit_requests = worker_lifecycle
    native_stopped = Event()
    release = Event()
    outcomes: list[object] = []
    heartbeats: list[bool] = []

    def delayed_join(completion):
        completion.worker_thread.wait()
        native_stopped.set()
        release.wait(5)
        completion._joined.emit()

    monkeypatch.setattr(ThreadCompletion, "_join", delayed_join)
    job = lifecycle.start_task(lambda _progress, _cancel: "synthetic network response")
    job.finished.connect(outcomes.append)
    try:
        qtbot.waitUntil(native_stopped.is_set)
        lifecycle.request_shutdown()
        QTimer.singleShot(0, lambda: heartbeats.append(True))
        qtbot.waitUntil(lambda: bool(heartbeats))
        assert lifecycle.has_active_jobs
        assert job.is_running
        assert not outcomes
        assert not quit_requests
    finally:
        release.set()
    qtbot.waitUntil(lambda: not lifecycle.has_active_jobs)
    assert len(outcomes) == 1
    assert outcomes[0].cancelled


@pytest.mark.parametrize("kind", ["background", "progress", "presentation"])
@pytest.mark.parametrize("shutdown", ["quit", "exit"])
def test_native_process_shutdown_drains_worker_threads(kind, shutdown) -> None:
    # A native abort cannot be tested safely in pytest's own QApplication process.
    # The presentation case exceeds the former five-second teardown wait.
    script = textwrap.dedent('''\
        import time
        from PySide6.QtCore import QTimer, qInstallMessageHandler
        from PySide6.QtWidgets import QApplication, QWidget
        from fpvs_studio.gui.update_lifecycle import update_lifecycle
        from fpvs_studio.gui.workers import BackgroundTask, ProgressTask
        qInstallMessageHandler(lambda kind, context, message: print(message, flush=True))
        app = QApplication([])
        window = QWidget()
        window.setWindowTitle("Studio synthetic worker shutdown")
        window.show()
        kind = KIND
        callback = lambda: time.sleep(6 if kind == "presentation" else 0.5)
        if kind == "background":
            task = BackgroundTask(parent_widget=window, callback=callback)
        else:
            task = ProgressTask(parent_widget=window, label="Synthetic task",
                callback=callback, persistent_thread=kind == "presentation")
        task.start()
        QTimer.singleShot(50, window.deleteLater)
        QTimer.singleShot(100, app.quit if SHUTDOWN == "quit" else lambda: app.exit(0))
        app.exec()
        while update_lifecycle(app).has_active_jobs:
            update_lifecycle(app).request_shutdown()
            app.exec()
        assert not update_lifecycle(app).has_active_jobs
        del window, task, app
        print("shutdown complete", flush=True)
    ''').replace("KIND", repr(kind)).replace("SHUTDOWN", repr(shutdown))
    result = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", script],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "shutdown complete" in result.stdout


@pytest.mark.parametrize("kind", ["background", "presentation", "online"])
def test_native_worker_reuse_and_fast_online_jobs_survive_collection(kind) -> None:
    script = textwrap.dedent('''\
        import gc
        from PySide6.QtCore import QTimer, qInstallMessageHandler
        from PySide6.QtWidgets import QApplication, QWidget
        from fpvs_studio.gui.update_lifecycle import update_lifecycle
        from fpvs_studio.gui.workers import BackgroundTask, ProgressTask
        qInstallMessageHandler(lambda kind, context, message: print(message, flush=True))
        app = QApplication([])
        window = QWidget()
        window.setWindowTitle("Studio synthetic worker reuse")
        window.show()
        lifecycle = update_lifecycle(app)
        kind = KIND
        count = 0
        def finished(*_args):
            global count
            count += 1
            gc.collect()
            if count == 30:
                lifecycle.request_shutdown()
            else:
                QTimer.singleShot(0, start)
        def start():
            if kind == "online":
                task = lifecycle.start_task(lambda _progress, _cancel: "synthetic response")
            elif kind == "background":
                task = BackgroundTask(parent_widget=window, callback=lambda: "synthetic result")
            else:
                task = ProgressTask(parent_widget=window, label="Synthetic presentation",
                    callback=lambda: "synthetic result", persistent_thread=True)
            task.finished.connect(finished)
            if kind != "online":
                task.start()
        QTimer.singleShot(0, start)
        app.exec()
        assert count == 30
        assert not lifecycle.has_active_jobs
        print("reuse complete", flush=True)
    ''').replace("KIND", repr(kind))
    result = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", script],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "reuse complete" in result.stdout
