"""Tests for GUI worker helpers."""

from __future__ import annotations

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QWidget

from fpvs_studio.gui.workers import ProgressTask


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


def test_persistent_progress_task_runs_on_stable_presentation_thread(qtbot) -> None:
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
