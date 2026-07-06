"""Shared FPVS Studio GUI components, roles, and theme styles.

This module is the public starting point for reusable PySide6 presentation
helpers. Keep persistent model logic, runtime flow, and domain validation out of
this layer.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QPolygon,
    QResizeEvent,
    QShowEvent,
)
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

from fpvs_studio.gui.design_system import (
    CARD_CORNER_RADIUS,
    FONT_SIZE_BODY,
    FONT_SIZE_CONTROL,
    FONT_SIZE_META,
    FONT_SIZE_PAGE_TITLE,
    FONT_SIZE_SECTION_TITLE,
    PAGE_SECTION_GAP,
    PathValueLabel,
    StatusBadgeLabel,
    StudioTheme,
    resolve_studio_theme,
)

NonHomePageShell: Any
PageContainer: Any
SectionCard: Any

__all__ = [
    "LaunchSurfaceFrame",
    "NonHomePageShell",
    "PAGE_SECTION_GAP",
    "PageContainer",
    "PathValueLabel",
    "SectionCard",
    "SetupChecklistPanel",
    "SetupMetricStrip",
    "SetupProgressStepper",
    "SetupSidePanel",
    "SetupSourceCard",
    "SetupWorkspaceFrame",
    "StatusBadgeLabel",
    "apply_condition_template_details_header_style",
    "apply_error_text_style",
    "apply_fixation_settings_theme",
    "apply_home_page_theme",
    "apply_image_size_preview_dialog_theme",
    "apply_non_home_shell_theme",
    "apply_project_overview_theme",
    "apply_section_card_theme",
    "apply_setup_wizard_theme",
    "apply_studio_theme",
    "apply_welcome_window_theme",
    "condition_template_details_header_stylesheet",
    "create_home_project_icon",
    "create_setup_project_icon",
    "error_text_stylesheet",
    "fixation_settings_stylesheet",
    "home_page_stylesheet",
    "image_size_preview_dialog_stylesheet",
    "project_overview_stylesheet",
    "mark_error_text",
    "mark_launch_action",
    "mark_home_launch_action",
    "mark_primary_action",
    "mark_secondary_action",
    "mark_destructive_action",
    "mark_welcome_action",
    "non_home_shell_stylesheet",
    "refresh_widget_style",
    "section_card_stylesheet",
    "studio_theme_stylesheet",
    "welcome_window_stylesheet",
]


class LaunchSurfaceFrame(QWidget):
    """Shared full-window launch/welcome frame with centered inner content."""

    def __init__(
        self,
        *,
        frame_object_name: str,
        hero_object_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(f"{frame_object_name}_surface")
        self.setProperty("launchSurfaceRoot", "true")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.page_layout = QVBoxLayout(self)
        self.page_layout.setContentsMargins(32, 32, 32, 32)
        self.page_layout.setSpacing(16)

        self.content_frame = QFrame(self)
        self.content_frame.setObjectName(frame_object_name)
        self.content_frame.setProperty("launchSurfaceFrame", "true")
        self.content_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.page_layout.addWidget(self.content_frame, 1)

        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(44, 40, 44, 40)
        self.content_layout.setSpacing(0)
        self.content_layout.addStretch(1)

        self.hero_container = QWidget(self.content_frame)
        self.hero_container.setObjectName(hero_object_name)
        self.hero_container.setMaximumWidth(760)
        self.hero_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        self.content_layout.addWidget(
            self.hero_container,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )

        self.hero_layout = QVBoxLayout(self.hero_container)
        self.hero_layout.setContentsMargins(0, 0, 0, 0)
        self.hero_layout.setSpacing(18)

        self.content_layout.addStretch(1)


class SetupChecklistPanel(QFrame):
    """Reusable read-only checklist for guided setup steps."""

    def __init__(
        self,
        title: str = "Ready for next step",
        *,
        object_name: str = "setup_checklist_panel",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setProperty("setupChecklistPanel", "true")
        self._item_labels: list[QLabel] = []
        self._status_labels: list[QLabel] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(10)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName(f"{object_name}_title")
        self.title_label.setProperty("setupChecklistTitle", "true")
        self._layout.addWidget(self.title_label)
        self._divider = QFrame(self)
        self._divider.setObjectName(f"{object_name}_divider")
        self._divider.setFrameShape(QFrame.Shape.HLine)
        self._divider.setProperty("setupChecklistDivider", "true")
        self._layout.addWidget(self._divider)

        self._items_widget = QWidget(self)
        self._items_layout = QGridLayout(self._items_widget)
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setHorizontalSpacing(12)
        self._items_layout.setVerticalSpacing(9)
        self._items_layout.setColumnStretch(0, 1)
        self._layout.addWidget(self._items_widget)
        self._layout.addStretch(1)

    def set_items(self, items: list[tuple[str, bool] | tuple[str, bool, str]]) -> None:
        for item_label in (*self._item_labels, *self._status_labels):
            self._items_layout.removeWidget(item_label)
            item_label.deleteLater()
        self._item_labels = []
        self._status_labels = []

        for row, item in enumerate(items):
            label_text = item[0]
            complete = item[1]
            status_text = item[2] if len(item) > 2 else ("Complete" if complete else "Missing")
            item_label = QLabel(self)
            item_label.setObjectName(f"setup_checklist_item_{_object_suffix(label_text)}")
            item_label.setProperty("setupChecklistItem", "true")
            item_label.setProperty(
                "setupChecklistState",
                "complete" if complete else "incomplete",
            )
            mark = "✓" if complete else "✕"
            mark = "\u2713" if complete else "\u2715"
            item_label.setText(f"{mark} {label_text}")
            status_label = QLabel(status_text, self)
            status_label.setObjectName(
                f"setup_checklist_status_{_object_suffix(label_text)}"
            )
            status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            status_label.setProperty("setupChecklistStatus", "true")
            status_label.setProperty(
                "setupChecklistState",
                "complete" if complete else "incomplete",
            )
            refresh_widget_style(item_label)
            refresh_widget_style(status_label)
            self._items_layout.addWidget(item_label, row, 0)
            self._items_layout.addWidget(status_label, row, 1)
            self._item_labels.append(item_label)
            self._status_labels.append(status_label)

    def item_labels(self) -> tuple[QLabel, ...]:
        return tuple(self._item_labels)

    def status_labels(self) -> tuple[QLabel, ...]:
        return tuple(self._status_labels)


class SetupProgressStepper(QWidget):
    """Connected horizontal progress indicator for Setup Wizard steps."""

    step_requested = Signal(int)

    _CIRCLE_SIZE = 30
    _CIRCLE_TOP = 0
    _CONNECTOR_GAP = 10
    _LABEL_TOP = 34
    _LABEL_HEIGHT = 22
    _STEPPER_HEIGHT = 58
    _SLOT_LABEL_MARGIN = 4

    def __init__(
        self,
        steps: list[str] | tuple[str, ...],
        *,
        object_name: str = "setup_wizard_progress_steps",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setProperty("setupProgressStepper", "true")
        self._steps = tuple(steps)
        self.step_items: list[QWidget] = []
        self.step_circles: list[QLabel] = []
        self.step_labels: list[QLabel] = []
        self.connectors: list[QFrame] = []
        self._navigation_enabled = False
        self._label_refresh_scheduled = False

        self.setMinimumHeight(self._STEPPER_HEIGHT)
        self.setMaximumHeight(self._STEPPER_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        for index, title in enumerate(self._steps):
            item = QWidget(self)
            item.setObjectName(f"setup_wizard_step_{index + 1}_{_object_suffix(title)}")
            item.setProperty("setupProgressStep", "true")
            item.setMinimumWidth(0)
            item.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

            circle = QLabel(str(index + 1), item)
            circle.setObjectName(f"{item.objectName()}_circle")
            circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            circle.setFixedSize(self._CIRCLE_SIZE, self._CIRCLE_SIZE)
            circle.setProperty("setupProgressCircle", "true")

            label = QLabel(title, item)
            label.setObjectName(f"{item.objectName()}_label")
            label.setProperty("setupProgressLabel", "true")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

            for widget in (item, circle, label):
                widget.installEventFilter(self)
            self.step_items.append(item)
            self.step_circles.append(circle)
            self.step_labels.append(label)

            if index < len(self._steps) - 1:
                connector = QFrame(self)
                connector.setObjectName(f"setup_wizard_step_connector_{index + 1}")
                connector.setFrameShape(QFrame.Shape.HLine)
                connector.setProperty("setupProgressConnector", "true")
                connector.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed,
                )
                connector.lower()
                self.connectors.append(connector)

        self.set_active_index(0)
        self._position_step_widgets()

    def sizeHint(self) -> QSize:
        return QSize(920, self._STEPPER_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        return QSize(680, self._STEPPER_HEIGHT)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._position_step_widgets()
        self._schedule_elided_label_refresh()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._schedule_elided_label_refresh()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if (
            self._navigation_enabled
            and event.type() == QEvent.Type.MouseButtonRelease
            and getattr(event, "button", lambda: None)() == Qt.MouseButton.LeftButton
        ):
            step_index = self._step_index_for_watched_widget(watched)
            if step_index is not None:
                self.step_requested.emit(step_index)
                return True
        return super().eventFilter(watched, event)

    def set_navigation_enabled(self, enabled: bool) -> None:
        self._navigation_enabled = bool(enabled)
        cursor = Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor
        for widget in (*self.step_items, *self.step_circles, *self.step_labels):
            widget.setCursor(cursor)

    def set_active_index(self, active_index: int) -> None:
        active_index = max(0, min(active_index, len(self._steps) - 1))
        for index, (item, circle, label) in enumerate(
            zip(self.step_items, self.step_circles, self.step_labels, strict=True)
        ):
            if index < active_index:
                state = "complete"
                circle_text = "\u2713"
            elif index == active_index:
                state = "current"
                circle_text = str(index + 1)
            else:
                state = "upcoming"
                circle_text = str(index + 1)
            for widget in (item, circle, label):
                widget.setProperty("setupProgressState", state)
                refresh_widget_style(widget)
            circle.setText(circle_text)
            item.setAccessibleName(f"{index + 1}. {self._steps[index]}: {state}")
            item.setToolTip(f"Step {index + 1}: {self._steps[index]} ({state})")

        for index, connector in enumerate(self.connectors):
            state = "complete" if index < active_index else "upcoming"
            connector.setProperty("setupProgressState", state)
            refresh_widget_style(connector)
        self._refresh_elided_labels()

    def _step_index_for_watched_widget(self, watched: object) -> int | None:
        for index, widgets in enumerate(
            zip(self.step_items, self.step_circles, self.step_labels, strict=True)
        ):
            if watched in widgets:
                return index
        return None

    def _schedule_elided_label_refresh(self) -> None:
        if self._label_refresh_scheduled:
            return
        self._label_refresh_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_label_refresh)

    def _run_scheduled_label_refresh(self) -> None:
        self._label_refresh_scheduled = False
        self._refresh_elided_labels()

    def _position_step_widgets(self) -> None:
        step_count = len(self.step_items)
        if step_count == 0:
            return

        width = max(0, self.width())
        if width <= 0:
            return

        for index, (item, circle, label) in enumerate(
            zip(self.step_items, self.step_circles, self.step_labels, strict=True)
        ):
            slot_left = round(width * index / step_count)
            slot_right = round(width * (index + 1) / step_count)
            slot_width = max(0, slot_right - slot_left)
            item.setGeometry(slot_left, 0, slot_width, self._STEPPER_HEIGHT)
            circle_x = max(0, round((slot_width - self._CIRCLE_SIZE) / 2))
            circle.setGeometry(
                circle_x,
                self._CIRCLE_TOP,
                self._CIRCLE_SIZE,
                self._CIRCLE_SIZE,
            )
            label.setGeometry(
                self._SLOT_LABEL_MARGIN,
                self._LABEL_TOP,
                max(0, slot_width - (self._SLOT_LABEL_MARGIN * 2)),
                self._LABEL_HEIGHT,
            )

        circle_radius = self._CIRCLE_SIZE // 2
        connector_y = self._CIRCLE_TOP + circle_radius
        for index, connector in enumerate(self.connectors):
            left_center = round(width * (index + 0.5) / step_count)
            right_center = round(width * (index + 1.5) / step_count)
            connector_left = left_center + circle_radius + self._CONNECTOR_GAP
            connector_right = right_center - circle_radius - self._CONNECTOR_GAP
            connector.setGeometry(
                connector_left,
                connector_y,
                max(0, connector_right - connector_left),
                2,
            )
            connector.lower()

    def _refresh_elided_labels(self) -> None:
        for title, label in zip(self._steps, self.step_labels, strict=True):
            available_width = label.width()
            if available_width <= 1:
                label.setText(title)
                label.setToolTip(title)
                continue
            display_text = label.fontMetrics().elidedText(
                title,
                Qt.TextElideMode.ElideRight,
                available_width,
            )
            label.setText(display_text)
            label.setToolTip(title if display_text != title else "")


class SetupWorkspaceFrame(QFrame):
    """Standard left/main/right workspace frame for setup wizard pages."""

    def __init__(
        self,
        *,
        object_name: str = "setup_workspace_frame",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setProperty("setupWorkspaceFrame", "true")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(18, 18, 18, 18)
        self._layout.setSpacing(PAGE_SECTION_GAP)

    def set_regions(
        self,
        *,
        left: QWidget | None = None,
        main: QWidget,
        right: QWidget | None = None,
    ) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        if left is not None:
            left.setMinimumWidth(300)
            self._layout.addWidget(left, 0)
        self._layout.addWidget(main, 1)
        if right is not None:
            right.setMinimumWidth(320)
            self._layout.addWidget(right, 0)


class SetupSidePanel(QFrame):
    """Reusable right-rail panel for setup summaries and actions."""

    def __init__(
        self,
        title: str,
        *,
        object_name: str = "setup_side_panel",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setProperty("setupSidePanel", "true")
        self._rows: list[tuple[QLabel, QLabel]] = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(18, 18, 18, 18)
        self._layout.setSpacing(12)
        self.title_label = QLabel(title, self)
        self.title_label.setProperty("setupSidePanelTitle", "true")
        self._layout.addWidget(self.title_label)
        self.row_grid = QGridLayout()
        self.row_grid.setContentsMargins(0, 0, 0, 0)
        self.row_grid.setHorizontalSpacing(16)
        self.row_grid.setVerticalSpacing(10)
        self.row_grid.setColumnStretch(1, 1)
        self._layout.addLayout(self.row_grid)

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
        for label, value in self._rows:
            self.row_grid.removeWidget(label)
            self.row_grid.removeWidget(value)
            label.deleteLater()
            value.deleteLater()
        self._rows = []
        for row, (label_text, value_text) in enumerate(rows):
            label = QLabel(label_text, self)
            label.setProperty("setupMetricLabel", "true")
            value = QLabel(value_text, self)
            value.setProperty("setupMetricValue", "true")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.row_grid.addWidget(label, row, 0)
            self.row_grid.addWidget(value, row, 1)
            self._rows.append((label, value))

    def add_action_button(self, button: QPushButton) -> None:
        self._layout.addWidget(button)

    def add_helper_text(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setWordWrap(True)
        label.setProperty("setupPanelHelper", "true")
        self._layout.addWidget(label)
        return label


class SetupMetricStrip(QFrame):
    """Compact label/value metric rows for derived setup values."""

    def __init__(
        self,
        *,
        object_name: str = "setup_metric_strip",
        compact: bool = False,
        center_content: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setProperty("setupMetricStrip", "true")
        self._center_content = center_content
        self._rows: list[tuple[QLabel, QLabel]] = []
        self._layout = QGridLayout(self)
        if compact:
            self._layout.setContentsMargins(8, 6, 8, 6)
        else:
            self._layout.setContentsMargins(12, 10, 12, 10)
        self._layout.setHorizontalSpacing(10 if compact else 14)
        self._layout.setVerticalSpacing(4 if compact else 8)
        self._layout.setColumnStretch(1, 1)

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
        for label, value in self._rows:
            self._layout.removeWidget(label)
            self._layout.removeWidget(value)
            label.setVisible(False)
            value.setVisible(False)
            label.deleteLater()
            value.deleteLater()
        self._rows = []
        for row, (label_text, value_text) in enumerate(rows):
            label = QLabel(label_text, self)
            label.setProperty("setupMetricLabel", "true")
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            label.setMinimumWidth(0)
            value = QLabel(value_text, self)
            value.setProperty("setupMetricValue", "true")
            value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            value.setMinimumWidth(0)
            if self._center_content:
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._layout.addWidget(label, row, 0)
            self._layout.addWidget(value, row, 1)
            self._rows.append((label, value))


class SetupSourceCard(QFrame):
    """Reusable display-only stimulus source card with choose-folder intent."""

    choose_requested = Signal()

    def __init__(
        self,
        title: str,
        button_text: str,
        *,
        object_name: str = "setup_source_card",
        compact: bool = False,
        show_variants: bool = True,
        show_folder: bool = True,
        center_title: bool = False,
        center_content: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setProperty("setupSourceCard", "true")
        self._show_variants = show_variants
        self._show_folder = show_folder
        self._layout = QVBoxLayout(self)
        if compact:
            self._layout.setContentsMargins(10, 8, 10, 8)
        else:
            self._layout.setContentsMargins(14, 14, 14, 14)
        self._layout.setSpacing(6 if compact else 10)

        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        self.title_label = QLabel(title, header)
        self.title_label.setProperty("setupSourceTitle", "true")
        self.status_badge = StatusBadgeLabel("Missing", header)
        if center_title:
            self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(self.title_label, 1)
            self.status_badge.setVisible(False)
        else:
            header_layout.addWidget(self.title_label)
            header_layout.addStretch(1)
            header_layout.addWidget(self.status_badge)
        self._layout.addWidget(header)

        folder_label = QLabel("Folder", self)
        folder_label.setProperty("setupMetricLabel", "true")
        self.folder_value = PathValueLabel(self)
        self.folder_value.setObjectName(f"{object_name}_folder")
        if center_content:
            folder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.folder_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        folder_label.setVisible(show_folder)
        self.folder_value.setVisible(show_folder)
        self._layout.addWidget(folder_label)
        self._layout.addWidget(self.folder_value)

        self.metrics = SetupMetricStrip(
            object_name=f"{object_name}_metrics",
            compact=compact,
            center_content=center_content,
            parent=self,
        )
        self._layout.addWidget(self.metrics)

        self.repeat_summary_label = QLabel("", self)
        self.repeat_summary_label.setObjectName(f"{object_name}_repeat_summary")
        self.repeat_summary_label.setProperty("setupMetricValue", "true")
        self.repeat_summary_label.setWordWrap(True)
        self.repeat_summary_label.setMinimumWidth(0)
        self.repeat_summary_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        if compact:
            self.repeat_summary_label.setMinimumHeight(30)
        if center_content:
            self.repeat_summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.repeat_summary_label.setVisible(False)
        self._layout.addWidget(self.repeat_summary_label)

        self.choose_button = QPushButton(button_text, self)
        self.choose_button.setObjectName(f"{object_name}_choose_button")
        self.choose_button.clicked.connect(self.choose_requested.emit)
        mark_secondary_action(self.choose_button)
        self._layout.addWidget(self.choose_button)

    def set_source_state(
        self,
        *,
        ready: bool,
        folder: str,
        image_count: str,
        resolution: str,
        variants: str,
        repeat_balance: str | None = None,
    ) -> None:
        self.status_badge.set_state(
            "ready" if ready else "warning",
            "Ready" if ready else "Missing",
        )
        if self._show_folder:
            self.folder_value.set_path_text(folder or "Not configured", max_length=74)
        rows = [
            ("Image Count", image_count),
            ("Resolution", resolution),
        ]
        self.repeat_summary_label.setText(repeat_balance or "")
        self.repeat_summary_label.setVisible(bool(repeat_balance))
        if self._show_variants:
            rows.append(("Variants", variants))
        self.metrics.set_rows(rows)


def _object_suffix(text: str) -> str:
    suffix = "".join(character.lower() if character.isalnum() else "_" for character in text)
    return "_".join(part for part in suffix.split("_") if part) or "item"


def __getattr__(name: str) -> object:
    if name in {"PageContainer", "NonHomePageShell", "SectionCard"}:
        from fpvs_studio.gui import window_layout

        return getattr(window_layout, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def refresh_widget_style(widget: QWidget) -> None:
    """Repolish a widget after changing a dynamic stylesheet property."""

    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _set_widget_property(widget: QWidget, name: str, value: str) -> None:
    widget.setProperty(name, value)
    refresh_widget_style(widget)


def mark_primary_action(button: QPushButton) -> None:
    _set_widget_property(button, "primaryActionRole", "true")


def mark_secondary_action(button: QPushButton) -> None:
    _set_widget_property(button, "secondaryActionRole", "true")


def mark_destructive_action(button: QPushButton) -> None:
    _set_widget_property(button, "destructiveActionRole", "true")


def mark_launch_action(button: QPushButton, *, home: bool = False) -> None:
    _set_widget_property(button, "launchActionRole", "primary")
    _set_widget_property(button, "primaryActionRole", "true")
    if home:
        _set_widget_property(button, "homeActionRole", "primary")


def mark_home_launch_action(button: QPushButton) -> None:
    mark_launch_action(button, home=True)
    _set_widget_property(button, "homeLaunchHeroAction", "true")
    button.setIcon(_green_play_icon())
    button.setIconSize(QSize(20, 20))


def create_home_project_icon(parent: QWidget | None = None) -> QLabel:
    label = QLabel(parent)
    label.setObjectName("home_project_icon")
    label.setPixmap(_home_project_pixmap())
    label.setFixedSize(48, 48)
    label.setScaledContents(False)
    return label


def create_setup_project_icon(parent: QWidget | None = None) -> QLabel:
    label = QLabel(parent)
    label.setObjectName("setup_project_icon")
    label.setPixmap(_setup_project_pixmap())
    label.setFixedSize(52, 52)
    label.setScaledContents(False)
    return label


def _green_play_icon() -> QIcon:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(Qt.PenStyle.NoPen))
    painter.setBrush(QBrush(QColor("#22c55e")))
    painter.drawPolygon(QPolygon([QPoint(8, 5), QPoint(8, 19), QPoint(19, 12)]))
    painter.end()
    return QIcon(pixmap)


def _home_project_pixmap() -> QPixmap:
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    painter.setPen(QPen(QColor("#1d4ed8"), 1))
    painter.setBrush(QBrush(QColor("#eff6ff")))
    painter.drawRoundedRect(4, 4, 40, 40, 10, 10)

    painter.setPen(QPen(QColor("#2563eb"), 2))
    painter.drawLine(14, 30, 34, 30)
    painter.drawLine(14, 24, 34, 24)
    painter.drawLine(14, 18, 34, 18)

    painter.setPen(QPen(Qt.PenStyle.NoPen))
    painter.setBrush(QBrush(QColor("#22c55e")))
    painter.drawEllipse(12, 16, 5, 5)
    painter.drawEllipse(31, 22, 5, 5)
    painter.drawEllipse(20, 28, 5, 5)
    painter.end()
    return pixmap


def _setup_project_pixmap() -> QPixmap:
    pixmap = QPixmap(52, 52)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    painter.setPen(QPen(QColor("#2563eb"), 2))
    painter.setBrush(QBrush(QColor("#eff6ff")))
    painter.drawRoundedRect(5, 5, 42, 42, 11, 11)

    painter.setPen(QPen(QColor("#1d4ed8"), 2))
    painter.drawRoundedRect(16, 13, 20, 25, 4, 4)
    painter.drawLine(21, 20, 31, 20)
    painter.drawLine(21, 25, 31, 25)
    painter.drawLine(21, 30, 27, 30)

    painter.setPen(QPen(Qt.PenStyle.NoPen))
    painter.setBrush(QBrush(QColor("#22c55e")))
    painter.drawEllipse(32, 32, 8, 8)
    painter.setPen(QPen(QColor("#ffffff"), 2))
    painter.drawLine(34, 36, 36, 38)
    painter.drawLine(36, 38, 40, 33)
    painter.end()
    return pixmap


def mark_welcome_action(button: QPushButton, role: str) -> None:
    if role not in {"primary", "secondary"}:
        raise ValueError(f"Unsupported welcome action role: {role}")
    _set_widget_property(button, "welcomeRole", role)


def mark_error_text(label: QLabel) -> None:
    _set_widget_property(label, "errorText", "true")
    apply_error_text_style(label)


def _resolved_theme(theme: StudioTheme | QPalette | None = None) -> StudioTheme:
    if isinstance(theme, StudioTheme):
        return theme
    return resolve_studio_theme(theme)


def studio_theme_stylesheet(theme: StudioTheme | QPalette | None = None) -> str:
    theme = _resolved_theme(theme)
    color_page_background = theme.page_background
    color_surface = theme.surface
    color_surface_alt = theme.surface_alt
    color_surface_elevated = theme.surface_elevated
    color_border = theme.border
    color_border_soft = theme.border_soft
    color_text_primary = theme.text_primary
    color_text_secondary = theme.text_secondary
    color_primary = theme.primary
    color_primary_border = theme.primary_border
    color_primary_hover = theme.primary_hover
    color_primary_pressed = theme.primary_pressed
    color_success_bg = theme.success_bg
    color_success_border = theme.success_border
    color_success_text = theme.success_text
    color_warning_bg = theme.warning_bg
    color_warning_border = theme.warning_border
    color_warning_text = theme.warning_text
    color_info_bg = theme.info_bg
    color_info_border = theme.info_border
    color_info_text = theme.info_text
    color_pending_bg = theme.pending_bg
    color_pending_border = theme.pending_border
    color_pending_text = theme.pending_text
    return f"""
    QMainWindow#studio_main_window,
    QStackedWidget#main_stack,
    QDialog#update_dialog {{
        background-color: {color_page_background};
        color: {color_text_primary};
        font-size: {FONT_SIZE_BODY}px;
    }}
    QMainWindow#studio_main_window QWidget {{
        font-size: {FONT_SIZE_BODY}px;
    }}
    QWidget#bundle_export_processing_page {{
        background-color: {color_page_background};
        color: {color_text_primary};
    }}
    QLabel#bundle_export_processing_eyebrow_label {{
        color: {color_primary};
        font-size: {FONT_SIZE_BODY}px;
        font-weight: 700;
    }}
    QLabel#bundle_export_processing_title_label {{
        color: {color_text_primary};
        font-size: {FONT_SIZE_PAGE_TITLE + 2}px;
        font-weight: 700;
    }}
    QLabel#bundle_export_processing_message_label {{
        color: {color_text_primary};
        font-size: {FONT_SIZE_SECTION_TITLE + 1}px;
        font-weight: 700;
    }}
    QLabel#bundle_export_processing_detail_label,
    QLabel#bundle_export_processing_status_hint_label {{
        color: {color_text_secondary};
        font-size: {FONT_SIZE_BODY + 1}px;
    }}
    QLabel#bundle_export_processing_status_badge {{
        font-size: {FONT_SIZE_CONTROL + 1}px;
    }}
    QFrame#bundle_export_processing_divider {{
        border: none;
        background-color: {color_border_soft};
        min-width: 1px;
        max-width: 1px;
    }}
    QLabel[processingStepNumber="true"] {{
        border: 1px solid {color_info_border};
        border-radius: 15px;
        background-color: {color_info_bg};
        color: {color_info_text};
        font-size: {FONT_SIZE_BODY}px;
        font-weight: 700;
    }}
    QLabel[processingStepNumber="true"][processingStepState="active"] {{
        border-color: {color_success_border};
        background-color: {color_success_bg};
        color: {color_success_text};
    }}
    QLabel[processingStepNumber="true"][processingStepState="active"][processingStepPulse="on"] {{
        border-color: {color_success_border};
        background-color: {color_success_border};
        color: {theme.selected_text};
    }}
    QLabel[processingStepNumber="true"][processingStepState="complete"] {{
        border-color: {color_success_border};
        background-color: {color_success_bg};
        color: {color_success_text};
    }}
    QLabel[processingStepLabel="true"] {{
        color: {color_text_primary};
        font-size: {FONT_SIZE_BODY + 1}px;
        font-weight: 600;
    }}
    QLabel[processingStepLabel="true"][processingStepState="active"],
    QLabel[processingStepLabel="true"][processingStepState="complete"] {{
        color: {color_success_text};
    }}
    QLabel#update_dialog_title {{
        color: {color_text_primary};
        font-size: {FONT_SIZE_SECTION_TITLE}px;
        font-weight: 700;
    }}
    QLabel#update_dialog_status,
    QLabel#update_dialog_notes {{
        color: {color_text_primary};
        font-size: {FONT_SIZE_BODY}px;
    }}
    QLabel#update_dialog_notes_heading {{
        color: {color_text_primary};
        font-size: {FONT_SIZE_CONTROL}px;
        font-weight: 700;
    }}
    QDialog#update_dialog QProgressBar {{
        border: 1px solid {color_border_soft};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {color_surface_elevated};
        min-height: 14px;
        text-align: center;
    }}
    QDialog#update_dialog QProgressBar::chunk {{
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {color_primary};
    }}
    QTabWidget#main_tabs::pane {{
        border: 1px solid {color_border};
        background-color: {color_surface_elevated};
        top: -1px;
    }}
    QPushButton {{
        border: 1px solid {color_border};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {color_surface_elevated};
        padding: 6px 12px;
        color: {color_text_primary};
        font-size: {FONT_SIZE_CONTROL}px;
        min-height: 30px;
    }}
    QPushButton:hover {{
        border-color: {color_border_soft};
        background-color: {color_surface_alt};
    }}
    QPushButton:pressed {{
        border-color: {color_border_soft};
        background-color: {color_surface_alt};
    }}
    QPushButton:disabled {{
        border-color: {color_border_soft};
        background-color: {color_surface_alt};
        color: {theme.disabled_text};
    }}
    QPushButton[launchActionRole="primary"],
    QPushButton[primaryActionRole="true"] {{
        border-color: {color_primary_border};
        background-color: {color_primary};
        color: {theme.selected_text};
        font-weight: 700;
        padding-left: 14px;
        padding-right: 14px;
    }}
    QPushButton[launchActionRole="primary"]:hover,
    QPushButton[primaryActionRole="true"]:hover {{
        border-color: {color_primary_hover};
        background-color: {color_primary_pressed};
    }}
    QPushButton[launchActionRole="primary"]:pressed,
    QPushButton[primaryActionRole="true"]:pressed {{
        border-color: {color_primary_border};
        background-color: {color_primary_pressed};
    }}
    QPushButton[launchActionRole="primary"]:disabled,
    QPushButton[primaryActionRole="true"]:disabled {{
        border-color: {theme.primary_disabled_bg};
        background-color: {theme.primary_disabled_bg};
        color: {theme.primary_disabled_text};
    }}
    QPushButton[secondaryActionRole="true"] {{
        font-weight: 600;
    }}
    QPushButton[destructiveActionRole="true"] {{
        color: {theme.destructive_text};
        font-weight: 600;
    }}
    QPushButton:focus {{
        border: 2px solid {theme.focus_ring};
    }}
    QLabel[statusBadge="true"] {{
        border: 1px solid {color_border_soft};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {color_surface_elevated};
        color: {color_text_primary};
        padding: 7px 18px;
        font-size: {FONT_SIZE_META}px;
        font-weight: 700;
    }}
    QLabel[statusBadge="true"][statusState="ready"] {{
        border-color: {color_success_border};
        background-color: {color_success_bg};
        color: {color_success_text};
    }}
    QLabel[statusBadge="true"][statusState="warning"] {{
        border-color: {color_warning_border};
        background-color: {color_warning_bg};
        color: {color_warning_text};
    }}
    QLabel[statusBadge="true"][statusState="info"] {{
        border-color: {color_info_border};
        background-color: {color_info_bg};
        color: {color_info_text};
    }}
    QLabel[statusBadge="true"][statusState="pending"] {{
        border-color: {color_pending_border};
        background-color: {color_pending_bg};
        color: {color_pending_text};
    }}
    QLabel[statusBadge="true"][statusState="error"] {{
        border-color: {theme.error_border};
        background-color: {theme.error_bg};
        color: {theme.error_text};
    }}
    QLabel[pathValue="true"] {{
        border: 1px solid {color_border_soft};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {color_surface_elevated};
        color: {color_text_primary};
        padding: 6px 8px;
    }}
    QListWidget#condition_list,
    QListWidget#setup_wizard_condition_list,
    QListWidget#run_readiness_checklist,
    QListWidget#home_readiness_list,
    QListWidget#dashboard_attention_list {{
        border: 1px solid {color_border_soft};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {color_surface_elevated};
        outline: none;
    }}
    QListWidget#condition_list {{
        padding: 4px;
    }}
    QListWidget#setup_wizard_condition_list,
    QListWidget#setup_wizard_condition_image_list {{
        padding: 5px;
    }}
    QListWidget#condition_list::item {{
        padding: 7px 10px;
        border-radius: 8px;
    }}
    QListWidget#setup_wizard_condition_list::item,
    QListWidget#setup_wizard_condition_image_list::item {{
        padding: 5px 10px;
        border-radius: 8px;
    }}
    QListWidget#condition_list::item:hover {{
        background-color: {color_surface_alt};
    }}
    QListWidget#setup_wizard_condition_list::item:hover,
    QListWidget#setup_wizard_condition_image_list::item:hover {{
        background-color: {color_surface_alt};
    }}
    QListWidget#condition_list::item:selected {{
        background-color: {color_primary};
        color: {theme.selected_text};
        font-weight: 700;
    }}
    QListWidget#setup_wizard_condition_list::item:selected,
    QListWidget#setup_wizard_condition_image_list::item:selected {{
        background-color: {color_primary};
        color: {theme.selected_text};
        font-weight: 700;
    }}
    QListWidget#run_readiness_checklist::item,
    QListWidget#home_readiness_list::item,
    QListWidget#dashboard_attention_list::item {{
        padding: 4px 6px;
    }}
    QWidget[setupProgressStepper="true"] {{
        background-color: transparent;
    }}
    QWidget[setupProgressStep="true"] {{
        background-color: transparent;
    }}
    QLabel[setupProgressCircle="true"] {{
        border: 1px solid {color_border_soft};
        border-radius: 15px;
        background-color: {color_surface_elevated};
        color: {color_text_secondary};
        font-size: {FONT_SIZE_CONTROL}px;
        font-weight: 700;
    }}
    QLabel[setupProgressCircle="true"][setupProgressState="complete"] {{
        border-color: {color_success_border};
        background-color: {color_success_bg};
        color: {color_success_text};
    }}
    QLabel[setupProgressCircle="true"][setupProgressState="current"] {{
        border-color: {color_primary_border};
        background-color: {color_primary};
        color: {theme.selected_text};
    }}
    QLabel[setupProgressLabel="true"] {{
        color: {color_text_secondary};
        font-size: {FONT_SIZE_META}px;
        font-weight: 500;
    }}
    QLabel[setupProgressLabel="true"][setupProgressState="current"] {{
        color: {color_primary};
        font-weight: 700;
    }}
    QLabel[setupProgressLabel="true"][setupProgressState="complete"] {{
        color: {color_text_primary};
    }}
    QFrame[setupProgressConnector="true"] {{
        border: none;
        border-top: 1px solid {color_border_soft};
        max-height: 1px;
    }}
    QFrame[setupProgressConnector="true"][setupProgressState="complete"] {{
        border-top: 2px solid {color_primary};
        max-height: 2px;
    }}
    QFrame[setupWorkspaceFrame="true"],
    QFrame[conditionDetailsSection="true"],
    QFrame[setupSidePanel="true"],
    QFrame[setupSourceCard="true"],
    QFrame[setupMetricStrip="true"] {{
        border: 1px solid {color_border_soft};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {color_surface_elevated};
    }}
    QLabel[setupSidePanelTitle="true"],
    QLabel[setupSourceTitle="true"] {{
        color: {color_text_primary};
        font-size: {FONT_SIZE_SECTION_TITLE}px;
        font-weight: 700;
    }}
    QLabel[setupMetricLabel="true"],
    QLabel[setupPanelHelper="true"] {{
        color: {color_text_secondary};
        font-size: {FONT_SIZE_META}px;
    }}
    QLabel[setupMetricValue="true"] {{
        color: {color_text_primary};
        font-weight: 600;
    }}
    QLabel[setupChecklistStatus="true"] {{
        color: {color_success_text};
        font-size: {FONT_SIZE_META}px;
        font-weight: 600;
    }}
    QLabel[setupChecklistStatus="true"][setupChecklistState="incomplete"] {{
        color: {theme.error_text};
    }}
    QFrame[setupChecklistDivider="true"] {{
        border: none;
        border-top: 1px solid {color_border_soft};
        max-height: 1px;
    }}
    QFrame#setup_wizard_status_strip {{
        border-top: 1px solid {color_border_soft};
        background-color: {color_surface};
    }}
    QLabel[wizardStep="true"] {{
        border: 1px solid {color_border_soft};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {color_surface_elevated};
        color: {color_text_secondary};
        padding: 6px 8px;
        font-weight: 600;
    }}
    QLabel[wizardStep="true"][wizardStepState="complete"] {{
        border-color: {color_success_border};
        background-color: {color_success_bg};
        color: {color_success_text};
    }}
    QLabel[wizardStep="true"][wizardStepState="current"] {{
        border-color: {color_primary_border};
        background-color: {color_primary};
        color: {theme.selected_text};
    }}
    QLabel[wizardStep="true"][wizardStepState="upcoming"] {{
        border-color: {color_border_soft};
        background-color: {color_surface_alt};
        color: {color_text_secondary};
    }}
    QTableWidget#assets_table {{
        border: 1px solid {color_border_soft};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {color_surface_elevated};
        gridline-color: {color_border_soft};
        selection-background-color: {color_primary};
        selection-color: {theme.selected_text};
        outline: none;
    }}
    QTableWidget#assets_table QHeaderView::section {{
        background-color: {color_surface_alt};
        border: none;
        border-right: 1px solid {color_border_soft};
        border-bottom: 1px solid {color_border_soft};
        padding: 6px 8px;
        color: {color_text_secondary};
        font-weight: 700;
    }}
    QTableWidget#assets_table::item {{
        padding: 4px 8px;
    }}
    QTableWidget#assets_table::item:selected {{
        background-color: {color_primary};
        color: {theme.selected_text};
    }}
    QTableWidget#assets_table::item:hover {{
        background-color: {color_surface_alt};
    }}
    QPlainTextEdit#assets_status_text,
    QPlainTextEdit#session_summary_text {{
        border: 1px solid {color_border_soft};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {color_surface_elevated};
        color: {color_text_primary};
    }}
    QFrame#run_summary_empty_state {{
        border: 1px dashed {color_border_soft};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {color_surface_elevated};
    }}
    QLabel#run_summary_empty_title {{
        color: {color_text_primary};
        font-size: {FONT_SIZE_SECTION_TITLE}px;
        font-weight: 700;
    }}
    QLabel#run_summary_empty_body {{
        color: {color_text_secondary};
    }}
    QLabel#home_launch_status_summary,
    QLabel#run_readiness_summary_value,
    QLabel#dashboard_attention_note {{
        color: {color_text_secondary};
    }}
    """


def apply_studio_theme(widget: QWidget) -> None:
    widget.setStyleSheet(studio_theme_stylesheet(widget.palette()))


def launch_surface_frame_stylesheet(theme: StudioTheme | QPalette | None = None) -> str:
    theme = _resolved_theme(theme)

    return f"""
    QWidget[launchSurfaceRoot="true"] {{
        background-color: {theme.page_background};
    }}
    QFrame[launchSurfaceFrame="true"] {{
        border: 1px solid {theme.border_soft};
        border-radius: 16px;
        background-color: {theme.surface};
    }}
    """


def home_page_stylesheet(theme: StudioTheme | QPalette | None = None) -> str:
    theme = _resolved_theme(theme)
    return (
        launch_surface_frame_stylesheet(theme)
        + f"""
    QWidget#home_page {{
        color: {theme.text_primary};
        font-size: 13px;
    }}
    QLabel#home_current_project_header {{
        font-size: 28px;
        font-weight: 700;
        color: {theme.text_primary};
    }}
    QLabel#home_current_project_subtitle {{
        font-size: 13px;
        color: {theme.text_secondary};
    }}
    QLabel[homeFieldLabel="true"] {{
        color: {theme.text_muted};
        font-size: 13px;
        font-weight: 600;
    }}
    QLabel[homeValueRole="primary"] {{
        color: {theme.text_primary};
        font-size: 15px;
        font-weight: 600;
    }}
    QLabel[homeValueRole="secondary"] {{
        color: {theme.text_secondary};
        font-size: 13px;
    }}
    QPushButton#home_create_project_button,
    QPushButton#home_open_project_button,
    QPushButton#home_edit_setup_button {{
        font-size: 14px;
        padding: 7px 12px;
    }}
    QFrame#home_launch_panel QLabel#home_launch_status_summary {{
        padding-top: 4px;
    }}
    QFrame#home_metrics_panel {{
        border: 1px solid {theme.border_soft};
        border-radius: 8px;
        background-color: {theme.surface_elevated};
    }}
    QFrame#home_metric_cell {{
        border-right: 1px solid {theme.border_soft};
        background-color: transparent;
    }}
    QLabel#home_metric_label {{
        color: {theme.text_muted};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel[homeValueRole="primary"] {{
        font-size: 20px;
        font-weight: 700;
    }}
    QPushButton#home_launch_experiment_button {{
        font-size: 18px;
        min-height: 54px;
        padding: 10px 24px;
    }}
    QPushButton[launchActionRole="primary"],
    QPushButton[homeActionRole="primary"] {{
        font-weight: 700;
    }}
    QLabel#home_launch_status_indicator {{
        min-height: 28px;
    }}
    QLabel#home_launch_status_summary {{
        color: {theme.text_secondary};
    }}
    """
    )


def apply_home_page_theme(widget: QWidget) -> None:
    widget.setStyleSheet(home_page_stylesheet(widget.palette()))


def project_overview_stylesheet(theme: StudioTheme | QPalette | None = None) -> str:
    theme = _resolved_theme(theme)
    return f"""
    QFrame#dashboard_project_overview_card {{
        background-color: {theme.surface};
    }}
    QLabel#project_overview_title {{
        color: {theme.text_primary};
        font-size: 24px;
        font-weight: 700;
    }}
    QLabel#project_overview_subtitle {{
        color: {theme.text_secondary};
        font-size: 13px;
    }}
    QFrame#project_overview_checklist {{
        border: 1px solid {theme.border_soft};
        border-radius: 8px;
        background-color: {theme.surface_elevated};
    }}
    QFrame[setupChecklistPanel="true"] {{
        border: 1px solid {theme.border_soft};
        border-radius: 8px;
        background-color: {theme.surface_elevated};
    }}
    QLabel[setupChecklistTitle="true"] {{
        color: {theme.text_primary};
        font-size: 13px;
        font-weight: 700;
    }}
    QLabel[setupChecklistItem="true"] {{
        color: {theme.success_text};
        font-size: 12px;
        font-weight: 700;
        padding: 3px 0;
    }}
    QLabel[setupChecklistItem="true"][setupChecklistState="incomplete"] {{
        color: {theme.error_text};
    }}
    """


def apply_project_overview_theme(widget: QWidget) -> None:
    widget.setStyleSheet(project_overview_stylesheet(widget.palette()))


def fixation_settings_stylesheet(theme: StudioTheme | QPalette | None = None) -> str:
    theme = _resolved_theme(theme)
    return f"""
    QFrame#fixation_feasibility_card {{
        border: 1px solid {theme.border_soft};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {theme.surface_elevated};
    }}
    QFrame[fixationSettingsSection="true"],
    QFrame[fixationPreviewPanel="true"] {{
        border: 1px solid {theme.border_soft};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {theme.surface_elevated};
    }}
    QLabel#fixation_feasibility_label {{
        color: {theme.text_primary};
        font-weight: 600;
    }}
    QLabel[fixationSettingsSectionTitle="true"] {{
        color: {theme.text_primary};
        font-weight: 700;
    }}
    """


def apply_fixation_settings_theme(widget: QWidget) -> None:
    widget.setStyleSheet(fixation_settings_stylesheet(widget.palette()))


def non_home_shell_stylesheet(theme: StudioTheme | QPalette | None = None) -> str:
    theme = _resolved_theme(theme)
    return f"""
    QLabel#non_home_shell_title {{
        font-size: {FONT_SIZE_PAGE_TITLE}px;
        font-weight: 700;
        color: {theme.text_primary};
    }}
    QLabel#non_home_shell_subtitle {{
        color: {theme.text_secondary};
        font-size: {FONT_SIZE_BODY}px;
    }}
    QFrame#non_home_shell_footer_strip {{
        border: 1px solid {theme.border_soft};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {theme.surface};
    }}
    QLabel#non_home_shell_footer_label {{
        color: {theme.text_secondary};
    }}
    """


def apply_non_home_shell_theme(widget: QWidget) -> None:
    widget.setStyleSheet(non_home_shell_stylesheet(widget.palette()))


def section_card_stylesheet(theme: StudioTheme | QPalette | None = None) -> str:
    theme = _resolved_theme(theme)
    return f"""
    QFrame[sectionCard="true"] {{
        border: 1px solid {theme.border};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {theme.surface};
    }}
    QFrame#setup_wizard_current_step_card[wizardProjectStepFrame="true"] {{
        border: none;
        background-color: transparent;
    }}
    QFrame[experimentSettingsSection="true"] {{
        border: 1px solid {theme.border_soft};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {theme.surface_elevated};
    }}
    QFrame[reviewSummarySection="true"] {{
        border: 1px solid {theme.border_soft};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {theme.surface_elevated};
    }}
    QFrame[reviewChecklistRow="true"] {{
        border: none;
        background-color: transparent;
    }}
    QLabel[sectionCardRole="title"] {{
        font-size: {FONT_SIZE_SECTION_TITLE}px;
        font-weight: 700;
        color: {theme.text_primary};
    }}
    QLabel[sectionCardRole="subtitle"] {{
        color: {theme.text_secondary};
    }}
    QLabel[reviewChecklistSection="true"],
    QLabel[reviewSummarySectionTitle="true"] {{
        color: {theme.text_primary};
        font-weight: 700;
        padding-top: 2px;
    }}
    QLabel[reviewChecklistLine="true"] {{
        color: {theme.text_primary};
    }}
    QLabel[reviewCheckIcon="true"] {{
        border: 1px solid {theme.success_border};
        border-radius: 10px;
        background-color: {theme.success_bg};
        color: {theme.success_text};
        font-size: {FONT_SIZE_META}px;
        font-weight: 700;
        min-width: 20px;
        max-width: 20px;
        min-height: 20px;
        max-height: 20px;
    }}
    QLabel#section_card_tooltip_badge {{
        border: 1px solid {theme.border_soft};
        border-radius: 8px;
        background-color: {theme.surface_alt};
        color: {theme.text_primary};
        font-size: {FONT_SIZE_META}px;
        font-weight: 700;
    }}
    """


def apply_section_card_theme(widget: QWidget) -> None:
    widget.setStyleSheet(section_card_stylesheet(widget.palette()))


def setup_wizard_stylesheet(theme: StudioTheme | QPalette | None = None) -> str:
    theme = _resolved_theme(theme)
    return (
        section_card_stylesheet(theme)
        + launch_surface_frame_stylesheet(theme)
        + f"""
    QWidget#setup_wizard_page QScrollArea#page_container_scroll_area,
    QWidget#setup_wizard_page QWidget#page_container_scroll_content,
    QWidget#setup_wizard_page QFrame#page_container_content_frame,
    QWidget#setup_wizard_page QFrame#non_home_shell_content_frame {{
        border: none;
        background: transparent;
    }}
    QWidget#setup_wizard_page {{
        color: {theme.text_primary};
        font-size: {FONT_SIZE_BODY}px;
    }}
    QLabel#setup_wizard_next_hint_label {{
        color: {theme.text_secondary};
        font-size: {FONT_SIZE_META}px;
    }}
    """
    )


def apply_setup_wizard_theme(widget: QWidget) -> None:
    widget.setStyleSheet(setup_wizard_stylesheet(widget.palette()))


def welcome_window_stylesheet(theme: StudioTheme | QPalette | None = None) -> str:
    theme = _resolved_theme(theme)
    return launch_surface_frame_stylesheet(theme) + f"""
    QWidget#welcome_hero_container {{
        background: transparent;
    }}
    QLabel#welcome_headline_label {{
        color: {theme.text_primary};
        font-size: 44px;
        font-weight: 700;
    }}
    QLabel#welcome_body_label {{
        color: {theme.text_secondary};
        font-size: 17px;
    }}
    QPushButton {{
        border: 1px solid {theme.border};
        border-radius: 10px;
        padding: 12px 26px;
        background-color: {theme.surface_elevated};
        color: {theme.text_primary};
        font-size: 16px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {theme.surface_alt};
    }}
    QPushButton:pressed {{
        background-color: {theme.surface};
    }}
    QPushButton[welcomeRole="primary"] {{
        border-color: {theme.primary_border};
        background-color: {theme.primary};
        color: {theme.selected_text};
        font-weight: 600;
    }}
    QPushButton[welcomeRole="primary"]:hover {{
        background-color: {theme.primary_hover};
    }}
    QPushButton[welcomeRole="primary"]:pressed {{
        background-color: {theme.primary_pressed};
    }}
    QPushButton:focus {{
        border: 2px solid {theme.focus_ring};
    }}
    """


def apply_welcome_window_theme(widget: QWidget) -> None:
    widget.setStyleSheet(welcome_window_stylesheet(widget.palette()))


def image_size_preview_dialog_stylesheet() -> str:
    return (
        "QDialog#image_size_preview_dialog { background: #101010; }"
        "QLabel#image_size_preview_value_label { color: #f8fafc; }"
        "QWidget#image_size_preview_control_panel { background: #f8fafc; border-radius: 8px; }"
    )


def apply_image_size_preview_dialog_theme(widget: QWidget) -> None:
    widget.setStyleSheet(image_size_preview_dialog_stylesheet())


def error_text_stylesheet() -> str:
    return """
    QLabel[errorText="true"] {
        color: #a1332b;
    }
    """


def apply_error_text_style(label: QLabel) -> None:
    label.setStyleSheet(error_text_stylesheet())


def condition_template_details_header_stylesheet() -> str:
    return """
    font-size: 18px;
    font-weight: 700;
    text-decoration: underline;
    """


def apply_condition_template_details_header_style(label: QLabel) -> None:
    label.setStyleSheet(condition_template_details_header_stylesheet())
