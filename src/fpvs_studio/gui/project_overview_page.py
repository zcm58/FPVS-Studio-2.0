"""Project overview page for the FPVS Studio main window."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSignalBlocker, QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.experiment_categories import experiment_category_label
from fpvs_studio.gui.components import (
    PathValueLabel,
    SectionCard,
    configure_setup_form,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    DebouncedTextCommitter,
    LeftToRightPlainTextEdit,
    _show_error_dialog,
    _sync_text_editor_contents,
)

_PARTICIPANT_TUTORIAL_TOOLTIP = (
    "Run three practice fixation color changes before the first condition starts when "
    "fixation accuracy tracking is enabled."
)
_REPEAT_PARTICIPANT_SESSIONS_TOOLTIP = (
    "Let a participant return using the same participant number for Session 2,\n"
    "Session 3, and later visits. Each visit has separate results.\n"
    "Previous session data is preserved.\n\n"
    "When off, a participant number with an earlier session cannot be used\n"
    "again in this project. This does not change condition repeats within a session."
)


class _ProjectFolderValueLabel(PathValueLabel):
    """Fit the folder path to its card while retaining the complete value."""

    def __init__(self, parent: QWidget) -> None:
        self._full_path = ""
        super().__init__(parent)
        self.setIndent(0)

    def set_full_path(self, path: str) -> None:
        self._full_path = path
        self.setToolTip(path)
        self.setAccessibleDescription(path)
        self._fit_path()

    def _fit_path(self) -> None:
        if self._full_path:
            available_width = max(0, self.contentsRect().width() - 2 * self.margin())
            self.setText(self.fontMetrics().elidedText(
                self._full_path, Qt.TextElideMode.ElideMiddle, available_width,
            ))

    def sizeHint(self) -> QSize:  # noqa: N802
        hint = super().sizeHint()
        hint.setWidth(0)
        return hint

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        hint = super().minimumSizeHint()
        hint.setWidth(0)
        return hint

    def event(self, event: QEvent) -> bool:
        handled = super().event(event)
        if event.type() in (
            QEvent.Type.Resize, QEvent.Type.FontChange,
            QEvent.Type.StyleChange, QEvent.Type.ContentsRectChange,
        ):
            self._fit_path()
        return handled


class ProjectOverviewEditor(QWidget):
    """Editor for project details and participant settings."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document

        self.project_name_edit = QLineEdit(self)
        self.project_name_edit.setObjectName("project_name_edit")
        self.project_name_edit.editingFinished.connect(self._apply_project_name)
        self.experiment_category_value = QLabel(self)
        self.experiment_category_value.setObjectName("project_experiment_category")
        self.experiment_category_value.setToolTip(
            "Experiment category is fixed. Create a new experiment to use another category."
        )

        self.project_description_edit = LeftToRightPlainTextEdit(self)
        self.project_description_edit.setObjectName("project_description_edit")
        self.project_description_edit.setPlaceholderText(
            "Describe the project goal and participant instructions."
        )
        self.project_description_edit.setTabChangesFocus(True)
        self.project_description_edit.setFixedHeight(104)
        self.project_description_edit.setMaximumBlockCount(20)
        self._description_committer = DebouncedTextCommitter(
            self.project_description_edit,
            self._apply_project_description,
        )
        self.project_description_edit.textChanged.connect(self._description_committer.schedule)

        self.project_root_value = _ProjectFolderValueLabel(self)
        self.project_root_value.setObjectName("project_root_value")
        self.project_root_value.setWordWrap(False)
        self.project_root_value.setFixedHeight(32)
        self.project_root_value.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.participant_tutorial_checkbox = QCheckBox("Enable participant tutorial", self)
        self.participant_tutorial_checkbox.setObjectName("participant_tutorial_checkbox")
        self.participant_tutorial_checkbox.setToolTip(_PARTICIPANT_TUTORIAL_TOOLTIP)
        self.participant_tutorial_checkbox.stateChanged.connect(
            self._apply_participant_tutorial_enabled
        )
        self.repeat_participant_sessions_checkbox = QCheckBox(
            "Allow repeat participant sessions", self,
        )
        self.repeat_participant_sessions_checkbox.setObjectName(
            "allow_repeated_participant_sessions_checkbox"
        )
        self.repeat_participant_sessions_checkbox.setToolTip(
            _REPEAT_PARTICIPANT_SESSIONS_TOOLTIP
        )
        self.repeat_participant_sessions_checkbox.setWhatsThis(
            _REPEAT_PARTICIPANT_SESSIONS_TOOLTIP
        )
        self.repeat_participant_sessions_checkbox.setAccessibleDescription(
            _REPEAT_PARTICIPANT_SESSIONS_TOOLTIP
        )
        self.repeat_participant_sessions_checkbox.toggled.connect(
            self._apply_repeat_participant_sessions
        )

        self.project_workspace = QWidget(self)
        self.project_workspace.setObjectName("project_details_workspace")
        self.project_workspace.setMaximumWidth(1040)
        self.project_workspace.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        self.project_details_card = SectionCard(
            title="Project details",
            object_name="project_details_card",
            parent=self.project_workspace,
        )
        self.experiment_setup_card = SectionCard(
            title="Experiment setup",
            object_name="experiment_setup_card",
            parent=self.project_workspace,
        )
        for card in (self.project_details_card, self.experiment_setup_card):
            card.card_layout.setContentsMargins(16, 16, 16, 16)
            card.card_layout.setSpacing(16)
            card.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            card.body_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            card.setMinimumWidth(0)
        self.project_details_heading = self.project_details_card.title_label
        self.experiment_setup_heading = self.experiment_setup_card.title_label

        self.project_details_column = QWidget(self.project_details_card)
        self.project_details_column.setObjectName("project_details_column")
        details_layout = QVBoxLayout(self.project_details_column)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(16)
        metadata_layout = QFormLayout()
        metadata_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        metadata_layout.addRow("Project Name", self.project_name_edit)
        metadata_layout.addRow("Description (optional)", self.project_description_edit)
        metadata_layout.addRow("Project Folder", self.project_root_value)
        configure_setup_form(metadata_layout, stacked=True)
        details_layout.addLayout(metadata_layout)
        details_layout.addStretch(1)

        self.experiment_setup_column = QWidget(self.experiment_setup_card)
        self.experiment_setup_column.setObjectName("experiment_setup_column")
        setup_layout = QVBoxLayout(self.experiment_setup_column)
        setup_layout.setContentsMargins(0, 0, 0, 0)
        setup_layout.setSpacing(16)
        experiment_layout = QFormLayout()
        experiment_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        experiment_layout.addRow("Experiment Category", self.experiment_category_value)
        configure_setup_form(experiment_layout, stacked=True)
        setup_layout.addLayout(experiment_layout)
        setup_layout.addWidget(self.participant_tutorial_checkbox)
        setup_layout.addWidget(self.repeat_participant_sessions_checkbox)
        setup_layout.addStretch(1)
        self.project_details_card.body_layout.addWidget(self.project_details_column)
        self.experiment_setup_card.body_layout.addWidget(self.experiment_setup_column)

        form_layout = QHBoxLayout(self.project_workspace)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(24)
        form_layout.addWidget(self.project_details_card, 3)
        form_layout.addWidget(self.experiment_setup_card, 2)
        QWidget.setTabOrder(self.project_name_edit, self.project_description_edit)
        QWidget.setTabOrder(self.project_description_edit, self.participant_tutorial_checkbox)
        QWidget.setTabOrder(self.participant_tutorial_checkbox,
                           self.repeat_participant_sessions_checkbox)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.project_workspace)
        layout.addStretch(1)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        project = self._document.project
        self.experiment_category_value.setText(
            experiment_category_label(project.experiment_category)
        )
        if not self.project_name_edit.isModified():
            with QSignalBlocker(self.project_name_edit):
                self.project_name_edit.setText(project.meta.name)
        if not self._description_committer.pending:
            _sync_text_editor_contents(self.project_description_edit, project.meta.description)
        self.project_root_value.set_full_path(str(self._document.project_root))
        with QSignalBlocker(self.participant_tutorial_checkbox):
            self.participant_tutorial_checkbox.setChecked(
                project.settings.fixation_task.participant_tutorial_enabled
            )
        self.participant_tutorial_checkbox.setEnabled(project.settings.fixation_task.show_cross)
        with QSignalBlocker(self.repeat_participant_sessions_checkbox):
            self.repeat_participant_sessions_checkbox.setChecked(
                project.settings.allow_repeated_participant_sessions
            )

    def flush_pending_edits(self) -> None:
        self._description_committer.flush()

    def has_pending_edits(self) -> bool:
        return (
            self._description_committer.pending
            or self.project_name_edit.text() != self._document.project.meta.name
        )

    def _apply_project_name(self) -> None:
        if not self.project_name_edit.text().strip():
            return
        try:
            self._document.update_project_name(self.project_name_edit.text())
            self.project_name_edit.setModified(False)
        except Exception as error:  # pragma: no cover - exercised via GUI tests
            _show_error_dialog(self, "Project Name Error", error)
            self.project_name_edit.setModified(False)
            self.refresh()

    def _apply_project_description(self) -> None:
        description = self.project_description_edit.toPlainText()
        if description == self._document.project.meta.description:
            return
        try:
            self._document.update_project_description(description)
        except Exception as error:  # pragma: no cover - exercised via GUI tests
            _show_error_dialog(self, "Project Description Error", error)
            self.refresh()

    def _apply_participant_tutorial_enabled(self) -> None:
        enabled = self.participant_tutorial_checkbox.isChecked()
        if enabled == self._document.project.settings.fixation_task.participant_tutorial_enabled:
            return
        try:
            self._document.update_fixation_settings(participant_tutorial_enabled=enabled)
        except Exception as error:
            _show_error_dialog(self, "Participant Tutorial Error", error)
            self.refresh()

    def _apply_repeat_participant_sessions(self, enabled: bool) -> None:
        try:
            self._document.update_allow_repeated_participant_sessions(enabled)
        except Exception as error:
            _show_error_dialog(self, "Participant Sessions Error", error)
            self.refresh()
