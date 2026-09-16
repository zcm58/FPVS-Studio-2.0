"""Visible, registered coverage of staged complete modifier authoring."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QLabel, QMessageBox
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.core.backward_counting import (
    create_backward_counting_baseline_task,
    create_backward_counting_report_task,
    create_backward_counting_start_task,
)
from fpvs_studio.core.condition_modifiers import (
    assign_modifier,
    create_backward_counting_modifier,
    create_image_memory_modifier,
    modifier_condition_ids,
)
from fpvs_studio.core.modifier_presets import list_modifier_presets
from fpvs_studio.core.task_models import TaskBinding, TaskFontFamily, TaskOccurrence
from fpvs_studio.gui.condition_modifier_dialog import ConditionModifierDialog
from fpvs_studio.gui.condition_task_dialog import ConditionTaskDialog
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.modifier_library_dialog import (
    ModifierLibraryDialog,
    ModifierScopeDialog,
    SaveModifierPresetDialog,
)


def _document(tmp_path: Path) -> tuple[ProjectDocument, str, str]:
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Modifier authoring")
    first = document.create_condition(name="Familiar objects — cognitive load")
    second = document.create_condition(name="Novel objects — cognitive load")
    return document, first, second


def _wait(dialog: ConditionModifierDialog, qtbot) -> None:
    qtbot.waitUntil(lambda: dialog._active_task is None, timeout=10000)
    QApplication.processEvents()


def _fit(dialog: QDialog, *, size: tuple[int, int] | None = None) -> None:
    QApplication.processEvents()
    if size is not None:
        assert (dialog.width(), dialog.height()) == size
    assert_visible_children_within_parent(dialog)
    for label in dialog.findChildren(QLabel):
        if label.isVisible() and label.text() and label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width()), label.text()


def _theme(dialog: QDialog, dark: bool) -> None:
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#202124" if dark else "#ffffff"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f1f3f4" if dark else "#202124"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f1f3f4" if dark else "#202124"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#303134" if dark else "#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f1f3f4" if dark else "#202124"))
    dialog.setPalette(palette)


def _capture(dialog: QDialog, name: str) -> None:
    output = os.environ.get("FPVS_MODIFIER_SCREENSHOTS")
    if output:
        path = Path(output)
        path.mkdir(parents=True, exist_ok=True)
        assert dialog.grab().save(str(path / f"{name}.png"))


@pytest.mark.parametrize("size", [(1100, 720), (1120, 760)])
@pytest.mark.parametrize("dark", [False, True])
def test_counting_tabs_fit_and_preserve_baseline_fields(qtbot, tmp_path: Path, size, dark) -> None:
    document, first, second = _document(tmp_path)
    definition = create_backward_counting_modifier(
        baseline_duration_seconds=30, baseline_instructions="Baseline practice instructions",
        baseline_endpoint_prompt="Your baseline endpoint?", instructions="Count during images.",
    )
    definition.task_modules[0].backward_counting.start_min = 5000
    definition.task_modules[0].backward_counting.start_max = 6000
    document.apply_condition_modifier_project(assign_modifier(document.project, definition,
                                                               [first, second]))
    before = document.project.model_dump()
    dialog = ConditionModifierDialog(document, condition_id=first, fpvs_root=tmp_path)
    qtbot.addWidget(dialog)
    _theme(dialog, dark)
    dialog.resize(*size)
    dialog.show()
    assert dialog.duration_spin.value() == 30
    assert dialog.copy_button.isVisible()
    for index in range(3):
        dialog.tabs.setCurrentIndex(index)
        _fit(dialog, size=size)
        if size == (1100, 720):
            _capture(dialog, f"counting-{'dark' if dark else 'light'}-{index}")
    for phase in range(4):
        dialog.preview_phase.setCurrentIndex(phase)
        _fit(dialog, size=size)
    assert "5000" in dialog.preview_text.text()
    dialog.tabs.setCurrentIndex(1)
    dialog.name_edit.setText("Backward counting with a retained participant baseline")
    assert dialog._save_fields()
    edited = dialog._definitions[dialog._selected_id]
    baseline = next(task.backward_counting for task in edited.task_modules
                    if task.task_id == edited.modifier.baseline_task_id)
    assert baseline.duration_seconds == 30
    assert baseline.instructions == "Baseline practice instructions"
    assert baseline.endpoint_prompt == "Your baseline endpoint?"
    assert baseline.start_min == 5000
    assert baseline.start_max == 6000
    dialog.reject()
    assert document.project.model_dump() == before


def test_legacy_open_apply_preserves_tasks_and_conversion_is_explicit(
    qtbot, tmp_path: Path, monkeypatch,
) -> None:
    document, first, second = _document(tmp_path)
    baseline = create_backward_counting_baseline_task(duration_seconds=30)
    start = create_backward_counting_start_task()
    report = create_backward_counting_report_task()
    legacy = document.project.model_copy(deep=True)
    legacy.task_modules = [baseline, start, report]
    for condition in legacy.conditions:
        condition.pre_task_bindings = [TaskBinding(
            task_id=baseline.task_id, occurrence=TaskOccurrence.FIRST_SESSION_ENTRY,
        )]
    legacy.conditions[0].pre_task_bindings.append(TaskBinding(
        task_id=start.task_id, replaces_condition_start_gate=True,
    ))
    legacy.conditions[0].post_task_bindings = [TaskBinding(task_id=report.task_id)]
    document.apply_condition_modifier_project(legacy)
    original = document.project.model_dump()
    dialog = ConditionModifierDialog(document, condition_id=first)
    qtbot.addWidget(dialog)
    assert dialog._definitions == {}
    assert dialog._build_project().model_dump() == original
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    dialog._convert_counting()
    assert dialog.duration_spin.value() == 30
    assert document.project.model_dump() == original
    converted = dialog._build_project()
    modifier = converted.condition_modifiers[0]
    assert modifier_condition_ids(converted, modifier.modifier_id) == [first]
    assert not converted.conditions[1].pre_task_bindings
    dialog.accept()
    _wait(dialog, qtbot)
    assert document.project.condition_modifiers
    assert second not in modifier_condition_ids(document.project, modifier.modifier_id)


@pytest.mark.parametrize("selected_index", [0, 1])
@pytest.mark.parametrize("replace", [False, True])
def test_remove_and_replace_modifier_only_on_selected_condition(
    qtbot, tmp_path: Path, selected_index, replace,
) -> None:
    document, first, second = _document(tmp_path)
    ids = [first, second]
    current_id, other_id = ids[selected_index], ids[1 - selected_index]
    shared = create_backward_counting_modifier(baseline_duration_seconds=30)
    project = assign_modifier(document.project, shared, ids)
    other = next(
        condition for condition in project.conditions if condition.condition_id == other_id
    )
    other.pre_task_bindings[0].occurrence = TaskOccurrence.FIRST_SESSION_ENTRY
    other.pre_task_bindings[0].replaces_condition_start_gate = False
    document.apply_condition_modifier_project(project)
    original = document.project.model_dump()
    dialog = ConditionModifierDialog(document, condition_id=current_id)
    qtbot.addWidget(dialog)
    dialog.show()

    qtbot.mouseClick(dialog.remove_button, Qt.MouseButton.LeftButton)

    assert dialog.modifier_list.count() == 0
    assert not dialog.remove_button.isEnabled()
    assert dialog.apply_button.text() == "Apply to 1 condition"
    assert document.project.model_dump() == original
    if replace:
        replacement = create_backward_counting_modifier(
            modifier_id="replacement", subtraction_step=7
        )
        dialog._add_definition(replacement)
        assert dialog.modifier_list.count() == 1
        assert dialog._scopes["replacement"] == [current_id]
        assert dialog.apply_button.text() == "Apply to 1 condition"
    _fit(dialog)
    qtbot.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)
    _wait(dialog, qtbot)

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert modifier_condition_ids(document.project, shared.modifier.modifier_id) == [other_id]
    assert document.get_condition(other_id) == other
    if replace:
        assert modifier_condition_ids(document.project, "replacement") == [current_id]
    else:
        assert not document.get_condition(current_id).pre_task_bindings
        assert not document.get_condition(current_id).post_task_bindings
    for condition_id, expected in ((current_id, int(replace)), (other_id, 1)):
        reopened = ConditionModifierDialog(document, condition_id=condition_id)
        qtbot.addWidget(reopened)
        assert reopened.modifier_list.count() == expected
        reopened.reject()


def test_cancel_per_condition_removal_preserves_shared_modifier(qtbot, tmp_path: Path) -> None:
    document, first, second = _document(tmp_path)
    shared = create_backward_counting_modifier()
    document.apply_condition_modifier_project(
        assign_modifier(document.project, shared, [first, second])
    )
    original = document.project.model_dump()
    dialog = ConditionModifierDialog(document, condition_id=first)
    qtbot.addWidget(dialog)
    dialog._remove_selected()
    assert modifier_condition_ids(dialog._build_project(), shared.modifier.modifier_id) == [second]
    dialog.reject()
    assert document.project.model_dump() == original


def test_add_and_remove_independent_modifiers_per_condition(qtbot, tmp_path: Path) -> None:
    document, first, second = _document(tmp_path)
    first_definition = create_backward_counting_modifier(modifier_id="first-counting")
    document.apply_condition_modifier_project(
        assign_modifier(document.project, first_definition, [first])
    )
    original_first = document.get_condition(first).model_copy(deep=True)
    dialog = ConditionModifierDialog(document, condition_id=second)
    qtbot.addWidget(dialog)
    assert dialog.modifier_list.count() == 0
    dialog._add_definition(create_backward_counting_modifier(modifier_id="second-counting"))
    assert dialog._scopes["second-counting"] == [second]
    assert dialog.modifier_list.count() == 1
    dialog.accept()
    _wait(dialog, qtbot)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert document.get_condition(first) == original_first

    reopened = ConditionModifierDialog(document, condition_id=second)
    qtbot.addWidget(reopened)
    assert reopened.modifier_list.count() == 1
    assert reopened._selected_id == "second-counting"
    reopened._remove_selected()
    reopened.accept()
    _wait(reopened, qtbot)
    assert reopened.result() == QDialog.DialogCode.Accepted
    assert document.get_condition(first) == original_first
    assert not document.get_condition(second).pre_task_bindings
    assert document.project.condition_modifiers == [first_definition.modifier]


def test_copy_for_current_condition_keeps_other_original(qtbot, tmp_path: Path) -> None:
    document, first, second = _document(tmp_path)
    definition = create_backward_counting_modifier(baseline_duration_seconds=30)
    document.apply_condition_modifier_project(assign_modifier(document.project, definition,
                                                               [first, second]))
    original = document.project.model_dump()
    dialog = ConditionModifierDialog(document, condition_id=first)
    qtbot.addWidget(dialog)
    dialog.step_spin.setValue(7)
    dialog._copy_for_condition()
    _wait(dialog, qtbot)
    copy_id = dialog._selected_id
    assert copy_id != definition.modifier.modifier_id
    assert dialog.step_spin.value() == 7
    assert dialog._save_fields()
    draft = dialog._build_project()
    assert modifier_condition_ids(draft, definition.modifier.modifier_id) == [second]
    assert modifier_condition_ids(draft, copy_id) == [first]
    original_start = next(task.backward_counting for task in draft.task_modules
                          if task.task_id == definition.modifier.pre_task_ids[0])
    assert original_start.subtraction_step == 13
    assert document.project.model_dump() == original
    dialog.reject()


@pytest.mark.parametrize("dark", [False, True])
def test_memory_file_draft_preview_and_custom_layout_survive_name_edit(
    qtbot, tmp_path: Path, monkeypatch, dark,
) -> None:
    document, first, _second = _document(tmp_path)
    dialog = ConditionModifierDialog(document, condition_id=first, fpvs_root=tmp_path)
    qtbot.addWidget(dialog)
    _theme(dialog, dark)
    dialog.resize(1100, 720)
    dialog.show()
    dialog._add_definition(create_image_memory_modifier())
    dialog.tabs.setCurrentIndex(1)
    _fit(dialog, size=(1100, 720))
    _capture(dialog, f"memory-{'dark' if dark else 'light'}-missing")
    paths = []
    for index in range(8):
        path = tmp_path / f"image-{index}.png"
        Image.new("RGB", (160, 160), (index * 30, 20, 200)).save(path)
        paths.append(str(path))
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *_args: (paths[:4], ""))
    dialog._choose_images(True)
    _wait(dialog, qtbot)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *_args: (paths[4:], ""))
    dialog._choose_images(False)
    _wait(dialog, qtbot)
    assert not list((document.project_root / "stimuli" / "task-assets").rglob("*.png"))
    assert dialog._save_fields()
    def edit_memory_screen(editor: ConditionTaskDialog) -> int:
        modules = editor.pre_editor.modules()
        modules[0].steps[0].font_family = TaskFontFamily.OPEN_SANS.value
        modules[0].steps[0].columns = 4
        modules[0].steps[0].continue_key = "return"
        editor.pre_editor.set_modules(modules)
        editor.accept()
        assert editor.result() == QDialog.DialogCode.Accepted, editor.validation_label.text()
        return int(editor.result())

    monkeypatch.setattr(ConditionTaskDialog, "exec", edit_memory_screen)
    dialog._edit_modifier_screens()
    _wait(dialog, qtbot)
    dialog.name_edit.setText("Retain customized memory layout")
    assert dialog._save_fields()
    study = dialog._study_module(dialog._definitions[dialog._selected_id]).steps[0]
    assert study.font_family == TaskFontFamily.OPEN_SANS
    assert study.columns == 4
    assert study.continue_key == "return"
    _capture(dialog, f"memory-{'dark' if dark else 'light'}-settings")
    dialog.tabs.setCurrentIndex(2)
    dialog.preview_phase.setCurrentIndex(2)
    _fit(dialog, size=(1100, 720))
    _capture(dialog, f"memory-{'dark' if dark else 'light'}-preview")
    for button in dialog.preview_images[:4]:
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert dialog.preview_submit.isEnabled()
    qtbot.mouseClick(dialog.preview_images[4], Qt.MouseButton.LeftButton)
    assert sum(button.isChecked() for button in dialog.preview_images) == 4
    dialog.accept()
    _wait(dialog, qtbot)
    assert document.project.condition_modifiers
    assert len(list((document.project_root / "stimuli" / "task-assets").rglob("*.png"))) == 12


def test_library_and_scope_fit_empty_and_conflicting_states(qtbot, tmp_path: Path) -> None:
    document, first, second = _document(tmp_path)
    library = ModifierLibraryDialog([], library_path=tmp_path, parent=None)
    qtbot.addWidget(library)
    library.show()
    _fit(library)
    library.tabs.setCurrentIndex(1)
    assert "No local presets" in library.details.text()
    assert not library.add_button.isEnabled()
    _fit(library)
    library.reject()
    scope = ModifierScopeDialog(document.project, selected_ids=[first],
                                conflicts={second: "Remember four images"})
    qtbot.addWidget(scope)
    scope.show()
    _fit(scope)
    assert not scope.conditions.item(1).flags() & Qt.ItemFlag.ItemIsEnabled


def test_advanced_dialog_deferred_apply_never_mutates_document(qtbot, tmp_path: Path) -> None:
    document, first, _second = _document(tmp_path)
    original = document.project.model_dump()
    dialog = ConditionTaskDialog(document, condition_id=first, defer_apply=True)
    qtbot.addWidget(dialog)
    dialog.accept()
    assert dialog.staged_result is not None
    assert document.project.model_dump() == original


def test_saved_preset_survives_cancel_and_can_be_loaded_into_an_independent_draft(
    qtbot, tmp_path: Path, monkeypatch,
) -> None:
    document, first, _second = _document(tmp_path)
    original = document.project.model_dump()
    dialog = ConditionModifierDialog(document, condition_id=first, fpvs_root=tmp_path)
    qtbot.addWidget(dialog)
    dialog._add_definition(create_backward_counting_modifier(baseline_duration_seconds=30))
    monkeypatch.setattr(SaveModifierPresetDialog, "exec",
                        lambda _dialog: int(QDialog.DialogCode.Accepted))
    dialog._save_preset()
    _wait(dialog, qtbot)
    assert "Saved locally" in dialog.status.text()
    presets = list_modifier_presets(tmp_path)
    assert len(presets) == 1
    dialog.reject()
    assert document.project.model_dump() == original
    second_dialog = ConditionModifierDialog(document, condition_id=first, fpvs_root=tmp_path)
    qtbot.addWidget(second_dialog)

    def choose_preset(library: ModifierLibraryDialog) -> int:
        library.selection = ("preset", presets[0].preset_id)
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(ModifierLibraryDialog, "exec", choose_preset)
    second_dialog._show_library(presets)
    _wait(second_dialog, qtbot)
    assert second_dialog.duration_spin.value() == 30
    assert second_dialog._selected_id != presets[0].definition.modifier.modifier_id
    second_dialog.reject()
    assert document.project.model_dump() == original


def test_failed_background_apply_keeps_dialog_and_live_document(qtbot, tmp_path: Path) -> None:
    document, first, _second = _document(tmp_path)
    original = document.project.model_dump()
    dialog = ConditionModifierDialog(document, condition_id=first)
    qtbot.addWidget(dialog)
    dialog.show()

    def fail() -> object:
        raise ValueError("A selected image is missing. Choose its replacement in Settings.")

    dialog._run_job(fail, lambda _value: pytest.fail("Failure called the success handler"),
                    "Validating…")
    dialog.reject()
    assert dialog.isVisible()
    _wait(dialog, qtbot)
    assert "selected image is missing" in dialog.status.text()
    assert dialog.apply_button.isEnabled()
    assert document.project.model_dump() == original
    _fit(dialog, size=(1120, 760))


def test_long_modifier_description_keeps_full_value_accessible(qtbot, tmp_path: Path) -> None:
    document, first, _second = _document(tmp_path)
    description = (
        "Hold the assigned number in mind while viewing familiar and unfamiliar images. " * 15
    )
    definition = create_backward_counting_modifier(
        name=("Serial subtraction during familiar and unfamiliar image sequences "
              "with baseline assessment"),
        description=description,
    )
    document.apply_condition_modifier_project(
        assign_modifier(document.project, definition, [first])
    )
    dialog = ConditionModifierDialog(document, condition_id=first)
    qtbot.addWidget(dialog)
    dialog.resize(1100, 720)
    dialog.show()
    assert dialog.description_label.toolTip() == description
    assert dialog.description_label.text().endswith("…")
    for tab in range(3):
        dialog.tabs.setCurrentIndex(tab)
        _fit(dialog, size=(1100, 720))
