"""Focused pytest-qt smoke tests for fixation settings widgets."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication
from tests.gui.helpers import configure_fixation_task

from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.fixation_settings_page import FixationSettingsEditor


def _build_editor(
    qtbot,
    tmp_path: Path,
    *,
    schedule_row_behavior: str = "hide",
) -> tuple[ProjectDocument, FixationSettingsEditor]:
    document = ProjectDocument.create_new(
        parent_dir=tmp_path,
        project_name="Focused Fixation Project",
    )
    editor = FixationSettingsEditor(
        document,
        schedule_row_behavior=schedule_row_behavior,
    )
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()
    return document, editor


def test_fixation_settings_editor_persists_fixed_mode_values(qtbot, tmp_path: Path) -> None:
    document, editor = _build_editor(qtbot, tmp_path)

    configure_fixation_task(
        editor,
        enabled=True,
        accuracy_enabled=True,
        target_count_mode="fixed",
        changes_per_sequence=7,
        response_key="return",
        response_window_seconds=1.5,
    )
    QApplication.processEvents()

    fixation = document.project.settings.fixation_task
    assert fixation.enabled is True
    assert fixation.accuracy_task_enabled is True
    assert fixation.target_count_mode == "fixed"
    assert fixation.changes_per_sequence == 7
    assert fixation.response_key == "return"
    assert fixation.response_keys == ["return"]
    assert fixation.response_window_seconds == 1.5


def test_fixation_settings_editor_toggles_fixed_and_randomized_rows(
    qtbot,
    tmp_path: Path,
) -> None:
    _, editor = _build_editor(qtbot, tmp_path, schedule_row_behavior="disable")

    configure_fixation_task(editor, enabled=True, target_count_mode="fixed")
    QApplication.processEvents()

    assert editor.changes_per_sequence_spin.isEnabled()
    assert not editor.target_count_min_spin.isEnabled()
    assert not editor.target_count_max_spin.isEnabled()
    assert not editor.no_repeat_count_checkbox.isEnabled()

    configure_fixation_task(
        editor,
        enabled=True,
        target_count_mode="randomized",
        target_count_min=2,
        target_count_max=6,
        no_immediate_repeat_count=True,
    )
    QApplication.processEvents()

    assert not editor.changes_per_sequence_spin.isEnabled()
    assert editor.target_count_min_spin.isEnabled()
    assert editor.target_count_max_spin.isEnabled()
    assert editor.no_repeat_count_checkbox.isEnabled()


def test_fixation_settings_editor_caps_counts_from_condition_duration(
    qtbot,
    tmp_path: Path,
) -> None:
    document, editor = _build_editor(qtbot, tmp_path, schedule_row_behavior="disable")
    condition_id = document.create_condition(name="Sixty Seconds")
    document.update_condition(
        condition_id,
        sequence_count=1,
        oddball_cycle_repeats_per_sequence=72,
    )
    QApplication.processEvents()

    assert editor.changes_per_sequence_spin.maximum() == 7
    assert editor.target_count_max_spin.maximum() == 7
    assert editor.fixation_feasibility_label.text() == (
        "Recommended maximum cross changes per condition: 7"
    )

    editor.target_count_mode_combo.setCurrentIndex(
        editor.target_count_mode_combo.findData("fixed")
    )
    editor.changes_per_sequence_spin.setValue(99)
    QApplication.processEvents()
    assert editor.changes_per_sequence_spin.value() == 7
    assert document.project.settings.fixation_task.changes_per_sequence == 7

    editor.target_count_mode_combo.setCurrentIndex(
        editor.target_count_mode_combo.findData("randomized")
    )
    editor.target_count_min_spin.setValue(9)
    editor.target_count_max_spin.setValue(99)
    QApplication.processEvents()
    fixation = document.project.settings.fixation_task
    assert editor.target_count_min_spin.value() == 7
    assert editor.target_count_max_spin.value() == 7
    assert fixation.target_count_min == 7
    assert fixation.target_count_max == 7
    assert fixation.no_immediate_repeat_count is False


def test_fixation_settings_editor_caps_roughly_120_seconds_at_fifteen(
    qtbot,
    tmp_path: Path,
) -> None:
    document, editor = _build_editor(qtbot, tmp_path)
    condition_id = document.create_condition(name="Two Minutes")
    document.update_condition(
        condition_id,
        sequence_count=1,
        oddball_cycle_repeats_per_sequence=144,
    )
    QApplication.processEvents()

    assert editor.changes_per_sequence_spin.maximum() == 15
    assert editor.target_count_max_spin.maximum() == 15
    assert editor.fixation_feasibility_label.text() == (
        "Recommended maximum cross changes per condition: 15"
    )


def test_fixation_settings_editor_keeps_color_changes_enabled(
    qtbot,
    tmp_path: Path,
) -> None:
    document, editor = _build_editor(qtbot, tmp_path)

    document.update_fixation_settings(enabled=False, accuracy_task_enabled=False)
    QApplication.processEvents()

    fixation = document.project.settings.fixation_task
    assert fixation.enabled is True
    assert not editor.fixation_enabled_checkbox.isVisible()
    assert editor.fixation_accuracy_checkbox.isEnabled()


def test_fixation_settings_editor_shows_feasibility_without_conditions(
    qtbot,
    tmp_path: Path,
) -> None:
    _, editor = _build_editor(qtbot, tmp_path)

    assert (
        editor.fixation_feasibility_label.text()
        == "Recommended maximum cross changes per condition: unavailable (add a condition)."
    )
    assert (
        editor.fixation_feasibility_label.toolTip()
        == "Derived from each condition's duration and the current fixation timing settings."
    )
