"""PySide6 application bootstrap and process-level window startup. It creates the
QApplication instance and hands control to the GUI controller that loads project,
preprocessing, and launch workflows. This module owns desktop app initialization only,
not persistent model truth or runtime execution logic."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyle

from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.update_lifecycle import update_lifecycle

_APP_ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "fpvs-studio.ico"


def _ensure_application_icon(app: QApplication) -> None:
    if not app.windowIcon().isNull():
        return
    if _APP_ICON_PATH.is_file():
        app_icon = QIcon(str(_APP_ICON_PATH))
        if not app_icon.isNull():
            app.setWindowIcon(app_icon)
            return
    fallback_icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
    if not fallback_icon.isNull():
        app.setWindowIcon(fallback_icon)


def create_application(argv: list[str] | None = None) -> QApplication:
    """Create or reuse the shared QApplication instance."""

    instance = QApplication.instance()
    if isinstance(instance, QApplication):
        app = instance
    else:
        app = QApplication(argv or sys.argv)
    app.setApplicationName("FPVS Studio")
    app.setOrganizationName("FPVS Studio")
    _ensure_application_icon(app)
    return app


def run_gui_app(argv: list[str] | None = None) -> int:
    """Run the FPVS Studio authoring GUI."""

    app = create_application(argv)
    controller = StudioController(app)
    lifecycle = update_lifecycle(app)
    lifecycle.begin_startup()
    startup_errors: list[Exception] = []

    def _show_initial_window() -> None:
        try:
            # This does not depend on a project root, release metadata, or a network
            # check. It runs even if first-run root-folder onboarding is canceled.
            controller.start_update_cache_housekeeping()
            controller.show_welcome()
        except Exception as error:
            startup_errors.append(error)
            lifecycle.request_shutdown()
        finally:
            lifecycle.finish_startup()
        if controller.welcome_window is None and controller.main_window is None:
            lifecycle.request_shutdown()

    QTimer.singleShot(0, _show_initial_window)
    exit_code = app.exec()
    # A direct QApplication.exit() can bypass the Quit event guard. Continue ordinary
    # event processing until updater cancellation finishes; never block on thread.wait.
    while lifecycle.has_active_jobs:
        lifecycle.request_shutdown()
        app.exec()
    if startup_errors:
        raise startup_errors[0]
    return exit_code
