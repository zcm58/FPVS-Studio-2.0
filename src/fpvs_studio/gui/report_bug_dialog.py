"""Native report editor. Collection, persistence and HTTP belong to support services."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.components import (
    DialogHeader,
    apply_dialog_theme,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.support.models import MAX_FEATURE_CHARACTERS, Draft


class ReportBugDialog(QDialog):
    """One modeless desktop surface, usable before any project exists."""

    action_requested = Signal(str)
    export_requested = Signal(str)
    draft_changed = Signal()
    closing = Signal()

    def __init__(
        self, draft: Draft, *, online: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.is_feature = draft.report.kind == "feature"
        caption = "Request a Feature" if self.is_feature else "Report a Bug"
        self.setObjectName("report_bug_dialog")
        self.setWindowTitle(caption)
        self.setMinimumSize(760, 680)
        self.resize(860, 760)
        self.online = online
        self._draft = draft
        self._updating = False
        self._state = "editing"
        self._pending_error = ""
        self._pending_title = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        self.header = DialogHeader(
            caption,
            "Describe the feature and how it would help your work."
            if self.is_feature else "Describe the problem and review the text you want to share.",
            parent=self,
        )
        layout.addWidget(self.header)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs, 1)
        details = QWidget(self.tabs)
        form = QFormLayout(details)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.title_edit = QLineEdit(details)
        self.title_edit.setPlaceholderText("A brief summary (required, up to 160 characters)")
        self.happened_edit = QPlainTextEdit(details)
        self.happened_edit.setPlaceholderText(
            "What were you doing, and what went wrong? (required)"
        )
        self.steps_edit = QPlainTextEdit(details)
        self.steps_edit.setPlaceholderText(
            "List the steps, or choose the unknown-cause option below."
        )
        self.expected_edit = QPlainTextEdit(details)
        self.expected_edit.setPlaceholderText("What should have happened? (optional)")
        self.email_edit = QLineEdit(details)
        self.email_edit.setPlaceholderText("Optional address for a private reply")
        self.fields: dict[str, QLineEdit | QPlainTextEdit] = {
            "title": self.title_edit,
            "happened": self.happened_edit,
            "steps": self.steps_edit,
            "expected": self.expected_edit,
            "email": self.email_edit,
        }
        for name, editor in self.fields.items():
            editor.setObjectName(f"report_{name}")
            if isinstance(editor, QPlainTextEdit):
                editor.setMinimumHeight(48)
                editor.setMaximumHeight(110)
            editor.textChanged.connect(self._changed)
        for caption, editor in (
            ("Summary *", self.title_edit),
            ("What happened? *", self.happened_edit),
            ("Steps to reproduce", self.steps_edit),
            ("Expected behavior", self.expected_edit),
            ("Reply email", self.email_edit),
        ):
            label = QLabel(caption, details)
            label.setBuddy(editor)
            editor.setAccessibleName(caption)
            form.addRow(label, editor)
        self.unknown_steps = QCheckBox("I don't know how to reproduce it", details)
        self.unknown_steps.toggled.connect(self._unknown_steps)
        form.addRow("", self.unknown_steps)
        self.tabs.addTab(details, "Details")

        diagnostics = QWidget(self.tabs)
        diagnostic_layout = QVBoxLayout(diagnostics)
        self.metadata_label = self._label("", diagnostics)
        diagnostic_layout.addWidget(self.metadata_label)
        self.include_logs = QCheckBox("Include error logs", diagnostics)
        self.include_logs.setChecked(True)
        self.include_logs.toggled.connect(self._changed)
        diagnostic_layout.addWidget(self.include_logs)
        self.diagnostics_edit = QPlainTextEdit(diagnostics)
        self.diagnostics_edit.setObjectName("report_diagnostics")
        self.diagnostics_edit.setAccessibleName("Reviewed error logs")
        self.diagnostics_edit.setPlaceholderText("Available application error logs appear here.")
        self.diagnostics_edit.textChanged.connect(self._changed)
        diagnostic_layout.addWidget(self.diagnostics_edit, 1)
        self.size_label = self._label("", diagnostics)
        diagnostic_layout.addWidget(self.size_label)
        diagnostic_layout.addWidget(
            self._label(
                "Review logs for personal or research information. Redaction may miss details. "
                "Excluding logs also excludes the error excerpt. App version and OS stay included.",
                diagnostics,
            )
        )
        self.refresh_button = QPushButton("Replace with latest logs", diagnostics)
        self.refresh_button.clicked.connect(lambda: self.action_requested.emit("refresh"))
        diagnostic_layout.addWidget(self.refresh_button)
        diagnostic_layout.addWidget(
            self._label(
                "When connected, reports go privately to the developer. Full logs and reply email "
                "are retained for 14 days (backup history may last seven more). The description "
                "and short error excerpt remain in the private GitHub issue until removed.",
                diagnostics,
            )
        )
        self.tabs.addTab(diagnostics, "Diagnostics")
        self.feature_count = self._label("", details)
        if self.is_feature:
            self.setObjectName("request_feature_dialog")
            for editor in (self.title_edit, self.steps_edit, self.expected_edit, self.email_edit):
                form.setRowVisible(editor, False)
            form.setRowVisible(self.unknown_steps, False)
            feature_label = form.labelForField(self.happened_edit)
            if isinstance(feature_label, QLabel):
                feature_label.setText("Feature request *")
            self.happened_edit.setAccessibleName("Feature request")
            self.happened_edit.setPlaceholderText(
                "What would you like FPVS Studio to do? Describe your idea and why it helps."
            )
            self.happened_edit.setMinimumHeight(260)
            self.happened_edit.setMaximumHeight(16777215)
            form.addRow("", self.feature_count)
            form.addRow(self._label(
                "Only your text and app version are included. When connected, requests go "
                "privately to the developer and remain in a GitHub issue until removed.", details
            ))
            self.tabs.removeTab(1)
            self.tabs.tabBar().hide()
        else:
            self.feature_count.hide()
        self.context_button = QPushButton("Use newly reported error", self)
        self.context_button.clicked.connect(self.use_pending_error)
        self.context_button.hide()
        layout.addWidget(self.context_button)
        self.status_label = self._label("", self)
        self.status_label.setObjectName("report_status")
        layout.addWidget(self.status_label)
        self.notice_label = self._label(
            "Drafts stay local for seven days. Submitting includes a brief browser verification.",
            self,
        )
        layout.addWidget(self.notice_label)
        footer = QHBoxLayout()
        self.more_button = QPushButton("More", self)
        menu = QMenu(self.more_button)
        self.menu_actions: dict[str, QAction] = {}
        for caption, action in (
            ("Copy Report", "copy"),
            ("Discard Draft", "discard"),
            ("New Report", "new"),
            ("Copy Receipt", "receipt"),
        ):
            item = QAction(caption, menu)
            self.menu_actions[action] = item
            item.triggered.connect(lambda _checked=False, name=action: self._secondary(name))
            menu.addAction(item)
        self.more_button.setMenu(menu)
        footer.addWidget(self.more_button)
        self.save_button = QPushButton("Save Report...", self)
        if self.is_feature:
            self.save_button.setText("Save Request...")
            self.menu_actions["copy"].setText("Copy Request")
            self.menu_actions["new"].setText("New Request")
        self.save_button.clicked.connect(self._export)
        mark_secondary_action(self.save_button)
        footer.addWidget(self.save_button)
        footer.addStretch(1)
        self.verify_button = QPushButton("Open verification page", self)
        self.verify_button.clicked.connect(lambda: self.action_requested.emit("browser"))
        self.verify_button.hide()
        footer.addWidget(self.verify_button)
        self.cancel_button = QPushButton("Cancel submission", self)
        self.cancel_button.clicked.connect(lambda: self.action_requested.emit("cancel"))
        self.cancel_button.hide()
        footer.addWidget(self.cancel_button)
        self.close_button = QPushButton("Close", self)
        self.close_button.clicked.connect(self.close)
        footer.addWidget(self.close_button)
        self.submit_button = QPushButton("Submit Report", self)
        mark_primary_action(self.submit_button)
        self.submit_button.clicked.connect(self._submit)
        self.submit_button.setAutoDefault(False)
        footer.addWidget(self.submit_button)
        layout.addLayout(footer)
        apply_dialog_theme(self)
        self.set_draft(draft)
        self.set_state("editing", self.connection_notice())

    @staticmethod
    def _label(text: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        return label

    def connection_notice(self) -> str:
        if self.is_feature:
            return (
                "Review your feature request before submitting."
                if self.online else
                "Online submission is not connected yet. You can copy or save this request."
            )
        return (
            "Review the Details and Diagnostics tabs before submitting."
            if self.online
            else "Online reporting is not connected yet. You can copy or save this report."
        )

    def snapshot(self) -> Draft:
        report = self._draft.report.model_copy(
            update={
                "title": self.title_edit.text(),
                "happened": self.happened_edit.toPlainText(),
                "steps": self.steps_edit.toPlainText(),
                "expected": self.expected_edit.toPlainText(),
                "email": self.email_edit.text().strip(),
                "diagnostics": self.diagnostics_edit.toPlainText(),
            }
        )
        return self._draft.model_copy(
            update={"report": report, "include_logs": self.include_logs.isChecked()}
        )

    def set_draft(self, draft: Draft) -> None:
        self._updating = True
        self._draft = draft.model_copy(deep=True)
        for name, editor in self.fields.items():
            value = getattr(draft.report, name)
            if isinstance(editor, QPlainTextEdit):
                editor.setPlainText(value)
            else:
                editor.setText(value)
        self.diagnostics_edit.setPlainText(draft.report.diagnostics)
        self.include_logs.setChecked(draft.include_logs)
        self.unknown_steps.setChecked(draft.report.steps == "I don't know how to reproduce it.")
        self.metadata_label.setText(
            f"FPVS Studio {draft.report.app_version} · {draft.report.os_version}"
        )
        self._updating = False
        self._changed()

    def set_delivery(self, draft: Draft) -> None:
        self._draft = draft.model_copy(deep=True)

    def set_state(self, state: str, message: str) -> None:
        self._state = state
        frozen = state in ("loading", "verifying", "sending", "checking") or self._draft.locked
        for editor in self.fields.values():
            editor.setReadOnly(frozen)
        self.diagnostics_edit.setReadOnly(frozen)
        self.include_logs.setEnabled(not frozen)
        self.unknown_steps.setEnabled(not frozen)
        self.refresh_button.setEnabled(not frozen)
        self.context_button.setEnabled(not frozen)
        self.menu_actions["receipt"].setEnabled(self._draft.locked)
        self.menu_actions["new"].setEnabled(self._draft.delivery == "submitted")
        self.menu_actions["discard"].setEnabled(not frozen)
        self.verify_button.setVisible(state == "verifying")
        self.cancel_button.setVisible(state in ("verifying", "sending", "checking"))
        self.submit_button.setVisible(state not in ("verifying", "sending", "checking"))
        self.submit_button.setText(
            "Done"
            if self._draft.delivery == "submitted"
            else "Check status"
            if self._draft.locked
            else "Submit Request" if self.is_feature else "Submit Report"
        )
        self.submit_button.setEnabled(
            state != "loading" and (self.online or self._draft.delivery == "submitted")
        )
        self.status_label.setText(message)
        self._update_feature_limit()

    def _update_feature_limit(self) -> None:
        if not self.is_feature:
            return
        count = len(self.happened_edit.toPlainText())
        excess = " — shorten your request to submit" if count > MAX_FEATURE_CHARACTERS else ""
        self.feature_count.setText(f"{count:,} / {MAX_FEATURE_CHARACTERS:,} characters{excess}")
        if self._state == "editing" and not self._draft.locked:
            self.submit_button.setEnabled(
                self.online and not self.snapshot().report.problems()
            )

    def offer_error(self, title: str, details: str) -> None:
        self._pending_title, self._pending_error = title, details
        self.context_button.show()

    def use_pending_error(self) -> None:
        self.diagnostics_edit.setPlainText(self._pending_error)
        if not self.title_edit.text():
            self.title_edit.setText(self._pending_title[:160])
        self.include_logs.setChecked(True)
        self.context_button.hide()
        self.tabs.setCurrentIndex(1)

    def _changed(self) -> None:
        if self._updating:
            return
        size = len(self.diagnostics_edit.toPlainText().encode("utf-8"))
        self.size_label.setText(f"Error log text: {size:,} / 98,304 bytes")
        self._update_feature_limit()
        self.draft_changed.emit()

    def _unknown_steps(self, checked: bool) -> None:
        if self._updating:
            return
        value = "I don't know how to reproduce it."
        if checked and not self.steps_edit.toPlainText().strip():
            self.steps_edit.setPlainText(value)
        elif not checked and self.steps_edit.toPlainText() == value:
            self.steps_edit.clear()

    def _submit(self) -> None:
        if self._draft.delivery == "submitted":
            self.close()
            return
        if self._draft.locked:
            self.action_requested.emit("check")
            return
        draft = self.snapshot()
        problems = draft.report.problems(include_logs=draft.include_logs)
        if problems:
            field, message = next(iter(problems.items()))
            self.status_label.setText(message)
            self.tabs.setCurrentIndex(1 if field == "diagnostics" else 0)
            (self.diagnostics_edit if field == "diagnostics" else self.fields[field]).setFocus()
            return
        self.action_requested.emit("submit")

    def _secondary(self, name: str) -> None:
        if name == "copy":
            draft = self.snapshot()
            QApplication.clipboard().setText(draft.report.as_text(include_logs=draft.include_logs))
            self.status_label.setText("Report copied to the clipboard. Nothing was sent.")
        elif name == "receipt":
            QApplication.clipboard().setText(str(self._draft.report.report_id))
        else:
            self.action_requested.emit(name)

    def _export(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save feature request" if self.is_feature else "Save bug report",
            "FPVS-feature-request.txt" if self.is_feature else "FPVS-bug-report.txt",
            "Text files (*.txt)"
        )
        if filename:
            self.export_requested.emit(filename)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.closing.emit()
        event.accept()

    def reject(self) -> None:
        self.close()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            if not getattr(self, "_refreshing_theme", False):
                self._refreshing_theme = True
                try:
                    apply_dialog_theme(self)
                finally:
                    self._refreshing_theme = False
