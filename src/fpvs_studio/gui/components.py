"""Shared FPVS Studio GUI components, roles, and theme styles.

This module is the public starting point for reusable PySide6 presentation
helpers. Keep persistent model logic, runtime flow, and domain validation out of
this layer.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPalette, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

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

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName(f"{object_name}_title")
        self.title_label.setProperty("setupChecklistTitle", "true")
        self._layout.addWidget(self.title_label)
        self._layout.addStretch(1)

    def set_items(self, items: list[tuple[str, bool]]) -> None:
        for item_label in self._item_labels:
            self._layout.removeWidget(item_label)
            item_label.deleteLater()
        self._item_labels = []

        insert_index = max(1, self._layout.count() - 1)
        for label_text, complete in items:
            item_label = QLabel(self)
            item_label.setObjectName(f"setup_checklist_item_{_object_suffix(label_text)}")
            item_label.setProperty("setupChecklistItem", "true")
            item_label.setProperty(
                "setupChecklistState",
                "complete" if complete else "incomplete",
            )
            mark = "✓" if complete else "✕"
            item_label.setText(f"{mark} {label_text}")
            refresh_widget_style(item_label)
            self._layout.insertWidget(insert_index, item_label)
            self._item_labels.append(item_label)
            insert_index += 1

    def item_labels(self) -> tuple[QLabel, ...]:
        return tuple(self._item_labels)


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
    QListWidget#condition_list::item {{
        padding: 7px 10px;
        border-radius: 8px;
    }}
    QListWidget#condition_list::item:hover {{
        background-color: {COLOR_SURFACE_ALT};
    }}
    QListWidget#condition_list::item:selected {{
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
