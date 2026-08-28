"""Registered Qt coverage for modular condition-task authoring."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QDialog,
    QFileDialog,
    QTableWidgetItem,
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
    TaskOption,
    TaskQuestion,
    TaskQuestionKind,
    TaskStep,
    TaskStepKind,
    TaskSubmissionMode,
)
from fpvs_studio.gui.condition_task_dialog import (
    ConditionTaskDialog,
    ConditionTaskFlowDraft,
    TaskOptionDraft,
    TaskParticipantPreview,
    TaskStepDraft,
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
        dialog.pre_editor.module_editor.step_list.setCurrentRow(row)
        QApplication.processEvents()
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
    dialog.resize(1000, 640)
    dialog.show()
    QApplication.processEvents()
    dialog.pre_editor.add_kind_combo.setCurrentIndex(
        dialog.pre_editor.add_kind_combo.findData("choice_grid")
    )
    qtbot.mouseClick(dialog.pre_editor.add_button, Qt.MouseButton.LeftButton)
    editor = dialog.pre_editor.module_editor.step_editor
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
    dialog.resize(1000, 640)
    dialog.show()
    QApplication.processEvents()

    dialog.pre_editor.add_kind_combo.setCurrentIndex(
        dialog.pre_editor.add_kind_combo.findData("choice_grid")
    )
    qtbot.mouseClick(dialog.pre_editor.add_button, Qt.MouseButton.LeftButton)
    module_editor = dialog.pre_editor.module_editor
    module_editor.module_id_edit.setText("creatine-recognition")
    module_editor.module_title_edit.setText("Creatine recognition")
    module_editor.module_repeat_count_spin.setValue(4)
    assert module_editor.replaces_start_gate_checkbox.isVisible()
    module_editor.replaces_start_gate_checkbox.setChecked(True)
    step_editor = module_editor.step_editor
    step_editor.step_id_edit.setText("recognition-choice")
    step_editor.prompt_edit.setPlainText("Select all 4")
    step_editor.layout_mode_combo.setCurrentIndex(step_editor.layout_mode_combo.findData("exact"))
    qtbot.mouseClick(step_editor.add_image_item_button, Qt.MouseButton.LeftButton)
    table = step_editor.option_table
    table.setItem(0, 6, QTableWidgetItem("-3"))
    table.setItem(0, 7, QTableWidgetItem("2"))
    table.setItem(0, 8, QTableWidgetItem("2.5"))
    table.setItem(0, 9, QTableWidgetItem("2"))
    module_editor.add_step_kind_combo.setCurrentIndex(
        module_editor.add_step_kind_combo.findData("timed_feedback")
    )
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
    condition_id = document.create_condition(name="Custom Questionnaire")
    dialog = ConditionTaskDialog(document, condition_id=condition_id, parent=window)
    qtbot.addWidget(dialog)
    dialog.resize(1000, 640)
    dialog.show()
    dialog.phase_tabs.setCurrentWidget(dialog.post_editor)
    QApplication.processEvents()

    dialog.post_editor.add_kind_combo.setCurrentIndex(
        dialog.post_editor.add_kind_combo.findData("questionnaire")
    )
    qtbot.mouseClick(dialog.post_editor.add_button, Qt.MouseButton.LeftButton)
    assert not dialog.post_editor.module_editor.replaces_start_gate_checkbox.isVisible()
    questionnaire = dialog.post_editor.module_editor.step_editor.questionnaire_editor
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
    editor_scroll = dialog.post_editor.findChild(
        QAbstractScrollArea,
        "condition_task_post_editor_scroll",
    )
    assert editor_scroll is not None
    assert (
        dialog.post_editor.module_editor.width()
        <= editor_scroll.viewport().width() + 1
    )
    _assert_visible_non_scroll_children_within_parent(dialog)


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


def test_conditions_step_opens_task_dialog_and_remains_six_step_sized(
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

    def capture(dialog: ConditionTaskDialog) -> int:
        captures.append(dialog._condition_id)
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(ConditionTaskDialog, "exec", capture)
    window.resize(1120, 720)
    window.show_setup_wizard(step_key="conditions")
    step = window.setup_wizard_page.condition_setup_step
    step._select_condition(condition_id)
    QApplication.processEvents()

    assert step.task_button.isVisible()
    assert step.task_summary_label.text() == "No pre/post tasks"
    qtbot.mouseClick(step.task_button, Qt.MouseButton.LeftButton)
    assert captures == [condition_id]
    assert len(window.setup_wizard_page.progress_step_labels) == 6
    _assert_widget_within_parent(step.task_button)
    _assert_widget_within_parent(step.task_summary_label)
