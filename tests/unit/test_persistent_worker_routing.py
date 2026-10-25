"""Exercise production presentation routing without importing or executing Qt."""

from __future__ import annotations

import ast
from collections import deque
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest


class _Signal:
    def __init__(self, loop, owner=None):
        self.loop = loop
        self.owner = owner
        self.slots = []

    def connect(self, slot, connection=None):
        self.slots.append((slot, connection))

    def disconnect(self, slot):
        self.slots = [(other, connection) for other, connection in self.slots if other != slot]

    def emit(self, *args):
        for slot, connection in tuple(self.slots):
            if connection == "queued":
                self.loop.worker.append((slot, args))
            elif getattr(self.owner, "queue_to_gui", False):
                self.loop.gui.append((slot, args))
            else:
                slot(*args)


class _SignalDescriptor:
    def __init__(self, loop):
        self.loop = loop

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if self.name not in instance.__dict__:
            instance.__dict__[self.name] = _Signal(self.loop, instance)
        return instance.__dict__[self.name]


class _Object:
    def __init__(self, parent=None):
        self.deleted = False

    def deleteLater(self):  # noqa: N802
        self.deleted = True


class _Dialog:
    def __init__(self, *_args):
        self.closed = False

    def setWindowTitle(self, _value):  # noqa: N802
        pass

    def setCancelButton(self, _value):  # noqa: N802
        pass

    def setWindowModality(self, _value):  # noqa: N802
        pass

    def setMinimumDuration(self, _value):  # noqa: N802
        pass

    def show(self):
        pass

    def close(self):
        self.closed = True


class _Harness:
    def __init__(self):
        self.worker = deque()
        self.gui = deque()
        self.lifecycle = SimpleNamespace(
            is_shutting_down=False, shutdown_started=_Signal(self),
        )
        source = Path(__file__).resolve().parents[2] / "src/fpvs_studio/gui/workers.py"
        parsed = ast.parse(source.read_text(encoding="utf-8"))
        names = {"_PresentationRequest", "PersistentThreadTaskWorker", "ProgressTask"}
        classes = [node for node in parsed.body if isinstance(node, ast.ClassDef)
                   and node.name in names]
        module = ast.Module(body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            *classes,
        ], type_ignores=[])
        namespace = {
            "QObject": _Object, "QProgressDialog": _Dialog, "Event": Event,
            "Signal": lambda *_args: _SignalDescriptor(self),
            "Slot": lambda *_args: lambda function: function,
            "Qt": SimpleNamespace(
                ConnectionType=SimpleNamespace(QueuedConnection="queued"),
                WindowModality=SimpleNamespace(WindowModal="modal"),
            ),
            "update_lifecycle": lambda: self.lifecycle, "isValid": lambda _worker: True,
        }
        exec(compile(ast.fix_missing_locations(module), str(source), "exec"), namespace)
        self.presentation = namespace["PersistentThreadTaskWorker"]()
        self.presentation.queue_to_gui = True
        namespace["_presentation_worker"] = lambda: self.presentation
        self.task_type = namespace["ProgressTask"]

    def task(self, callback):
        dialogs = []

        def dialog_factory(*args):
            dialog = _Dialog(*args)
            dialogs.append(dialog)
            return dialog

        task = self.task_type(
            parent_widget=SimpleNamespace(destroyed=_Signal(self)),
            label="Synthetic presentation", callback=callback, persistent_thread=True,
            dialog_factory=dialog_factory,
        )
        task.outcomes = []
        task.completions = []
        task.succeeded.connect(lambda value: task.outcomes.append(("success", value)))
        task.failed.connect(lambda error: task.outcomes.append(("error", str(error))))
        task.finished.connect(lambda: task.completions.append("finished"))
        task.start()
        task.progress_dialog = dialogs[0]
        return task

    def run_one(self):
        slot, args = self.worker.popleft()
        slot(*args)

    def drain_gui(self):
        while self.gui:
            slot, args = self.gui.popleft()
            slot(*args)

    def shutdown(self):
        self.lifecycle.is_shutting_down = True
        self.lifecycle.shutdown_started.emit()


