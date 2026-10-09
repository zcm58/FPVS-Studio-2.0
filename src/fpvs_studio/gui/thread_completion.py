"""Deliver completion after Qt's native thread cleanup, without a GUI-thread wait."""

from __future__ import annotations

from threading import Thread

from PySide6.QtCore import QObject, QThread, Signal, Slot


class ThreadCompletion(QObject):
    """Retain a QThread through native cleanup and deliver completion on the GUI.

    QThread.finished is emitted before deferred worker deletion and thread-local
    destructors finish. Releasing a Python worker wrapper at that point can race
    Shiboken's native destruction. A short-lived join monitor waits off the GUI
    thread; it performs no backend work and never accesses widgets.
    """

    finished = Signal()
    _joined = Signal()

    def __init__(self, thread: QThread, *, parent: QObject) -> None:
        super().__init__(parent)
        self.worker_thread = thread
        self._monitor: Thread | None = None
        thread.finished.connect(self._begin_join)
        self._joined.connect(self._finish)

    @Slot()
    def _begin_join(self) -> None:
        self._monitor = Thread(
            target=self._join, daemon=True, name="fpvs-qt-thread-cleanup"
        )
        self._monitor.start()

    def _join(self) -> None:
        self.worker_thread.wait()
        self._joined.emit()

    @Slot()
    def _finish(self) -> None:
        self.finished.emit()
        self.worker_thread.deleteLater()
        self.deleteLater()
