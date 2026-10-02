"""Application-wide error popup explanations and explicit reporting handoff."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from fpvs_studio.support.error_explanations import explain_error

REPORT_BUTTON_TEXT = "Report this bug. Please!"
_DECORATED = "fpvs_reportable_error"


def _open_report(title: str, details: str, message: str) -> None:
    from fpvs_studio.gui.bug_report_controller import show_bug_report

    show_bug_report(title, details, message)


class ErrorDialogReporter(QObject):
    """Cover ordinary error popups without changing confirmation-dialog decisions."""

    def __init__(
        self, app: QApplication, *, report: Callable[[str, str, str], None] = _open_report
    ) -> None:
        super().__init__(app)
        self.setObjectName("fpvs_error_dialog_reporter")
        self._report = report
        app.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show and isinstance(watched, QMessageBox):
            self.decorate(watched)
        return super().eventFilter(watched, event)

    def decorate(self, box: QMessageBox, *, error: BaseException | None = None) -> None:
        if box.property(_DECORATED) or box.icon() not in (
            QMessageBox.Icon.Critical,
            QMessageBox.Icon.Warning,
        ):
            return
        if box.icon() == QMessageBox.Icon.Warning and (
            box.standardButtons()
            & ~(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Close)
            or any(
                box.buttonRole(button)
                in (
                    QMessageBox.ButtonRole.YesRole,
                    QMessageBox.ButtonRole.NoRole,
                    QMessageBox.ButtonRole.DestructiveRole,
                    QMessageBox.ButtonRole.ApplyRole,
                )
                for button in box.buttons()
            )
        ):
            return
        box.setProperty(_DECORATED, True)
        title = box.windowTitle()
        original = box.text()
        informative = box.informativeText()
        details = box.detailedText()
        explanation = explain_error(title, original, error=error, details=details)
        diagnostic = "\n\n".join(
            value for value in (title, original, informative, details) if value
        )
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(explanation.summary)
        box.setInformativeText(explanation.advice)
        box.setDetailedText(diagnostic)
        box.setMinimumWidth(580)
        # Show Details is an ActionRole button. It must not prevent Qt's ordinary
        # dismissal button from being added before our own custom report action.
        if box.standardButtons() == QMessageBox.StandardButton.NoButton and not any(
            box.buttonRole(existing) != QMessageBox.ButtonRole.ActionRole
            for existing in box.buttons()
        ):
            box.setStandardButtons(QMessageBox.StandardButton.Ok)
        button = QPushButton(REPORT_BUTTON_TEXT, box)
        button.setObjectName("report_error_button")
        button.setAccessibleName(REPORT_BUTTON_TEXT)
        button.setToolTip(
            "Open a report with this error attached. Add a note if you like, then submit."
        )
        button.setAutoDefault(False)
        button.setDefault(False)
        box.addButton(button, QMessageBox.ButtonRole.ActionRole)
        button.clicked.connect(
            lambda: QTimer.singleShot(
                0,
                partial(self._report, title, diagnostic, explanation.description),
            )
        )
        if box.standardButtons() & QMessageBox.StandardButton.Ok:
            if box.defaultButton() is None:
                box.setDefaultButton(QMessageBox.StandardButton.Ok)
            if box.escapeButton() is None:
                box.setEscapeButton(QMessageBox.StandardButton.Ok)


def install_error_reporting(app: QApplication) -> ErrorDialogReporter:
    existing = app.findChild(ErrorDialogReporter, "fpvs_error_dialog_reporter")
    return existing if existing is not None else ErrorDialogReporter(app)


def decorate_error_dialog(box: QMessageBox, error: BaseException) -> None:
    app = QApplication.instance()
    if isinstance(app, QApplication):
        install_error_reporting(app).decorate(box, error=error)
