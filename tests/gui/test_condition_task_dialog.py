"""Registered Qt coverage for modular condition-task authoring."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QLabel,
    QScrollArea,
    QTableWidgetItem,
    QTabWidget,
    QWidget,
)
from tests.gui.helpers import (
    _open_created_project,
)

from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskBranchOperator,
    TaskBranchRule,
    TaskDisplayItem,
    TaskFontFamily,
    TaskItemModality,
    TaskLayoutMode,
    TaskModule,
    TaskOccurrence,
    TaskOption,
    TaskQuestion,
    TaskQuestionKind,
    TaskStep,
    TaskStepKind,
    TaskSubmissionMode,
)
from fpvs_studio.gui.condition_modifier_dialog import ConditionModifierDialog
from fpvs_studio.gui.condition_task_dialog import (
    ConditionTaskDialog,
    ConditionTaskFlowDraft,
    TaskOptionDraft,
    TaskParticipantPreview,
    TaskStepDraft,
    TaskStepEditor,
    _module_from_draft,
    _module_to_draft,
    build_condition_task_models,
)
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.document_support import DocumentError


def _assert_visible_non_scroll_children_within_parent(root: QWidget) -> None:
    """Check visible layout chrome while allowing intentional scroll content."""

    for child in root.findChildren(QWidget):
        parent = child.parentWidget()
        if parent is None or not child.isVisible():
            continue
        ancestor: QWidget | None = parent
        inside_scroll_area = False
        while ancestor is not None and ancestor is not root:
            if isinstance(ancestor, QAbstractScrollArea):
                inside_scroll_area = True
                break
            ancestor = ancestor.parentWidget()
        if inside_scroll_area:
            continue
        top_left = child.mapTo(parent, child.rect().topLeft())
        bottom_right = child.mapTo(parent, child.rect().bottomRight())
        assert top_left.x() >= -1, child.objectName()
        assert top_left.y() >= -1, child.objectName()
        assert bottom_right.x() <= parent.width() + 1, child.objectName()
        assert bottom_right.y() <= parent.height() + 1, child.objectName()


def _assert_widget_within_parent(widget: QWidget) -> None:
    parent = widget.parentWidget()
    assert parent is not None
    top_left = widget.mapTo(parent, widget.rect().topLeft())
    bottom_right = widget.mapTo(parent, widget.rect().bottomRight())
    assert top_left.x() >= -1, widget.objectName()
    assert top_left.y() >= -1, widget.objectName()
    assert bottom_right.x() <= parent.width() + 1, widget.objectName()
    assert bottom_right.y() <= parent.height() + 1, widget.objectName()


def _show_editor_control(dialog: ConditionTaskDialog, widget: QWidget, qtbot) -> None:
    """Follow the same focused pages a user needs to reach an editor control."""

    for phase in (dialog.pre_editor, dialog.post_editor):
        if not phase.isAncestorOf(widget):
            continue
        dialog.phase_tabs.setCurrentWidget(phase)
        module = phase.module_editor
        if module.isAncestorOf(widget):
            settings = module.settings_page.isAncestorOf(widget)
            if module.module_settings_button.isChecked() != settings:
                qtbot.mouseClick(module.module_settings_button, Qt.MouseButton.LeftButton)
    for tabs in dialog.findChildren(QTabWidget):
        for index in range(tabs.count()):
            page = tabs.widget(index)
            if page is widget or page.isAncestorOf(widget):
                tabs.setCurrentIndex(index)
                break
    QApplication.processEvents()
    assert widget.isVisible(), widget.objectName()


def _assert_task_dialog_fits(dialog: ConditionTaskDialog) -> None:
    QApplication.processEvents()
    assert not dialog.findChildren(QScrollArea), "Task forms must use pages, not scrolling."
    _assert_visible_non_scroll_children_within_parent(dialog)
    for label in dialog.findChildren(QLabel):
        if not label.isVisible() or not label.text():
            continue
        if label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width()), label.objectName()
        else:
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text()), (
                label.objectName(),
                label.text(),
                label.width(),
            )
    for checkbox in dialog.findChildren(QCheckBox):
        if checkbox.isVisible():
            assert checkbox.width() >= checkbox.sizeHint().width(), checkbox.objectName()


def _visit_task_step_pages(dialog: ConditionTaskDialog, module, qtbot) -> None:
    """Check every available page without changing the authored task values."""

    _show_editor_control(dialog, module.step_editor, qtbot)
    editor = module.step_editor
    for index in range(editor.editor_tabs.count()):
        if not editor.editor_tabs.isTabVisible(index):
            continue
        editor.editor_tabs.setCurrentIndex(index)
        _assert_task_dialog_fits(dialog)
        questions = editor.questionnaire_editor
        if questions.isVisible():
            for question_index in range(questions.question_tabs.count()):
                if questions.question_tabs.isTabVisible(question_index):
                    questions.question_tabs.setCurrentIndex(question_index)
                    _assert_task_dialog_fits(dialog)


@pytest.mark.parametrize("role", ["baseline", "load_start", "load_report"])
def test_counting_library_modules_are_configurable_without_steps(
    qtbot, controller, tmp_path, role,
):
    document, window = _open_created_project(controller, qtbot, tmp_path, "Counting Library")
    condition_id = document.create_condition(name="Placeholder")
    dialog = ConditionTaskDialog(document, condition_id=condition_id, parent=window)
    qtbot.addWidget(dialog)
    dialog.resize(1100, 720)
    dialog.show()
    phase = dialog.post_editor if role == "load_report" else dialog.pre_editor
    dialog.phase_tabs.setCurrentWidget(phase)
    phase.add_kind_combo.setCurrentIndex(phase.add_kind_combo.findData(f"counting:{role}"))
    phase.add_button.click()
    editor = phase.module_editor
    assert editor.steps_group.isHidden()
    assert editor.step_selector.isHidden()
    assert editor.counting_group.isVisible()
    assert editor.counting_duration_spin.isVisible() == (role == "baseline")
    assert editor.counting_step_spin.isVisible() == (role != "load_report")
    editor.counting_link_edit.setText("counting-study-pair")
    if role != "load_report":
        editor.counting_step_spin.setValue(7)
        editor.counting_min_spin.setValue(1053)
        editor.counting_max_spin.setValue(2053)
    if role == "baseline":
        editor.counting_duration_spin.setValue(45)
    _assert_task_dialog_fits(dialog)
    modules, pre, post, copies = build_condition_task_models(
        dialog.draft(), project_root=document.project_root,
    )
    module = modules[0]
    assert module.steps == []
    assert module.backward_counting.role.value == role
    assert module.backward_counting.link_id == "counting-study-pair"
    assert copies == []
    if role != "load_report":
        assert module.backward_counting.subtraction_step == 7
        assert module.backward_counting.start_min == 1053
        assert module.backward_counting.start_max == 2053
    if role == "baseline":
        assert module.backward_counting.duration_seconds == 45
        assert pre[0].occurrence == TaskOccurrence.FIRST_SESSION_ENTRY
    if role == "load_start":
        assert pre[0].replaces_condition_start_gate
    if role == "load_report":
        assert len(post) == 1
    binding = (pre or post)[0]
    assert _module_from_draft(_module_to_draft(module, binding)) == module
    before = document.project.model_dump()
    dialog.reject()
    assert document.project.model_dump() == before


def test_counting_invalid_range_stays_a_draft(qtbot, controller, tmp_path):
    document, window = _open_created_project(controller, qtbot, tmp_path, "Counting Validation")
    condition_id = document.create_condition(name="Placeholder")
    before = document.project.model_dump()
    dialog = ConditionTaskDialog(document, condition_id=condition_id, parent=window)
    qtbot.addWidget(dialog)
    dialog.resize(1100, 720)
    dialog.show()
    phase = dialog.pre_editor
    phase.add_kind_combo.setCurrentIndex(phase.add_kind_combo.findData("counting:baseline"))
    phase.add_button.click()
    phase.module_editor.counting_min_spin.setValue(99999)
    assert not dialog.apply_button.isEnabled()
    assert dialog.validation_label.isVisible()
    _assert_task_dialog_fits(dialog)
    assert document.project.model_dump() == before
    phase.module_editor.counting_max_spin.setValue(100000)
    assert dialog.apply_button.isEnabled()


def test_shared_counting_baseline_edits_require_explicit_all_conditions_choice(
    qtbot, tmp_path,
):
    from fpvs_studio.core.enums import ExperimentCategory
    from fpvs_studio.gui.document import ProjectDocument

    document = ProjectDocument.create_new(
        parent_dir=tmp_path, project_name="Shared Counting",
        experiment_category=ExperimentCategory.COGNITIVE_LOAD_FPVS,
    )
    # Keep this legacy-editor regression independent of the new grouped starter.
    legacy = document.project.model_copy(deep=True)
    baseline_id = legacy.condition_modifiers[0].baseline_task_id
    assert baseline_id is not None
    legacy.condition_modifiers = []
    for condition in legacy.conditions:
        condition.pre_task_bindings.insert(0, TaskBinding(
            task_id=baseline_id, occurrence=TaskOccurrence.FIRST_SESSION_ENTRY,
        ))
    document.apply_condition_modifier_project(legacy)
    condition_id = document.project.conditions[0].condition_id
    dialog = ConditionTaskDialog(document, condition_id=condition_id)
    qtbot.addWidget(dialog)
    dialog.resize(1100, 720)
    dialog.show()
    assert dialog.update_shared_checkbox.isVisible()
    editor = dialog.pre_editor.module_editor
    editor.counting_duration_spin.setValue(60)
    before = document.project.model_dump()
    dialog.apply_button.click()
    assert document.project.model_dump() == before
    assert "shared" in dialog.validation_label.text()
    dialog.update_shared_checkbox.setChecked(True)
    _assert_task_dialog_fits(dialog)
    assert dialog.apply_button.isEnabled()
    dialog.apply_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    baseline = next(
        module for module in document.project.task_modules
        if module.backward_counting is not None
        and module.backward_counting.role.value == "baseline"
    )
    assert baseline.backward_counting.duration_seconds == 60
    assert all(
        any(binding.task_id == baseline.task_id for binding in condition.pre_task_bindings)
        for condition in document.project.conditions
    )


def test_task_model_adapter_preserves_unset_scoring_geometry_and_question_bounds() -> None:
    module = TaskModule(
        task_id="roundtrip",
        name="Round trip",
        steps=[
            TaskStep(
                step_id="choice",
                kind=TaskStepKind.CHOICE_GRID,
                font_family=TaskFontFamily.OPEN_SANS,
                layout_mode=TaskLayoutMode.RESPONSIVE_GRID,
                columns=2,
                submission_mode=TaskSubmissionMode.EXPLICIT,
                show_footer=False,
                items=[
                    TaskDisplayItem(
                        item_id="text-item",
                        modality=TaskItemModality.TEXT,
                        text="Word",
                        width=None,
                        height=2.5,
                        selectable=True,
                        correct=None,
                        unit="window_height_fraction",
                    ),
                    TaskDisplayItem(
                        item_id="text-item-2",
                        modality=TaskItemModality.TEXT,
                        text="Another word",
                        width=None,
                        height=2.5,
                        selectable=True,
                        correct=None,
                        unit="window_height_fraction",
                    ),
                ],
                allowed_keys=["left", "right"],
                timeout_seconds=2.5,
                repeat_count=2,
                max_attempts=3,
                retry_on_invalid=True,
                retry_on_incorrect=True,
                randomize_options=True,
                require_response=True,
                allow_duplicate_selections_across_repeats=False,
            ),
            TaskStep(
                step_id="questions",
                kind=TaskStepKind.QUESTIONNAIRE,
                questions=[
                    TaskQuestion(
                        question_id="optional-choice",
                        kind=TaskQuestionKind.MULTIPLE_CHOICE,
                        prompt="Choose any that apply",
                        required=False,
                        options=[
                            TaskOption(
                                option_id="option-a",
                                label="Option A | first line\nsecond line",
                                image_path=("stimuli/task-assets/roundtrip/option-a.png"),
                                correct=None,
                            )
                        ],
                        min_selections=None,
                        max_selections=None,
                        max_text_length=3_333,
                    ),
                    TaskQuestion(
                        question_id="optional-text",
                        kind=TaskQuestionKind.SHORT_TEXT,
                        prompt="Enter an optional value",
                        required=False,
                    ),
                ],
                submission_mode=TaskSubmissionMode.EXPLICIT,
                require_response=True,
                branch_rules=[
                    TaskBranchRule(
                        rule_id="optional-route",
                        question_id="optional-text",
                        operator=TaskBranchOperator.EQUALS,
                        expected_values=["literal,with,commas"],
                        next_step_id="acknowledge",
                    )
                ],
            ),
            TaskStep(
                step_id="acknowledge",
                kind=TaskStepKind.INSTRUCTION,
                font_family=TaskFontFamily.OPEN_SANS,
                heading="Continue",
                text="Ready?",
                continue_key="space",
                allowed_keys=["y", "n", "left", "right", "space"],
                duration_seconds=None,
                show_footer=False,
            ),
        ],
    )

    rebuilt = _module_from_draft(_module_to_draft(module, TaskBinding(task_id=module.task_id)))

    assert rebuilt == module
    text_item = rebuilt.steps[0].items[0]
    assert text_item.width is None
    assert text_item.height == 2.5
    assert text_item.correct is None
    question = rebuilt.steps[1].questions[0]
    assert question.min_selections is None
    assert question.max_selections is None
    assert question.options[0].image_path.endswith("option-a.png")
    instruction = rebuilt.steps[2]
    assert instruction.continue_key == "space"
    assert instruction.allowed_keys == ["y", "n", "left", "right", "space"]
    assert instruction.duration_seconds is None


def test_typed_recall_next_label_and_answer_key_survive_task_editor_roundtrip():
    module = TaskModule(
        task_id="ab-recall", name="Target recall", steps=[TaskStep(
            step_id="t1-recall", kind=TaskStepKind.QUESTIONNAIRE,
            submit_label="Next", questions=[TaskQuestion(
                question_id="t1-recall", kind=TaskQuestionKind.SHORT_TEXT,
                prompt="What was the green number?", required=True,
                max_text_length=32, correct_text="3",
            )],
        )],
    )
    draft = _module_to_draft(module, TaskBinding(task_id=module.task_id))
    assert draft.steps[0].submit_label == "Next"
    assert draft.steps[0].questions[0].correct_text == "3"
    assert _module_from_draft(draft) == module


def test_pre_task_binding_start_gate_replacement_roundtrips(tmp_path: Path) -> None:
    module = TaskModule(
        task_id="condition-reminder",
        name="Condition reminder",
        steps=[
            TaskStep(
                step_id="reminder",
                kind=TaskStepKind.INSTRUCTION,
                continue_key="space",
            )
        ],
    )
    binding = TaskBinding(
        task_id=module.task_id,
        replaces_condition_start_gate=True,
    )
    draft_module = _module_to_draft(module, binding)

    modules, pre_bindings, post_bindings, copies = build_condition_task_models(
        ConditionTaskFlowDraft(pre_modules=[draft_module]),
        project_root=tmp_path,
    )

    assert modules == [module]
    assert pre_bindings == [binding]
    assert post_bindings == []
    assert copies == []


def test_native_circle_styles_and_spatial_shuffle_survive_task_editor(qtbot, tmp_path) -> None:
    module = TaskModule(
        task_id="masking-report", name="Masking response",
        steps=[TaskStep(
            step_id="choice", kind=TaskStepKind.CHOICE_GRID,
            layout_mode=TaskLayoutMode.EXACT, randomize_positions=True,
            degree_geometry="linear",
            text="What target color did you see?", prompt_y=10,
            prompt_height=2.5, prompt_width=40, show_footer=False,
            items=[TaskDisplayItem(
                item_id="color", modality=TaskItemModality.CIRCLE, width=5, height=5,
                x=-5, y=5, color_rgb=(0.91, -0.4387, -0.602),
                line_color_rgb=(1, 1, 1), circle_edges=64, selectable=True,
            )],
        )],
    )
    draft = _module_to_draft(module, TaskBinding(task_id=module.task_id))
    editor = TaskStepEditor(tmp_path)
    qtbot.addWidget(editor)
    editor.resize(1100, 720)
    editor.set_step(draft.steps[0])
    editor.show()
    QApplication.processEvents()
    assert editor.randomize_options_checkbox.isChecked()
    assert editor.option_table.options()[0].shape == "circle"
    updated = editor.step()
    assert updated is not None
    draft.steps[0] = updated
    assert _module_from_draft(draft) == module
    _assert_visible_non_scroll_children_within_parent(editor)


@pytest.mark.parametrize("size", [(1100, 720), (1120, 760)])
def test_positioned_instruction_items_expose_editable_alignment_and_preview(
    qtbot, tmp_path, monkeypatch, size,
) -> None:
    module = TaskModule(task_id="masking-instructions", name="Masking", steps=[TaskStep(
        step_id="instructions", kind=TaskStepKind.INSTRUCTION, layout_mode=TaskLayoutMode.EXACT,
        font_family=TaskFontFamily.OPEN_SANS, continue_key="space", show_footer=False,
        items=[TaskDisplayItem(
            item_id="body", modality=TaskItemModality.TEXT,
            text="Identify the target.\nSome sequences contain no target.\nKeep looking at the +.",
            text_alignment="left", width=0.9, height=0.035,
            unit="window_height_fraction", y=0.1,
        )],
    )])
    draft = _module_to_draft(module, TaskBinding(task_id=module.task_id))
    editor = TaskStepEditor(tmp_path)
    qtbot.addWidget(editor)
    editor.resize(*size)
    editor.set_step(draft.steps[0])
    editor.show()
    QApplication.processEvents()
    assert editor.option_table.isVisible()
    assert editor.editor_tabs.currentIndex() == 0
    assert editor.type_stack.currentWidget() == editor._type_pages["study"]
    alignment = editor.option_table.cellWidget(0, 11)
    assert isinstance(alignment, QComboBox)
    assert alignment.currentData() == "left" and alignment.isEnabled()
    assert "center anchor" in alignment.toolTip()
    assert editor.option_table.item(0, 1).toolTip() == module.steps[0].items[0].text
    draft.steps[0] = editor.step()
    assert _module_from_draft(draft) == module
    alignment.setCurrentIndex(alignment.findData("right"))
    draft.steps[0] = editor.step()
    updated = _module_from_draft(draft)
    assert updated.steps[0].kind == TaskStepKind.INSTRUCTION
    assert updated.steps[0].items[0].text_alignment == "right"
    assert updated.steps[0].items[0].x == 0 and updated.steps[0].items[0].y == 0.1
    assert updated.steps[0].items[0].text == module.steps[0].items[0].text
    _assert_visible_non_scroll_children_within_parent(editor)

    rendered = []
    original = TaskParticipantPreview._paint_text_item

    def capture(painter, rect, option):
        rendered.append((option.label, option.text_alignment))
        original(painter, rect, option)

    monkeypatch.setattr(TaskParticipantPreview, "_paint_text_item", staticmethod(capture))
    preview = TaskParticipantPreview(tmp_path)
    qtbot.addWidget(preview)
    preview.resize(400, 420)
    preview.set_step(draft.steps[0])
    preview.show()
    QApplication.processEvents()
    assert (module.steps[0].items[0].text, "right") in rendered


def test_condition_task_dialog_apply_is_lossless_after_visiting_every_step(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Task Round Trip",
    )
    condition_id = document.create_condition(name="Round Trip")
    option_asset = document.project_root / "stimuli" / "task-assets" / "roundtrip" / "option-a.png"
    option_asset.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (12, 12), color=(30, 60, 90)).save(option_asset)
    module = TaskModule(
        task_id="roundtrip",
        name="Round trip",
        steps=[
            TaskStep(
                step_id="choice",
                kind=TaskStepKind.CHOICE_GRID,
                font_family=TaskFontFamily.OPEN_SANS,
                columns=2,
                items=[
                    TaskDisplayItem(
                        item_id="word",
                        modality=TaskItemModality.TEXT,
                        text="Word",
                        width=None,
                        height=0.2,
                        unit="window_height_fraction",
                        selectable=True,
                        correct=None,
                    )
                ],
                submission_mode=TaskSubmissionMode.EXPLICIT,
                require_response=True,
            ),
            TaskStep(
                step_id="questions",
                kind=TaskStepKind.QUESTIONNAIRE,
                questions=[
                    TaskQuestion(
                        question_id="optional-choice",
                        kind=TaskQuestionKind.MULTIPLE_CHOICE,
                        prompt="Choose any that apply",
                        required=False,
                        options=[
                            TaskOption(
                                option_id="option-a",
                                label="Option A | first line\nsecond line",
                                image_path=("stimuli/task-assets/roundtrip/option-a.png"),
                                correct=None,
                            )
                        ],
                        min_selections=None,
                        max_selections=None,
                    ),
                    TaskQuestion(
                        question_id="optional-text",
                        kind=TaskQuestionKind.SHORT_TEXT,
                        prompt="Enter an optional value",
                        required=False,
                    ),
                ],
                submission_mode=TaskSubmissionMode.EXPLICIT,
                require_response=True,
                branch_rules=[
                    TaskBranchRule(
                        rule_id="optional-route",
                        question_id="optional-text",
                        operator=TaskBranchOperator.EQUALS,
                        expected_values=["literal,with,commas"],
                        next_step_id="acknowledge",
                    )
                ],
            ),
            TaskStep(
                step_id="acknowledge",
                kind=TaskStepKind.INSTRUCTION,
                continue_key="space",
                allowed_keys=["y", "n", "left", "right", "space"],
                duration_seconds=None,
                show_footer=False,
            ),
        ],
    )
    document.set_condition_task_flow(
        condition_id,
        modules=[module],
        pre_bindings=[TaskBinding(task_id=module.task_id)],
        post_bindings=[],
    )

    dialog = ConditionTaskDialog(document, condition_id=condition_id, parent=window)
    qtbot.addWidget(dialog)
    dialog.show()
    for row in range(3):
        dialog.pre_editor.module_editor.step_selector.setCurrentIndex(row)
        QApplication.processEvents()
        _visit_task_step_pages(dialog, dialog.pre_editor.module_editor, qtbot)
    qtbot.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)

    rebuilt = next(item for item in document.project.task_modules if item.task_id == module.task_id)
    assert rebuilt == module


def test_task_asset_plan_retargets_media_when_module_is_renamed(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, _window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Task Rename",
    )
    source = document.project_root / "stimuli" / "task-assets" / "old-task" / "item.png"
    source.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (10, 10), color=(90, 40, 10)).save(source)
    module = TaskModule(
        task_id="old-task",
        name="Old task",
        steps=[
            TaskStep(
                step_id="study",
                kind=TaskStepKind.STUDY,
                items=[
                    TaskDisplayItem(
                        item_id="item",
                        modality=TaskItemModality.IMAGE,
                        image_path="stimuli/task-assets/old-task/item.png",
                    )
                ],
                continue_key="space",
            )
        ],
    )
    draft_module = _module_to_draft(module, TaskBinding(task_id=module.task_id))
    draft_module.module_id = "new-task"

    modules, _pre, _post, copies = build_condition_task_models(
        ConditionTaskFlowDraft(pre_modules=[draft_module]),
        project_root=document.project_root,
    )

    assert modules[0].steps[0].items[0].image_path == ("stimuli/task-assets/new-task/item.png")
    assert [(copy.source, copy.relative_target) for copy in copies] == [
        (source.resolve(), "stimuli/task-assets/new-task/item.png")
    ]


def test_task_asset_plan_preserves_nested_media_for_unchanged_module(
    tmp_path: Path,
) -> None:
    relative = "stimuli/task-assets/nested-task/category/set/item.png"
    source = tmp_path.joinpath(*Path(relative).parts)
    source.parent.mkdir(parents=True)
    Image.new("RGB", (10, 10), color=(10, 40, 90)).save(source)
    module = TaskModule(
        task_id="nested-task",
        name="Nested task",
        steps=[
            TaskStep(
                step_id="study",
                kind=TaskStepKind.STUDY,
                items=[
                    TaskDisplayItem(
                        item_id="item",
                        modality=TaskItemModality.IMAGE,
                        image_path=relative,
                    )
                ],
                continue_key="space",
            )
        ],
    )

    modules, _pre, _post, copies = build_condition_task_models(
        ConditionTaskFlowDraft(
            pre_modules=[_module_to_draft(module, TaskBinding(task_id=module.task_id))]
        ),
        project_root=tmp_path,
    )

    assert modules == [module]
    assert modules[0].steps[0].items[0].image_path == relative
    assert copies == []


def test_document_rejects_silent_edits_to_modules_shared_by_other_conditions(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, _window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Shared Tasks",
    )
    first_id = document.create_condition(name="First")
    second_id = document.create_condition(name="Second")
    module = TaskModule(
        task_id="shared-task",
        name="Shared task",
        steps=[
            TaskStep(
                step_id="instruction",
                kind=TaskStepKind.INSTRUCTION,
                continue_key="space",
            )
        ],
    )
    binding = TaskBinding(task_id=module.task_id)
    document.set_condition_task_flow(
        first_id,
        modules=[module],
        pre_bindings=[binding],
        post_bindings=[],
    )
    document.set_condition_task_flow(
        second_id,
        modules=[module],
        pre_bindings=[binding],
        post_bindings=[],
    )

    with pytest.raises(DocumentError, match="also bound to another condition"):
        document.set_condition_task_flow(
            first_id,
            modules=[module.model_copy(update={"name": "Changed silently"})],
            pre_bindings=[binding],
            post_bindings=[],
        )


def test_condition_task_dialog_cancel_keeps_model_and_disk_unchanged(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    document, window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Task Cancel",
    )
    condition_id = document.create_condition(name="Creatine Images")
    source = tmp_path / "external-apple.png"
    Image.new("RGB", (24, 24), color=(160, 20, 20)).save(source)
    window.start_deferred_open_tasks()
    qtbot.waitUntil(lambda: window._session_seed_ready, timeout=5_000)
    original = document.project.model_copy(deep=True)
    task_assets_root = document.project_root / "stimuli" / "task-assets"
    original_asset_entries = sorted(
        path.relative_to(task_assets_root) for path in task_assets_root.rglob("*")
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(source), "Images"),
    )

    dialog = ConditionTaskDialog(document, condition_id=condition_id, parent=window)
    qtbot.addWidget(dialog)
    dialog.resize(1100, 720)
    dialog.show()
    QApplication.processEvents()
    dialog.pre_editor.add_kind_combo.setCurrentIndex(
        dialog.pre_editor.add_kind_combo.findData("choice_grid")
    )
    qtbot.mouseClick(dialog.pre_editor.add_button, Qt.MouseButton.LeftButton)
    editor = dialog.pre_editor.module_editor.step_editor
    _show_editor_control(dialog, editor.add_image_item_button, qtbot)
    qtbot.mouseClick(editor.add_image_item_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert (
        sorted(path.relative_to(task_assets_root) for path in task_assets_root.rglob("*"))
        == original_asset_entries
    )
    dialog.reject()

    assert document.project == original
    assert (
        sorted(path.relative_to(task_assets_root) for path in task_assets_root.rglob("*"))
        == original_asset_entries
    )


def test_condition_task_dialog_applies_exact_group_repeat_and_asset_import(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    document, window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Task Apply",
    )
    condition_id = document.create_condition(name="Creatine Recognition")
    source = tmp_path / "apple.png"
    Image.new("RGB", (32, 28), color=(180, 30, 30)).save(source)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(source), "Images"),
    )
    dialog = ConditionTaskDialog(document, condition_id=condition_id, parent=window)
    qtbot.addWidget(dialog)
    dialog.resize(1100, 720)
    dialog.show()
    QApplication.processEvents()

    dialog.pre_editor.add_kind_combo.setCurrentIndex(
        dialog.pre_editor.add_kind_combo.findData("choice_grid")
    )
    qtbot.mouseClick(dialog.pre_editor.add_button, Qt.MouseButton.LeftButton)
    module_editor = dialog.pre_editor.module_editor
    _show_editor_control(dialog, module_editor.module_id_edit, qtbot)
    module_editor.module_id_edit.setText("creatine-recognition")
    module_editor.module_title_edit.setText("Creatine recognition")
    module_editor.module_repeat_count_spin.setValue(4)
    assert module_editor.replaces_start_gate_checkbox.isVisible()
    module_editor.replaces_start_gate_checkbox.setChecked(True)
    step_editor = module_editor.step_editor
    step_editor.step_id_edit.setText("recognition-choice")
    step_editor.prompt_edit.setPlainText("Select all 4")
    step_editor.layout_mode_combo.setCurrentIndex(step_editor.layout_mode_combo.findData("exact"))
    _show_editor_control(dialog, step_editor.add_image_item_button, qtbot)
    qtbot.mouseClick(step_editor.add_image_item_button, Qt.MouseButton.LeftButton)
    table = step_editor.option_table
    table.setItem(0, 6, QTableWidgetItem("-3"))
    table.setItem(0, 7, QTableWidgetItem("2"))
    table.setItem(0, 8, QTableWidgetItem("2.5"))
    table.setItem(0, 9, QTableWidgetItem("2"))
    module_editor.add_step_kind_combo.setCurrentIndex(
        module_editor.add_step_kind_combo.findData("timed_feedback")
    )
    _show_editor_control(dialog, module_editor.add_step_button, qtbot)
    qtbot.mouseClick(module_editor.add_step_button, Qt.MouseButton.LeftButton)
    feedback_editor = module_editor.step_editor
    feedback_editor.step_id_edit.setText("correct-feedback")
    feedback_editor.title_edit.setText("")
    feedback_editor.prompt_edit.setPlainText("correct")
    feedback_editor.duration_spin.setValue(1.0)
    QApplication.processEvents()

    assert dialog.apply_button.isEnabled()
    qtbot.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)

    assert not dialog.validation_label.isVisible(), dialog.validation_label.text()
    assert dialog.result() == QDialog.DialogCode.Accepted
    condition = document.get_condition(condition_id)
    assert condition is not None
    assert [binding.task_id for binding in condition.pre_task_bindings] == ["creatine-recognition"]
    assert condition.pre_task_bindings[0].replaces_condition_start_gate is True
    module = next(
        module
        for module in document.project.task_modules
        if module.task_id == "creatine-recognition"
    )
    assert module.repeat_count == 4
    assert [step.kind for step in module.steps] == [
        TaskStepKind.CHOICE_GRID,
        TaskStepKind.TIMED_FEEDBACK,
    ]
    choice = module.steps[0]
    assert choice.layout_mode == TaskLayoutMode.EXACT
    assert choice.items[0].correct is None
    assert choice.items[0].selectable is True
    assert choice.items[0].x == -3
    assert choice.items[0].height == 2
    assert module.steps[1].text == "correct"
    assert module.steps[1].duration_seconds == 1.0
    image_path = document.project_root / Path(choice.items[0].image_path)
    assert image_path.is_file()
    assert image_path.parent == (
        document.project_root / "stimuli" / "task-assets" / "creatine-recognition"
    )


def test_condition_task_dialog_exposes_all_questionnaire_types_and_fits_minimum_size(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Questionnaire Authoring",
    )
    condition_name = "Participant questionnaire after image recognition and confidence ratings"
    condition_id = document.create_condition(name=condition_name)
    dialog = ConditionTaskDialog(document, condition_id=condition_id, parent=window)
    qtbot.addWidget(dialog)
    dialog.resize(1100, 720)
    dialog.show()
    dialog.phase_tabs.setCurrentWidget(dialog.post_editor)
    QApplication.processEvents()

    dialog.post_editor.add_kind_combo.setCurrentIndex(
        dialog.post_editor.add_kind_combo.findData("questionnaire")
    )
    qtbot.mouseClick(dialog.post_editor.add_button, Qt.MouseButton.LeftButton)
    assert not dialog.post_editor.module_editor.replaces_start_gate_checkbox.isVisible()
    questionnaire = dialog.post_editor.module_editor.step_editor.questionnaire_editor
    _show_editor_control(dialog, questionnaire.add_button, qtbot)
    authored_kinds = {questionnaire.question_kind_combo.currentData()}
    for kind in (
        "multiple_choice",
        "short_text",
        "long_text",
        "numeric",
        "rating",
    ):
        questionnaire.add_kind_combo.setCurrentIndex(questionnaire.add_kind_combo.findData(kind))
        qtbot.mouseClick(questionnaire.add_button, Qt.MouseButton.LeftButton)
        authored_kinds.add(questionnaire.question_kind_combo.currentData())
    QApplication.processEvents()

    assert authored_kinds == {
        "single_choice",
        "multiple_choice",
        "short_text",
        "long_text",
        "numeric",
        "rating",
    }
    assert (
        dialog.post_editor.module_editor.step_editor.submission_mode_combo.findData("explicit") >= 0
    )
    assert dialog.preview.isVisible()
    assert dialog.header.title_label.text() == "Participant tasks"
    assert condition_name in dialog.header.subtitle_label.text()
    assert dialog.header.title_label.wordWrap()
    assert any(
        label.isVisible() and "only when you select Apply Tasks" in label.text()
        for label in dialog.findChildren(QLabel)
    )
    assert dialog.header.title_label.height() >= dialog.header.title_label.heightForWidth(
        dialog.header.title_label.width()
    )
    _visit_task_step_pages(dialog, dialog.post_editor.module_editor, qtbot)


@pytest.mark.parametrize("size", [(1100, 720), (1120, 760)])
@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_task_dialog_pages_fit_all_task_and_question_kinds(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    size: tuple[int, int],
    background: str,
) -> None:
    document, window = _open_created_project(controller, qtbot, tmp_path, "Task Page Layout")
    condition_id = document.create_condition(
        name="Participant questionnaire after image recognition and confidence ratings"
    )
    dialog = ConditionTaskDialog(document, condition_id=condition_id, parent=window)
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.resize(*size)
    dialog.show()
    _assert_task_dialog_fits(dialog)
    assert (dialog.width(), dialog.height()) == size
    assert dialog.pre_editor.empty_panel.isVisible()
    assert not dialog.pre_editor.module_editor.isVisible()

    dialog.phase_tabs.setCurrentWidget(dialog.post_editor)
    phase = dialog.post_editor
    for kind in (
        "instruction",
        "study",
        "choice_grid",
        "raw_key",
        "timed_feedback",
        "questionnaire",
    ):
        phase.add_kind_combo.setCurrentIndex(phase.add_kind_combo.findData(kind))
        qtbot.mouseClick(phase.add_button, Qt.MouseButton.LeftButton)
        module = phase.module_editor
        _show_editor_control(dialog, module.module_title_edit, qtbot)
        title = f"Participant recognition and confidence questionnaire - {kind}"
        module.module_title_edit.setText(title)
        assert title in phase.module_list.currentItem().toolTip()
        assert not module.replaces_start_gate_checkbox.isVisible()
        _assert_task_dialog_fits(dialog)

        editor = module.step_editor
        editor.title_edit.setText("Participant response after the complete recognition sequence")
        if kind in {"study", "choice_grid"}:
            _show_editor_control(dialog, editor.add_text_item_button, qtbot)
            qtbot.mouseClick(editor.add_text_item_button, Qt.MouseButton.LeftButton)
        _visit_task_step_pages(dialog, module, qtbot)
        assert editor.title_edit.text() in module.step_list.currentItem().toolTip()
        assert (dialog.width(), dialog.height()) == size

        if kind == "questionnaire":
            questionnaire = editor.questionnaire_editor
            for question_kind in (
                "single_choice",
                "multiple_choice",
                "short_text",
                "long_text",
                "numeric",
                "rating",
            ):
                if question_kind != "single_choice":
                    _show_editor_control(dialog, questionnaire.add_button, qtbot)
                    questionnaire.add_kind_combo.setCurrentIndex(
                        questionnaire.add_kind_combo.findData(question_kind)
                    )
                    qtbot.mouseClick(questionnaire.add_button, Qt.MouseButton.LeftButton)
                _show_editor_control(dialog, questionnaire.question_prompt_edit, qtbot)
                questionnaire.question_prompt_edit.setPlainText(
                    "Did you notice any white letters during the previous sequence of numbers?"
                )
                assert questionnaire.question_kind_combo.currentData() == question_kind
                assert questionnaire.question_prompt_edit.toPlainText() in (
                    questionnaire.question_list.currentItem().toolTip()
                )
                _visit_task_step_pages(dialog, module, qtbot)

    while phase.module_list.count():
        qtbot.mouseClick(phase.remove_button, Qt.MouseButton.LeftButton)
    _assert_task_dialog_fits(dialog)
    assert phase.empty_panel.isVisible()
    assert not phase.module_editor.isVisible()
    assert dialog.preview._step is None


def test_task_dialog_validation_stays_visible_and_recovers_without_scrolling(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, window = _open_created_project(controller, qtbot, tmp_path, "Task Validation")
    condition_id = document.create_condition(name="SOA 100 ms")
    dialog = ConditionTaskDialog(document, condition_id=condition_id, parent=window)
    qtbot.addWidget(dialog)
    dialog.resize(1100, 720)
    dialog.show()
    qtbot.mouseClick(dialog.pre_editor.add_button, Qt.MouseButton.LeftButton)
    module = dialog.pre_editor.module_editor
    _show_editor_control(dialog, module.module_id_edit, qtbot)
    original_id = module.module_id_edit.text()
    module.module_id_edit.clear()
    assert dialog.validation_label.isVisible()
    assert dialog.validation_label.text()
    assert not dialog.apply_button.isEnabled()
    _assert_task_dialog_fits(dialog)
    module.module_id_edit.setText(original_id)
    assert not dialog.validation_label.isVisible()
    assert dialog.apply_button.isEnabled()
    _assert_task_dialog_fits(dialog)


def test_task_participant_preview_caches_and_invalidates_image_rendering(
    qtbot,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "preview.png"
    Image.new("RGB", (24, 12), "red").save(image_path)
    preview = TaskParticipantPreview(tmp_path)
    qtbot.addWidget(preview)
    preview.resize(preview.sizeHint())
    preview.show()
    step = TaskStepDraft(
        step_id="image-choice",
        kind="choice_grid",
        title="Choose an image",
        columns=1,
        options=[
            TaskOptionDraft(
                option_id="image-option",
                label="Preview image",
                source_path=image_path,
            )
        ],
    )
    preview.set_step(step)
    QApplication.processEvents()

    source_key = preview._source_option_pixmaps[0].cacheKey()
    scaled_key = preview._scaled_option_pixmaps[0].cacheKey()
    preview.repaint()
    QApplication.processEvents()
    assert preview._source_option_pixmaps[0].cacheKey() == source_key
    assert preview._scaled_option_pixmaps[0].cacheKey() == scaled_key

    preview.resize(420, 440)
    QApplication.processEvents()
    assert preview._source_option_pixmaps[0].cacheKey() == source_key
    assert preview._scaled_option_pixmaps[0].cacheKey() != scaled_key

    Image.new("RGB", (36, 18), "green").save(image_path)
    preview.repaint()
    QApplication.processEvents()
    refreshed_source = preview._source_option_pixmaps[0]
    assert refreshed_source.cacheKey() != source_key
    assert refreshed_source.size().width() == 36
    assert refreshed_source.toImage().pixelColor(0, 0).name() == "#008000"
    scaled_image = preview._scaled_option_pixmaps[0].toImage()
    assert scaled_image.pixelColor(scaled_image.rect().center()).name() == "#008000"
    assert preview._step is not None
    assert preview._step.options[0].label == "Preview image"

    preview.set_step(None)
    assert preview._source_option_pixmaps == {}
    assert preview._scaled_option_pixmaps == {}


def test_conditions_step_opens_modifier_dialog_and_remains_eight_step_sized(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    document, window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Task Entry Point",
    )
    condition_id = document.create_condition(name="Condition Tasks")
    captures: list[str] = []

    def capture(dialog: ConditionModifierDialog) -> int:
        captures.append(dialog._condition_id)
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(ConditionModifierDialog, "exec", capture)
    window.resize(1120, 820)
    window.show_setup_wizard(step_key="conditions")
    step = window.setup_wizard_page.condition_setup_step
    step._select_condition(condition_id)
    QApplication.processEvents()

    assert step.task_button.isVisible()
    assert step.task_summary_label.text() == "No modifiers"
    qtbot.mouseClick(step.task_button, Qt.MouseButton.LeftButton)
    assert captures == [condition_id]
    assert len(window.setup_wizard_page.progress_step_labels) == 8
    _assert_widget_within_parent(step.task_button)
    _assert_widget_within_parent(step.task_summary_label)
