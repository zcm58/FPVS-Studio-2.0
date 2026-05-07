"""Shared FPVS Studio GUI components, roles, and theme styles.

This module is the public starting point for reusable PySide6 presentation
helpers. Keep persistent model logic, runtime flow, and domain validation out of
this layer.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, QSize, Qt, Signal
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
    COLOR_BORDER,
    COLOR_BORDER_SOFT,
    COLOR_INFO_BG,
    COLOR_INFO_BORDER,
    COLOR_INFO_TEXT,
    COLOR_PENDING_BG,
    COLOR_PENDING_BORDER,
    COLOR_PENDING_TEXT,
    COLOR_PRIMARY,
    COLOR_PRIMARY_BORDER,
    COLOR_PRIMARY_HOVER,
    COLOR_PRIMARY_PRESSED,
    COLOR_SUCCESS_BG,
    COLOR_SUCCESS_BORDER,
    COLOR_SUCCESS_TEXT,
    COLOR_SURFACE,
    COLOR_SURFACE_ALT,
    COLOR_SURFACE_ELEVATED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_WARNING_BG,
    COLOR_WARNING_BORDER,
    COLOR_WARNING_TEXT,
    PAGE_SECTION_GAP,
    PathValueLabel,
    StatusBadgeLabel,
)

NonHomePageShell: Any
PageContainer: Any
SectionCard: Any

__all__ = [
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
    "apply_non_home_shell_theme",
    "apply_section_card_theme",
    "apply_studio_theme",
    "apply_welcome_window_theme",
    "condition_template_details_header_stylesheet",
    "create_home_project_icon",
    "create_setup_project_icon",
    "error_text_stylesheet",
    "fixation_settings_stylesheet",
    "home_page_stylesheet",
    "apply_project_overview_theme",
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

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for index, title in enumerate(self._steps):
            item = QWidget(self)
            item.setObjectName(f"setup_wizard_step_{index + 1}_{_object_suffix(title)}")
            item.setProperty("setupProgressStep", "true")
            item.setMinimumWidth(0)
            item.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(6)

            circle = QLabel(str(index + 1), item)
            circle.setObjectName(f"{item.objectName()}_circle")
            circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            circle.setFixedSize(30, 30)
            circle.setProperty("setupProgressCircle", "true")

            label = QLabel(title, item)
            label.setObjectName(f"{item.objectName()}_label")
            label.setProperty("setupProgressLabel", "true")
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

            item_layout.addWidget(circle)
            item_layout.addWidget(label, 1)
            layout.addWidget(item, 1)
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
                layout.addWidget(connector, 1)
                self.connectors.append(connector)

        self.set_active_index(0)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh_elided_labels()

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

    def _refresh_elided_labels(self) -> None:
        for title, label in zip(self._steps, self.step_labels, strict=True):
            available_width = max(1, label.width())
            label.setText(
                label.fontMetrics().elidedText(
                    title,
                    Qt.TextElideMode.ElideRight,
                    available_width,
                )
            )


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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setProperty("setupMetricStrip", "true")
        self._rows: list[tuple[QLabel, QLabel]] = []
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(12, 10, 12, 10)
        self._layout.setHorizontalSpacing(14)
        self._layout.setVerticalSpacing(8)
        self._layout.setColumnStretch(1, 1)

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
        for label, value in self._rows:
            self._layout.removeWidget(label)
            self._layout.removeWidget(value)
            label.deleteLater()
            value.deleteLater()
        self._rows = []
        for row, (label_text, value_text) in enumerate(rows):
            label = QLabel(label_text, self)
            label.setProperty("setupMetricLabel", "true")
            value = QLabel(value_text, self)
            value.setProperty("setupMetricValue", "true")
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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setProperty("setupSourceCard", "true")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 14, 14, 14)
        self._layout.setSpacing(10)

        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        self.title_label = QLabel(title, header)
        self.title_label.setProperty("setupSourceTitle", "true")
        self.status_badge = StatusBadgeLabel("Missing", header)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.status_badge)
        self._layout.addWidget(header)

        folder_label = QLabel("Folder", self)
        folder_label.setProperty("setupMetricLabel", "true")
        self.folder_value = PathValueLabel(self)
        self.folder_value.setObjectName(f"{object_name}_folder")
        self._layout.addWidget(folder_label)
        self._layout.addWidget(self.folder_value)

        self.metrics = SetupMetricStrip(object_name=f"{object_name}_metrics", parent=self)
        self._layout.addWidget(self.metrics)

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
    ) -> None:
        self.status_badge.set_state(
            "ready" if ready else "warning",
            "Ready" if ready else "Missing",
        )
        self.folder_value.set_path_text(folder or "Not configured", max_length=74)
        self.metrics.set_rows(
            [
                ("Image Count", image_count),
                ("Resolution", resolution),
                ("Variants", variants),
            ]
        )


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


def studio_theme_stylesheet() -> str:
    return f"""
    QTabWidget#main_tabs::pane {{
        border: 1px solid {COLOR_BORDER};
        background-color: {COLOR_SURFACE_ELEVATED};
        top: -1px;
    }}
    QPushButton {{
        border: 1px solid {COLOR_BORDER};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {COLOR_SURFACE_ELEVATED};
        padding: 6px 12px;
        color: {COLOR_TEXT_PRIMARY};
        min-height: 30px;
    }}
    QPushButton:hover {{
        border-color: {COLOR_BORDER_SOFT};
        background-color: {COLOR_SURFACE_ALT};
    }}
    QPushButton:pressed {{
        border-color: {COLOR_BORDER_SOFT};
        background-color: {COLOR_SURFACE_ALT};
    }}
    QPushButton:disabled {{
        border-color: {COLOR_BORDER_SOFT};
        background-color: {COLOR_SURFACE_ALT};
        color: #8a97a8;
    }}
    QPushButton[launchActionRole="primary"],
    QPushButton[primaryActionRole="true"] {{
        border-color: {COLOR_PRIMARY_BORDER};
        background-color: {COLOR_PRIMARY};
        color: #ffffff;
        font-weight: 700;
        padding-left: 14px;
        padding-right: 14px;
    }}
    QPushButton[launchActionRole="primary"]:hover,
    QPushButton[primaryActionRole="true"]:hover {{
        border-color: {COLOR_PRIMARY_HOVER};
        background-color: {COLOR_PRIMARY_PRESSED};
    }}
    QPushButton[launchActionRole="primary"]:pressed,
    QPushButton[primaryActionRole="true"]:pressed {{
        border-color: {COLOR_PRIMARY_BORDER};
        background-color: {COLOR_PRIMARY_PRESSED};
    }}
    QPushButton[launchActionRole="primary"]:disabled,
    QPushButton[primaryActionRole="true"]:disabled {{
        border-color: #93c5fd;
        background-color: #93c5fd;
        color: #eff6ff;
    }}
    QPushButton[secondaryActionRole="true"] {{
        font-weight: 600;
    }}
    QPushButton[destructiveActionRole="true"] {{
        color: #b91c1c;
        font-weight: 600;
    }}
    QPushButton:focus {{
        border: 2px solid {COLOR_PRIMARY};
    }}
    QLabel[statusBadge="true"] {{
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {COLOR_SURFACE_ELEVATED};
        color: {COLOR_TEXT_PRIMARY};
        padding: 5px 10px;
        font-size: 12px;
        font-weight: 700;
    }}
    QLabel[statusBadge="true"][statusState="ready"] {{
        border-color: {COLOR_SUCCESS_BORDER};
        background-color: {COLOR_SUCCESS_BG};
        color: {COLOR_SUCCESS_TEXT};
    }}
    QLabel[statusBadge="true"][statusState="warning"] {{
        border-color: {COLOR_WARNING_BORDER};
        background-color: {COLOR_WARNING_BG};
        color: {COLOR_WARNING_TEXT};
    }}
    QLabel[statusBadge="true"][statusState="info"] {{
        border-color: {COLOR_INFO_BORDER};
        background-color: {COLOR_INFO_BG};
        color: {COLOR_INFO_TEXT};
    }}
    QLabel[statusBadge="true"][statusState="pending"] {{
        border-color: {COLOR_PENDING_BORDER};
        background-color: {COLOR_PENDING_BG};
        color: {COLOR_PENDING_TEXT};
    }}
    QLabel[statusBadge="true"][statusState="error"] {{
        border-color: #fca5a5;
        background-color: #fef2f2;
        color: #991b1b;
    }}
    QLabel[pathValue="true"] {{
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {COLOR_SURFACE_ELEVATED};
        color: {COLOR_TEXT_PRIMARY};
        padding: 6px 8px;
    }}
    QListWidget#condition_list,
    QListWidget#setup_wizard_condition_list,
    QListWidget#run_readiness_checklist,
    QListWidget#home_readiness_list,
    QListWidget#dashboard_attention_list,
    QListWidget#setup_wizard_step_list,
    QListWidget#setup_wizard_review_readiness_list {{
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {COLOR_SURFACE_ELEVATED};
        outline: none;
    }}
    QListWidget#condition_list {{
        padding: 4px;
    }}
    QListWidget#setup_wizard_condition_list {{
        padding: 5px;
    }}
    QListWidget#condition_list::item {{
        padding: 7px 10px;
        border-radius: 8px;
    }}
    QListWidget#setup_wizard_condition_list::item {{
        padding: 10px 12px;
        border-radius: 8px;
    }}
    QListWidget#condition_list::item:hover {{
        background-color: {COLOR_SURFACE_ALT};
    }}
    QListWidget#setup_wizard_condition_list::item:hover {{
        background-color: {COLOR_SURFACE_ALT};
    }}
    QListWidget#condition_list::item:selected {{
        background-color: {COLOR_PRIMARY};
        color: #ffffff;
        font-weight: 700;
    }}
    QListWidget#setup_wizard_condition_list::item:selected {{
        background-color: {COLOR_PRIMARY};
        color: #ffffff;
        font-weight: 700;
    }}
    QListWidget#run_readiness_checklist::item,
    QListWidget#home_readiness_list::item,
    QListWidget#dashboard_attention_list::item,
    QListWidget#setup_wizard_step_list::item,
    QListWidget#setup_wizard_review_readiness_list::item {{
        padding: 4px 6px;
    }}
    QListWidget#setup_wizard_step_list::item:selected {{
        background-color: {COLOR_PRIMARY};
        color: #ffffff;
        font-weight: 700;
    }}
    QWidget[setupProgressStepper="true"] {{
        background-color: transparent;
    }}
    QWidget[setupProgressStep="true"] {{
        background-color: transparent;
    }}
    QLabel[setupProgressCircle="true"] {{
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: 15px;
        background-color: {COLOR_SURFACE_ELEVATED};
        color: {COLOR_TEXT_SECONDARY};
        font-size: 13px;
        font-weight: 700;
    }}
    QLabel[setupProgressCircle="true"][setupProgressState="complete"] {{
        border-color: {COLOR_SUCCESS_BORDER};
        background-color: {COLOR_SUCCESS_BG};
        color: {COLOR_SUCCESS_TEXT};
    }}
    QLabel[setupProgressCircle="true"][setupProgressState="current"] {{
        border-color: {COLOR_PRIMARY_BORDER};
        background-color: {COLOR_PRIMARY};
        color: #ffffff;
    }}
    QLabel[setupProgressLabel="true"] {{
        color: {COLOR_TEXT_SECONDARY};
        font-weight: 500;
    }}
    QLabel[setupProgressLabel="true"][setupProgressState="current"] {{
        color: {COLOR_PRIMARY};
        font-weight: 700;
    }}
    QLabel[setupProgressLabel="true"][setupProgressState="complete"] {{
        color: {COLOR_TEXT_PRIMARY};
    }}
    QFrame[setupProgressConnector="true"] {{
        border: none;
        border-top: 1px solid {COLOR_BORDER_SOFT};
        max-height: 1px;
    }}
    QFrame[setupProgressConnector="true"][setupProgressState="complete"] {{
        border-top: 2px solid {COLOR_PRIMARY};
        max-height: 2px;
    }}
    QFrame[setupWorkspaceFrame="true"],
    QFrame[setupSidePanel="true"],
    QFrame[setupSourceCard="true"],
    QFrame[setupMetricStrip="true"] {{
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {COLOR_SURFACE_ELEVATED};
    }}
    QLabel[setupSidePanelTitle="true"],
    QLabel[setupSourceTitle="true"] {{
        color: {COLOR_TEXT_PRIMARY};
        font-size: 15px;
        font-weight: 700;
    }}
    QLabel[setupMetricLabel="true"],
    QLabel[setupPanelHelper="true"] {{
        color: {COLOR_TEXT_SECONDARY};
    }}
    QLabel[setupMetricValue="true"] {{
        color: {COLOR_TEXT_PRIMARY};
        font-weight: 600;
    }}
    QLabel[setupChecklistStatus="true"] {{
        color: {COLOR_SUCCESS_TEXT};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel[setupChecklistStatus="true"][setupChecklistState="incomplete"] {{
        color: #991b1b;
    }}
    QFrame[setupChecklistDivider="true"] {{
        border: none;
        border-top: 1px solid {COLOR_BORDER_SOFT};
        max-height: 1px;
    }}
    QFrame#setup_wizard_status_strip {{
        border-top: 1px solid {COLOR_BORDER_SOFT};
        background-color: {COLOR_SURFACE};
    }}
    QLabel#setup_wizard_status_message,
    QLabel#setup_wizard_runtime_mode_label {{
        color: {COLOR_TEXT_SECONDARY};
    }}
    QLabel[wizardStep="true"] {{
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {COLOR_SURFACE_ELEVATED};
        color: {COLOR_TEXT_SECONDARY};
        padding: 6px 8px;
        font-weight: 600;
    }}
    QLabel[wizardStep="true"][wizardStepState="complete"] {{
        border-color: {COLOR_SUCCESS_BORDER};
        background-color: {COLOR_SUCCESS_BG};
        color: {COLOR_SUCCESS_TEXT};
    }}
    QLabel[wizardStep="true"][wizardStepState="current"] {{
        border-color: {COLOR_PRIMARY_BORDER};
        background-color: {COLOR_PRIMARY};
        color: #ffffff;
    }}
    QLabel[wizardStep="true"][wizardStepState="upcoming"] {{
        border-color: {COLOR_BORDER_SOFT};
        background-color: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT_SECONDARY};
    }}
    QTableWidget#assets_table {{
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {COLOR_SURFACE_ELEVATED};
        gridline-color: {COLOR_BORDER_SOFT};
        selection-background-color: {COLOR_PRIMARY};
        selection-color: #ffffff;
        outline: none;
    }}
    QTableWidget#assets_table QHeaderView::section {{
        background-color: {COLOR_SURFACE_ALT};
        border: none;
        border-right: 1px solid {COLOR_BORDER_SOFT};
        border-bottom: 1px solid {COLOR_BORDER_SOFT};
        padding: 6px 8px;
        color: {COLOR_TEXT_SECONDARY};
        font-weight: 700;
    }}
    QTableWidget#assets_table::item {{
        padding: 4px 8px;
    }}
    QTableWidget#assets_table::item:selected {{
        background-color: {COLOR_PRIMARY};
        color: #ffffff;
    }}
    QTableWidget#assets_table::item:hover {{
        background-color: {COLOR_SURFACE_ALT};
    }}
    QPlainTextEdit#assets_status_text,
    QPlainTextEdit#session_summary_text {{
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {COLOR_SURFACE_ELEVATED};
        color: {COLOR_TEXT_PRIMARY};
    }}
    QFrame#run_summary_empty_state {{
        border: 1px dashed {COLOR_BORDER_SOFT};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {COLOR_SURFACE_ELEVATED};
    }}
    QLabel#run_summary_empty_title {{
        color: {COLOR_TEXT_PRIMARY};
        font-size: 14px;
        font-weight: 700;
    }}
    QLabel#run_summary_empty_body {{
        color: {COLOR_TEXT_SECONDARY};
    }}
    QLabel#home_launch_status_summary,
    QLabel#run_readiness_summary_value,
    QLabel#dashboard_attention_note {{
        color: {COLOR_TEXT_SECONDARY};
    }}
    """


def apply_studio_theme(widget: QWidget) -> None:
    widget.setStyleSheet(studio_theme_stylesheet())


def home_page_stylesheet() -> str:
    return """
    QWidget#home_page {
        color: #243447;
        font-size: 13px;
    }
    QLabel#home_current_project_header {
        font-size: 28px;
        font-weight: 700;
        color: #142033;
    }
    QLabel#home_current_project_subtitle {
        font-size: 13px;
        color: #495869;
    }
    QLabel[homeFieldLabel="true"] {
        color: #4c5d73;
        font-size: 13px;
        font-weight: 600;
    }
    QLabel[homeValueRole="primary"] {
        color: #1f2f44;
        font-size: 15px;
        font-weight: 600;
    }
    QLabel[homeValueRole="secondary"] {
        color: #2f435b;
        font-size: 13px;
    }
    QPushButton#home_create_project_button,
    QPushButton#home_open_project_button,
    QPushButton#home_save_project_button,
    QPushButton#home_edit_setup_button {
        font-size: 14px;
        padding: 7px 12px;
    }
    QWidget#home_launch_panel {
        border: 1px solid #c7d2e5;
        border-radius: 8px;
        background-color: #f8fbff;
    }
    QWidget#home_launch_panel QLabel#home_launch_status_summary {
        padding-top: 4px;
    }
    QFrame#home_metrics_panel {
        border: 1px solid #d6e0ef;
        border-radius: 8px;
        background-color: #ffffff;
    }
    QFrame#home_metric_cell {
        border-right: 1px solid #d6e0ef;
        background-color: transparent;
    }
    QLabel#home_metric_label {
        color: #52637a;
        font-size: 12px;
        font-weight: 600;
    }
    QLabel[homeValueRole="primary"] {
        font-size: 20px;
        font-weight: 700;
    }
    QPushButton#home_launch_experiment_button {
        font-size: 18px;
        min-height: 54px;
        padding: 10px 24px;
    }
    QPushButton[launchActionRole="primary"],
    QPushButton[homeActionRole="primary"] {
        font-weight: 700;
    }
    QLabel#home_launch_status_indicator {
        min-height: 28px;
    }
    QLabel#home_launch_status_summary {
        color: #33485f;
    }
    """


def apply_home_page_theme(widget: QWidget) -> None:
    widget.setStyleSheet(home_page_stylesheet())


def project_overview_stylesheet() -> str:
    return """
    QFrame#dashboard_project_overview_card {
        background-color: #f8fbff;
    }
    QLabel#project_overview_title {
        color: #142033;
        font-size: 24px;
        font-weight: 700;
    }
    QLabel#project_overview_subtitle {
        color: #495869;
        font-size: 13px;
    }
    QLabel#project_overview_step_badge {
        border: 1px solid #c7d2e5;
        border-radius: 8px;
        background-color: #eef6ff;
        color: #27476f;
        font-size: 12px;
        font-weight: 700;
        padding: 6px 10px;
    }
    QFrame#project_overview_checklist {
        border: 1px solid #d6e0ef;
        border-radius: 8px;
        background-color: #ffffff;
    }
    QFrame[setupChecklistPanel="true"] {
        border: 1px solid #d6e0ef;
        border-radius: 8px;
        background-color: #ffffff;
    }
    QLabel[setupChecklistTitle="true"] {
        color: #142033;
        font-size: 13px;
        font-weight: 700;
    }
    QLabel[setupChecklistItem="true"] {
        color: #166534;
        font-size: 12px;
        font-weight: 700;
        padding: 3px 0;
    }
    QLabel[setupChecklistItem="true"][setupChecklistState="incomplete"] {
        color: #991b1b;
    }
    """


def apply_project_overview_theme(widget: QWidget) -> None:
    widget.setStyleSheet(project_overview_stylesheet())


def fixation_settings_stylesheet() -> str:
    return f"""
    QFrame#fixation_feasibility_card {{
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {COLOR_SURFACE_ELEVATED};
    }}
    QLabel#fixation_feasibility_label {{
        color: {COLOR_TEXT_PRIMARY};
        font-weight: 600;
    }}
    """


def apply_fixation_settings_theme(widget: QWidget) -> None:
    widget.setStyleSheet(fixation_settings_stylesheet())


def non_home_shell_stylesheet() -> str:
    return f"""
    QLabel#non_home_shell_title {{
        font-size: 24px;
        font-weight: 700;
        color: {COLOR_TEXT_PRIMARY};
    }}
    QLabel#non_home_shell_subtitle {{
        color: {COLOR_TEXT_SECONDARY};
        font-size: 13px;
    }}
    QFrame#non_home_shell_footer_strip {{
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {COLOR_SURFACE};
    }}
    QLabel#non_home_shell_footer_label {{
        color: {COLOR_TEXT_SECONDARY};
    }}
    """


def apply_non_home_shell_theme(widget: QWidget) -> None:
    widget.setStyleSheet(non_home_shell_stylesheet())


def section_card_stylesheet() -> str:
    return f"""
    QFrame[sectionCard="true"] {{
        border: 1px solid {COLOR_BORDER};
        border-radius: {CARD_CORNER_RADIUS}px;
        background-color: {COLOR_SURFACE};
    }}
    QFrame#setup_wizard_current_step_card[wizardProjectStepFrame="true"] {{
        border: none;
        background-color: transparent;
    }}
    QLabel[sectionCardRole="title"] {{
        font-size: 15px;
        font-weight: 700;
        color: {COLOR_TEXT_PRIMARY};
    }}
    QLabel[sectionCardRole="subtitle"] {{
        color: {COLOR_TEXT_SECONDARY};
    }}
    QLabel#section_card_tooltip_badge {{
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: 8px;
        background-color: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT_PRIMARY};
        font-size: 11px;
        font-weight: 700;
    }}
    """


def apply_section_card_theme(widget: QWidget) -> None:
    widget.setStyleSheet(section_card_stylesheet())


def _rgba(color: QColor) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def welcome_window_stylesheet(palette: QPalette) -> str:
    window_color = palette.color(QPalette.ColorRole.Window)
    base_color = palette.color(QPalette.ColorRole.Base)
    mid_color = palette.color(QPalette.ColorRole.Mid)
    text_color = palette.color(QPalette.ColorRole.Text)
    highlight_color = palette.color(QPalette.ColorRole.Highlight)
    highlighted_text_color = palette.color(QPalette.ColorRole.HighlightedText)

    muted_text = QColor(text_color)
    muted_text.setAlpha(190)
    subtle_text = QColor(text_color)
    subtle_text.setAlpha(150)
    frame_border = QColor(mid_color)
    frame_border.setAlpha(100 if window_color.lightness() >= 128 else 145)

    is_dark = window_color.lightness() < 128
    content_bg = window_color.lighter(106) if is_dark else window_color.lighter(102)
    row_hover_bg = base_color.lighter(118) if is_dark else window_color.lighter(107)
    focus_color = highlight_color.lighter(125) if is_dark else highlight_color.darker(110)
    primary_hover = highlight_color.lighter(112) if is_dark else highlight_color.darker(108)
    primary_pressed = highlight_color.lighter(124) if is_dark else highlight_color.darker(118)

    return f"""
    QFrame#welcome_content_frame {{
        border: 1px solid {_rgba(frame_border)};
        border-radius: 16px;
        background-color: {_rgba(content_bg)};
    }}
    QWidget#welcome_hero_container {{
        background: transparent;
    }}
    QLabel#welcome_brand_label {{
        color: {_rgba(subtle_text)};
        font-size: 14px;
        font-weight: 600;
    }}
    QLabel#welcome_headline_label {{
        color: {_rgba(text_color)};
        font-size: 44px;
        font-weight: 700;
    }}
    QLabel#welcome_body_label {{
        color: {_rgba(muted_text)};
        font-size: 17px;
    }}
    QLabel#welcome_recent_projects_header {{
        color: {_rgba(subtle_text)};
        font-size: 13px;
        font-weight: 600;
    }}
    QListWidget#welcome_recent_project_list {{
        border: 1px solid {_rgba(mid_color)};
        border-radius: 8px;
        background-color: {_rgba(base_color)};
        color: {_rgba(text_color)};
        font-size: 13px;
        outline: none;
        padding: 4px;
    }}
    QListWidget#welcome_recent_project_list::item {{
        padding: 5px 8px;
        border-radius: 5px;
    }}
    QListWidget#welcome_recent_project_list::item:hover {{
        background-color: {_rgba(row_hover_bg)};
    }}
    QListWidget#welcome_recent_project_list::item:selected {{
        background-color: {_rgba(highlight_color)};
        color: {_rgba(highlighted_text_color)};
    }}
    QPushButton {{
        border: 1px solid {_rgba(mid_color)};
        border-radius: 10px;
        padding: 12px 26px;
        background-color: {_rgba(base_color)};
        color: {_rgba(text_color)};
        font-size: 16px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {_rgba(row_hover_bg)};
    }}
    QPushButton:pressed {{
        background-color: {_rgba(content_bg)};
    }}
    QPushButton[welcomeRole="primary"] {{
        border-color: {_rgba(highlight_color.darker(115))};
        background-color: {_rgba(highlight_color)};
        color: {_rgba(highlighted_text_color)};
        font-weight: 600;
    }}
    QPushButton[welcomeRole="primary"]:hover {{
        background-color: {_rgba(primary_hover)};
    }}
    QPushButton[welcomeRole="primary"]:pressed {{
        background-color: {_rgba(primary_pressed)};
    }}
    QPushButton:focus {{
        border: 2px solid {_rgba(focus_color)};
    }}
    """


def apply_welcome_window_theme(widget: QWidget) -> None:
    widget.setStyleSheet(welcome_window_stylesheet(widget.palette()))


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
