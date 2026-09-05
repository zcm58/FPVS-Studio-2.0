"""Focused pytest-qt smoke tests for fixation settings widgets."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel
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


def test_fixation_settings_editor_uses_current_option_defaults(qtbot, tmp_path: Path) -> None:
    document, editor = _build_editor(qtbot, tmp_path)

    fixation = document.project.settings.fixation_task
    assert fixation.target_count_min == 8
    assert fixation.target_count_max == 13
    assert fixation.target_duration_ms == 300
    assert editor.target_count_min_spin.value() == 8
    assert editor.target_count_max_spin.value() == 13
    assert editor.target_duration_spin.value() == 300


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
    assert fixation.participant_tutorial_enabled is True
    assert fixation.target_count_mode == "fixed"
    assert fixation.changes_per_sequence == 7
    assert fixation.response_key == "return"
    assert fixation.response_keys == ["return"]
    assert fixation.response_window_seconds == 1.5


def test_fixation_settings_editor_does_not_expose_maximum_gap(qtbot, tmp_path: Path) -> None:
    _, editor = _build_editor(qtbot, tmp_path)

    assert editor.max_gap_spin.isHidden()
    assert all(
        "Maximum gap" not in label.text()
        for label in editor.findChildren(QLabel)
    )


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
        "Effective maximum changes per condition: 7\nLimited by Sixty Seconds (60 s)."
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
        "Effective maximum changes per condition: 15\nLimited by Two Minutes (120 s)."
    )


def test_fixation_settings_editor_refresh_does_not_enable_color_changes(
    qtbot,
    tmp_path: Path,
) -> None:
    document, editor = _build_editor(qtbot, tmp_path)

    document.update_fixation_settings(enabled=False, accuracy_task_enabled=False)
    QApplication.processEvents()

    fixation = document.project.settings.fixation_task
    assert fixation.enabled is False
    assert not editor.fixation_enabled_checkbox.isVisible()
    assert editor.fixation_accuracy_checkbox.isEnabled()

    editor.fixation_accuracy_checkbox.setChecked(True)
    QApplication.processEvents()

    fixation = document.project.settings.fixation_task
    assert fixation.enabled is True
    assert fixation.accuracy_task_enabled is True


def test_fixation_settings_editor_shows_feasibility_without_conditions(
    qtbot,
    tmp_path: Path,
) -> None:
    _, editor = _build_editor(qtbot, tmp_path)

    assert (
        editor.fixation_feasibility_label.text()
        == "Effective maximum changes per condition: unavailable (add a condition)."
    )
    assert (
        editor.fixation_feasibility_label.toolTip()
        == "Derived from each condition's duration and the current fixation timing settings."
    )
    assert not editor.fixation_adjustment_label.isVisible()


def test_fixation_guidance_names_the_condition_that_sets_the_effective_limit(
    qtbot,
    tmp_path: Path,
) -> None:
    document, editor = _build_editor(qtbot, tmp_path)
    long_id = document.create_condition(name="Two Minutes")
    document.update_condition(
        long_id, sequence_count=1, oddball_cycle_repeats_per_sequence=144
    )
    short_id = document.create_condition(name="Sixty Seconds")
    document.update_condition(
        short_id, sequence_count=1, oddball_cycle_repeats_per_sequence=72
    )
    QApplication.processEvents()

    assert editor.target_count_max_spin.maximum() == 7
    assert editor.fixation_feasibility_label.text() == (
        "Effective maximum changes per condition: 7\nLimited by Sixty Seconds (60 s)."
    )
    assert "Two Minutes: 15 changes (120 s)" in editor.fixation_feasibility_label.toolTip()
    assert "Sixty Seconds: 7 changes (60 s)" in editor.fixation_feasibility_label.toolTip()
    assert "7-15" not in editor.fixation_feasibility_label.text()


def test_automatic_fixed_count_clamp_updates_model_and_reports_actual_adjustment(
    qtbot,
    tmp_path: Path,
) -> None:
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Cap Persistence")
    condition_id = document.create_condition(name="Two Minutes")
    document.update_condition(
        condition_id, sequence_count=1, oddball_cycle_repeats_per_sequence=144
    )
    document.update_fixation_settings(
        enabled=False,
        accuracy_task_enabled=False,
        changes_per_sequence=50,
        target_count_min=2,
        target_count_max=3,
        no_immediate_repeat_count=False,
    )
    editor = FixationSettingsEditor(document)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    fixation = document.project.settings.fixation_task
    assert fixation.changes_per_sequence == 15
    assert editor.changes_per_sequence_spin.value() == 15
    assert fixation.target_count_min == 2
    assert fixation.target_count_max == 3
    assert fixation.enabled is False
    assert fixation.accuracy_task_enabled is False
    assert editor.fixation_adjustment_label.isVisible()
    assert "fixed changes 50 → 15" in editor.fixation_adjustment_label.text()
    editor.refresh()
    assert editor.fixation_adjustment_label.isVisible()

    document.update_fixation_settings(changes_per_sequence=12)
    QApplication.processEvents()
    assert not editor.fixation_adjustment_label.isVisible()


def test_randomized_clamp_reports_the_range_and_repeat_change(
    qtbot,
    tmp_path: Path,
) -> None:
    document, editor = _build_editor(qtbot, tmp_path)
    document.update_fixation_settings(
        target_count_mode="randomized",
        target_count_min=8,
        target_count_max=13,
        no_immediate_repeat_count=True,
    )
    condition_id = document.create_condition(name="Sixty Seconds")
    document.update_condition(
        condition_id, sequence_count=1, oddball_cycle_repeats_per_sequence=72
    )
    QApplication.processEvents()

    fixation = document.project.settings.fixation_task
    assert (fixation.target_count_min, fixation.target_count_max) == (7, 7)
    assert fixation.no_immediate_repeat_count is False
    note = editor.fixation_adjustment_label.text()
    assert "minimum 8 → 7" in note
    assert "maximum 13 → 7" in note
    assert "range now has one value" in note
