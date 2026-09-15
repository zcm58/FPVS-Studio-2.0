"""Native AB sources, onset separation, shared edits and default-size layout."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QColorDialog, QSpinBox
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.core.attentional_blink_stream import iter_attentional_blink_stream_cycles
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.gui.attentional_blink_character_size import AttentionalBlinkCharacterSizeEditor
from fpvs_studio.gui.attentional_blink_stream_designer import AttentionalBlinkStreamDesigner
from fpvs_studio.gui.condition_setup_step import ConditionSetupStep
from fpvs_studio.gui.design_setup_step import DesignSetupStep
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.runtime_settings_page import DisplaySettingsEditor


@pytest.fixture
def stream_document(tmp_path):
    return ProjectDocument.create_new(
        parent_dir=tmp_path,
        project_name="Digit and letter attentional blink",
        experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
    )


@pytest.fixture
def legacy_stream_document(stream_document):
    project = stream_document.project
    project.settings.session.randomize_across_blocks = False
    project.settings.protocol.oddball_every_n = 20
    for condition in project.conditions:
        condition.post_task_bindings = []
        condition.attentional_blink.t2_slot_index = 15
    stream_document.apply_attentional_blink_stream_design(
        list("23456789"), list("ABCDEFG"), list("ABCDEFG"),
        {item.condition_id: item.attentional_blink.soa_ms for item in project.conditions},
        t1_color="#FF0000", t2_color="#FFFFFF",
    )
    return stream_document


def _editor(qtbot, document):
    step = DesignSetupStep(document)
    qtbot.addWidget(step)
    step.resize(1000, 590)
    step.show()
    QApplication.processEvents()
    assert isinstance(step.editor, AttentionalBlinkStreamDesigner)
    return step, step.editor


def test_burst_count_is_atomic_configurable_and_persists(qtbot, stream_document):
    step, editor = _editor(qtbot, stream_document)
    before = stream_document.project.model_dump(mode="json")
    editor.bursts_per_soa_spin.setValue(20)
    assert editor.burst_summary.text() == "100 s EEG per SOA · 60 total bursts"
    assert stream_document.project.model_dump(mode="json") == before
    soa = next(iter(editor.soa_edits.values()))
    soa.setText("250")
    assert not step.apply_pending_design()
    assert stream_document.project.model_dump(mode="json") == before
    soa.setText("100")
    assert step.apply_pending_design()
    assert stream_document.project.settings.session.block_count == 20
    assert stream_document.project.settings.session.randomize_across_blocks
    stream_document.save()
    reopened = ProjectDocument.open_existing(stream_document.project_root)
    _, restored = _editor(qtbot, reopened)
    assert restored.bursts_per_soa_spin.value() == 20
    assert restored.burst_summary.text() == "100 s EEG per SOA · 60 total bursts"


def test_burst_rate_preserves_five_seconds_and_rejects_partial_character_grid(
    qtbot, stream_document,
):
    step, editor = _editor(qtbot, stream_document)
    editor.rate_edit.setText("20")
    assert editor.timeline.description.cycle_ms == 5000
    assert editor.timeline.description.t2_slot_index == 60
    assert editor.timeline.description.cycle_slots == 100
    assert step.apply_pending_design()
    assert stream_document.project.settings.protocol.oddball_every_n == 100
    before = stream_document.project.model_dump(mode="json")
    editor.rate_edit.setText("7.5")
    assert "character boundaries" in editor.validation_message()
    assert not step.apply_pending_design()
    assert stream_document.project.model_dump(mode="json") == before


def test_three_soas_show_core_target_positions_and_intervening_digits(qtbot, stream_document):
    step, editor = _editor(qtbot, stream_document)
    assert not step.condition_combo.isVisible()
    assert editor.findChildren(QSpinBox) == [editor.bursts_per_soa_spin]
    assert editor.bursts_per_soa_spin.value() == 24
    assert editor.burst_summary.text() == "120 s EEG per SOA · 72 total bursts"
    assert editor.condition_table.rowCount() == 3
    assert editor.condition_table.columnCount() == 3
    for row, (soa, t1, count) in enumerate(((100, 29, 0), (300, 27, 2), (500, 25, 4))):
        editor.condition_table.selectRow(row)
        assert editor.timeline.description.soa_ms == soa
        assert editor.timeline.description.t1_slot_index == t1
        assert editor.timeline.description.t2_slot_index == 30
        assert editor.timeline.description.intervening_digits == count
        assert editor.condition_table.item(row, 2).text() == str(count)
        assert f"{count} distractors between targets" in editor.separation_label.text()
        assert f"{count} distractors between T1 and T2" in editor.timeline.accessibleName()
        assert len(editor.timeline.symbols) == 50
        assert all(symbol.isalpha() for symbol in editor.timeline.symbols[31:])
        assert editor.timeline.symbols[t1].isdigit()
        assert editor.timeline.symbols[30].isdigit()
        assert editor.timeline.symbols[t1] != editor.timeline.symbols[30]
        assert (
            step.selected_condition_id() == stream_document.ordered_conditions()[row].condition_id
        )


def test_shared_edits_stay_drafts_until_next_and_invalid_soa_is_blocked(qtbot, stream_document):
    step, editor = _editor(qtbot, stream_document)
    before = stream_document.project.model_dump(mode="json")
    condition = stream_document.ordered_conditions()[1]
    editor.soa_edits[condition.condition_id].setText("250")
    editor.base_edit.setText("A B C D")
    assert "whole multiple of 100 ms" in editor.validation_message()
    assert not editor.preview_button.isEnabled()
    assert not step.apply_pending_design()
    assert stream_document.project.model_dump(mode="json") == before
    editor.soa_edits[condition.condition_id].setText("300")
    editor.condition_table.selectRow(2)
    assert step.has_pending_design()
    assert step.apply_pending_design()
    for item in stream_document.ordered_conditions():
        assert stream_document.get_condition_stimulus_set(item.condition_id, "base").words == list(
            "ABCD"
        )
    assert not step.has_pending_design()
    stream_document.save()
    reopened = ProjectDocument.open_existing(stream_document.project_root)
    assert [item.attentional_blink.soa_ms for item in reopened.ordered_conditions()] == [
        100,
        300,
        500,
    ]


def test_rate_edit_updates_preview_and_applies_without_changing_soas(qtbot, stream_document):
    step, editor = _editor(qtbot, stream_document)
    before = stream_document.project.model_dump(mode="json")
    soa_text = {key: edit.text() for key, edit in editor.soa_edits.items()}
    editor.preview_button.setChecked(True)
    editor.rate_edit.setText("20")
    assert not editor.preview_timer.isActive()
    assert not editor.validation_message()
    assert editor.has_pending_design()
    assert stream_document.project.model_dump(mode="json") == before
    editor.refresh()
    assert editor.rate_edit.text() == "20"
    assert {key: edit.text() for key, edit in editor.soa_edits.items()} == soa_text
    assert editor.timeline.description.base_hz == 20
    assert editor.rate_label.text() == "50 ms per character"
    assert "20 Hz" in editor.timeline.accessibleName()
    assert "100 characters · 5 s" in editor.cycle_summary.text()
    editor.preview_button.setChecked(True)
    assert editor.preview_timer.interval() == 200
    editor.preview_button.setChecked(False)
    assert step.apply_pending_design()
    assert stream_document.project.settings.protocol.base_hz == 20
    assert not editor.has_pending_design()
    assert [item.attentional_blink.soa_ms for item in stream_document.ordered_conditions()] == [
        100, 300, 500,
    ]
    stream_document.save()
    reopened = ProjectDocument.open_existing(stream_document.project_root)
    _, restored_editor = _editor(qtbot, reopened)
    assert float(restored_editor.rate_edit.text()) == 20
    assert restored_editor.timeline.description.base_hz == 20


def test_fractional_rate_and_soas_reopen_without_precision_loss(qtbot, legacy_stream_document):
    stream_document = legacy_stream_document
    step, editor = _editor(qtbot, stream_document)
    editor.rate_edit.setText("7.5")
    assert "whole multiple" in editor.validation_message()
    for edit, lag in zip(editor.soa_edits.values(), (1, 3, 5), strict=True):
        edit.setText(str(lag * 1000 / 7.5))
    assert not editor.validation_message()
    assert step.apply_pending_design()
    stream_document.save()
    reopened = ProjectDocument.open_existing(stream_document.project_root)
    _, restored_editor = _editor(qtbot, reopened)
    assert float(restored_editor.rate_edit.text()) == 7.5
    assert not restored_editor.validation_message()
    assert not restored_editor.has_pending_design()
    for condition in reopened.ordered_conditions():
        assert float(restored_editor.soa_edits[condition.condition_id].text()) == (
            condition.attentional_blink.soa_ms
        )


@pytest.mark.parametrize("text", ["", "letters", "0", "-1", "nan", "inf", "7.5"])
def test_invalid_rate_draft_cannot_apply_or_start_preview(qtbot, stream_document, text):
    step, editor = _editor(qtbot, stream_document)
    before = stream_document.project.model_dump(mode="json")
    editor.rate_edit.setText(text)
    assert editor.validation_message()
    assert not editor.preview_button.isEnabled()
    assert not editor.timeline.isEnabled()
    assert not step.apply_pending_design()
    assert stream_document.project.model_dump(mode="json") == before
    editor.rate_edit.setText("10.0")
    assert not editor.validation_message()
    assert not editor.has_pending_design()


@pytest.mark.parametrize("rate", [1e-6, 1e4, 1e-305])
def test_extreme_rate_keeps_static_timeline_without_unsafe_animation(
    qtbot, legacy_stream_document, rate,
):
    stream_document = legacy_stream_document
    _, editor = _editor(qtbot, stream_document)
    editor.rate_edit.setText(str(rate))
    for edit in editor.soa_edits.values():
        edit.setText(str(1000 / rate))
    assert not editor.validation_message()
    assert editor.timeline.isEnabled()
    assert not editor.preview_button.isEnabled()
    assert "outside the animated preview" in editor.preview_caption.text()
    editor.preview_button.setChecked(True)
    assert not editor.preview_timer.isActive()
    assert not editor.preview_button.isChecked()


@pytest.mark.parametrize(
    ("role", "initial", "selected"),
    [("t1", "#00FF00", "#12ABCD"), ("t2", "#FFFFFF", "#76CD12")],
)
def test_visual_target_color_picker_preserves_drafts_and_saves_all_conditions(
    qtbot, monkeypatch, stream_document, role, initial, selected,
):
    step, editor = _editor(qtbot, stream_document)
    button = getattr(editor, f"{role}_color_button")
    before = stream_document.project.model_dump(mode="json")
    choices = iter((QColor(), QColor(selected), QColor()))
    opened = []

    def choose_color(color, parent, title, options):
        opened.append((color.name().upper(), parent, title, options))
        return next(choices)

    monkeypatch.setattr(QColorDialog, "getColor", choose_color)
    assert button.color_hex() == initial
    assert not button.icon().isNull()
    initial_icon = button.icon().cacheKey()
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert button.color_hex() == initial
    assert button.icon().cacheKey() == initial_icon
    assert not step.has_pending_design()
    assert stream_document.project.model_dump(mode="json") == before

    button.setFocus()
    qtbot.keyClick(button, Qt.Key.Key_Space)
    assert button.color_hex() == selected
    assert selected in button.text()
    assert selected in button.accessibleDescription()
    swatch = button.icon().pixmap(button.iconSize()).toImage()
    assert swatch.pixelColor(swatch.width() // 2, swatch.height() // 2) == QColor(selected)
    assert getattr(editor.timeline, f"{role}_color") == selected
    assert step.has_pending_design()
    assert stream_document.project.model_dump(mode="json") == before

    selected_snapshot = editor._snapshot()
    selected_icon = button.icon().cacheKey()
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert editor._snapshot() == selected_snapshot
    assert button.icon().cacheKey() == selected_icon
    assert step.has_pending_design()
    assert stream_document.project.model_dump(mode="json") == before
    assert [entry[0] for entry in opened] == [initial, initial, selected]
    for _color, parent, title, options in opened:
        assert parent is button
        assert title == f"Choose {role.upper()} color"
        assert options & QColorDialog.ColorDialogOption.DontUseNativeDialog
        assert not options & QColorDialog.ColorDialogOption.ShowAlphaChannel

    assert step.apply_pending_design()
    assert not step.has_pending_design()
    stream_document.save()
    reopened = ProjectDocument.open_existing(stream_document.project_root)
    expected = {"t1": "#00FF00", "t2": "#FFFFFF", role: selected}
    for condition in reopened.ordered_conditions():
        assert condition.attentional_blink.t1_color == expected["t1"]
        assert condition.attentional_blink.t2_color == expected["t2"]
    assert [condition.attentional_blink.soa_ms for condition in reopened.ordered_conditions()] == [
        100, 300, 500,
    ]


def test_preview_tracks_roles_and_stops_when_design_is_hidden(qtbot, stream_document):
    step, editor = _editor(qtbot, stream_document)
    editor.preview_button.setChecked(True)
    assert editor.preview_timer.isActive()
    editor._preview_index = editor.timeline.description.t1_slot_index - 1
    editor._advance_preview()
    assert "T1" in editor.preview_caption.text()
    assert editor.timeline.t1_color in editor.preview_symbol.text()
    step.hide()
    QApplication.processEvents()
    assert not editor.preview_timer.isActive()


def test_randomized_examples_use_playback_rules_without_editing_project(qtbot, stream_document):
    _step, editor = _editor(qtbot, stream_document)
    editor.base_edit.setText("DCBA")
    snapshot = editor._snapshot()
    project = stream_document.project.model_dump(mode="json")
    description = editor.timeline.description
    expected = next(iter_attentional_blink_stream_cycles(
        description,
        base_words=list("DCBA"),
        t1_words=list(editor.t1_edit.text()),
        t2_words=list(editor.t2_edit.text()),
        random_seed=0,
    ))
    original = editor.timeline.symbols
    assert original == expected
    assert "Random order" in editor.base_order_label.text()
    assert "not their presentation order" in editor.base_edit.toolTip()
    base_positions = [index for index, role in enumerate(description.roles) if role == "base"]
    assert all(original[index] in "DCBA" for index in base_positions)
    assert [original[index] for index in base_positions] != [
        "DCBA"[index % 4] for index in base_positions
    ]
    editor.preview_button.setChecked(True)
    qtbot.mouseClick(editor.shuffle_button, Qt.MouseButton.LeftButton)
    assert not editor.preview_timer.isActive()
    assert not editor.preview_button.isChecked()
    assert editor.timeline.symbols != original
    assert editor.timeline.description == description
    assert editor._snapshot() == snapshot
    assert stream_document.project.model_dump(mode="json") == project
    editor.base_edit.setText("2")
    assert not editor.shuffle_button.isEnabled()


def test_preview_draws_new_cycles_without_adjacent_digit_repeats(qtbot, stream_document):
    _step, editor = _editor(qtbot, stream_document)
    before = stream_document.project.model_dump(mode="json")
    editor.preview_button.setChecked(True)
    editor.preview_timer.stop()
    first_cycle = editor.timeline.symbols
    for _ in range(len(first_cycle)):
        editor._advance_preview()
    second_cycle = editor.timeline.symbols
    assert editor._preview_index == 0
    assert second_cycle != first_cycle
    combined = first_cycle + second_cycle
    for first, second in zip(combined, combined[1:], strict=False):
        if first.isdigit() and second.isdigit():
            assert first != second
    assert not editor.has_pending_design()
    assert stream_document.project.model_dump(mode="json") == before


def test_question_button_reuses_condition_tasks(qtbot, monkeypatch, stream_document):
    from fpvs_studio.gui import attentional_blink_stream_designer as module

    _step, editor = _editor(qtbot, stream_document)
    opened = []

    class FakeTaskDialog:
        def __init__(self, document, *, condition_id, parent):
            opened.append((document, condition_id, parent))

        def exec(self):
            return 0

    monkeypatch.setattr(module, "ConditionTaskDialog", FakeTaskDialog)
    editor.condition_table.selectRow(1)
    editor.question_button.click()
    assert opened == [
        (stream_document, stream_document.ordered_conditions()[1].condition_id, editor),
    ]


def test_removing_all_conditions_returns_to_empty_design_state(qtbot, stream_document):
    step, _editor_widget = _editor(qtbot, stream_document)
    for condition in list(stream_document.ordered_conditions()):
        stream_document.remove_condition(condition.condition_id)
    assert step.editor is None
    assert "Add a condition" in step.status_label.text()


def test_cloned_letter_stream_profile_preserves_layout_and_fixation_defaults(qtbot):
    from fpvs_studio.core.condition_template_profiles import (
        ATTENTIONAL_BLINK_STREAM_PROFILE_ID,
        built_in_condition_template_profiles,
    )
    from fpvs_studio.gui.condition_template_profile_editor_dialog import (
        ConditionTemplateProfileEditorDialog,
    )

    profile = next(
        item for item in built_in_condition_template_profiles()
        if item.profile_id == ATTENTIONAL_BLINK_STREAM_PROFILE_ID
    )
    dialog = ConditionTemplateProfileEditorDialog(
        existing_profile_ids=set(), initial_profile=profile,
    )
    qtbot.addWidget(dialog)
    dialog.profile_id_edit.setText("my-letter-stream")
    dialog.display_name_edit.setText("My digit and letter study")
    result = dialog._build_profile()
    assert result.defaults.attentional_blink_layout == "letter_stream"
    assert result.defaults.protocol == profile.defaults.protocol
    assert result.defaults.fixation_task.enabled == profile.defaults.fixation_task.enabled
    assert not result.defaults.fixation_task.accuracy_task_enabled
    assert not result.defaults.fixation_task.participant_tutorial_enabled


def test_conditions_hide_oddball_word_editors_and_keep_questionnaire(qtbot, stream_document):
    step = ConditionSetupStep(stream_document)
    qtbot.addWidget(step)
    step.resize(1000, 560)
    step.show()
    QApplication.processEvents()
    assert not step.words_panel.isVisible()
    assert not step.modality_combo.isVisible()
    assert not step.presentation_button.isVisible()
    assert step.task_button.isVisible()
    assert "SOA 100 ms" in step.ab_stream_summary.text()
    assert not step.ab_stream_summary.isVisible()
    assert "score T1 and T2 recall separately" in step.task_button.toolTip()
    assert step.condition_details_section.property("setupFlatSection") == "true"
    assert step.trigger_code_spin.width() <= 160
    assert step.add_condition_button.width() > step.duplicate_condition_button.width()
    assert step.duplicate_condition_button.y() == step.remove_condition_button.y()
    assert_visible_children_within_parent(step)


def test_character_height_updates_native_text_not_image_width(qtbot, stream_document):
    editor = AttentionalBlinkCharacterSizeEditor(stream_document)
    qtbot.addWidget(editor)
    editor.show()
    previous_image = stream_document.project.settings.presentation.defaults.image_geometry
    editor.character_height_edit.setText("1.4")
    editor.character_height_edit.editingFinished.emit()
    assert stream_document.project.settings.presentation.defaults.text_height.values == [1.4]
    assert stream_document.project.settings.presentation.defaults.image_geometry == previous_image
    assert not editor.width_degrees_spin.isVisible()
    assert not editor.full_screen_preview_button.isVisible()


def test_timing_rejects_rounded_character_intervals(qtbot, stream_document):
    editor = DisplaySettingsEditor(stream_document)
    qtbot.addWidget(editor)
    stream_document.update_display_settings(preferred_refresh_hz=144)
    report = editor.timing_report()
    assert not report.compatible
    assert report.errors
    stream_document.update_display_settings(preferred_refresh_hz=60)
    assert editor.timing_report().compatible
    assert not editor.base_hz_spin.isVisible()
    assert not editor.oddball_every_n_spin.isVisible()


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("size", [(1120, 820), (1448, 1086)])
def test_stream_design_fits_wizard_in_both_themes(
    qtbot,
    qapp,
    controller,
    stream_document,
    dark,
    size,
):
    previous_palette = qapp.palette()
    qapp.setPalette(QPalette(QColor("#202124" if dark else "#f4f7fb")))
    try:
        stream_document.save()
        controller.open_project(stream_document.project_root)
        window = controller.main_window
        qtbot.addWidget(window)
        window.show_setup_wizard(step_key="design")
        window.setup_wizard_page.open_wizard(step_key="design", allow_step_jumps=True)
        window.resize(*size)
        window.show()
        QApplication.processEvents()
        step = window.setup_wizard_page.design_setup_step
        editor = step.editor
        assert isinstance(editor, AttentionalBlinkStreamDesigner)
        assert (window.width(), window.height()) == size
        assert_visible_children_within_parent(step)
        assert editor.condition_table.horizontalScrollBar().maximum() == 0
        assert editor.condition_table.verticalScrollBar().maximum() == 0
        for row, condition in enumerate(stream_document.ordered_conditions()):
            field = editor.soa_edits[condition.condition_id]
            cell_rect = editor.condition_table.visualRect(
                editor.condition_table.model().index(row, 1)
            )
            field_rect = field.rect().translated(
                field.mapTo(editor.condition_table.viewport(), QPoint(0, 0))
            )
            assert cell_rect.contains(field_rect)
            assert abs(field_rect.center().y() - cell_rect.center().y()) <= 1
            assert field_rect.top() >= cell_rect.top() + 2
            assert field_rect.bottom() <= cell_rect.bottom() - 2
            assert field.height() >= field.minimumSizeHint().height()
        visible = editor.timeline.visible_slots()
        assert editor.timeline.slot_rect(visible.stop - 1).right() <= editor.timeline.width()
        assert editor.timeline.description.t1_slot_index in visible
        assert editor.timeline.description.t2_slot_index in visible
        for label in (
            editor.rate_caption, editor.rate_label, editor.cycle_summary, editor.separation_label,
            editor.base_order_label, editor.timeline_title, editor.burst_count_label,
        ):
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
        assert editor.shuffle_button.isVisible()
        assert editor.shuffle_button.width() >= editor.shuffle_button.sizeHint().width()
        for button in (editor.t1_color_button, editor.t2_color_button):
            assert button.isVisible()
            assert button.width() >= button.sizeHint().width()
            assert button.height() >= button.minimumSizeHint().height()
            assert not button.icon().isNull()
        assert editor.preview_caption.height() >= editor.preview_caption.heightForWidth(
            editor.preview_caption.width()
        )
        assert window.setup_wizard_page.progress_step_labels[4].text() == "Character Size"
        assert editor.rate_edit.isVisible()
        assert editor.rate_edit.height() >= editor.rate_edit.minimumSizeHint().height()
        for rate in (10, 20):
            editor.rate_edit.setText(str(rate))
            for edit, lag in zip(editor.soa_edits.values(), (1, 3, 5), strict=True):
                edit.setText(str(lag * 1000 / rate))
            QApplication.processEvents()
            assert not editor.validation_message()
            assert_visible_children_within_parent(step)
            for label in (editor.rate_caption, editor.rate_label, editor.cycle_summary,
                          editor.separation_label):
                assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
        editor.base_edit.setText("2")
        QApplication.processEvents()
        assert editor.validation_label.isVisible()
        assert_visible_children_within_parent(step)
        assert not window.setup_wizard_page.setup_wizard_next_button.isEnabled()
        qtbot.keyClick(editor.base_edit, Qt.Key.Key_Tab)
    finally:
        qapp.setPalette(previous_palette)


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("show_cross", [True, False])
def test_all_stream_setup_steps_fit_default_window(
    qtbot, qapp, controller, stream_document, dark, show_cross,
):
    previous_palette = qapp.palette()
    qapp.setPalette(QPalette(QColor("#202124" if dark else "#f4f7fb")))
    try:
        stream_document.update_fixation_settings(show_cross=show_cross)
        stream_document.save()
        controller.open_project(stream_document.project_root)
        window = controller.main_window
        qtbot.addWidget(window)
        window.resize(1120, 820)
        window.show_setup_wizard(step_key="project")
        window.show()
        wizard = window.setup_wizard_page
        for step_key in (
            "project", "conditions", "design", "experiment", "image_size",
            "fixation", "response", "review",
        ):
            wizard.open_wizard(step_key=step_key, allow_step_jumps=True)
            QApplication.processEvents()
            assert wizard._current_step_key() == step_key
            assert (window.width(), window.height()) == (1120, 820), step_key
            assert wizard.step_count_label.text() == f"Step {wizard._active_step_index + 1} of 8"
            assert wizard.step_count_label.isVisible()
            assert wizard.shell.title_label.alignment() & Qt.AlignmentFlag.AlignLeft
            assert "border-top" not in wizard.styleSheet()
            for card in (
                wizard.project_overview_editor.project_overview_card,
                wizard.experiment_settings_card, wizard.image_size_settings_card,
                wizard.session_settings_card, wizard.review_card,
            ):
                assert card.property("setupFlatSection") == "true"
                if card.isVisible():
                    assert card.title_label.isVisible() == (
                        card in (wizard.experiment_settings_card, wizard.session_settings_card)
                    )
                    if card.subtitle_label is not None:
                        assert not card.subtitle_label.isVisible()
            surface = wizard.step_stack.currentWidget()
            content = surface.content
            assert abs(content.mapTo(surface, content.rect().center()).x()
                       - surface.rect().center().x()) <= 2, step_key
            assert abs(content.mapTo(surface, content.rect().center()).y()
                       - surface.rect().center().y()) <= 2, step_key
            scroll = wizard.shell.page_container.scroll_area
            assert scroll.verticalScrollBar().maximum() == 0, step_key
            assert scroll.horizontalScrollBar().maximum() == 0, step_key
            assert_visible_children_within_parent(wizard.step_stack.currentWidget())
            if step_key == "image_size":
                editor = wizard.image_display_size_editor
                assert editor.character_height_edit.isVisible()
                assert not editor.width_degrees_spin.isVisible()
            if step_key == "review":
                sections = {
                    key: lines for key, _title, lines in wizard._review_checklist_sections()
                }
                assert "Letter distractors and target digits" in sections["conditions"][0]
                height = stream_document.project.settings.presentation.defaults.text_height
                assert sections["image_size"][0] == (
                    f"Character height: {height.values[0]:g} visual degrees"
                )
    finally:
        qapp.setPalette(previous_palette)
