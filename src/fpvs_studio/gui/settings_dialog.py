"""Application settings dialog for local FPVS Studio preferences. It edits GUI-level
configuration that shapes the desktop authoring experience without becoming part of
ProjectFile, RunSpec, or SessionPlan data. The module owns app-preference widgets only;
experiment semantics and runtime settings stay in their respective backend layers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio import __version__
from fpvs_studio.gui.components import (
    DialogHeader,
    apply_dialog_theme,
    mark_secondary_action,
)


class AppSettingsDialog(QDialog):
    """Expose lightweight app-level settings that are not project-scoped."""

    def __init__(
        self,
        *,
        fpvs_root_dir: Path,
        on_show_root_folder_setup: Callable[[QWidget], Path | None] | None = None,
        on_manage_condition_templates: Callable[[], object] | None = None,
        detailed_run_exports_enabled: bool = True,
        on_detailed_run_exports_changed: Callable[[bool], None] | None = None,
        biosemi_recording_confirmation_required: bool = True,
        on_biosemi_recording_confirmation_required_changed: Callable[[bool], None]
        | None = None,
        sophia_mode_ticker_enabled: bool = False,
        on_sophia_mode_ticker_enabled_changed: Callable[[bool], None] | None = None,
        experiment_test_mode_available: bool = False,
        experiment_test_mode_enabled: bool = False,
        on_experiment_test_mode_changed: Callable[[bool], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("fpvs_root_settings_dialog")
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumSize(700, 610 if experiment_test_mode_available else 520)
        self.resize(self.minimumSize())

        self._on_show_root_folder_setup = on_show_root_folder_setup
        self._on_manage_condition_templates = on_manage_condition_templates
        self._on_detailed_run_exports_changed = on_detailed_run_exports_changed
        self._on_biosemi_recording_confirmation_required_changed = (
            on_biosemi_recording_confirmation_required_changed
        )
        self._on_sophia_mode_ticker_enabled_changed = (
            on_sophia_mode_ticker_enabled_changed
        )
        self._on_experiment_test_mode_changed = on_experiment_test_mode_changed

        self.header = DialogHeader(
            "Settings",
            "Preferences for this computer. Changes are saved immediately.",
            parent=self,
        )
        workspace = QFrame(self)
        workspace.setObjectName("settings_workspace_section")
        workspace.setProperty("settingsSection", "true")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(16, 12, 16, 12)
        workspace_layout.setSpacing(10)
        workspace_title = QLabel("Workspace", workspace)
        workspace_title.setProperty("settingsSectionTitle", "true")
        workspace_layout.addWidget(workspace_title)
        workspace_actions = QHBoxLayout()
        workspace_actions.setSpacing(12)
        self.root_folder_setup_button = QPushButton("Root Folder Setup...", self)
        self.root_folder_setup_button.setObjectName("root_folder_setup_button")
        self.root_folder_setup_button.setToolTip(str(fpvs_root_dir))
        mark_secondary_action(self.root_folder_setup_button)
        self.root_folder_setup_button.setEnabled(self._on_show_root_folder_setup is not None)
        self.root_folder_setup_button.clicked.connect(self._show_root_folder_setup)
        workspace_actions.addWidget(self.root_folder_setup_button, 1)
        self.manage_templates_button = QPushButton("Manage Condition Templates...", self)
        self.manage_templates_button.setObjectName("manage_condition_templates_button")
        mark_secondary_action(self.manage_templates_button)
        self.manage_templates_button.setEnabled(self._on_manage_condition_templates is not None)
        self.manage_templates_button.clicked.connect(self._manage_condition_templates)
        workspace_actions.addWidget(self.manage_templates_button, 1)
        workspace_layout.addLayout(workspace_actions)
        participant = QFrame(self)
        participant.setObjectName("settings_participant_section")
        participant.setProperty("settingsSection", "true")
        participant_layout = QVBoxLayout(participant)
        participant_layout.setContentsMargins(16, 12, 16, 12)
        participant_layout.setSpacing(10)
        participant_title = QLabel("Participant runs", participant)
        participant_title.setProperty("settingsSectionTitle", "true")
        participant_layout.addWidget(participant_title)
        self.detailed_run_exports_checkbox = QCheckBox(
            "Save detailed runs folder after each participant run",
            self,
        )
        self.detailed_run_exports_checkbox.setObjectName("detailed_run_exports_checkbox")
        self.detailed_run_exports_checkbox.setChecked(detailed_run_exports_enabled)
        self.detailed_run_exports_checkbox.toggled.connect(
            self._set_detailed_run_exports_enabled
        )
        participant_layout.addWidget(self.detailed_run_exports_checkbox)
        self.sophia_mode_checkbox = QCheckBox(
            "Enable Sophia Mode",
            self,
        )
        self.sophia_mode_checkbox.setObjectName("sophia_mode_checkbox")
        self.sophia_mode_checkbox.setToolTip(
            "Requires a NERD Lab administrator to type Confirm before each launch."
        )
        self.sophia_mode_checkbox.setChecked(
            biosemi_recording_confirmation_required
        )
        self.sophia_mode_checkbox.toggled.connect(
            self._set_biosemi_recording_confirmation_required
        )
        self.biosemi_recording_confirmation_checkbox = self.sophia_mode_checkbox
        participant_layout.addWidget(self.sophia_mode_checkbox)
        self.sophia_mode_ticker_checkbox = QCheckBox(
            "Show Sophia Mode ticker on Home",
            self,
        )
        self.sophia_mode_ticker_checkbox.setObjectName("sophia_mode_ticker_checkbox")
        self.sophia_mode_ticker_checkbox.setToolTip(
            "Controls only the Home screen ticker; launch confirmation remains separate."
        )
        self.sophia_mode_ticker_checkbox.setChecked(sophia_mode_ticker_enabled)
        self.sophia_mode_ticker_checkbox.setEnabled(
            biosemi_recording_confirmation_required
        )
        self.sophia_mode_ticker_checkbox.toggled.connect(
            self._set_sophia_mode_ticker_enabled
        )
        participant_layout.addWidget(self.sophia_mode_ticker_checkbox)

        self.experiment_test_mode_checkbox: QCheckBox | None = None
        developer: QFrame | None = None
        if experiment_test_mode_available:
            developer = QFrame(self)
            developer.setObjectName("settings_developer_section")
            developer.setProperty("settingsSection", "true")
            developer_layout = QVBoxLayout(developer)
            developer_layout.setContentsMargins(16, 12, 16, 12)
            developer_layout.setSpacing(10)
            developer_title = QLabel("Development", developer)
            developer_title.setProperty("settingsSectionTitle", "true")
            developer_layout.addWidget(developer_title)
            self.experiment_test_mode_checkbox = QCheckBox(
                "Enable experiment test mode",
                self,
            )
            self.experiment_test_mode_checkbox.setObjectName("experiment_test_mode_checkbox")
            self.experiment_test_mode_checkbox.setToolTip(
                "Uses logged null-trigger output, skips the Sophia Mode recording check, "
                "bypasses connected-display refresh verification, and replaces participant "
                "collection with an explicit test-launch acknowledgement. Fullscreen "
                "presentation remains enabled, along with compiled timing validation and "
                "runtime timing QC. Available only in source-tree Windows and Linux runs."
            )
            self.experiment_test_mode_checkbox.setChecked(experiment_test_mode_enabled)
            self.experiment_test_mode_checkbox.toggled.connect(
                self._set_experiment_test_mode_enabled
            )
            developer_layout.addWidget(self.experiment_test_mode_checkbox)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        self.button_box.setObjectName("settings_button_box")
        mark_secondary_action(self.button_box.button(QDialogButtonBox.StandardButton.Close))
        self.button_box.rejected.connect(self.reject)

        self.version_value = QLabel(f"FPVS Studio version {__version__}", self)
        self.version_value.setObjectName("app_version_value")
        self.version_value.setProperty("dialogHelp", "true")
        self.version_value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        footer_layout = QGridLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setColumnStretch(0, 1)
        footer_layout.setColumnStretch(1, 1)
        footer_layout.setColumnStretch(2, 1)
        footer_layout.addWidget(self.version_value, 0, 1, Qt.AlignmentFlag.AlignCenter)
        footer_layout.addWidget(self.button_box, 0, 2, Qt.AlignmentFlag.AlignRight)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(self.header)
        layout.addWidget(workspace)
        layout.addWidget(participant)
        if developer is not None:
            layout.addWidget(developer)
        layout.addStretch(1)
        layout.addLayout(footer_layout)
        apply_dialog_theme(self)

    def _show_root_folder_setup(self) -> None:
        if self._on_show_root_folder_setup is None:
            return
        updated_root = self._on_show_root_folder_setup(self)
        if updated_root is not None:
            self.root_folder_setup_button.setToolTip(str(updated_root))

    def _manage_condition_templates(self) -> None:
        if self._on_manage_condition_templates is None:
            return
        self._on_manage_condition_templates()

    def _set_detailed_run_exports_enabled(self, checked: bool) -> None:
        if self._on_detailed_run_exports_changed is None:
            return
        self._on_detailed_run_exports_changed(bool(checked))

    def _set_biosemi_recording_confirmation_required(self, checked: bool) -> None:
        self.sophia_mode_ticker_checkbox.setEnabled(bool(checked))
        if self._on_biosemi_recording_confirmation_required_changed is None:
            return
        self._on_biosemi_recording_confirmation_required_changed(bool(checked))

    def _set_sophia_mode_ticker_enabled(self, checked: bool) -> None:
        if self._on_sophia_mode_ticker_enabled_changed is None:
            return
        self._on_sophia_mode_ticker_enabled_changed(bool(checked))

    def _set_experiment_test_mode_enabled(self, checked: bool) -> None:
        if self._on_experiment_test_mode_changed is None:
            return
        self._on_experiment_test_mode_changed(bool(checked))
