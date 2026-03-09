"""PySide6 application bootstrap for FPVS Studio."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from fpvs_studio.gui.controller import StudioController


def create_application(argv: list[str] | None = None) -> QApplication:
    """Create or reuse the shared QApplication instance."""

    app = QApplication.instance()
    if app is not None:
        return app
    created_app = QApplication(argv or sys.argv)
    created_app.setApplicationName("FPVS Studio")
    created_app.setOrganizationName("FPVS Studio")
    return created_app


def run_gui_app(argv: list[str] | None = None) -> int:
    """Run the FPVS Studio authoring GUI."""

    app = create_application(argv)
    controller = StudioController(app)
    controller.show_welcome()
    return app.exec()
