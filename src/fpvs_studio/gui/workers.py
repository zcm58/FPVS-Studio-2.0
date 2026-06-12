"""Small Qt worker helpers for GUI-triggered backend tasks."""

from __future__ import annotations

import atexit
from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, QObject, Qt, QThread, Signal, Slot
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


class PersistentThreadTaskWorker(QObject):
    """Run callbacks on one long-lived worker thread.

    PsychoPy's pyglet backend binds its Win32 event loop to the thread that imports it,
    so presentation callbacks must reuse one thread across launches.
    """

    task_requested = Signal(object)
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._busy = False
        self.task_requested.connect(self._run_task, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _run_task(self, callback: Callable[[], object]) -> None:
        if self._busy:
            self.failed.emit(RuntimeError("A presentation task is already running."))
            self.finished.emit()
            return
        self._busy = True
        try:
            result = callback()
        except Exception as error:
            self.failed.emit(error)
        else:
            self.succeeded.emit(result)
        finally:
            self._busy = False
            self.finished.emit()


_persistent_thread: QThread | None = None
_persistent_worker: PersistentThreadTaskWorker | None = None
_persistent_thread_shutdown_connected = False


def _presentation_worker() -> PersistentThreadTaskWorker:
    """Return the app-wide presentation worker, creating it if needed."""

    global _persistent_thread
    global _persistent_worker
    global _persistent_thread_shutdown_connected

    if (
        _persistent_thread is not None
        and _persistent_thread.isRunning()
        and _persistent_worker is not None
    ):
        return _persistent_worker

    app = QCoreApplication.instance()
    thread = QThread(app)
    thread.setObjectName("fpvs-studio-presentation-thread")
    worker = PersistentThreadTaskWorker()
    worker.moveToThread(thread)
    thread.finished.connect(worker.deleteLater)
    if app is not None and not _persistent_thread_shutdown_connected:
        app.aboutToQuit.connect(_shutdown_presentation_worker)
        _persistent_thread_shutdown_connected = True

    _persistent_thread = thread
    _persistent_worker = worker
    thread.start()
    return worker


def _shutdown_presentation_worker() -> None:
    """Stop the app-wide presentation worker during Qt shutdown."""

    global _persistent_thread
    global _persistent_worker

    thread = _persistent_thread
    if thread is not None and thread.isRunning():
        thread.quit()
        thread.wait(5000)
    _persistent_thread = None
    _persistent_worker = None


atexit.register(_shutdown_presentation_worker)


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
        persistent_thread: bool = False,
    ) -> None:
        super().__init__(parent_widget)
        self._parent_widget = parent_widget
        self._label = label
        self._callback = callback
        self._dialog_factory = dialog_factory
        self._window_title = window_title
        self._persistent_thread = persistent_thread
        self._thread: QThread | None = None
        self._worker: GuiTaskWorker | None = None
        self._persistent_worker: PersistentThreadTaskWorker | None = None
        self._dialog: QProgressDialog | None = None

    def start(self) -> None:
        dialog = self._dialog_factory(self._label, "", 0, 0, self._parent_widget)
        if self._window_title is not None:
            dialog.setWindowTitle(self._window_title)
        dialog.setCancelButton(None)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.show()

        if self._persistent_thread:
            persistent_worker = _presentation_worker()
            persistent_worker.succeeded.connect(self._handle_succeeded)
            persistent_worker.failed.connect(self._handle_failed)
            persistent_worker.finished.connect(self._handle_worker_finished)
            persistent_worker.finished.connect(self._handle_persistent_task_finished)

            self._dialog = dialog
            self._persistent_worker = persistent_worker
            persistent_worker.task_requested.emit(self._callback)
            return

        thread = QThread(self)
        gui_worker = GuiTaskWorker(self._callback)
        gui_worker.moveToThread(thread)

        thread.started.connect(gui_worker.run)
        gui_worker.succeeded.connect(self._handle_succeeded)
        gui_worker.failed.connect(self._handle_failed)
        gui_worker.finished.connect(self._handle_worker_finished)
        gui_worker.finished.connect(thread.quit)
        gui_worker.finished.connect(gui_worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._handle_thread_finished)

        self._dialog = dialog
        self._thread = thread
        self._worker = gui_worker
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
    def _handle_persistent_task_finished(self) -> None:
        worker = self._persistent_worker
        if worker is not None:
            worker.succeeded.disconnect(self._handle_succeeded)
            worker.failed.disconnect(self._handle_failed)
            worker.finished.disconnect(self._handle_worker_finished)
            worker.finished.disconnect(self._handle_persistent_task_finished)
        self._persistent_worker = None
        self._dialog = None
        self.finished.emit()
        self.deleteLater()

    @Slot()
    def _handle_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._dialog = None
        self.finished.emit()
        self.deleteLater()


class BackgroundTask(QObject):
    """Run one backend callback on a disposable worker thread without UI chrome."""

    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(
        self,
        *,
        parent_widget: QWidget,
        callback: Callable[[], object],
    ) -> None:
        super().__init__(parent_widget)
        self._callback = callback
        self._thread: QThread | None = None
        self._worker: GuiTaskWorker | None = None

    def start(self) -> None:
        thread = QThread(self)
        gui_worker = GuiTaskWorker(self._callback)
        gui_worker.moveToThread(thread)

        thread.started.connect(gui_worker.run)
        gui_worker.succeeded.connect(self.succeeded)
        gui_worker.failed.connect(self.failed)
        gui_worker.finished.connect(thread.quit)
        gui_worker.finished.connect(gui_worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._handle_thread_finished)

        self._thread = thread
        self._worker = gui_worker
        thread.start()

    @Slot()
    def _handle_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self.finished.emit()
        self.deleteLater()
