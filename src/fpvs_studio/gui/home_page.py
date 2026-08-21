"""Home launch surface for the FPVS Studio main window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QPainter, QPaintEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.models import ConditionTemplateProfile
from fpvs_studio.gui.components import (
    PAGE_SECTION_GAP,
    LaunchSurfaceFrame,
    StatusBadgeLabel,
    apply_home_page_theme,
    create_home_project_icon,
    mark_home_launch_action,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    LauncherReadinessReport,
    _launcher_readiness_report,
)

_HOME_LAUNCH_BUTTON_MIN_HEIGHT = 72
_HOME_LAUNCH_BUTTON_MIN_WIDTH = 280
_HOME_LAUNCH_BUTTON_HORIZONTAL_CHROME = 76
_HOME_LAUNCH_BUTTON_VERTICAL_CHROME = 40
_HOME_LAUNCH_BUTTON_ICON_GAP = 8
_HOME_HERO_MIN_HEIGHT = 328
_SOPHIA_MODE_TICKER_TEXT = (
    "SOPHIA MODE ENABLED    SOPHIA MODE ENABLED    SOPHIA MODE ENABLED"
)
_SOPHIA_MODE_TICKER_HEIGHT = 30
_SOPHIA_MODE_TICKER_INTERVAL_MS = 24
_SOPHIA_MODE_TICKER_STEP_PX = 3


class SophiaModeTicker(QWidget):
    """Scrolling launch-surface indicator shown while Sophia Mode is enabled."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sophia_mode_ticker")
        self.setProperty("sophiaModeTickerActive", "false")
        self.setProperty("sophiaModeTickerText", _SOPHIA_MODE_TICKER_TEXT)
        self.setFixedHeight(_SOPHIA_MODE_TICKER_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ticker_font = self.font()
        ticker_font.setFamily("Consolas")
        ticker_font.setBold(True)
        ticker_font.setPixelSize(13)
        self.setFont(ticker_font)

        self._offset = 0
        self._timer = QTimer(self)
        self._timer.setObjectName("sophia_mode_ticker_timer")
        self._timer.setInterval(_SOPHIA_MODE_TICKER_INTERVAL_MS)
        self._timer.timeout.connect(self._advance_ticker)
        self.setVisible(False)

    def set_sophia_mode_enabled(self, enabled: bool) -> None:
        if not enabled:
            self._timer.stop()
            self.setProperty("sophiaModeTickerActive", "false")
            self.setVisible(False)
            return

        self.setVisible(True)
        self.setProperty("sophiaModeTickerActive", "true")
        self._sync_scroll_offset()
        self.update()
        if not self._timer.isActive():
            self._timer.start()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        if not self.isVisible():
            return
        painter = QPainter(self)
        painter.setClipRect(self.rect())
        painter.setPen(QColor("#00d46a"))
        painter.setFont(self.font())
        metrics = painter.fontMetrics()
        text = f"{_SOPHIA_MODE_TICKER_TEXT}    "
        text_width = max(1, metrics.horizontalAdvance(text))
        baseline = (self.height() + metrics.ascent() - metrics.descent()) // 2
        x = self._offset
        while x > 0:
            x -= text_width
        while x < self.width():
            painter.drawText(x, baseline, text)
            x += text_width

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_scroll_offset()
        if self.isVisible():
            self.update()

    def _advance_ticker(self) -> None:
        if not self.isVisible() or self.width() <= 0:
            return
        text_width = self._ticker_text_width()
        next_offset = self._offset - _SOPHIA_MODE_TICKER_STEP_PX
        if next_offset <= -text_width:
            next_offset = 0
        self._offset = next_offset
        self.update()

    def _sync_scroll_offset(self) -> None:
        if self._offset <= -self._ticker_text_width():
            self._offset = 0

    def _ticker_text_width(self) -> int:
        return max(
            1,
            self.fontMetrics().horizontalAdvance(f"{_SOPHIA_MODE_TICKER_TEXT}    "),
        )


class HomePage(QWidget):
    """Launcher-oriented overview page for the current project."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        load_condition_template_profiles: Callable[[], list[ConditionTemplateProfile]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._load_condition_template_profiles = load_condition_template_profiles
        self._edit_setup_action: Callable[[], None] | None = None
        self._complete_setup_action: Callable[[], None] | None = None
        self.setObjectName("home_page")

        self.new_project_button = QPushButton("Create Project", self)
        self.new_project_button.setObjectName("home_create_project_button")
        self.import_project_button = QPushButton("Import New Project", self)
        self.import_project_button.setObjectName("home_import_project_button")
        self.open_project_button = QPushButton("Open Existing Project", self)
        self.open_project_button.setObjectName("home_open_project_button")
        self.launch_button = QPushButton("Launch Experiment", self)
        self.launch_button.setObjectName("home_launch_experiment_button")
        mark_home_launch_action(self.launch_button)
        self._launch_tooltip_text = (
            "Launch Experiment with fullscreen display verification and timing checks."
        )
        self._launch_status_tip_text = self._launch_tooltip_text
        self.edit_setup_button = QPushButton("Edit Setup", self)
        self.edit_setup_button.setObjectName("home_edit_setup_button")
        mark_secondary_action(self.edit_setup_button)

        for button in (
            self.new_project_button,
            self.import_project_button,
            self.open_project_button,
            self.edit_setup_button,
        ):
            button.setMinimumHeight(38)
            button.setMaximumHeight(38)
            button.setMinimumWidth(160)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.launch_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.launch_status_label = StatusBadgeLabel("Setup Required", self)
        self.launch_status_label.setObjectName("home_launch_status_indicator")
        self.launch_status_label.setMinimumHeight(34)
        self.launch_status_label.setMinimumWidth(224)
        self.launch_status_summary = QLabel(self)
        self.launch_status_summary.setObjectName("home_launch_status_summary")
        self.launch_status_summary.setWordWrap(True)
        self.launch_status_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.launch_status_summary.setMinimumHeight(28)
        self.launch_status_summary.setVisible(False)

        self.launch_surface = LaunchSurfaceFrame(
            frame_object_name="home_launch_panel",
            hero_object_name="home_hero_container",
            parent=self,
        )
        base_margins = self.launch_surface.page_layout.contentsMargins()
        self._launch_surface_base_margins = (
            base_margins.left(),
            base_margins.top(),
            base_margins.right(),
            base_margins.bottom(),
        )
        launch_panel = self.launch_surface.content_frame
        self.sophia_mode_ticker = SophiaModeTicker(launch_panel)
        self.launch_surface.content_layout.insertWidget(0, self.sophia_mode_ticker)
        launch_panel_layout = self.launch_surface.hero_layout
        launch_panel_layout.setSpacing(PAGE_SECTION_GAP)
        self.launch_surface.hero_container.setMinimumHeight(_HOME_HERO_MIN_HEIGHT)

        identity_row = QHBoxLayout()
        identity_row.setContentsMargins(0, 0, 0, 0)
        identity_row.setSpacing(PAGE_SECTION_GAP)
        self.project_icon = create_home_project_icon(launch_panel)
        identity_text = QWidget(launch_panel)
        identity_text_layout = QVBoxLayout(identity_text)
        identity_text_layout.setContentsMargins(0, 0, 0, 0)
        identity_text_layout.setSpacing(6)

        self.current_project_header = QLabel(identity_text)
        self.current_project_header.setObjectName("home_current_project_header")
        self.current_project_header.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.current_project_header.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.current_project_subtitle = QLabel(
            "Open a project, confirm its identity, and launch quickly.",
            identity_text,
        )
        self.current_project_subtitle.setObjectName("home_current_project_subtitle")
        self.current_project_subtitle.setWordWrap(True)
        self.current_project_subtitle.setMaximumHeight(
            self.current_project_subtitle.fontMetrics().lineSpacing() * 2 + 4
        )
        self.current_project_subtitle.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.current_project_subtitle.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        identity_text_layout.addWidget(self.current_project_header)
        identity_text_layout.addWidget(self.current_project_subtitle)
        identity_row.addWidget(
            self.project_icon,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )
        identity_row.addWidget(identity_text, 1)
        identity_row.addWidget(
            self.launch_status_label,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )
        launch_panel_layout.addLayout(identity_row)

        action_layout = QGridLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setHorizontalSpacing(PAGE_SECTION_GAP)
        action_layout.setVerticalSpacing(PAGE_SECTION_GAP)
        for column, button in enumerate(
            (
                self.new_project_button,
                self.import_project_button,
                self.open_project_button,
                self.edit_setup_button,
            )
        ):
            action_layout.addWidget(button, 0, column)
            action_layout.setColumnStretch(column, 1)
        launch_panel_layout.addLayout(action_layout)

        self.condition_count_value = self._new_value_label(
            "home_condition_count_value",
            role="primary",
        )
        self.block_count_value = self._new_value_label(
            "home_block_count_value",
            role="primary",
        )
        self.fixation_task_value = self._new_value_label("home_fixation_task_value")
        self.accuracy_task_value = self._new_value_label("home_accuracy_task_value")

        launch_panel_layout.addWidget(self.launch_status_summary)

        metrics_panel = QFrame(launch_panel)
        metrics_panel.setObjectName("home_metrics_panel")
        metrics_layout = QGridLayout(metrics_panel)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setHorizontalSpacing(0)
        metrics_layout.setVerticalSpacing(0)
        self._add_metric(metrics_layout, 0, "Conditions", self.condition_count_value)
        self._add_metric(metrics_layout, 1, "Blocks", self.block_count_value)
        self._add_metric(metrics_layout, 2, "Fixation Cross", self.fixation_task_value)
        self._add_metric(metrics_layout, 3, "Accuracy Tracking", self.accuracy_task_value)
        for column in range(4):
            metrics_layout.setColumnStretch(column, 1)
        launch_panel_layout.addWidget(metrics_panel)
        launch_panel_layout.addWidget(self.launch_button, 0, Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.launch_surface)

        apply_home_page_theme(self)
        self._sync_launch_button_geometry()

        self._document.project_changed.connect(self.refresh)
        self._document.session_plan_changed.connect(self.refresh)
        self.refresh()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            if getattr(self, "_theme_refreshing", False):
                return
            self._theme_refreshing = True
            try:
                apply_home_page_theme(self)
                self._sync_launch_button_geometry()
            finally:
                self._theme_refreshing = False

    def _sync_launch_button_geometry(self) -> None:
        """Keep the hero launch action large enough for themed text and icon chrome."""

        metrics = self.launch_button.fontMetrics()
        icon_width = 0
        icon_height = 0
        if not self.launch_button.icon().isNull():
            icon_size = self.launch_button.iconSize()
            icon_width = icon_size.width()
            icon_height = icon_size.height()

        content_width = metrics.horizontalAdvance(self.launch_button.text())
        if icon_width:
            content_width += icon_width + _HOME_LAUNCH_BUTTON_ICON_GAP
        width = max(
            _HOME_LAUNCH_BUTTON_MIN_WIDTH,
            content_width + _HOME_LAUNCH_BUTTON_HORIZONTAL_CHROME,
        )
        height = max(
            _HOME_LAUNCH_BUTTON_MIN_HEIGHT,
            max(metrics.height(), icon_height) + _HOME_LAUNCH_BUTTON_VERTICAL_CHROME,
        )
        self.launch_button.setMinimumSize(width, height)
        self.launch_button.setFixedHeight(height)

    def set_top_chrome_offset(self, offset: int) -> None:
        """Keep the launch surface visually stable when main-window chrome is visible."""

        left, top, right, bottom = self._launch_surface_base_margins
        adjusted_top = max(0, top - max(0, offset))
        self.launch_surface.page_layout.setContentsMargins(left, adjusted_top, right, bottom)
        self.launch_surface.page_layout.activate()
        self.launch_surface.content_layout.activate()

    def bind_quick_actions(
        self,
        *,
        new_project_action: QAction,
        import_project_bundle_action: QAction,
        open_project_action: QAction,
        launch_action: QAction,
    ) -> None:
        self._bind_button_to_action(
            self.new_project_button,
            new_project_action,
            "Create Project",
        )
        self._bind_button_to_action(
            self.import_project_button,
            import_project_bundle_action,
            "Import New Project",
        )
        self._bind_button_to_action(
            self.open_project_button,
            open_project_action,
            "Open Existing Project",
        )
        self._bind_button_to_action(
            self.launch_button,
            launch_action,
            "Launch Experiment",
        )
        if launch_action.toolTip():
            self._launch_tooltip_text = launch_action.toolTip()
        if launch_action.statusTip():
            self._launch_status_tip_text = launch_action.statusTip()
        self._set_status_indicator(self._status_report())

    def bind_navigation_actions(
        self,
        *,
        edit_setup: Callable[[], None],
        complete_setup: Callable[[], None] | None = None,
    ) -> None:
        self._edit_setup_action = edit_setup
        self._complete_setup_action = complete_setup or edit_setup
        self.edit_setup_button.clicked.connect(self._open_setup_from_home)

    def refresh(self) -> None:
        project = self._document.project
        session_settings = project.settings.session
        fixation_settings = project.settings.fixation_task
        ordered_conditions = self._document.ordered_conditions()
        report = self._status_report()

        self.current_project_header.setText(project.meta.name)
        subtitle_text = self._project_description_text(project.meta.description)
        self.current_project_subtitle.setText(subtitle_text)
        self.current_project_subtitle.setToolTip(
            " ".join(project.meta.description.split()) or "No description set yet."
        )

        self.condition_count_value.setText(str(len(ordered_conditions)))
        self.block_count_value.setText(str(session_settings.block_count))
        self.fixation_task_value.setText("Enabled" if fixation_settings.enabled else "Disabled")
        self.accuracy_task_value.setText(
            "Enabled" if fixation_settings.accuracy_task_enabled else "Disabled"
        )
        self._refresh_sophia_mode_ticker()
        self._set_status_indicator(report)
        self.launch_surface.hero_layout.activate()

    def _refresh_sophia_mode_ticker(self) -> None:
        self.sophia_mode_ticker.set_sophia_mode_enabled(
            self._document.require_biosemi_recording_confirmation
            and self._document.show_sophia_mode_ticker
        )

    def _status_report(self) -> LauncherReadinessReport:
        return _launcher_readiness_report(
            self._document,
            refresh_hz=self._status_refresh_hz(),
        )

    def _status_refresh_hz(self) -> float:
        preferred_refresh = self._document.project.settings.display.preferred_refresh_hz
        return float(preferred_refresh if preferred_refresh is not None else 60.0)

    @staticmethod
    def _project_description_text(description: str) -> str:
        compact = " ".join(description.split())
        if not compact:
            return "No description set yet."
        if len(compact) > 96:
            compact = f"{compact[:93]}..."
        return compact

    def _set_status_indicator(self, report: LauncherReadinessReport) -> None:
        self.launch_status_label.set_state(report.badge_state, report.status_label)
        is_ready = report.badge_state == "ready"
        self.launch_button.setEnabled(is_ready)
        self._set_setup_action_state(is_ready=is_ready)
        self.launch_status_summary.setText("")
        self.launch_status_summary.setToolTip("")
        self.launch_status_summary.setVisible(False)
        if is_ready:
            self.launch_button.setToolTip(self._normal_launch_tooltip)
            self.launch_button.setStatusTip(self._normal_launch_status_tip)
            return
        blocker_text = _first_actionable_blocker(report)
        self.launch_status_summary.setText(_home_blocker_summary_text(blocker_text))
        self.launch_status_summary.setToolTip(blocker_text)
        self.launch_status_summary.setVisible(True)
        self.launch_button.setToolTip(blocker_text)
        self.launch_button.setStatusTip(blocker_text)

    def _set_setup_action_state(self, *, is_ready: bool) -> None:
        if is_ready:
            self.edit_setup_button.setText("Edit Setup")
            self.edit_setup_button.setProperty("primaryActionRole", "false")
            mark_secondary_action(self.edit_setup_button)
        else:
            self.edit_setup_button.setText("Complete Setup")
            self.edit_setup_button.setProperty("secondaryActionRole", "false")
            mark_primary_action(self.edit_setup_button)

    def _open_setup_from_home(self) -> None:
        report = self._status_report()
        is_ready = report.badge_state == "ready"
        action = self._edit_setup_action if is_ready else self._complete_setup_action
        if action is not None:
            action()

    def _add_metric(
        self,
        layout: QGridLayout,
        column: int,
        label_text: str,
        value_widget: QLabel,
    ) -> None:
        metric_cell = QFrame(self)
        metric_cell.setObjectName("home_metric_cell")
        cell_layout = QVBoxLayout(metric_cell)
        cell_layout.setContentsMargins(14, 12, 14, 12)
        cell_layout.setSpacing(8)
        row_label = QLabel(label_text, metric_cell)
        row_label.setObjectName("home_metric_label")
        row_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_widget.setProperty("homeValueRole", "primary")
        value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cell_layout.addWidget(row_label)
        cell_layout.addWidget(value_widget)
        layout.addWidget(metric_cell, 0, column)

    def _new_value_label(
        self,
        object_name: str,
        *,
        role: str = "secondary",
        selectable: bool = False,
    ) -> QLabel:
        label = QLabel(self)
        label.setObjectName(object_name)
        label.setProperty("homeValueRole", role)
        label.setWordWrap(True)
        if selectable:
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    @staticmethod
    def _bind_button_to_action(button: QPushButton, action: QAction, label: str) -> None:
        button.setText(label)
        if action.toolTip():
            button.setToolTip(action.toolTip())
        if action.statusTip():
            button.setStatusTip(action.statusTip())
        button.clicked.connect(lambda _checked=False, target=action: target.trigger())

    @property
    def _normal_launch_tooltip(self) -> str:
        return self._launch_tooltip_text

    @property
    def _normal_launch_status_tip(self) -> str:
        return self._launch_status_tip_text


def _first_actionable_blocker(report: LauncherReadinessReport) -> str:
    for item in report.readiness_items:
        if item.startswith(("Needs setup:", "Warning:")):
            return item
    return report.status_summary


def _home_blocker_summary_text(blocker_text: str) -> str:
    for prefix in ("Needs setup: ", "Warning: "):
        if blocker_text.startswith(prefix):
            return blocker_text.removeprefix(prefix)
    return blocker_text