@pytest.mark.parametrize("first_fails", [False, True])
@pytest.mark.parametrize("second_fails", [False, True])
@pytest.mark.parametrize("deliver_between_callbacks", [False, True])
def test_overlapping_presentations_keep_results_and_completion_separate(
    first_fails, second_fails, deliver_between_callbacks,
):
    harness = _Harness()
    executed = []

    def callback(label, fails):
        executed.append(label)
        if fails:
            raise RuntimeError(label)
        return label

    first = harness.task(lambda: callback("first", first_fails))
    second = harness.task(lambda: callback("second", second_fails))
    harness.run_one()
    if deliver_between_callbacks:
        harness.drain_gui()
        assert first.completions == ["finished"]
        assert second.outcomes == []
        assert second.completions == []
        assert not second.progress_dialog.closed
    harness.run_one()
    harness.drain_gui()

    assert executed == ["first", "second"]
    assert first.outcomes == [("error" if first_fails else "success", "first")]
    assert second.outcomes == [("error" if second_fails else "success", "second")]
    for task in (first, second):
        assert task.completions == ["finished"]
        assert task.progress_dialog.closed
        assert task.deleted


@pytest.mark.parametrize("dispatch_cancelled_request", [False, True])
@pytest.mark.parametrize("running_fails", [False, True])
def test_shutdown_finishes_queued_work_without_interrupting_running_presentation(
    dispatch_cancelled_request, running_fails,
):
    harness = _Harness()
    executed = []

    def running_callback():
        executed.append("running")
        harness.shutdown()
        assert queued.completions == ["finished"]
        assert queued.progress_dialog.closed
        assert queued.deleted
        assert running.completions == []
        assert not running.progress_dialog.closed
        assert not running.deleted
        if running_fails:
            raise RuntimeError("Running callback failed during shutdown")
        return "running result"

    running = harness.task(running_callback)
    queued = harness.task(lambda: executed.append("queued"))
    harness.run_one()
    if dispatch_cancelled_request:
        harness.run_one()
    else:
        # QThread.quit may discard an invocation behind the active callback.
        harness.worker.clear()
    harness.drain_gui()

    assert executed == ["running"]
    for task in (running, queued):
        assert task.outcomes == []
        assert task.completions == ["finished"]
        assert task.progress_dialog.closed
        assert task.deleted
    assert harness.lifecycle.shutdown_started.slots == []


def test_presentation_submitted_during_shutdown_finishes_without_queueing():
    harness = _Harness()
    harness.shutdown()
    executed = []

    task = harness.task(lambda: executed.append("unexpected"))

    assert not harness.worker
    assert not executed
    assert not task.outcomes
    assert task.completions == ["finished"]
    assert task.progress_dialog.closed
    assert task.deleted
    assert harness.lifecycle.shutdown_started.slots == []


@pytest.mark.parametrize("destroy_running_owner", [False, True])
def test_owner_destruction_skips_pending_callback_but_retains_running_callback(
    destroy_running_owner,
):
    harness = _Harness()
    executed = []

    def running_callback():
        victim = running if destroy_running_owner else queued
        victim._parent_widget.destroyed.emit()
        assert victim.deleted is not destroy_running_owner
        executed.append("running")
        return "running result"

    running = harness.task(running_callback)
    queued = harness.task(lambda: executed.append("queued"))
    harness.run_one()
    harness.drain_gui()
    harness.run_one()
    harness.drain_gui()

    victim = running if destroy_running_owner else queued
    survivor = queued if destroy_running_owner else running
    assert victim.deleted
    assert victim.outcomes == []
    assert victim.completions == []
    assert survivor.completions == ["finished"]
    assert executed == (["running", "queued"] if destroy_running_owner else ["running"])
    assert harness.lifecycle.shutdown_started.slots == []
