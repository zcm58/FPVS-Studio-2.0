"""Application preferences and the active project's recording-device controls."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio import __version__
from fpvs_studio.gui.components import (
    DialogHeader,
    PathValueLabel,
    apply_dialog_theme,
    mark_error_text,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.recording_dialog import (
    RECORDING_HARDWARE_CHOICES,
    RecordingSetupEditor,
    recording_preference_summary,
)
from fpvs_studio.gui.window_helpers import _show_error_dialog

_LOGGER = logging.getLogger(__name__)


def _section_title(text: str, parent: QWidget) -> QLabel:
    title = QLabel(text, parent)
    title.setProperty("settingsSectionTitle", "true")
    return title


class AppSettingsDialog(QDialog):
    """Expose computer defaults and project recording overrides."""

    def __init__(
        self,
        *,
        fpvs_root_dir: Path,
        initial_category: str = "General",
        theme_mode: str = "auto",
        on_theme_mode_changed: Callable[[str], None] | None = None,
        default_recording_configuration: dict[str, object] | None = None,
        on_default_recording_configuration_changed: Callable[[dict[str, object]], None]
        | None = None,
        recording_configuration: dict[str, object] | None = None,
        biosemi_serial_port: str | None = "COM3",
        biosemi_serial_baudrate: int = 115200,
        on_recording_configuration_changed: Callable[[dict[str, object]], None] | None = None,
        recording_uses_default: bool = False,
        on_use_default_recording_configuration: Callable[[], None] | None = None,
        on_show_root_folder_setup: Callable[[QWidget], Path | None] | None = None,
        on_manage_condition_templates: Callable[[], object] | None = None,
        on_show_library: Callable[[], None] | None = None,
        detailed_run_exports_enabled: bool = False,
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
        automatic_crash_reports_enabled: bool = True,
        automatic_crash_reports_status: str = "Automatic crash reporting is on by default.",
        on_automatic_crash_reports_changed: Callable[[bool], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("fpvs_root_settings_dialog")
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumSize(860, 560)
        self.resize(1000, 680)

        self._developer_mode_active = developer_mode_active
        self._on_theme_mode_changed = on_theme_mode_changed
        self._theme_mode = theme_mode if theme_mode in ("light", "dark", "auto") else "auto"
        self._on_automatic_crash_reports_changed = on_automatic_crash_reports_changed
        self._default_recording_configuration = dict(default_recording_configuration or {
            "recording_backend": "serial", "unicorn_udp_port": 1000,
        })
        self._on_default_recording_configuration_changed = (
            on_default_recording_configuration_changed
        )
        self._recording_uses_default = recording_uses_default
        self._on_use_default_recording_configuration = on_use_default_recording_configuration
        self._recording_configuration = dict(recording_configuration or {
            "recording_backend": None, "unicorn_udp_port": 1000,
        })
        self._biosemi_serial_port = biosemi_serial_port
        self._biosemi_serial_baudrate = biosemi_serial_baudrate
        self._on_recording_configuration_changed = on_recording_configuration_changed
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

        sidebar = QFrame(self)
        sidebar.setObjectName("settings_sidebar")
        sidebar.setFixedWidth(200)
        self.header = DialogHeader("Settings", "", parent=sidebar)
        self.header.subtitle_label.hide()
        self.navigation = QListWidget(sidebar)
        self.navigation.setObjectName("settings_navigation")
        self.navigation.setAccessibleName("Settings categories")
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pages = QStackedWidget(self)
        self.pages.setObjectName("settings_pages")
        self.page_title = QLabel(self)
        self.page_title.setObjectName("settings_page_title")
        self.page_title.setProperty("settingsPageTitle", "true")
        appearance = QWidget(self)
        appearance.setObjectName("settings_appearance_section")
        appearance_layout = QVBoxLayout(appearance)
        appearance_layout.setContentsMargins(0, 0, 0, 0)
        appearance_layout.setSpacing(8)
        appearance_row = QHBoxLayout()
        appearance_row.addWidget(_section_title("Color theme", appearance))
        appearance_row.addStretch(1)
        theme_toggle = QWidget(appearance)
        theme_toggle.setAccessibleName("Color theme")
        theme_toggle_layout = QHBoxLayout(theme_toggle)
        theme_toggle_layout.setContentsMargins(0, 0, 0, 0)
        theme_toggle_layout.setSpacing(0)
        self.theme_button_group = QButtonGroup(self)
        self.theme_button_group.setExclusive(True)
        self.theme_buttons: dict[str, QPushButton] = {}
        for mode, title, position in (
            ("light", "Light", "first"),
            ("dark", "Dark", "middle"),
            ("auto", "Auto", "last"),
        ):
            button = QPushButton(title, theme_toggle)
            button.setObjectName(f"settings_theme_{mode}")
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.setProperty("settingsThemeOption", "true")
            button.setProperty("settingsThemePosition", position)
            button.setMinimumWidth(78)
            button.setToolTip(
                "Follow the system theme." if mode == "auto" else f"Use the {mode} theme."
            )
            self.theme_button_group.addButton(button)
            self.theme_buttons[mode] = button
            theme_toggle_layout.addWidget(button)
            button.clicked.connect(lambda _checked=False, value=mode: self._set_theme_mode(value))
        self.theme_buttons[self._theme_mode].setChecked(True)
        appearance_row.addWidget(theme_toggle)
        appearance_layout.addLayout(appearance_row)
        self.theme_status = QLabel(appearance)
        self.theme_status.setObjectName("settings_theme_status")
        self.theme_status.setWordWrap(True)
        mark_error_text(self.theme_status)
        self.theme_status.hide()
        appearance_layout.addWidget(self.theme_status)

        workspace = QWidget(self)
        workspace.setObjectName("settings_workspace_section")
        workspace.setProperty("settingsSection", "true")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(8)
        root_row = QHBoxLayout()
        root_row.addWidget(_section_title("FPVS Studio Root Folder", workspace))
        root_row.addStretch(1)
        self.root_folder_setup_button = QPushButton("Root Folder Setup...", workspace)
        self.root_folder_setup_button.setObjectName("root_folder_setup_button")
        mark_secondary_action(self.root_folder_setup_button)
        self.root_folder_setup_button.setEnabled(self._on_show_root_folder_setup is not None)
        self.root_folder_setup_button.clicked.connect(self._show_root_folder_setup)
        root_row.addWidget(self.root_folder_setup_button)
        workspace_layout.addLayout(root_row)
        self.root_folder_value = PathValueLabel(workspace)
        self.root_folder_value.setObjectName("settings_root_folder_value")
        self._set_workspace_root(fpvs_root_dir)
        workspace_layout.addWidget(self.root_folder_value)

        workspace_layout.addSpacing(12)
        workspace_actions = QHBoxLayout()
        workspace_actions.setSpacing(12)
        self.manage_templates_button = QPushButton("Manage Condition Templates...", workspace)
        self.manage_templates_button.setObjectName("manage_condition_templates_button")
        mark_secondary_action(self.manage_templates_button)
        self.manage_templates_button.setEnabled(self._on_manage_condition_templates is not None)
        self.manage_templates_button.clicked.connect(self._manage_condition_templates)
        workspace_actions.addWidget(self.manage_templates_button)
        self.library_button = QPushButton("Manage Library Access…", workspace)
        self.library_button.setObjectName("settings_experiment_library")
        self.library_button.setToolTip(
            "Connect with a lab access code or disconnect this computer."
        )
        mark_secondary_action(self.library_button)
        self.library_button.setVisible(on_show_library is not None)
        self.library_button.clicked.connect(self._show_library)
        workspace_actions.addWidget(self.library_button)
        workspace_actions.addStretch(1)
        workspace_layout.addLayout(workspace_actions)
        participant = QWidget(self)
        participant.setObjectName("settings_participant_section")
        participant.setProperty("settingsSection", "true")
        participant_layout = QVBoxLayout(participant)
        participant_layout.setContentsMargins(0, 0, 0, 0)
        participant_layout.setSpacing(8)
        participant_layout.addWidget(_section_title("Participant runs", participant))
        self.detailed_run_exports_checkbox = QCheckBox(
            "Save detailed timing and trigger CSVs",
            self,
        )
        self.detailed_run_exports_checkbox.setObjectName("detailed_run_exports_checkbox")
        self.detailed_run_exports_checkbox.setToolTip(
            "Participant results are always saved in logs/participant_summary.xlsx. "
            "Enable this to also save detailed run folders with timing, event, "
            "response and trigger CSVs."
        )
        self.detailed_run_exports_checkbox.setChecked(detailed_run_exports_enabled)
        self.detailed_run_exports_checkbox.toggled.connect(
            self._set_detailed_run_exports_enabled
        )
        participant_layout.addWidget(self.detailed_run_exports_checkbox)
        self.sophia_mode_checkbox = QCheckBox(
            "Enable Recording Reminder",
            self,
        )
        self.sophia_mode_checkbox.setObjectName("sophia_mode_checkbox")
        self.sophia_mode_checkbox.setToolTip(
            "Type Confirmed after starting EEG recording to continue."
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
            "Show recording reminder ticker on Home",
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
        developer: QWidget | None = None
        if experiment_test_mode_available:
            developer = QWidget(self)
            developer.setObjectName("settings_developer_section")
            developer.setProperty("settingsSection", "true")
            developer_layout = QVBoxLayout(developer)
            developer_layout.setContentsMargins(0, 0, 0, 0)
            developer_layout.setSpacing(8)
            developer_layout.addWidget(_section_title("Local experiment testing", developer))
            self.experiment_test_mode_checkbox = QCheckBox(
                "Enable experiment test mode",
                self,
            )
            self.experiment_test_mode_checkbox.setObjectName("experiment_test_mode_checkbox")
            refresh_policy = (
                "verifies the local display" if sys.platform == "darwin"
                else "bypasses connected-display refresh verification"
            )
            self.experiment_test_mode_checkbox.setToolTip(
                "For this app session only. Starts off each time FPVS Studio opens. "
                "Uses logged null-trigger output, skips the recording reminder, "
                f"{refresh_policy}, and replaces participant "
                "collection with an explicit test-launch acknowledgement. Fullscreen "
                "presentation remains enabled, along with compiled timing validation and "
                "runtime timing QC."
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
                    "Uses the project's demographics questionnaire and saves T1/T2 accuracy "
                    "without EEG hardware. It skips the recording reminder and graphics-memory "
                    f"checks and {refresh_policy}. Fullscreen playback and timing records "
                    "remain enabled. "
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

        self.version_value = QLabel(f"FPVS Studio version {__version__}", sidebar)
        self.version_value.setObjectName("app_version_value")
        self.version_value.setProperty("dialogHelp", "true")
        self.version_value.setWordWrap(True)

        general = QWidget(self)
        general.setObjectName("settings_general_page")
        general_layout = QVBoxLayout(general)
        general_layout.setContentsMargins(0, 0, 0, 0)
        general_layout.setSpacing(20)
        general_layout.addWidget(participant)
        if developer is not None:
            general_layout.addWidget(developer)
        general_layout.addStretch(1)
        recording = QWidget(self)
        recording.setObjectName("settings_recording_page")
        recording_layout = QVBoxLayout(recording)
        recording_layout.setContentsMargins(0, 0, 0, 0)
        recording_layout.setSpacing(12)
        self.recording_summary = QLabel(recording_preference_summary(
            self._recording_configuration,
        ), recording)
        self.recording_summary.setObjectName("settings_recording_summary")
        self.recording_summary.setWordWrap(True)
        recording_layout.addWidget(self.recording_summary)
        self._recording_editor_host = QWidget(recording)
        self._recording_editor_layout = QVBoxLayout(self._recording_editor_host)
        self._recording_editor_layout.setContentsMargins(0, 0, 0, 0)
        self.recording_editor = self._create_recording_editor()
        self._recording_editor_layout.addWidget(self.recording_editor)
        recording_layout.addWidget(self._recording_editor_host)
        self.apply_recording_button = QPushButton("Apply to Project", recording)
        self.apply_recording_button.setObjectName("settings_apply_recording")
        self.apply_recording_button.setAutoDefault(False)
        mark_primary_action(self.apply_recording_button)
        self.apply_recording_button.setVisible(on_recording_configuration_changed is not None)
        self.apply_recording_button.clicked.connect(self._apply_recording_setup)
        self.save_default_recording_button = QPushButton("Save Default Settings", recording)
        self.save_default_recording_button.setObjectName("settings_save_default_recording")
        self.save_default_recording_button.setAutoDefault(False)
        mark_secondary_action(self.save_default_recording_button)
        self.save_default_recording_button.setEnabled(
            on_default_recording_configuration_changed is not None,
        )
        self.save_default_recording_button.setToolTip(
            "Save the displayed hardware settings for this computer. Projects with an override "
            "keep their settings. The BioSemi serial port remains project-specific."
        )
        self.save_default_recording_button.clicked.connect(self._save_default_recording_setup)
        save_recording_row = QHBoxLayout()
        save_recording_row.addWidget(self.apply_recording_button)
        save_recording_row.addWidget(self.save_default_recording_button)
        save_recording_row.addStretch(1)
        recording_layout.addLayout(save_recording_row)
        self.use_default_recording_button = QPushButton("Use Computer Default", recording)
        self.use_default_recording_button.setObjectName("settings_use_default_recording")
        self.use_default_recording_button.setAutoDefault(False)
        mark_secondary_action(self.use_default_recording_button)
        self.use_default_recording_button.setVisible(on_recording_configuration_changed is not None)
        self.use_default_recording_button.setToolTip(
            "Remove this project's recording override and replace the displayed edits with "
            "the computer default. The project's BioSemi serial port is preserved."
        )
        self.use_default_recording_button.clicked.connect(self._use_default_recording_setup)
        recording_layout.addWidget(
            self.use_default_recording_button, 0, Qt.AlignmentFlag.AlignLeft,
        )
        self.default_recording_summary = QLabel(recording)
        self.default_recording_summary.setWordWrap(True)
        self.default_recording_summary.setObjectName("settings_default_recording_summary")
        recording_layout.addWidget(self.default_recording_summary)
        self._refresh_recording_summaries()
        self.finished.connect(lambda _result: self.recording_editor.cancel())
        recording_layout.addStretch(1)
        advanced = QWidget(self)
        advanced.setObjectName("settings_advanced_page")
        advanced_layout = QVBoxLayout(advanced)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(12)
        advanced_layout.addWidget(_section_title("Developer tools", advanced))
        self.developer_mode_checkbox = QCheckBox("Enable developer mode", advanced)
        self.developer_mode_checkbox.setObjectName("developer_mode_checkbox")
        self.developer_mode_checkbox.setToolTip("Restart FPVS Studio to apply this change.")
        self.developer_mode_checkbox.setChecked(developer_mode_requested)
        self.developer_mode_checkbox.setEnabled(on_developer_mode_changed is not None)
        self.developer_mode_checkbox.toggled.connect(self._toggle_developer_mode)
        advanced_layout.addWidget(self.developer_mode_checkbox)
        help_label = QLabel(
            "Publishing to the Experiment Library requires GitHub write access.", advanced,
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
        diagnostics = QWidget(self)
        diagnostics.setObjectName("settings_diagnostics_page")
        diagnostics_layout = QVBoxLayout(diagnostics)
        diagnostics_layout.setContentsMargins(0, 0, 0, 0)
        diagnostics_layout.setSpacing(12)
        diagnostics_layout.addWidget(_section_title("Crash reporting", diagnostics))
        self.crash_reports_checkbox = QCheckBox("Automatically send crash reports", diagnostics)
        self.crash_reports_checkbox.setObjectName("automatic_crash_reports_checkbox")
        self.crash_reports_checkbox.setChecked(automatic_crash_reports_enabled)
        self.crash_reports_checkbox.setEnabled(on_automatic_crash_reports_changed is not None)
        self.crash_reports_checkbox.toggled.connect(self._configure_crash_reports)
        diagnostics_layout.addWidget(self.crash_reports_checkbox)
        crash_help = QLabel(
            "Studio sends a report on the next launch after a crash. "
            "Reports contain the Studio and OS versions, failure category, and sanitized "
            "stack locations. They exclude error messages, full logs, projects, stimuli "
            "and participant records. The reporting service notifies the Studio maintainer.",
            diagnostics,
        )
        crash_help.setWordWrap(True)
        crash_help.setProperty("dialogHelp", "true")
        diagnostics_layout.addWidget(crash_help)
        consent_help = QLabel(
            "This setting applies to this computer. Turning it off discards queued reports "
            "and revokes access when connected. Reports already sent or in transit "
            "cannot be recalled. Use File to send a manual bug report.", diagnostics,
        )
        consent_help.setWordWrap(True)
        consent_help.setProperty("dialogHelp", "true")
        diagnostics_layout.addWidget(consent_help)
        self.crash_reports_status = QLabel(automatic_crash_reports_status, diagnostics)
        self.crash_reports_status.setObjectName("automatic_crash_reports_status")
        self.crash_reports_status.setWordWrap(True)
        diagnostics_layout.addWidget(self.crash_reports_status)
        diagnostics_layout.addStretch(1)
        self._refresh_developer_status()

        self._category_focus_controls = [
            self.detailed_run_exports_checkbox,
            self.recording_editor.backend_combo,
            self.theme_buttons["light"],
            self.root_folder_setup_button,
            self.developer_mode_checkbox,
            self.crash_reports_checkbox,
        ]
        for name, page in (
            ("General", general),
            ("Recording", recording),
            ("Appearance", appearance),
            ("Workspace", workspace),
            ("Advanced", advanced),
            ("Diagnostics", diagnostics),
        ):
            # A page keeps its controls and scroll position when categories change.
            scroll = QScrollArea(self.pages)
            scroll.setObjectName(f"settings_{name.lower()}_scroll")
            scroll.setProperty("settingsPageScroll", "true")
            scroll.viewport().setObjectName("settings_page_viewport")
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setWidget(page)
            page.setAutoFillBackground(False)
            scroll.viewport().setAutoFillBackground(False)
            scroll.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.pages.addWidget(scroll)
            self.navigation.addItem(name)
        # These compact sections remain anchored below their page heading.
        appearance_layout.addStretch(1)
        workspace_layout.addStretch(1)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 24, 16, 20)
        sidebar_layout.setSpacing(20)
        sidebar_layout.addWidget(self.header)
        sidebar_layout.addWidget(self.navigation, 1)
        sidebar_layout.addWidget(self.version_value)
        content = QWidget(self)
        content.setObjectName("settings_content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 24, 28, 20)
        content_layout.setSpacing(20)
        content_layout.addWidget(self.page_title)
        content_layout.addWidget(self.pages, 1)
        content_layout.addWidget(self.button_box)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(sidebar)
        layout.addWidget(content, 1)
        for checkbox in self.findChildren(QCheckBox):
            checkbox.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self.navigation.currentRowChanged.connect(self._select_category)
        matches = self.navigation.findItems(initial_category, Qt.MatchFlag.MatchExactly)
        if not matches:
            raise ValueError(f"Unknown Settings category: {initial_category!r}")
        self.navigation.setCurrentItem(matches[0])
        apply_dialog_theme(self)

    def _select_category(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.page_title.setText(self.navigation.item(index).text())
        QWidget.setTabOrder(self.navigation, self._category_focus_controls[index])

    def _set_theme_mode(self, mode: str) -> None:
        if mode == self._theme_mode:
            return
        try:
            if self._on_theme_mode_changed is not None:
                self._on_theme_mode_changed(mode)
        except (ValueError, OSError):
            _LOGGER.exception("Could not save color theme preference")
            self.theme_buttons[self._theme_mode].setChecked(True)
            self.theme_status.setText("Theme could not be saved. Try again.")
            self.theme_status.show()
            return
        self._theme_mode = mode
        self.theme_status.hide()

    def _configure_crash_reports(self, enabled: bool) -> None:
        if self._on_automatic_crash_reports_changed is not None:
            self._on_automatic_crash_reports_changed(enabled)

    def set_crash_reporting_state(self, enabled: bool, status: str, busy: bool) -> None:
        self.crash_reports_checkbox.blockSignals(True)
        self.crash_reports_checkbox.setChecked(enabled)
        self.crash_reports_checkbox.blockSignals(False)
        self.crash_reports_checkbox.setEnabled(
            self._on_automatic_crash_reports_changed is not None,
        )
        self.crash_reports_status.setText(status)

    def _create_recording_editor(self) -> RecordingSetupEditor:
        project_open = self._on_recording_configuration_changed is not None
        return RecordingSetupEditor(
            (self._recording_configuration if project_open
             else self._default_recording_configuration),
            self._recording_editor_host,
            computer_default=not project_open,
            biosemi_serial_port=self._biosemi_serial_port,
            biosemi_serial_baudrate=self._biosemi_serial_baudrate,
        )

    def _reload_recording_editor(self) -> None:
        previous = self.recording_editor
        previous.cancel()
        self._recording_editor_layout.removeWidget(previous)
        previous.hide()
        previous.deleteLater()
        self.recording_editor = self._create_recording_editor()
        self._recording_editor_layout.addWidget(self.recording_editor)
        self._category_focus_controls[1] = self.recording_editor.backend_combo
        if self.navigation.currentRow() == 1:
            QWidget.setTabOrder(self.navigation, self.recording_editor.backend_combo)

    def _apply_recording_setup(self) -> None:
        if self._on_recording_configuration_changed is None:
            return
        try:
            configuration = self.recording_editor.validated_configuration()
        except ValueError as exc:
            _show_error_dialog(self, "Recording Setup Error", exc)
            return
        port = self._biosemi_serial_port
        payload = dict(configuration)
        if configuration.get("recording_backend") in ("serial", "biosemi_active_three"):
            port = self.recording_editor.biosemi_serial_port
            payload["serial_port"] = port
        try:
            self._on_recording_configuration_changed(payload)
        except (ValueError, OSError) as exc:
            _LOGGER.exception("Could not save project recording settings")
            _show_error_dialog(self, "Save Recording Setup Error", exc)
            return
        self._recording_configuration = configuration
        self._biosemi_serial_port = port
        self._recording_uses_default = False
        self.recording_editor.retain_reviewed_selection()
        self._refresh_recording_summaries()

    def _refresh_recording_summaries(self) -> None:
        self.recording_summary.setToolTip("")
        self.default_recording_summary.setToolTip("")
        backend = self._default_recording_configuration.get("recording_backend")
        label = next(
            (label for label, value in RECORDING_HARDWARE_CHOICES if value == backend),
            "Choose EEG hardware",
        )
        self.default_recording_summary.setText(f"Computer default: {label}")
        if self._on_recording_configuration_changed is None:
            text = "Settings for this computer"
        else:
            summary = recording_preference_summary({
                **self._recording_configuration, "serial_port": self._biosemi_serial_port,
            })
            scope = "Using computer default" if self._recording_uses_default else "Project override"
            text = f"{scope}: {summary}"
        self.recording_summary.setText(text)
        self.use_default_recording_button.setEnabled(
            self._on_use_default_recording_configuration is not None
            and not self._recording_uses_default,
        )

    def _save_default_recording_setup(self) -> None:
        if self._on_default_recording_configuration_changed is None:
            return
        try:
            configuration = self.recording_editor.validated_configuration(computer_default=True)
        except ValueError as exc:
            _show_error_dialog(self, "Recording Setup Error", exc)
            return
        try:
            self._on_default_recording_configuration_changed(configuration)
        except (ValueError, OSError) as exc:
            _LOGGER.exception("Could not save computer recording default")
            _show_error_dialog(self, "Save Default Recording Setup Error", exc)
            return
        self._default_recording_configuration = configuration
        if self._recording_uses_default or self._on_recording_configuration_changed is None:
            self._recording_configuration = dict(configuration)
        self.recording_editor.retain_reviewed_selection()
        self._refresh_recording_summaries()

    def _use_default_recording_setup(self) -> None:
        if self._on_use_default_recording_configuration is None:
            return
        try:
            self._on_use_default_recording_configuration()
        except (ValueError, OSError) as exc:
            _LOGGER.exception("Could not reset project recording choice")
            _show_error_dialog(self, "Reset Recording Setup Error", exc)
            return
        self._recording_uses_default = True
        self._recording_configuration = dict(self._default_recording_configuration)
        self._reload_recording_editor()
        self._refresh_recording_summaries()

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
            self._set_workspace_root(updated_root)

    def _set_workspace_root(self, root: Path) -> None:
        full_path = str(root)
        self.root_folder_value.set_path_text(full_path)
        self.root_folder_value.setAccessibleName(f"FPVS Studio Root Folder: {full_path}")

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
