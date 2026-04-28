"""Shared helpers for the FPVS Studio main window pages."""

from __future__ import annotations

import traceback
from dataclasses import dataclass

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QSizePolicy,
    QTextEdit,
    QWidget,
)

from fpvs_studio.core.enums import (
    DutyCycleMode,
    InterConditionMode,
    StimulusVariant,
    ValidationSeverity,
)
from fpvs_studio.gui.design_system import (
    CONTENT_MAX_WIDTHS,
    elide_middle,
)
from fpvs_studio.gui.document import ProjectDocument

_CYCLE_HELP_TEXT = "Cycle = one turn of base presentations plus one oddball presentation."
_FIXATION_FEASIBILITY_TOOLTIP_TEXT = (
    "Derived from each condition's duration and the current fixation timing settings."
)
_RUNTIME_BACKGROUND_COLOR_PRESETS: tuple[tuple[str, str], ...] = (
    ("Black", "#000000"),
    ("Dark Gray", "#101010"),
)
_LAUNCH_INTERSTITIAL_DURATION_MS = 700
_PAGE_WIDTH_PRESETS: dict[str, int] = CONTENT_MAX_WIDTHS


def _canonical_runtime_background_hex(background_color: str) -> str | None:
    """Return the canonical preset hex when one runtime background preset matches."""

    normalized = background_color.strip().lower()
    for _label, preset_hex in _RUNTIME_BACKGROUND_COLOR_PRESETS:
        if preset_hex.lower() == normalized:
            return preset_hex
    return None


def _show_error_dialog(parent: QWidget, title: str, error: Exception) -> None:
    """Show one user-facing error dialog with expandable details."""

    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setWindowTitle(title)
    dialog.setText(str(error))
    dialog.setDetailedText(
        "".join(traceback.format_exception(type(error), error, error.__traceback__))
    )
    dialog.exec()


def _configure_centered_page_header_label(label: QLabel) -> None:
    """Configure a page-header label to span the page band and center its text."""

    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)


def _variant_label(variant: StimulusVariant) -> str:
    return {
        StimulusVariant.ORIGINAL: "Original",
        StimulusVariant.GRAYSCALE: "Grayscale",
        StimulusVariant.ROT180: "Orientation-Inverted (180 deg)",
        StimulusVariant.PHASE_SCRAMBLED: "Fourier Phase-Scrambled",
    }[variant]


def _duty_cycle_label(mode: DutyCycleMode) -> str:
    return {
        DutyCycleMode.CONTINUOUS: "Continuous",
        DutyCycleMode.BLANK_50: "50% Blank",
    }[mode]


def _transition_label(mode: InterConditionMode) -> str:
    return {
        InterConditionMode.FIXED_BREAK: "Fixed Break",
        InterConditionMode.MANUAL_CONTINUE: "Manual Continue",
    }[mode]


def _resolution_text(width_height) -> str:
    if width_height is None:
        return "Not imported"
    return f"{width_height.width_px} x {width_height.height_px}"


def _sync_text_editor_contents(editor: QTextEdit | QPlainTextEdit, text: str) -> None:
    """Update a text editor only when external state actually changed."""

    if editor.toPlainText() == text:
        return

    cursor = editor.textCursor()
    anchor = cursor.anchor()
    position = cursor.position()
    had_focus = editor.hasFocus()

    with QSignalBlocker(editor):
        editor.setPlainText(text)

    if not had_focus:
        return

    restored_cursor = editor.textCursor()
    restored_cursor.setPosition(min(anchor, len(text)))
    move_mode = (
        QTextCursor.MoveMode.KeepAnchor
        if anchor != position
        else QTextCursor.MoveMode.MoveAnchor
    )
    restored_cursor.setPosition(min(position, len(text)), move_mode)
    editor.setTextCursor(restored_cursor)


def _set_form_row_visible(layout: QFormLayout, field: QWidget, visible: bool) -> None:
    label = layout.labelForField(field)
    if label is not None:
        label.setVisible(visible)
    field.setVisible(visible)


def _prefixed_object_name(prefix: str, name: str) -> str:
    if not prefix:
        return name
    return f"{prefix}{name}"


