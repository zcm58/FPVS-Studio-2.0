"""Registered timing drafts, confirmation and compact Timing & Display checks."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox
from tests.gui.helpers import assert_visible_children_within_parent, record_setup_validation_dialogs

from fpvs_studio.core.condition_timing import resolve_condition_stream_timing
from fpvs_studio.core.enums import StimulusModality
from fpvs_studio.core.session_ordering import effective_condition_presentation_count
from fpvs_studio.gui.condition_timing_table import FREQUENCY_OVERRIDE_WARNING, ConditionTimingTable
from fpvs_studio.gui.document import DocumentError, ProjectDocument
from fpvs_studio.gui.experiment_designer_dialog import ExperimentDesignerWidget
from fpvs_studio.gui.setup_wizard_page import SetupWizardPage


def _document(tmp_path):
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Condition frequencies")
    document.update_display_settings(preferred_refresh_hz=60)
    first = document.create_condition(name="Image presentation")
    second = document.create_condition(name="Word presentation")
    document.set_condition_stimulus_modality(second, modality=StimulusModality.WORD)
    document.update_condition_words(second, role="base", words=["house", "tree"])
    document.update_condition_words(second, role="oddball", words=["fear", "anger"])
    for condition_id in (first, second):
        document.update_condition(
            condition_id, sequence_count=1, oddball_cycle_repeats_per_sequence=12,
        )
    return document, first, second


@pytest.mark.parametrize("answer", [QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No])
@pytest.mark.parametrize("condition_index", [0, 1])
def test_frequency_override_requires_exact_warning_and_preserves_other_conditions(
    qtbot, monkeypatch, tmp_path, answer, condition_index,
):
    document, first, second = _document(tmp_path)
    target = (first, second)[condition_index]
    original = document.project.model_copy(deep=True)
    prompts = []

    def confirm(*args):
        prompts.append(args)
        return answer

    monkeypatch.setattr(QMessageBox, "question", confirm)
    editor = ConditionTimingTable(document)
    qtbot.addWidget(editor)
    editor.resize(880, 240)
    editor.show()
    editor.frequency_spins[target].setValue(4)
    assert document.project == original
    assert editor.apply_pending_edits() == (answer == QMessageBox.StandardButton.Yes)
    assert prompts[0][2] == FREQUENCY_OVERRIDE_WARNING
    assert prompts[0][3] == QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    assert prompts[0][4] == QMessageBox.StandardButton.No
    if answer == QMessageBox.StandardButton.Yes:
        changed = document.get_condition(target)
        assert changed.base_hz == 4
        assert changed.oddball_cycle_repeats_per_sequence == 8  # Still ten seconds at 60 Hz.
        assert editor.source_labels[target].text() == "Custom"
        other = second if target == first else first
        assert document.get_condition(other) == next(
            item for item in original.conditions if item.condition_id == other
        )
    else:
        assert document.project == original
        assert editor.frequency_spins[target].value() == 6
        assert not editor.has_pending_edits()


def test_shared_frequency_preserves_custom_values_and_reset_restores_inheritance(
    qtbot, monkeypatch, tmp_path,
):
    document, first, second = _document(tmp_path)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    editor = ConditionTimingTable(document)
    qtbot.addWidget(editor)
    editor.frequency_spins[first].setValue(4)
    assert editor.apply_pending_edits()
    editor.shared_frequency_spin.setValue(3)
    assert editor.apply_pending_edits()
    assert document.project.settings.protocol.base_hz == 3
    assert document.get_condition(first).base_hz == 4
    assert document.get_condition(first).oddball_cycle_repeats_per_sequence == 8
    assert document.get_condition(second).base_hz is None
    assert document.get_condition(second).oddball_cycle_repeats_per_sequence == 6
    editor.reset_buttons[first].click()
    assert editor.apply_pending_edits()
    assert document.get_condition(first).base_hz is None
    assert document.get_condition(first).oddball_cycle_repeats_per_sequence == 6
    assert editor.source_labels[first].text() == "Shared"


def test_invalid_frequency_draft_has_no_partial_edits_and_can_be_discarded(
    qtbot, monkeypatch, tmp_path,
):
    document, first, _second = _document(tmp_path)
    original = document.project.model_copy(deep=True)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: pytest.fail("Draft is invalid"))
    editor = ConditionTimingTable(document)
    qtbot.addWidget(editor)
    editor.shared_frequency_spin.setValue(7)
    editor.frequency_spins[first].setValue(3)
    assert not editor.apply_pending_edits()
    assert document.project == original
    assert "Valid durations" in editor.error_label.text()
    editor.discard_button.click()
    assert not editor.has_pending_edits()
    assert editor.shared_frequency_spin.value() == 6
    assert editor.frequency_spins[first].value() == 6


def test_frequency_change_requires_an_explicit_display_rate(qtbot, tmp_path):
    document, first, _second = _document(tmp_path)
    document.update_display_settings(preferred_refresh_hz=None)
    original = document.project.model_copy(deep=True)
    editor = ConditionTimingTable(document)
    qtbot.addWidget(editor)
    assert not editor.duration_spins[first].isEnabled()
    assert editor.duration_spins[first].specialValueText() == "Select display rate"
    editor.shared_frequency_spin.setValue(4)
    assert not editor.apply_pending_edits()
    assert "Select a monitor refresh rate" in editor.error_label.text()
    assert document.project == original
    document.update_display_settings(preferred_refresh_hz=60)
    assert editor.duration_spins[first].isEnabled()
    assert editor.duration_spins[first].value() == 10
    assert document.get_condition(first).stream_duration_seconds is None


def test_image_and_word_durations_apply_together_without_changing_exposure_targets(qtbot, tmp_path):
    document, first, second = _document(tmp_path)
    exposure_target = document.project.settings.condition_defaults.target_repeats_per_image
    editor = ConditionTimingTable(document)
    qtbot.addWidget(editor)
    assert editor.apply_button.text() == "Apply timing"
    editor.duration_spins[first].setValue(20)
    editor.duration_spins[second].setValue(30)
    assert document.get_condition(first).stream_duration_seconds is None
    assert editor.apply_pending_edits()
    assert document.get_condition(first).stream_duration_seconds == 20
    assert document.get_condition(second).stream_duration_seconds == 30
    for condition_id, expected in ((first, 20), (second, 30)):
        timing = resolve_condition_stream_timing(
            document.project, document.get_condition(condition_id), 60,
        )
        assert timing.duration_seconds == expected
    assert document.project.settings.condition_defaults.target_repeats_per_image == exposure_target
    assert "Excludes lead-in" in editor.duration_spins[first].toolTip()


def test_explicit_seconds_replace_legacy_continuous_count_divisibility(qtbot, tmp_path):
    document, first, _second = _document(tmp_path)
    document.update_condition(first, sequence_count=2)
    editor = ConditionTimingTable(document)
    qtbot.addWidget(editor)
    assert editor.duration_spins[first].value() == 20
    editor.duration_spins[first].setValue(17.5)
    assert editor.apply_pending_edits()
    timing = resolve_condition_stream_timing(document.project, document.get_condition(first), 60)
    assert timing.duration_seconds == 17.5
    assert timing.total_oddball_cycles == 21


def test_frequency_and_seconds_are_one_atomic_draft(qtbot, monkeypatch, tmp_path):
    document, first, second = _document(tmp_path)
    original = document.project.model_copy(deep=True)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    editor = ConditionTimingTable(document)
    qtbot.addWidget(editor)
    editor.frequency_spins[first].setValue(7)
    editor.duration_spins[first].setValue(10.5)
    editor.duration_spins[second].setValue(0)
    assert not editor.apply_pending_edits()
    assert document.project == original
    assert editor.frequency_spins[first].value() == 7
    assert editor.duration_spins[first].value() == 10.5
    editor.duration_spins[second].setValue(10)
    assert editor.apply_pending_edits()
    assert document.get_condition(first).base_hz == 7
    assert document.get_condition(first).stream_duration_seconds == 10.5
    assert document.get_condition(second) == original.conditions[1]


@pytest.mark.parametrize("choose", ["button", "typed_display_text"])
def test_5994_duration_alternatives_are_explicit_and_displayed_values_are_usable(
    qtbot, tmp_path, choose,
):
    document, first, _second = _document(tmp_path)
    document.update_display_settings(preferred_refresh_hz=59.94)
    original = document.project.model_copy(deep=True)
    editor = ConditionTimingTable(document)
    qtbot.addWidget(editor)
    editor.show()
    editor.duration_spins[first].setValue(12)
    assert not editor.apply_pending_edits()
    assert document.project == original
    assert editor.duration_spins[first].value() == 12
    assert editor.duration_choice_buttons
    button = editor.duration_choice_buttons[0]
    displayed = button.text().removeprefix("Use ").removesuffix(" s")
    if choose == "button":
        button.click()
    else:
        edit = editor.duration_spins[first].lineEdit()
        assert edit is not None
        edit.selectAll()
        qtbot.keyClicks(edit, displayed)
        qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert editor.apply_pending_edits()
    timing = resolve_condition_stream_timing(document.project, document.get_condition(first), 59.94)
    assert timing.total_oddball_cycles == 14
    assert timing.duration_seconds == pytest.approx(float(displayed), abs=1e-9)


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("state", [
    "shared", "custom", "invalid", "duration_invalid", "unresolved", "counts", "count_invalid",
])
def test_timing_frequency_table_fits_wizard_and_reports_mixed_review_rates(
    qtbot, monkeypatch, tmp_path, background, state,
):
    document, first, second = _document(tmp_path)
    document.update_condition(
        first, name="Semantic categories with low visual similarity and high emotional salience",
    )
    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda _self: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    if state == "custom":
        document.update_condition_frequencies(overrides={first: 4})
    elif state == "counts":
        document.update_condition_timing(presentation_counts={first: 3, second: 2})
    elif state == "unresolved":
        document.update_display_settings(preferred_refresh_hz=None)
    wizard = SetupWizardPage(
        document, load_condition_template_profiles=lambda: [],
        manage_condition_templates=lambda: [],
    )
    qtbot.addWidget(wizard)
    palette = wizard.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    wizard.setPalette(palette)
    wizard.resize(1120, 820)
    wizard.show()
    wizard.open_wizard(step_key="experiment", allow_step_jumps=True)
    table = wizard.condition_timing_table
    if state == "invalid":
        table.shared_frequency_spin.setValue(7)
        assert not wizard.flush_pending_edits()
    elif state == "duration_invalid":
        table.duration_spins[first].setValue(10.1)
        assert not wizard.flush_pending_edits()
        assert table.duration_choice_buttons
    elif state == "count_invalid":
        table.presentation_count_spins[first].setValue(3)
        table.presentation_count_spins[second].setValue(1)
        assert not wizard.flush_pending_edits()
        assert table.error_label.isVisible()
    if state in {"invalid", "duration_invalid", "count_invalid"}:
        wizard.open_wizard(step_key="session", allow_step_jumps=True)
        assert wizard.step_stack.currentWidget() is wizard.experiment_step_surface
        assert wizard.has_pending_edits()
    QApplication.processEvents()
    assert wizard.size().toTuple() == (1120, 820)
    assert wizard.experiment_step_surface.content.maximumWidth() == 1040
    assert table.isVisible()
    assert not wizard.runtime_settings_editor.base_hz_spin.isVisible()
    assert table.geometry().bottom() < wizard.experiment_settings_card.geometry().top()
    assert_visible_children_within_parent(wizard.experiment_step_surface)
    for label in table.findChildren(QLabel):
        if label.isVisible() and label.text():
            if label.wordWrap():
                assert label.height() >= label.heightForWidth(label.width())
            else:
                assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    assert table.table.item(0, 0).toolTip() == document.get_condition(first).name
    assert table.source_labels[second].text() == "Shared"
    assert table.table.columnCount() == 7
    assert not wizard.session_structure_editor.block_count_spin.isVisible()
    assert table.table.horizontalScrollBar().maximum() == 0
    for column in range(1, table.table.columnCount()):
        text = table.table.horizontalHeaderItem(column).text()
        assert table.table.columnWidth(column) >= table.fontMetrics().horizontalAdvance(text) + 8
    for spin in table.presentation_count_spins.values():
        assert spin.minimum() == 1
        assert spin.isVisible()
        assert spin.width() >= spin.sizeHint().width()
    if state == "counts":
        assert table.presentation_count_spins[first].value() == 3
        assert table.total_stimulation_labels[first].text() == "30 s"
        assert wizard.session_structure_editor.presentation_total_label.text() == "5 total"
    if state == "unresolved":
        assert not table.duration_spins[first].isEnabled()
        assert all("Stimulation total:" not in line
                   for line in wizard._review_timing_estimate_lines())
    for button in table.duration_choice_buttons:
        if button.isVisible():
            assert button.width() >= button.sizeHint().width()
    if state == "custom":
        review = " ".join(line for _name, _title, lines in wizard._review_checklist_sections()
                          for line in lines)
        assert "Stimulus frequency varies by condition" in review


def test_hidden_display_rate_control_cannot_round_a_saved_rate_during_cadence_edit(
    qtbot, monkeypatch, tmp_path,
):
    document, _first, _second = _document(tmp_path)
    document.update_protocol_settings(base_hz=6.123456)
    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda _self: None)
    wizard = SetupWizardPage(
        document, load_condition_template_profiles=lambda: [],
        manage_condition_templates=lambda: [],
    )
    qtbot.addWidget(wizard)
    wizard.runtime_settings_editor.oddball_every_n_spin.setValue(6)
    assert document.project.settings.protocol.base_hz == 6.123456
    assert document.project.settings.protocol.oddball_every_n == 6
    assert not wizard.condition_timing_table.has_pending_edits()


def test_timing_frequency_changes_refresh_readonly_design_without_creating_a_draft(
    qtbot, monkeypatch, tmp_path,
):
    document, first, _second = _document(tmp_path)
    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda _self: None)
    designer = ExperimentDesignerWidget(document, condition_id=first, embedded=True)
    qtbot.addWidget(designer)
    assert designer.rate_spin.isReadOnly()
    assert not designer.has_pending_design()
    document.update_condition_frequencies(overrides={first: 4})
    designer.refresh()
    assert designer.rate_spin.value() == 4
    assert not designer.has_pending_design()
    designer.cycle_canvas.add_role("base")
    roles = designer.cycle_canvas.roles()
    document.update_condition_frequencies(overrides={first: 3})
    designer.refresh()
    assert designer.rate_spin.value() == 3
    assert designer.cycle_canvas.roles() == roles
    assert designer.has_pending_design()


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_three_populated_timing_rows_fit_on_first_themed_show(
    qtbot, tmp_path, background,
):
    document, first, second = _document(tmp_path)
    document.update_condition(
        first, name="Semantic categories with low visual similarity and high emotional salience",
    )
    document.update_condition(
        second, name="Written words with matched lexical frequency and perceptual properties",
    )
    document.create_condition(
        name="Unfamiliar natural objects with carefully matched stimulus characteristics",
    )
    document.update_condition_frequencies(overrides={first: 4})
    wizard = SetupWizardPage(
        document, load_condition_template_profiles=lambda: [],
        manage_condition_templates=lambda: [],
    )
    qtbot.addWidget(wizard)
    palette = wizard.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    wizard.setPalette(palette)
    wizard.resize(1120, 820)
    wizard.open_wizard(step_key="experiment", allow_step_jumps=True)
    wizard.show()
    QApplication.processEvents()

    timing = wizard.condition_timing_table
    QApplication.processEvents()
    table = timing.table
    assert wizard.size().toTuple() == (1120, 820)
    assert table.rowCount() == 3
    assert table.verticalScrollBar().maximum() == 0
    assert table.horizontalScrollBar().maximum() == 0
    for row, condition in enumerate(document.ordered_conditions()):
        item = table.item(row, 0)
        assert item.toolTip() == condition.name
        assert item.data(Qt.ItemDataRole.AccessibleTextRole) == condition.name
        button = timing.reset_buttons[condition.condition_id]
        assert button.isVisible()
        assert table.rowHeight(row) >= button.sizeHint().height()
        assert button.height() >= button.sizeHint().height()
        top_left = button.mapTo(table.viewport(), button.rect().topLeft())
        bottom_right = button.mapTo(table.viewport(), button.rect().bottomRight())
        assert table.viewport().rect().contains(top_left)
        assert table.viewport().rect().contains(bottom_right)
        assert table.visualItemRect(item).bottom() <= table.viewport().rect().bottom()
    assert_visible_children_within_parent(wizard.experiment_step_surface)


def test_authored_seconds_disable_legacy_count_editing_and_update_stimulation_total(
    qtbot, monkeypatch, tmp_path,
):
    document, first, second = _document(tmp_path)
    document.update_condition_timing(durations={first: 20, second: 30})
    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda _self: None)
    wizard = SetupWizardPage(
        document, load_condition_template_profiles=lambda: [],
        manage_condition_templates=lambda: [],
    )
    qtbot.addWidget(wizard)
    wizard.conditions_page.condition_list.setCurrentRow(0)
    wizard.conditions_page.refresh()
    assert not wizard.conditions_page.sequence_count_spin.isEnabled()
    assert not wizard.conditions_page.oddball_cycles_spin.isEnabled()
    assert "Timing & Display" in wizard.conditions_page.sequence_count_spin.toolTip()
    assert wizard._review_timing_estimate_lines()[0] == "Stimulation total: 100 seconds"


def test_design_cadence_change_validates_authored_seconds_before_commit(qtbot, tmp_path):
    document, first, _second = _document(tmp_path)
    document.update_condition_timing(durations={first: 10})
    assert document.project.settings.protocol.base_hz == 6
    assert document.project.settings.protocol.oddball_every_n == 5
    assert document.get_condition(first).stream_duration_seconds == 10
    assert document.get_condition(first).oddball_cycle_repeats_per_sequence == 12
    original = document.project.model_copy(deep=True)
    with pytest.raises(DocumentError, match="Valid durations"):
        document.apply_experiment_design(first, base_hz=6, slot_count=7, attentional_blink=None)
    assert document.project == original
    document.apply_experiment_design(first, base_hz=6, slot_count=6, attentional_blink=None)
    assert document.project.settings.protocol.oddball_every_n == 6
    assert document.get_condition(first).stream_duration_seconds == 10
    assert document.get_condition(first).sequence_count == 1
    assert document.get_condition(first).oddball_cycle_repeats_per_sequence == 10
    timing = resolve_condition_stream_timing(document.project, document.get_condition(first), 60)
    assert timing.duration_seconds == 10
    assert timing.total_oddball_cycles == 10


def test_new_condition_inherits_authored_duration_defaults_without_a_display_guess(qtbot, tmp_path):
    document, _first, _second = _document(tmp_path)
    document.update_display_settings(preferred_refresh_hz=None)
    document.update_condition_defaults(stream_duration_seconds=120)
    condition_id = document.create_condition(name="New duration template condition")
    assert document.get_condition(condition_id).stream_duration_seconds == 120
    assert document.project.settings.display.preferred_refresh_hz is None
    document.set_condition_stimulus_modality(condition_id, modality=StimulusModality.WORD)
    assert document.get_condition(condition_id).stream_duration_seconds == 120


def test_changed_display_rate_surfaces_incompatible_authored_duration(qtbot, monkeypatch, tmp_path):
    document, first, _second = _document(tmp_path)
    document.update_condition_timing(durations={first: 10})
    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda _self: None)
    wizard = SetupWizardPage(
        document, load_condition_template_profiles=lambda: [],
        manage_condition_templates=lambda: [],
    )
    qtbot.addWidget(wizard)
    document.update_display_settings(preferred_refresh_hz=59.94)
    report = wizard.runtime_settings_editor.timing_report()
    assert not report.compatible
    assert "Valid durations" in report.errors[0]
    assert "Valid durations" in wizard.runtime_settings_editor.timing_blocker()


def test_word_cadence_edit_preserves_authored_seconds_atomically(tmp_path):
    from fpvs_studio.gui.document import DocumentError

    document, _first, second = _document(tmp_path)
    document.update_condition_timing(durations={second: 10})
    before = document.project.model_copy(deep=True)
    with pytest.raises(DocumentError, match="Valid durations"):
        document.update_protocol_settings(oddball_every_n=7)
    assert document.project == before
    document.update_protocol_settings(oddball_every_n=6)
    assert document.get_condition(second).stream_duration_seconds == 10
    assert document.get_condition(second).oddball_cycle_repeats_per_sequence == 10


def test_total_presentation_counts_apply_with_frequency_and_duration_atomically(qtbot, tmp_path):
    document, first, second = _document(tmp_path)
    original = document.project.model_copy(deep=True)
    editor = ConditionTimingTable(document)
    qtbot.addWidget(editor)
    editor.show()
    editor.shared_frequency_spin.setValue(3)
    editor.duration_spins[first].setValue(20)
    editor.duration_spins[second].setValue(30)
    editor.presentation_count_spins[first].setValue(3)
    editor.presentation_count_spins[second].setValue(1)
    assert editor.total_stimulation_labels[first].text() == "60 s"
    assert not editor.apply_pending_edits()
    assert document.project == original
    assert editor.has_pending_edits()
    assert editor.shared_frequency_spin.value() == 3
    assert editor.duration_spins[first].value() == 20
    assert editor.presentation_count_spins[first].value() == 3
    assert "Image presentation" in editor.error_label.text()
    assert not editor.duration_choice_buttons

    editor.presentation_count_spins[second].setValue(2)
    assert editor.apply_pending_edits()
    assert document.project.settings.protocol.base_hz == 3
    assert document.get_condition(first).stream_duration_seconds == 20
    assert document.get_condition(second).stream_duration_seconds == 30
    assert document.get_condition(first).presentation_count == 3
    assert effective_condition_presentation_count(
        document.project, document.get_condition(second),
    ) == 2
    assert document.project.settings.session.block_count == original.settings.session.block_count
    assert not editor.has_pending_edits()


def test_count_only_edit_keeps_unresolved_legacy_stream_and_supports_discard(qtbot, tmp_path):
    document, first, second = _document(tmp_path)
    document.update_display_settings(preferred_refresh_hz=None)
    before = {item.condition_id: item.model_copy(deep=True) for item in document.project.conditions}
    editor = ConditionTimingTable(document)
    qtbot.addWidget(editor)
    assert editor.presentation_count_spins[first].value() == 2
    assert not editor.duration_spins[first].isEnabled()
    editor.presentation_count_spins[first].setValue(3)
    editor.discard_button.click()
    assert editor.presentation_count_spins[first].value() == 2
    assert not editor.has_pending_edits()
    editor.presentation_count_spins[first].setValue(3)
    assert editor.apply_pending_edits()
    assert document.project.settings.display.preferred_refresh_hz is None
    for condition in document.project.conditions:
        previous = before[condition.condition_id]
        assert condition.stream_duration_seconds is None
        assert condition.sequence_count == previous.sequence_count
        assert condition.oddball_cycle_repeats_per_sequence == (
            previous.oddball_cycle_repeats_per_sequence
        )
    assert document.get_condition(first).presentation_count == 3
    assert document.get_condition(second) == before[second]
    assert editor.total_stimulation_labels[first].text() == "Unresolved"


def test_three_total_presentations_compile_as_three_separate_streams_after_reload(qtbot, tmp_path):
    document, first, second = _document(tmp_path)
    document.set_condition_stimulus_modality(first, modality=StimulusModality.WORD)
    document.update_condition_words(first, role="base", words=["chair", "desk"])
    document.update_condition_words(first, role="oddball", words=["fear", "anger"])
    editor = ConditionTimingTable(document)
    qtbot.addWidget(editor)
    for condition_id in (first, second):
        editor.duration_spins[condition_id].setValue(60)
    editor.presentation_count_spins[first].setValue(3)
    editor.presentation_count_spins[second].setValue(2)
    editor.apply_button.click()
    assert not editor.has_pending_edits()
    assert editor.total_stimulation_labels[first].text() == "180 s"
    document.save()
    reopened = ProjectDocument.open_existing(document.project_root)
    plan = reopened.compile_session(refresh_hz=60)
    entries = plan.ordered_entries()
    assert [entry.condition_id for entry in entries] == [first, second, first, second, first]
    assert len({entry.run_id for entry in entries}) == 5
    assert all(entry.run_spec.display.total_frames == 3600 for entry in entries)
    assert all(entry.run_spec.condition.requested_duration_seconds == 60 for entry in entries)


def test_saved_impossible_single_condition_count_is_actionable_in_timing(
    qtbot, monkeypatch, tmp_path,
):
    document, first, second = _document(tmp_path)
    document.remove_condition(second)
    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda _self: None)
    wizard = SetupWizardPage(
        document, load_condition_template_profiles=lambda: [],
        manage_condition_templates=lambda: [],
    )
    qtbot.addWidget(wizard)
    monkeypatch.setattr(wizard.runtime_settings_editor, "timing_is_compatible", lambda: True)
    wizard.resize(1120, 820)
    wizard.show()
    wizard.open_wizard(step_key="experiment", allow_step_jumps=True)
    table = wizard.condition_timing_table
    assert table.presentation_count_spins[first].value() == 2
    assert table.error_label.isVisible()
    assert not wizard._step_valid(wizard._step_index_for_key("experiment"))
    assert wizard._current_step_blocker() == table.presentation_count_blocker()
    messages = record_setup_validation_dialogs(monkeypatch)
    before = document.project.model_copy(deep=True)
    assert wizard.setup_wizard_next_button.isEnabled()
    qtbot.mouseClick(wizard.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    assert wizard.step_stack.currentWidget() is wizard.experiment_step_surface
    assert messages == [("Complete this setup step", table.presentation_count_blocker())]
    assert document.project == before
    assert effective_condition_presentation_count(
        document.project, document.get_condition(first),
    ) == 2
    table.presentation_count_spins[first].setValue(1)
    assert wizard.flush_pending_edits()
    assert not table.presentation_count_blocker()
    assert not table.error_label.isVisible()
    assert wizard._step_valid(wizard._step_index_for_key("experiment"))
    qtbot.mouseClick(wizard.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    assert wizard.step_stack.currentWidget() is wizard.session_step_surface
    assert len(messages) == 1


def test_next_reports_invalid_duration_draft_once_and_preserves_it(
    qtbot, monkeypatch, tmp_path,
):
    document, first, _second = _document(tmp_path)
    wizard = SetupWizardPage(
        document, load_condition_template_profiles=lambda: [],
        manage_condition_templates=lambda: [],
    )
    qtbot.addWidget(wizard)
    wizard.resize(1120, 820)
    wizard.show()
    wizard.open_wizard(step_key="experiment", allow_step_jumps=True)
    table = wizard.condition_timing_table
    before = document.project.model_copy(deep=True)
    messages = record_setup_validation_dialogs(monkeypatch)
    table.duration_spins[first].setValue(10.1)
    QApplication.processEvents()
    assert wizard.setup_wizard_next_button.isEnabled()
    assert messages == []
    qtbot.mouseClick(wizard.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    assert wizard.step_stack.currentWidget() is wizard.experiment_step_surface
    assert document.project == before
    assert table.duration_spins[first].value() == pytest.approx(10.1)
    assert table.has_pending_edits()
    assert "Valid durations" in table.error_label.text()
    assert messages == [("Complete this setup step", table.error_label.text())]


def test_new_condition_uses_template_total_presentations_for_image_and_word(qtbot, tmp_path):
    document, _first, _second = _document(tmp_path)
    document.update_condition_defaults(presentation_count=3)
    condition_id = document.create_condition(name="Template presentations")
    assert document.get_condition(condition_id).presentation_count == 3
    document.set_condition_stimulus_modality(condition_id, modality=StimulusModality.WORD)
    assert document.get_condition(condition_id).presentation_count == 3


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_masking_keeps_group_repeat_control_and_disables_independent_counts(
    qtbot, monkeypatch, tmp_path, background,
):
    from tests.unit.test_masking import masking_project

    document, _first, _second = _document(tmp_path)
    project = masking_project(("color",))
    project.meta = document.project.meta.model_copy(deep=True)
    project.settings.display.preferred_refresh_hz = 60
    document.apply_condition_modifier_project(project)
    catch_id = document.add_masking_catch_condition("color-1")
    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda _self: None)
    wizard = SetupWizardPage(
        document, load_condition_template_profiles=lambda: [],
        manage_condition_templates=lambda: [],
    )
    qtbot.addWidget(wizard)
    palette = wizard.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    wizard.setPalette(palette)
    wizard.resize(1120, 820)
    wizard.show()
    wizard.open_wizard(step_key="session", allow_step_jumps=True)
    QApplication.processEvents()
    editor = wizard.session_structure_editor
    assert not editor.randomization_editor.isVisible()
    assert editor.block_count_spin.isVisible()
    assert editor.session_layout.labelForField(editor.block_count_spin).text() == (
        "Repeats per condition"
    )
    table = wizard.condition_timing_table
    assert all(not spin.isEnabled() for spin in table.presentation_count_spins.values())
    assert table.presentation_count_spins[catch_id].value() == 1
    assert "variant and catch grouping" in table.presentation_count_spins[catch_id].toolTip()
    duration_draft = table.duration_spins["color-1"].value() + 1
    table.duration_spins["color-1"].setValue(duration_draft)
    editor.block_count_spin.setValue(4)
    assert document.project.settings.session.block_count == 4
    assert table.presentation_count_spins["color-1"].value() == 4
    assert table.presentation_count_spins[catch_id].value() == 1
    assert table.duration_spins["color-1"].value() == duration_draft
    assert editor.presentation_total_label.text() == "13 total"
    assert wizard.step_stack.currentWidget() is wizard.session_step_surface
    assert editor.isVisible()
    assert not table.isVisible()
    assert_visible_children_within_parent(wizard.session_step_surface)
