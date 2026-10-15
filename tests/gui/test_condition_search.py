"""Registered visible checks for condition search and safe editor selection."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from tests.gui.helpers import assert_visible_children_within_parent, write_image_directory
from tests.unit.test_masking import masking_project

from fpvs_studio.core.enums import ExperimentCategory, StimulusModality
from fpvs_studio.gui.condition_setup_step import ConditionSetupStep
from fpvs_studio.gui.document import ProjectDocument


@pytest.fixture
def search_step(qtbot, tmp_path):
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Condition search")
    condition_ids = [
        document.create_condition(name=name)
        for name in ("Faces neutral", "Animal words", "Tools familiar")
    ]
    for condition_id, code in zip(condition_ids, (12, 42, 92), strict=True):
        document.update_condition(condition_id, trigger_code=code)
    step = ConditionSetupStep(document)
    qtbot.addWidget(step)
    return document, step, condition_ids


def _visible_ids(step):
    return [
        step.condition_list.item(index).data(Qt.ItemDataRole.UserRole)
        for index in range(step.condition_list.count())
        if not step.condition_list.item(index).isHidden()
    ]


def test_search_matches_names_and_triggers_preserving_order_and_selection(search_step):
    document, step, condition_ids = search_step
    before = document.project.model_dump(mode="json")

    step.condition_search_edit.setText("  ANIMAL 42  ")

    assert _visible_ids(step) == condition_ids[:2]
    assert step.selected_condition_id() == condition_ids[0]
    assert step.condition_search_status.text() == "1 match. Selected condition kept visible."
    assert step.condition_name_edit.text() == "Faces neutral"
    assert step.condition_name_edit.isEnabled()
    step.condition_search_edit.setText("92")
    assert _visible_ids(step) == [condition_ids[0], condition_ids[2]]
    step.condition_search_edit.clear()
    assert _visible_ids(step) == condition_ids
    assert step.condition_search_status.isHidden()
    assert document.project.model_dump(mode="json") == before


def test_filtering_does_not_commit_or_replace_pending_text(search_step):
    document, step, condition_ids = search_step
    document.set_condition_stimulus_modality(condition_ids[0], modality=StimulusModality.WORD)
    step.condition_name_edit.setText("Pending name")
    step.instructions_edit.setPlainText("Pending instructions for faces")
    step.base_words_edit.setPlainText("cat\ndog")
    step.oddball_words_edit.setPlainText("hammer\nsaw")
    before = document.project.model_dump(mode="json")

    step.condition_search_edit.setText("no matching condition")

    assert step.selected_condition_id() == condition_ids[0]
    assert _visible_ids(step) == [condition_ids[0]]
    assert step.condition_search_status.text() == "No matches. Selected condition kept visible."
    assert step.condition_name_edit.text() == "Pending name"
    assert step.instructions_edit.toPlainText() == "Pending instructions for faces"
    assert step.base_words_edit.toPlainText() == "cat\ndog"
    assert step.oddball_words_edit.toPlainText() == "hammer\nsaw"
    assert step.has_pending_edits()
    assert document.project.model_dump(mode="json") == before
    step.condition_search_edit.clear()
    assert document.project.model_dump(mode="json") == before
    step.flush_pending_edits()


def test_keyboard_selection_commits_drafts_to_the_previous_condition(qtbot, search_step):
    document, step, condition_ids = search_step
    document.set_condition_stimulus_modality(condition_ids[0], modality=StimulusModality.WORD)
    step.resize(1000, 600)
    step.show()
    QApplication.processEvents()
    step.condition_search_edit.setFocus()
    step.instructions_edit.setPlainText("Faces instructions")
    step.base_words_edit.setPlainText("cat\ndog")
    step.oddball_words_edit.setPlainText("hammer\nsaw")
    step.condition_search_edit.setText("TOOLS")

    qtbot.keyClick(step.condition_search_edit, Qt.Key.Key_Tab)
    assert step.condition_list.hasFocus()
    qtbot.keyClick(step.condition_list, Qt.Key.Key_Down)

    assert step.selected_condition_id() == condition_ids[2]
    assert _visible_ids(step) == [condition_ids[2]]
    assert step.condition_name_edit.text() == "Tools familiar"
    assert step.condition_search_status.text() == "1 match."
    assert document.get_condition(condition_ids[0]).instructions == "Faces instructions"
    assert document.get_condition_stimulus_set(condition_ids[0], "base").words == ["cat", "dog"]
    assert document.get_condition_stimulus_set(condition_ids[0], "oddball").words == [
        "hammer", "saw",
    ]
    assert document.get_condition(condition_ids[2]).instructions != "Faces instructions"


def test_search_refresh_and_rename_keep_selected_identity(search_step):
    document, step, condition_ids = search_step
    step._select_condition(condition_ids[1])
    step.condition_search_edit.setText("animal")
    step.condition_name_edit.setText("Vehicles unfamiliar")
    step.condition_name_edit.editingFinished.emit()
    document.manifest_changed.emit()

    assert step.selected_condition_id() == condition_ids[1]
    assert _visible_ids(step) == [condition_ids[1]]
    assert step.condition_search_status.text() == "No matches. Selected condition kept visible."
    assert step.condition_name_edit.text() == "Vehicles unfamiliar"
    assert "Vehicles unfamiliar" in step.condition_list.currentItem().toolTip()
    step.trigger_code_spin.setValue(123)
    step.condition_search_edit.setText("123")
    assert step.condition_search_status.text() == "1 match."
    assert "Trigger 123" in step.condition_list.currentItem().toolTip()


def test_add_duplicate_and_remove_remain_visible_under_search(search_step):
    document, step, condition_ids = search_step
    step.condition_search_edit.setText("animal")
    step._add_condition()
    added_id = step.selected_condition_id()
    assert added_id not in condition_ids
    assert _visible_ids(step) == [condition_ids[1], added_id]
    step.condition_name_edit.setText("New experiment condition")
    step.condition_name_edit.editingFinished.emit()
    step._duplicate_condition()
    duplicated_id = step.selected_condition_id()
    assert duplicated_id not in [*condition_ids, added_id]
    assert _visible_ids(step) == [condition_ids[1], duplicated_id]

    step._remove_condition()

    assert document.get_condition(duplicated_id) is None
    assert step.selected_condition_id() == condition_ids[1]
    assert _visible_ids(step) == [condition_ids[1]]
    assert step.condition_name_edit.text() == "Animal words"


def test_empty_search_result_does_not_enable_condition_actions(qtbot, tmp_path):
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Empty search")
    step = ConditionSetupStep(document)
    qtbot.addWidget(step)
    step.condition_search_edit.setText("missing")

    assert step.selected_condition_id() is None
    assert step.condition_search_status.text() == "No matches."
    assert not step.condition_name_edit.isEnabled()
    assert not step.duplicate_condition_button.isEnabled()
    assert not step.remove_condition_button.isEnabled()
    assert step.add_condition_button.isEnabled()
    step._add_condition()
    assert step.selected_condition_id() is not None
    assert not step.condition_list.currentItem().isHidden()
    assert step.condition_name_edit.isEnabled()
    step._remove_condition()
    assert step.selected_condition_id() is None
    assert step.condition_list.count() == 0
    assert step.condition_search_status.text() == "No matches."
    assert not step.condition_name_edit.isEnabled()


@pytest.mark.parametrize("mode", ["image", "word", "native-ab", "masking"])
def test_search_long_content_and_feedback_fit_full_wizard(
    qtbot, controller, tmp_path, monkeypatch, mode,
):
    category = (
        ExperimentCategory.ATTENTIONAL_BLINK if mode == "native-ab"
        else ExperimentCategory.FPVS_ODDBALL
    )
    document = controller.create_project("Search layout", tmp_path, experiment_category=category)
    window = controller.main_window
    qtbot.addWidget(window)
    guide = window.setup_wizard_page
    monkeypatch.setattr(guide, "_ensure_condition_image_prescan_started", lambda: None)
    if mode == "masking":
        project = masking_project(("color", "faces", "number"))
        project.meta = document.project.meta.model_copy(deep=True)
        document.apply_condition_modifier_project(project)
    elif mode != "native-ab":
        for index in range(6):
            condition_id = document.create_condition(name=f"Semantic category {index + 1}")
            if mode == "word":
                document.set_condition_stimulus_modality(
                    condition_id, modality=StimulusModality.WORD,
                )
                document.update_condition_words(condition_id, role="base", words=["cat", "dog"])
                document.update_condition_words(condition_id, role="oddball", words=["tool"])
            else:
                source_dir = write_image_directory(tmp_path / f"images-{index}", count=1)
                for role in ("base", "oddball"):
                    document.import_condition_stimulus_folder(
                        condition_id, role=role, source_dir=source_dir,
                    )
    condition_id = document.ordered_conditions()[0].condition_id
    long_name = "Familiar animal words and unfamiliar semantic exemplars with delayed responses"
    document.update_condition(condition_id, name=long_name, trigger_code=255)
    step = guide.condition_setup_step
    window.show_setup_wizard(step_key="conditions")
    window.resize(1120, 820)
    window.show()
    step._select_condition(condition_id)

    for query in ("", "255", "No matching conditions in this experiment"):
        step.condition_search_edit.setText(query)
        QApplication.processEvents()
        assert (window.width(), window.height()) == (1120, 820)
        assert step.selected_condition_id() == condition_id
        assert not step.condition_list.currentItem().isHidden()
        assert long_name in step.condition_list.currentItem().toolTip()
        assert long_name in step.condition_list.currentItem().data(
            Qt.ItemDataRole.AccessibleTextRole,
        )
        assert step.condition_search_edit.isClearButtonEnabled()
        assert step.condition_search_edit.accessibleName() == (
            "Search conditions by name or trigger"
        )
        assert step.condition_search_edit.width() >= (
            step.condition_search_edit.fontMetrics().horizontalAdvance(
                step.condition_search_edit.placeholderText(),
            ) + 32
        )
        assert_visible_children_within_parent(step)
        if query:
            status = step.condition_search_status
            assert status.isVisible()
            assert status.height() >= status.heightForWidth(status.width())
        assert not guide.shell.page_container.scroll_area.verticalScrollBar().isEnabled()
