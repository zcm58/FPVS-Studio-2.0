"""PySide6 application bootstrap for FPVS Studio."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QStyle

from fpvs_studio.gui.controller import StudioController


def _ensure_application_icon(app: QApplication) -> None:
    if not app.windowIcon().isNull():
        return
    fallback_icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
    if not fallback_icon.isNull():
        app.setWindowIcon(fallback_icon)


def create_application(argv: list[str] | None = None) -> QApplication:
    """Create or reuse the shared QApplication instance."""

    app = QApplication.instance()
    if app is None:
        app = QApplication(argv or sys.argv)
    app.setApplicationName("FPVS Studio")
    app.setOrganizationName("FPVS Studio")
    _ensure_application_icon(app)
    return app


def run_gui_app(argv: list[str] | None = None) -> int:
    """Run the FPVS Studio authoring GUI."""

    app = create_application(argv)
    controller = StudioController(app)
    controller.show_welcome()
    return app.exec()