@dataclass(frozen=True)
class LauncherReadinessReport:
    status_label: str
    badge_state: str
    status_summary: str
    readiness_items: tuple[str, ...]
    preview_note: str | None = None


def _truncate_line(value: str, max_length: int) -> str:
    return elide_middle(value, max_length)


def _configure_read_only_list(widget: QListWidget) -> None:
    widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
    widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    widget.setWordWrap(True)
    widget.setSpacing(2)
    widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)


def _set_widget_property(widget: QWidget, name: str, value: str) -> None:
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _set_list_items(widget: QListWidget, lines: list[str] | tuple[str, ...]) -> None:
    widget.clear()
    for line in lines:
        widget.addItem(line)


def _conditions_have_assigned_assets(document: ProjectDocument, ordered_conditions: list) -> bool:
    if not ordered_conditions:
        return False
    available_set_ids = {stimulus_set.set_id for stimulus_set in document.project.stimulus_sets}
    if not available_set_ids:
        return False
    return all(
        condition.base_stimulus_set_id in available_set_ids
        and condition.oddball_stimulus_set_id in available_set_ids
        for condition in ordered_conditions
    )


def _launcher_readiness_report(document: ProjectDocument, *, refresh_hz: float) -> LauncherReadinessReport:
    ordered_conditions = document.ordered_conditions()
    validation = document.validation_report(refresh_hz=refresh_hz)
    blocking_issues = [
        issue for issue in validation.issues if issue.severity == ValidationSeverity.ERROR
    ]
    blocking_issue_count = len(blocking_issues)

    conditions_ready = bool(ordered_conditions)
    assets_ready = _conditions_have_assigned_assets(document, ordered_conditions)
    preview_available = document.last_session_plan is not None

    if not conditions_ready:
        status_label = "Setup Required"
        badge_state = "pending"
    elif not assets_ready:
        status_label = "Missing Required Assets"
        badge_state = "warning"
    elif blocking_issue_count > 0:
        status_label = "Validation Issues"
        badge_state = "warning"
    else:
        status_label = "Ready to Launch"
        badge_state = "ready"

    if not conditions_ready:
        status_summary = "Add at least one condition before launching."
    elif not assets_ready:
        status_summary = "Assign all base and oddball stimulus sets before launching."
    elif blocking_issue_count > 0:
        status_summary = (
            f"Validation at {refresh_hz:.2f} Hz reports {blocking_issue_count} blocking issue(s)."
        )
    else:
        status_summary = f"Launch requirements are satisfied at {refresh_hz:.2f} Hz."

    readiness_items: list[str] = []
    if conditions_ready:
        readiness_items.append(f"[OK] Conditions configured: {len(ordered_conditions)}.")
    else:
        readiness_items.append("[TODO] Add at least one condition.")

    if conditions_ready and assets_ready:
        readiness_items.append("[OK] Stimulus assignments present for all conditions.")
    elif conditions_ready:
        readiness_items.append("[TODO] Assign base and oddball sets for each condition.")
    else:
        readiness_items.append("[TODO] Assign base and oddball sets for each condition.")

    if blocking_issue_count > 0:
        readiness_items.append(
            f"[WARN] Validation ({refresh_hz:.2f} Hz): {blocking_issue_count} blocking issue(s)."
        )
        readiness_items.append(
            f"[WARN] First blocker: {_truncate_line(blocking_issues[0].message, 120)}"
        )
    else:
        readiness_items.append(f"[OK] Validation ({refresh_hz:.2f} Hz) clear.")

    readiness_items.append("[INFO] Runtime path: alpha test-mode only.")
    return LauncherReadinessReport(
        status_label=status_label,
        badge_state=badge_state,
        status_summary=status_summary,
        readiness_items=tuple(readiness_items),
        preview_note=(
            "Session preview available for inspection. Launch will still compile and run launch checks automatically."
            if preview_available
            else "Launch will compile and run launch checks automatically."
        ),
    )


class LeftToRightPlainTextEdit(QPlainTextEdit):
    """Plain-text editor with left-to-right document defaults."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LeftToRight)
        text_option = self.document().defaultTextOption()
        text_option.setTextDirection(Qt.LeftToRight)
        self.document().setDefaultTextOption(text_option)

