"""Registered frequency draft, confirmation and compact Timing & Session checks."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.core.enums import StimulusModality
from fpvs_studio.gui.condition_timing_table import FREQUENCY_OVERRIDE_WARNING, ConditionTimingTable
from fpvs_studio.gui.document import ProjectDocument
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
    document, _first, _second = _document(tmp_path)
    document.update_display_settings(preferred_refresh_hz=None)
    original = document.project.model_copy(deep=True)
    editor = ConditionTimingTable(document)
    qtbot.addWidget(editor)
    editor.shared_frequency_spin.setValue(4)
    assert not editor.apply_pending_edits()
    assert "Select a monitor refresh rate" in editor.error_label.text()
    assert document.project == original


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("state", ["shared", "custom", "invalid"])
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
    QApplication.processEvents()
    assert wizard.size().toTuple() == (1120, 820)
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
    assert designer.rate_spin.value() == 4
    assert not designer.has_pending_design()
    designer.cycle_canvas.add_role("base")
    roles = designer.cycle_canvas.roles()
    document.update_condition_frequencies(overrides={first: 3})
    assert designer.rate_spin.value() == 3
    assert designer.cycle_canvas.roles() == roles
    assert designer.has_pending_design()
