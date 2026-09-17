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
    QLineEdit,
    QPushButton,
    QTabWidget,
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
        on_show_library: Callable[[], None] | None = None,
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
        attentional_blink_pilot_mode_available: bool = False,
        attentional_blink_pilot_mode_enabled: bool = False,
        on_attentional_blink_pilot_mode_changed: Callable[[bool], None] | None = None,
        developer_mode_active: bool = False,
        developer_mode_requested: bool = False,
        on_developer_mode_changed: Callable[[bool, str], bool] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("fpvs_root_settings_dialog")
        self.setWindowTitle("Settings")
        self.setModal(True)
        minimum_height = 610 if experiment_test_mode_available else 520
        self.setMinimumSize(700, 680 if attentional_blink_pilot_mode_available else minimum_height)
        self.setMinimumHeight(self.minimumHeight() + 40)
        self.resize(self.minimumSize())

        self._developer_mode_active = developer_mode_active
        self._developer_mode_requested = developer_mode_requested
        self._on_developer_mode_changed = on_developer_mode_changed
        self._on_show_root_folder_setup = on_show_root_folder_setup
        self._on_manage_condition_templates = on_manage_condition_templates
        self._on_show_library = on_show_library
        self._on_detailed_run_exports_changed = on_detailed_run_exports_changed
        self._on_biosemi_recording_confirmation_required_changed = (
            on_biosemi_recording_confirmation_required_changed
        )
        self._on_sophia_mode_ticker_enabled_changed = (
            on_sophia_mode_ticker_enabled_changed
        )
        self._on_experiment_test_mode_changed = on_experiment_test_mode_changed
        self._on_attentional_blink_pilot_mode_changed = on_attentional_blink_pilot_mode_changed

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
        self.library_button = QPushButton("Experiment Library / Manage Access...", self)
        self.library_button.setObjectName("settings_experiment_library")
        self.library_button.setToolTip(
            "Connect with a lab access code or disconnect this computer."
        )
        mark_secondary_action(self.library_button)
        self.library_button.setVisible(on_show_library is not None)
        self.library_button.clicked.connect(self._show_library)
        workspace_layout.addWidget(self.library_button)
        if on_show_library is not None:
            self.setMinimumHeight(self.minimumHeight() + 44)
            self.resize(self.minimumSize())
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
        self.attentional_blink_pilot_mode_checkbox: QCheckBox | None = None
        developer: QFrame | None = None
        if experiment_test_mode_available:
            developer = QFrame(self)
            developer.setObjectName("settings_developer_section")
            developer.setProperty("settingsSection", "true")
            developer_layout = QVBoxLayout(developer)
            developer_layout.setContentsMargins(16, 12, 16, 12)
            developer_layout.setSpacing(10)
            developer_title = QLabel("Local experiment testing", developer)
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
                "runtime timing QC. Available on Windows and Linux, including installed builds."
            )
            self.experiment_test_mode_checkbox.setChecked(experiment_test_mode_enabled)
            self.experiment_test_mode_checkbox.toggled.connect(
                self._set_experiment_test_mode_enabled
            )
            developer_layout.addWidget(self.experiment_test_mode_checkbox)
            if attentional_blink_pilot_mode_available:
                self.attentional_blink_pilot_mode_checkbox = QCheckBox(
                    "Enable Pilot Study Mode (Attentional Blink)", self,
                )
                pilot = self.attentional_blink_pilot_mode_checkbox
                pilot.setObjectName("attentional_blink_pilot_mode_checkbox")
                pilot.setToolTip(
                    "Collects full participant demographics and saves T1/T2 accuracy without "
                    "EEG hardware. Skips Sophia Mode, display refresh and graphics-memory "
                    "checks; fullscreen playback and timing records remain enabled. "
                    "Takes precedence over Test Mode for attentional-blink studies only."
                )
                pilot.setChecked(attentional_blink_pilot_mode_enabled)
                pilot.toggled.connect(self._set_attentional_blink_pilot_mode_enabled)
                developer_layout.addWidget(pilot)
                pilot_help = QLabel(
                    "Pilot runs collect demographics and T1/T2 accuracy without EEG hardware. "
                    "For this study, Pilot Mode takes precedence over Test Mode.", developer,
                )
                pilot_help.setWordWrap(True)
                pilot_help.setProperty("dialogHelp", "true")
                developer_layout.addWidget(pilot_help)

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
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("settings_tabs")
        general = QWidget(self.tabs)
        general_layout = QVBoxLayout(general)
        general_layout.setContentsMargins(0, 8, 0, 0)
        general_layout.setSpacing(12)
        general_layout.addWidget(workspace)
        general_layout.addWidget(participant)
        if developer is not None:
            general_layout.addWidget(developer)
        general_layout.addStretch(1)
        self.tabs.addTab(general, "General")
        advanced = QWidget(self.tabs)
        advanced_layout = QVBoxLayout(advanced)
        advanced_layout.setContentsMargins(16, 16, 16, 16)
        advanced_layout.setSpacing(12)
        self.developer_mode_checkbox = QCheckBox("Enable developer mode", advanced)
        self.developer_mode_checkbox.setObjectName("developer_mode_checkbox")
        self.developer_mode_checkbox.setChecked(developer_mode_requested)
        self.developer_mode_checkbox.setEnabled(on_developer_mode_changed is not None)
        self.developer_mode_checkbox.toggled.connect(self._toggle_developer_mode)
        advanced_layout.addWidget(self.developer_mode_checkbox)
        help_label = QLabel(
            "Enables developer tools, including publishing experiments to the Library. "
            "Changes take effect after restarting FPVS Studio. "
            "Publishing also requires your GitHub account's write access.", advanced,
        )
        help_label.setWordWrap(True)
        advanced_layout.addWidget(help_label)
        self.developer_password_row = QWidget(advanced)
        password_layout = QHBoxLayout(self.developer_password_row)
        password_layout.setContentsMargins(0, 0, 0, 0)
        self.developer_password = QLineEdit(self.developer_password_row)
        self.developer_password.setObjectName("developer_password")
        self.developer_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.developer_password.setPlaceholderText("Developer password")
        self.developer_password.setAccessibleName("Developer password")
        password_layout.addWidget(self.developer_password, 1)
        self.developer_enable_button = QPushButton("Enable", self.developer_password_row)
        self.developer_enable_button.setAutoDefault(False)
        mark_secondary_action(self.developer_enable_button)
        self.developer_enable_button.clicked.connect(self._enable_developer_mode)
        password_layout.addWidget(self.developer_enable_button)
        self.developer_cancel_button = QPushButton("Cancel", self.developer_password_row)
        self.developer_cancel_button.setAutoDefault(False)
        mark_secondary_action(self.developer_cancel_button)
        self.developer_cancel_button.clicked.connect(self._cancel_developer_unlock)
        password_layout.addWidget(self.developer_cancel_button)
        self.developer_password_row.hide()
        advanced_layout.addWidget(self.developer_password_row)
        self.developer_status = QLabel(advanced)
        self.developer_status.setObjectName("developer_mode_status")
        self.developer_status.setWordWrap(True)
        advanced_layout.addWidget(self.developer_status)
        advanced_layout.addStretch(1)
        self.tabs.addTab(advanced, "Advanced")
        self._refresh_developer_status()
        layout.addWidget(self.tabs, 1)
        layout.addLayout(footer_layout)
        apply_dialog_theme(self)

    def _refresh_developer_status(self) -> None:
        if self._developer_mode_requested != self._developer_mode_active:
            state = "enable" if self._developer_mode_requested else "disable"
            self.developer_status.setText(
                f"Restart required. Close and reopen FPVS Studio to {state} developer mode."
            )
        else:
            state = "enabled" if self._developer_mode_active else "disabled"
            self.developer_status.setText(f"Developer mode is {state} for this session.")

    def _toggle_developer_mode(self, enabled: bool) -> None:
        self.developer_password.clear()
        self.developer_password_row.setVisible(enabled and not self._developer_mode_requested)
        self.developer_enable_button.setDefault(enabled and not self._developer_mode_requested)
        if enabled and not self._developer_mode_requested:
            self.developer_status.setText("Enter the developer password to enable this setting.")
            self.developer_password.setFocus()
        elif not enabled:
            if self._on_developer_mode_changed is not None:
                self._on_developer_mode_changed(False, "")
            self._developer_mode_requested = False
            self._refresh_developer_status()

    def _enable_developer_mode(self) -> None:
        if not self.developer_password_row.isVisible():
            return
        password = self.developer_password.text()
        self.developer_password.clear()
        if self._on_developer_mode_changed is None or not self._on_developer_mode_changed(
            True, password
        ):
            self.developer_status.setText("Incorrect developer password. Try again or cancel.")
            self.developer_password.setFocus()
            return
        self._developer_mode_requested = True
        self.developer_enable_button.setDefault(False)
        self.developer_password_row.hide()
        self._refresh_developer_status()

    def _cancel_developer_unlock(self) -> None:
        self.developer_mode_checkbox.setChecked(False)

    def _show_root_folder_setup(self) -> None:
        if self._on_show_root_folder_setup is None:
            return
        updated_root = self._on_show_root_folder_setup(self)
        if updated_root is not None:
            self.root_folder_setup_button.setToolTip(str(updated_root))

    def _show_library(self) -> None:
        if self._on_show_library is not None:
            self.accept()
            self._on_show_library()

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

    def _set_attentional_blink_pilot_mode_enabled(self, checked: bool) -> None:
        if self._on_attentional_blink_pilot_mode_changed is not None:
            self._on_attentional_blink_pilot_mode_changed(bool(checked))

    def _set_experiment_test_mode_enabled(self, checked: bool) -> None:
        if self._on_experiment_test_mode_changed is None:
            return
        self._on_experiment_test_mode_changed(bool(checked))
