"""Registered visible coverage for native masking authoring and draft boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QLabel, QMessageBox
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.core.condition_modifiers import assign_modifier, create_backward_counting_modifier
from fpvs_studio.core.masking import MaskingCatchTrialSettings
from fpvs_studio.core.masking_presets import create_masking_modifier
from fpvs_studio.gui import condition_modifier_dialog
from fpvs_studio.gui.condition_modifier_dialog import ConditionModifierDialog
from fpvs_studio.gui.condition_pages import ConditionsPage
from fpvs_studio.gui.condition_task_dialog import ConditionTaskDialog
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.masking_source_dialog import MaskingSourceDialog
from fpvs_studio.gui.modifier_library_dialog import ModifierLibraryDialog


def _fit(widget) -> None:
    QApplication.processEvents()
    assert_visible_children_within_parent(widget)
    for label in widget.findChildren(QLabel):
        if label.isVisible() and label.text() and label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width()), label.text()


def _document(tmp_path: Path, variant: str = "color"):
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Masking authoring")
    condition_id = document.create_condition(name="Masking with precisely authored native sources")
    definition = create_masking_modifier(variant=variant)
    document.apply_condition_modifier_project(
        assign_modifier(document.project, definition, [condition_id])
    )
    return document, condition_id


@pytest.mark.parametrize("variant", ["color", "faces", "number"])
@pytest.mark.parametrize("size", [(1100, 720), (1120, 760)])
@pytest.mark.parametrize("catch_enabled", [False, True])
def test_masking_tabs_fit_and_edits_preserve_native_sources(
    qtbot, tmp_path: Path, variant, size, catch_enabled,
) -> None:
    document, condition_id = _document(tmp_path, variant)
    original = document.project.model_dump()
    dialog = ConditionModifierDialog(document, condition_id=condition_id, fpvs_root=tmp_path)
    qtbot.addWidget(dialog)
    dialog.resize(*size)
    dialog.show()
    dialog.tabs.setCurrentIndex(1)
    assert dialog.settings_stack.currentIndex() == 2
    assert dialog.screens_button.isVisible()
    assert not dialog.instructions_button.isVisible()
    assert not dialog.masking_catch_checkbox.isChecked()
    assert "automatic" in dialog.masking_catch_checkbox.text()
    assert "Setup → Conditions → Add Catch Condition" in dialog.masking_catch_help.text()
    assert not dialog.masking_catch_trigger_spin.isEnabled()
    assert dialog.masking_catch_trigger_spin.value() == {
        "color": 10, "faces": 11, "number": 12,
    }[variant]
    dialog.masking_catch_checkbox.setChecked(catch_enabled)
    assert dialog.masking_catch_trigger_spin.isEnabled() == catch_enabled
    assert "All SOAs in the same variant must use matching catch settings and code" in (
        dialog.masking_catch_help.text()
    )
    before = dialog._definitions[dialog._selected_id].model_copy(deep=True)
    assert "does not rewrite participant instructions" in dialog.masking_catch_help.text()
    for tab in range(4):
        dialog.tabs.setCurrentIndex(tab)
        _fit(dialog)
        assert (dialog.width(), dialog.height()) == size
        if tab == dialog.masking_catch_tab_index:
            assert dialog.masking_catch_checkbox.width() >= (
                dialog.masking_catch_checkbox.sizeHint().width()
            )
    dialog.tabs.setCurrentIndex(2)
    for phase in range(4):
        dialog.preview_phase.setCurrentIndex(phase)
        _fit(dialog)
        assert not dialog.preview_grid_widget.isVisible()
    dialog.masking_timing_spins["soa_ms"].setValue(100)
    assert dialog._save_fields()
    after = dialog._definitions[dialog._selected_id]
    assert after.modifier.masking.soa_ms == 100
    assert after.modifier.masking.target_duration_ms == before.modifier.masking.target_duration_ms
    assert after.modifier.masking.base_visuals == before.modifier.masking.base_visuals
    if catch_enabled:
        assert after.modifier.masking.catch_trial.trigger_code == (
            dialog.masking_catch_trigger_spin.value()
        )
    else:
        assert after.modifier.masking.catch_trial is None
    assert after.task_modules == before.task_modules
    dialog.reject()
    assert document.project.model_dump() == original


@pytest.mark.parametrize("initially_enabled", [False, True])
def test_masking_catch_apply_reopens_with_enabled_state_and_code(
    qtbot, tmp_path: Path, initially_enabled,
) -> None:
    document, condition_id = _document(tmp_path)
    definition = create_masking_modifier()
    definition.modifier.masking.catch_trial = (
        MaskingCatchTrialSettings(trigger_code=71) if initially_enabled else None
    )
    document.apply_condition_modifier_project(
        assign_modifier(document.project, definition, [condition_id])
    )
    modifier = document.project.condition_modifiers[0]
    before = document.project.model_dump()
    dialog = ConditionModifierDialog(document, condition_id=condition_id)
    qtbot.addWidget(dialog)
    assert dialog.masking_catch_checkbox.isChecked() == initially_enabled
    if initially_enabled:
        assert dialog.masking_catch_trigger_spin.value() == 71
    dialog.masking_catch_checkbox.setChecked(not initially_enabled)
    if not initially_enabled:
        dialog.masking_catch_trigger_spin.setValue(72)
    assert document.project.model_dump() == before
    dialog.accept()
    qtbot.waitUntil(lambda: dialog._active_task is None, timeout=10000)
    assert dialog.result() == QDialog.DialogCode.Accepted
    updated = document.project.condition_modifiers[0].masking
    assert updated.base_visuals == modifier.masking.base_visuals
    assert updated.target_visuals == modifier.masking.target_visuals
    if initially_enabled:
        assert updated.catch_trial is None
        assert "catch_trial" not in updated.model_dump()
    else:
        assert updated.catch_trial.trigger_code == 72
        assert document.project.schema_version == "1.8.0"
    reopened = ConditionModifierDialog(document, condition_id=condition_id)
    qtbot.addWidget(reopened)
    assert reopened.masking_catch_checkbox.isChecked() == (not initially_enabled)
    assert reopened.masking_catch_trigger_spin.isEnabled() == (not initially_enabled)
    if not initially_enabled:
        assert reopened.masking_catch_trigger_spin.value() == 72
    reopened.reject()


def test_masking_catch_copy_keeps_other_condition_and_cancel_unchanged(
    qtbot, tmp_path: Path,
) -> None:
    document, condition_id = _document(tmp_path)
    other_id = document.create_condition(name="Same variant with another SOA")
    definition = create_masking_modifier()
    definition.modifier.masking.catch_trial = MaskingCatchTrialSettings(trigger_code=10)
    document.apply_condition_modifier_project(
        assign_modifier(document.project, definition, [condition_id, other_id])
    )
    before = document.project.model_dump()
    dialog = ConditionModifierDialog(document, condition_id=condition_id)
    qtbot.addWidget(dialog)
    original_id = dialog._selected_id
    dialog._copy_for_condition()
    qtbot.waitUntil(lambda: dialog._active_task is None, timeout=10000)
    assert dialog._selected_id != original_id
    assert dialog.masking_catch_checkbox.isChecked()
    assert dialog.masking_catch_trigger_spin.value() == 10
    dialog.masking_catch_trigger_spin.setValue(73)
    assert dialog._save_fields()
    assert dialog._definitions[dialog._selected_id].modifier.masking.catch_trial.trigger_code == 73
    assert dialog._definitions[original_id].modifier.masking.catch_trial.trigger_code == 10
    assert dialog._scopes[original_id] == [other_id]
    assert document.project.model_dump() == before
    dialog.reject()
    assert document.project.model_dump() == before


def test_catch_tab_is_hidden_for_other_modifier_kinds(qtbot, tmp_path: Path) -> None:
    document, condition_id = _document(tmp_path)
    document.apply_condition_modifier_project(
        assign_modifier(document.project, create_backward_counting_modifier(), [condition_id])
    )
    dialog = ConditionModifierDialog(document, condition_id=condition_id)
    qtbot.addWidget(dialog)
    assert not dialog.tabs.isTabVisible(dialog.masking_catch_tab_index)
    dialog.reject()


@pytest.mark.parametrize("variant", ["color", "faces", "number"])
@pytest.mark.parametrize("size", [(940, 660), (1020, 700)])
def test_native_source_roles_fit_and_preserve_exact_fields(
    qtbot, tmp_path: Path, variant, size,
) -> None:
    definition = create_masking_modifier(variant=variant)
    settings = definition.modifier.masking
    original = settings.model_dump()
    dialog = MaskingSourceDialog(settings, project_root=tmp_path, task_id="masking-before")
    qtbot.addWidget(dialog)
    dialog.resize(*size)
    dialog.show()
    for role in range(5):
        dialog.role_combo.setCurrentIndex(role)
        for tab in range(3):
            dialog.tabs.setCurrentIndex(tab)
            _fit(dialog)
            assert (dialog.width(), dialog.height()) == size
    dialog.accept()
    assert dialog.settings.model_dump() == original
    assert settings.model_dump() == original


def test_native_palette_edit_retains_rgb_precision_and_matching_circle_units(
    qtbot, tmp_path: Path,
) -> None:
    settings = create_masking_modifier().modifier.masking
    dialog = MaskingSourceDialog(settings, project_root=tmp_path, task_id="masking-before")
    qtbot.addWidget(dialog)
    dialog.role_combo.setCurrentIndex(1)
    assert dialog.rgb_spins[0].value() == 0.97
    dialog.rgb_spins[0].setValue(0.971234567)
    dialog.accept()
    result = dialog.settings
    assert result.target_visuals[0].rgb == (0.971234567, 0.36, 0.37)
    assert result.target_visuals[0].edges is None
    assert result.base_visuals[0].units == "deg"
    assert result.target_visuals[0].units == "deg"
    assert result.mask_visuals[0].units == "deg"
    assert settings.target_visuals[0].rgb[0] == 0.97


def test_face_image_intake_is_staged_and_answer_is_explicit(
    qtbot, tmp_path: Path, monkeypatch,
) -> None:
    source = tmp_path / "face.png"
    Image.new("RGB", (25, 25), "white").save(source)
    settings = create_masking_modifier(variant="faces").modifier.masking
    dialog = MaskingSourceDialog(
        settings, project_root=tmp_path, task_id="masking-before", answers={"happy": "Happy"},
    )
    qtbot.addWidget(dialog)
    dialog.role_combo.setCurrentIndex(1)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *_args: ([str(source)], ""))
    dialog._import_images()
    assert not (tmp_path / "stimuli").exists()
    assert dialog.answer_combo.currentData() == ""
    dialog.answer_combo.setCurrentIndex(dialog.answer_combo.findData("happy"))
    dialog.accept()
    target = dialog.settings.target_visuals[0]
    assert target.image_path.startswith("stimuli/task-assets/masking-before/")
    assert dialog.asset_sources[target.image_path] == source
    assert dialog.settings.target_answers[target.visual_id] == "happy"
    assert not settings.target_visuals
    assert not (tmp_path / "stimuli").exists()


def test_source_file_picker_cancel_and_dialog_cancel_leave_inputs_untouched(
    qtbot, tmp_path: Path, monkeypatch,
) -> None:
    settings = create_masking_modifier(variant="number").modifier.masking
    before = settings.model_dump()
    dialog = MaskingSourceDialog(settings, project_root=tmp_path, task_id="masking-before")
    qtbot.addWidget(dialog)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *_args: ([], ""))
    dialog._import_images()
    dialog.text_edit.setText("Z")
    dialog.reject()
    assert settings.model_dump() == before
    assert not dialog.asset_sources
    assert not (tmp_path / "stimuli").exists()


def test_source_timing_action_is_explicit_and_remains_staged(
    qtbot, tmp_path: Path, monkeypatch,
) -> None:
    document, condition_id = _document(tmp_path)
    before = document.project.model_dump()
    dialog = ConditionModifierDialog(document, condition_id=condition_id)
    qtbot.addWidget(dialog)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No)
    dialog._apply_masking_defaults()
    assert dialog._project.settings.protocol.base_hz == 6
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    dialog._apply_masking_defaults()
    assert dialog._project.settings.protocol.base_hz == 5
    assert dialog._project.conditions[0].oddball_cycle_repeats_per_sequence == 40
    assert document.project.model_dump() == before
    dialog.reject()
    assert document.project.model_dump() == before


def test_changed_target_rgb_updates_only_matching_answer_fill(
    qtbot, tmp_path: Path, monkeypatch,
) -> None:
    document, condition_id = _document(tmp_path)
    original_project = document.project.model_dump()
    dialog = ConditionModifierDialog(document, condition_id=condition_id)
    qtbot.addWidget(dialog)
    definition = dialog._definitions[dialog._selected_id]
    identity = next(step for task in definition.task_modules for step in task.steps
                    if step.step_id == "masking-identification")
    identity.items.append(identity.items[1].model_copy(update={"item_id": "independent-swatch"}))
    original_choices = [item.model_dump() for item in identity.items]

    class EditedSources:
        def __init__(self, settings, **_kwargs):
            self.settings = settings.model_copy(deep=True)
            self.settings.target_visuals[0].rgb = (0.11, 0.22, 0.33)
            self.asset_sources = {}

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(condition_modifier_dialog, "MaskingSourceDialog", EditedSources)
    dialog._edit_masking_sources()
    updated = dialog._definitions[dialog._selected_id]
    identity = next(step for task in updated.task_modules for step in task.steps
                    if step.step_id == "masking-identification")
    assert identity.items[0].color_rgb == (0.11, 0.22, 0.33)
    expected_first = {**original_choices[0], "color_rgb": (0.11, 0.22, 0.33)}
    assert identity.items[0].model_dump() == expected_first
    assert [item.model_dump() for item in identity.items[1:]] == original_choices[1:]
    dialog.reject()
    assert document.project.model_dump() == original_project


def test_masking_screen_editor_preserves_first_and_last_group_bindings(
    qtbot, tmp_path: Path, monkeypatch,
) -> None:
    document, condition_id = _document(tmp_path)
    dialog = ConditionModifierDialog(document, condition_id=condition_id)
    qtbot.addWidget(dialog)
    inspected = []

    def inspect_screens(editor):
        condition = editor._document.get_condition(condition_id)
        inspected.append(condition)
        assert condition.pre_task_bindings[0].occurrence.value == "first_stream_group_entry"
        assert [binding.occurrence.value for binding in condition.post_task_bindings] == [
            "every_entry", "last_stream_group_entry",
        ]
        assert editor.pre_editor.modules()[0].occurrence == "first_stream_group_entry"
        assert editor.post_editor.modules()[-1].occurrence == "last_stream_group_entry"
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(ConditionTaskDialog, "exec", inspect_screens)
    dialog._edit_modifier_screens()
    assert len(inspected) == 1
    dialog.reject()


def test_library_exposes_all_three_reusable_masking_variants(qtbot) -> None:
    dialog = ModifierLibraryDialog([], library_path=None)
    qtbot.addWidget(dialog)
    keys = [dialog.built_in_list.item(index).data(256)
            for index in range(dialog.built_in_list.count())]
    assert {"masking-color", "masking-faces", "masking-number"}.issubset(keys)
    dialog.show()
    for index in range(2, 5):
        dialog.built_in_list.setCurrentRow(index)
        assert "SOA" in dialog.details.text()
        _fit(dialog)


def test_conditions_page_does_not_require_ordinary_sources_for_masking(
    qtbot, tmp_path: Path,
) -> None:
    document, _condition_id = _document(tmp_path)
    document.project.stimulus_sets.clear()
    page = ConditionsPage(document)
    qtbot.addWidget(page)
    assert "Masking" in (
        page.base_source_value.toolTip() + page.base_source_value.text()
    )
    assert not page.base_import_button.isEnabled()
