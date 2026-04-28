"""Small Qt worker helpers for GUI-triggered backend tasks."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QProgressDialog, QWidget

ProgressDialogFactory = Callable[[str, str, int, int, QWidget], QProgressDialog]


class GuiTaskWorker(QObject):
    """Run one backend callback away from the UI thread."""

    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, callback: Callable[[], object]) -> None:
        super().__init__()
        self._callback = callback

    @Slot()
    def run(self) -> None:
        try:
            result = self._callback()
        except Exception as error:
            self.failed.emit(error)
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()


class ProgressTask(QObject):
    """Own a progress dialog and worker thread for one GUI task."""

    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(
        self,
        *,
        parent_widget: QWidget,
        label: str,
        callback: Callable[[], object],
        dialog_factory: ProgressDialogFactory = QProgressDialog,
        window_title: str | None = None,
    ) -> None:
        super().__init__(parent_widget)
        self._parent_widget = parent_widget
        self._label = label
        self._callback = callback
        self._dialog_factory = dialog_factory
        self._window_title = window_title
        self._thread: QThread | None = None
        self._worker: GuiTaskWorker | None = None
        self._dialog: QProgressDialog | None = None

    def start(self) -> None:
        dialog = self._dialog_factory(self._label, "", 0, 0, self._parent_widget)
        if self._window_title is not None:
            dialog.setWindowTitle(self._window_title)
        dialog.setCancelButton(None)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.show()

        thread = QThread(self)
        worker = GuiTaskWorker(self._callback)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.succeeded.connect(self._handle_succeeded)
        worker.failed.connect(self._handle_failed)
        worker.finished.connect(self._handle_worker_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._handle_thread_finished)

        self._dialog = dialog
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(object)
    def _handle_succeeded(self, result: object) -> None:
        self.succeeded.emit(result)

    @Slot(object)
    def _handle_failed(self, error: object) -> None:
        self.failed.emit(error)

    @Slot()
    def _handle_worker_finished(self) -> None:
        if self._dialog is not None:
            self._dialog.close()

    @Slot()
    def _handle_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._dialog = None
        self.finished.emit()
        self.deleteLater()
