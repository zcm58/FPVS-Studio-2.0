"""Focused GUI workflow tests split from the former layout dashboard suite."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QPushButton,
    QWidget,
)
from tests.gui.helpers import (
    _assert_visible_children_within_parent,
    _ImmediateProgressTask,
    _open_created_project,
    _write_image_directory,
    _write_mixed_image_directory,
)

from fpvs_studio.core.enums import DutyCycleMode, StimulusModality, StimulusVariant
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.design_system import PAGE_SECTION_GAP


def test_setup_wizard_conditions_step_duplicates_metadata_without_images(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Condition Duplicate")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")

    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    step.condition_name_edit.setText("Faces")
    step.condition_name_edit.editingFinished.emit()
    step.trigger_code_spin.setValue(42)
    step.instructions_edit.setPlainText("Look at each image.")

    qtbot.mouseClick(step.duplicate_condition_button, Qt.MouseButton.LeftButton)

    duplicated_id = step.selected_condition_id()
    assert isinstance(duplicated_id, str)
    assert duplicated_id != condition_id
    duplicated = window.document.get_condition(duplicated_id)
    assert duplicated is not None
    assert duplicated.name == "Faces Copy"
    assert duplicated.trigger_code == 2
    assert duplicated.instructions == "Look at each image."
    base_set = window.document.get_condition_stimulus_set(duplicated_id, "base")
    oddball_set = window.document.get_condition_stimulus_set(duplicated_id, "oddball")
    assert base_set.image_count == 0
    assert oddball_set.image_count == 0
    assert "Needs images" in step.condition_list.currentItem().toolTip()
    assert "Continuous Images" in step.condition_list.currentItem().text()


def test_setup_wizard_conditions_step_authors_word_condition(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Word Condition")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    window.show_setup_wizard(step_key="conditions")
    next_button = guide.findChild(QPushButton, "setup_wizard_next_button")
    assert next_button is not None

    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    step.condition_name_edit.setText("Animal Words")
    step.condition_name_edit.editingFinished.emit()
    step.trigger_code_spin.setValue(10)
    step.modality_combo.setCurrentIndex(step.modality_combo.findData(StimulusModality.WORD.value))
    QApplication.processEvents()

    base_set = window.document.get_condition_stimulus_set(condition_id, "base")
    oddball_set = window.document.get_condition_stimulus_set(condition_id, "oddball")
    assert base_set.modality == StimulusModality.WORD
    assert oddball_set.modality == StimulusModality.WORD
    assert step.words_panel.isVisible()
    assert not step.sources_row.isVisible()
    assert step.base_check_status.text() == "Base Words Not Configured"
    assert not next_button.isEnabled()

    step.base_words_edit.setPlainText("cat\n dog\ncat\n")
    step.oddball_words_edit.setPlainText("tool\nchair")
    step.flush_pending_edits()
    QApplication.processEvents()

    base_set = window.document.get_condition_stimulus_set(condition_id, "base")
    oddball_set = window.document.get_condition_stimulus_set(condition_id, "oddball")
    assert base_set.words == ["cat", "dog", "cat"]
    assert oddball_set.words == ["tool", "chair"]
    assert step.base_words_count.text() == "3 words"
    assert step.oddball_words_count.text() == "2 words"
    assert step.base_check_status.text() == "Complete"
    assert step.oddball_check_status.text() == "Complete"
    assert next_button.isEnabled()


def test_setup_wizard_conditions_next_scans_images_without_blocking_gui(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Async Image Check")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")
    progress_tasks: list[object] = []
    background_tasks: list[_DeferredBackgroundTask] = []

    class _UnexpectedProgressTask(QObject):
        def __init__(self, **_kwargs: object) -> None:
            super().__init__()
            progress_tasks.append(self)
            raise AssertionError("Next should wait for the active background image check.")

    class _DeferredBackgroundTask(QObject):
        succeeded = Signal(object)
        failed = Signal(object)
        finished = Signal()

        def __init__(
            self,
            *,
            parent_widget: QWidget,
            callback: Callable[[], object],
        ) -> None:
            super().__init__(parent_widget)
            self.started = False
            self._callback = callback
            background_tasks.append(self)

        def start(self) -> None:
            self.started = True

        def finish_success(self) -> None:
            try:
                result = self._callback()
            except Exception as error:
                self.failed.emit(error)
            else:
                self.succeeded.emit(result)
            finally:
                self.finished.emit()

    original_scan = guide._document.scan_condition_image_normalization
    scan_calls = 0

    def _scan_after_worker_start() -> object:
        nonlocal scan_calls
        scan_calls += 1
        return original_scan()

    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.BackgroundTask",
        _DeferredBackgroundTask,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.ProgressTask",
        _UnexpectedProgressTask,
    )
    monkeypatch.setattr(
        guide._document,
        "scan_condition_image_normalization",
        _scan_after_worker_start,
    )
    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    guide._document.update_condition(condition_id, name="Faces", trigger_code=1)
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="base",
        source_dir=_write_image_directory(tmp_path / "async-base"),
    )
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=_write_image_directory(tmp_path / "async-oddball"),
    )
    QApplication.processEvents()

    assert len(background_tasks) == 1
    assert background_tasks[0].started is True
    assert scan_calls == 0
    assert guide.step_stack.currentWidget() is guide.conditions_step_surface
    assert guide.setup_wizard_next_button.isEnabled()

    qtbot.mouseClick(guide.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert progress_tasks == []
    assert scan_calls == 0
    assert guide.step_stack.currentWidget() is guide.conditions_step_surface
    assert not guide.setup_wizard_next_button.isEnabled()
    assert guide.setup_wizard_next_hint_label.text() == "Checking image readiness..."

    background_tasks[0].finish_success()
    QApplication.processEvents()

    assert scan_calls == 1
    assert guide.step_stack.currentWidget() is guide.experiment_step_surface


def test_setup_wizard_conditions_next_uses_cached_background_image_check(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Cached Image Check")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")
    background_calls = 0
    scan_calls = 0

    class _ImmediateBackgroundTask(QObject):
        succeeded = Signal(object)
        failed = Signal(object)
        finished = Signal()

        def __init__(
            self,
            *,
            parent_widget: QWidget,
            callback: Callable[[], object],
        ) -> None:
            super().__init__(parent_widget)
            self._callback = callback

        def start(self) -> None:
            nonlocal background_calls
            background_calls += 1
            try:
                result = self._callback()
            except Exception as error:
                self.failed.emit(error)
            else:
                self.succeeded.emit(result)
            finally:
                self.finished.emit()

    class _UnexpectedProgressTask(QObject):
        def __init__(self, **_kwargs: object) -> None:
            super().__init__()
            raise AssertionError("Cached image check should not show progress.")

    original_scan = guide._document.scan_condition_image_normalization

    def _count_scan() -> object:
        nonlocal scan_calls
        scan_calls += 1
        return original_scan()

    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.BackgroundTask",
        _ImmediateBackgroundTask,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.ProgressTask",
        _UnexpectedProgressTask,
    )
    monkeypatch.setattr(guide._document, "scan_condition_image_normalization", _count_scan)

    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    guide._document.update_condition(condition_id, name="Faces", trigger_code=1)
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="base",
        source_dir=_write_image_directory(tmp_path / "cached-base"),
    )
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=_write_image_directory(tmp_path / "cached-oddball"),
    )
    QApplication.processEvents()

    assert background_calls == 1
    assert scan_calls == 1

    qtbot.mouseClick(guide.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert scan_calls == 1
    assert guide.step_stack.currentWidget() is guide.experiment_step_surface


def test_setup_wizard_word_editor_keeps_blank_line_after_debounce(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Word Editor Debounce")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")

    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    step.modality_combo.setCurrentIndex(step.modality_combo.findData(StimulusModality.WORD.value))
    QApplication.processEvents()

    step.base_words_edit.setFocus()
    qtbot.keyClicks(step.base_words_edit, "cat")
    cursor = step.base_words_edit.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    step.base_words_edit.setTextCursor(cursor)
    qtbot.keyClick(step.base_words_edit, Qt.Key.Key_Return)
    qtbot.wait(350)
    QApplication.processEvents()

    assert window.document.get_condition_stimulus_set(condition_id, "base").words == ["cat"]
    assert step.base_words_edit.toPlainText() == "cat\n"
    assert step.base_words_edit.textCursor().blockNumber() == 1


def test_setup_wizard_blocks_populated_modality_switch(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Word Switch Block")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")
    errors: list[str] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step._show_error_dialog",
        lambda _parent, _title, error: errors.append(str(error)),
    )

    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    step.modality_combo.setCurrentIndex(step.modality_combo.findData(StimulusModality.WORD.value))
    step.base_words_edit.setPlainText("cat")
    step.flush_pending_edits()

    step.modality_combo.setCurrentIndex(step.modality_combo.findData(StimulusModality.IMAGE.value))
    QApplication.processEvents()

    assert errors == [
        "Condition stimulus type can only be changed before images or words are added."
    ]
    assert (
        window.document.get_condition_stimulus_set(condition_id, "base").modality
        == StimulusModality.WORD
    )


def test_setup_wizard_conditions_step_requires_descriptive_name_and_positive_trigger(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Condition Gate")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")
    next_button = guide.findChild(QPushButton, "setup_wizard_next_button")
    assert next_button is not None

    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    assert "Needs name" in step.condition_list.currentItem().toolTip()
    assert "Continuous Images" in step.condition_list.currentItem().text()
    assert not guide.step_status_label.isVisible()
    assert not step.base_source_card.status_badge.isVisible()
    assert not step.oddball_source_card.status_badge.isVisible()
    assert step.name_check_status.text() == "Enter a descriptive name"
    assert step.base_check_status.text() == "Base Images Not Selected"
    assert step.oddball_check_status.text() == "Oddball Images Not Selected"
    assert not next_button.isEnabled()

    for invalid_name in ("A", "AB", "Condition 3"):
        guide._document.update_condition(condition_id, name=invalid_name)
        QApplication.processEvents()
        assert step.name_check_status.text() == "Enter a descriptive name"
        assert not next_button.isEnabled()

    guide._document.update_condition(condition_id, name="Dog")
    QApplication.processEvents()
    assert step.name_check_status.text() == "Complete"

    assert step.trigger_code_spin.minimum() == 1
    step.trigger_code_spin.setValue(0)
    QApplication.processEvents()
    assert step.trigger_code_spin.value() == 1
    assert step.trigger_check_status.text() == "Complete"

    guide._document.update_condition(condition_id, trigger_code=1)
    QApplication.processEvents()
    assert step.trigger_check_status.text() == "Complete"
    assert step.base_check_status.text() == "Base Images Not Selected"
    assert step.oddball_check_status.text() == "Oddball Images Not Selected"
    assert not next_button.isEnabled()

    base_dir = _write_image_directory(tmp_path / "gated-condition-base")
    oddball_dir = _write_image_directory(tmp_path / "gated-condition-oddball")
    guide._document.import_condition_stimulus_folder(condition_id, role="base", source_dir=base_dir)
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=oddball_dir,
    )
    QApplication.processEvents()
    assert step.base_check_status.text() == "Complete"
    assert step.oddball_check_status.text() == "Complete"
    assert next_button.isEnabled()


def test_setup_wizard_condition_timing_template_updates_selected_condition_only(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Mixed Timing")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")

    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    first_condition_id = step.selected_condition_id()
    assert isinstance(first_condition_id, str)
    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    second_condition_id = step.selected_condition_id()
    assert isinstance(second_condition_id, str)

    blank_index = step.timing_template_combo.findData(DutyCycleMode.BLANK_50)
    assert blank_index >= 0
    step.timing_template_combo.setCurrentIndex(blank_index)
    QApplication.processEvents()

    first_condition = window.document.get_condition(first_condition_id)
    second_condition = window.document.get_condition(second_condition_id)
    assert first_condition is not None
    assert second_condition is not None
    assert first_condition.duty_cycle_mode == DutyCycleMode.CONTINUOUS
    assert second_condition.duty_cycle_mode == DutyCycleMode.BLANK_50
    assert "50% Blank Between Images" in step.condition_list.currentItem().text()


def test_setup_wizard_conditions_step_shows_repeat_target_and_balance(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Wizard Repeat Balance")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")

    condition_id = guide._document.create_condition()
    guide._document.update_condition(condition_id, name="Faces", trigger_code=1)
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="base",
        source_dir=_write_image_directory(tmp_path / "repeat-base", count=15),
    )
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=_write_image_directory(tmp_path / "repeat-oddball", count=18),
    )
    step._select_condition(condition_id)
    QApplication.processEvents()

    assert step.target_repeats_spin.value() == 7
    assert not step.base_source_card.folder_value.isVisible()
    assert not step.oddball_source_card.folder_value.isVisible()
    assert step.base_source_card.repeat_summary_label.text() == ""
    assert not step.base_source_card.repeat_summary_label.isVisible()
    assert step.oddball_source_card.repeat_summary_label.text() == ""
    assert not step.oddball_source_card.repeat_summary_label.isVisible()
    _assert_visible_children_within_parent(step.base_source_card)
    _assert_visible_children_within_parent(step.oddball_source_card)

    calculator_snapshots: list[dict[str, str]] = []

    def capture_calculator(dialog: QDialog) -> QDialog.DialogCode:
        calculator_snapshots.append(
            {
                name: dialog.findChild(QLabel, name).text()
                for name in (
                    "repeat_calculator_condition_length_value",
                    "repeat_calculator_summary_label",
                    "repeat_calculator_base_presentations_value",
                    "repeat_calculator_oddball_presentations_value",
                    "repeat_calculator_target_value",
                    "repeat_calculator_required_base_value",
                    "repeat_calculator_required_oddball_value",
                    "repeat_calculator_current_base_value",
                    "repeat_calculator_current_oddball_value",
                )
            }
        )
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step.RepeatCalculatorDialog.exec",
        capture_calculator,
    )

    qtbot.mouseClick(step.repeat_calculator_button, Qt.MouseButton.LeftButton)

    assert calculator_snapshots[-1] == {
        "repeat_calculator_condition_length_value": "146 oddball cycles, 730 stimuli",
        "repeat_calculator_summary_label": (
            "Your Faces condition is 146 oddball cycles long. This means you will display "
            "584 base images and 146 oddball images. If you want each image to repeat "
            "7 times, then you will need at least 84 base images and 21 oddball images "
            "in each folder."
        ),
        "repeat_calculator_base_presentations_value": "584",
        "repeat_calculator_oddball_presentations_value": "146",
        "repeat_calculator_target_value": "7x",
        "repeat_calculator_required_base_value": "84 images",
        "repeat_calculator_required_oddball_value": "21 images",
        "repeat_calculator_current_base_value": "15 images, about 38-39x each",
        "repeat_calculator_current_oddball_value": "18 images, about 8-9x each",
    }

    step.target_repeats_spin.setValue(10)
    QApplication.processEvents()

    assert guide._document.project.settings.condition_defaults.target_repeats_per_image == 10
    assert step.base_source_card.repeat_summary_label.text() == ""
    assert step.oddball_source_card.repeat_summary_label.text() == ""

    qtbot.mouseClick(step.repeat_calculator_button, Qt.MouseButton.LeftButton)

    assert calculator_snapshots[-1]["repeat_calculator_target_value"] == "10x"
    assert calculator_snapshots[-1]["repeat_calculator_required_base_value"] == "59 images"
    assert calculator_snapshots[-1]["repeat_calculator_required_oddball_value"] == "15 images"
    assert (
        "If you want each image to repeat 10 times, then you will need at least "
        "59 base images and 15 oddball images in each folder."
    ) in calculator_snapshots[-1]["repeat_calculator_summary_label"]


def test_setup_wizard_conditions_step_keeps_source_geometry_for_incomplete_condition(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Condition Geometry")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    window.resize(1120, 720)
    window.show_setup_wizard(step_key="conditions")

    condition_ids = []
    for index, name in enumerate(("Faces", "Objects"), start=1):
        condition_id = guide._document.create_condition()
        condition_ids.append(condition_id)
        guide._document.update_condition(condition_id, name=name, trigger_code=index)
        guide._document.import_condition_stimulus_folder(
            condition_id,
            role="base",
            source_dir=_write_image_directory(tmp_path / f"{name}-base"),
        )
        guide._document.import_condition_stimulus_folder(
            condition_id,
            role="oddball",
            source_dir=_write_image_directory(tmp_path / f"{name}-oddball"),
        )

    step._select_condition(condition_ids[0])
    QApplication.processEvents()
    workspace = step.findChild(QWidget, "setup_conditions_workspace")
    assert workspace is not None
    assert workspace.property("setupWorkspaceFrame") is None
    before_geometry = {
        "workspace": workspace.size(),
        "details_section": step.condition_details_section.size(),
        "base_card": step.base_source_card.size(),
        "oddball_card": step.oddball_source_card.size(),
        "base_folder": step.base_source_value.size(),
        "oddball_folder": step.oddball_source_value.size(),
        "base_metrics": step.base_source_card.metrics.size(),
        "oddball_metrics": step.oddball_source_card.metrics.size(),
        "instructions": step.instructions_edit.size(),
    }

    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert workspace.size() == before_geometry["workspace"]
    assert step.condition_details_section.size() == before_geometry["details_section"]
    assert step.base_source_card.size() == before_geometry["base_card"]
    assert step.oddball_source_card.size() == before_geometry["oddball_card"]
    assert step.base_source_value.size() == before_geometry["base_folder"]
    assert step.oddball_source_value.size() == before_geometry["oddball_folder"]
    assert step.base_source_card.metrics.size() == before_geometry["base_metrics"]
    assert step.oddball_source_card.metrics.size() == before_geometry["oddball_metrics"]
    assert step.instructions_edit.size() == before_geometry["instructions"]
    assert step.instructions_edit.height() == 80
    assert step.repeat_calculator_button.text() == "i"
    assert step.repeat_calculator_button.size().width() == 30
    assert step.repeat_calculator_button.size().height() == 30
    assert step.repeat_calculator_button.accessibleName() == "Target repeat information"
    assert step.repeat_calculator_button.toolTip() == "Show target repeat calculations"
    standard_field_width = step.timing_template_combo.width()
    for field in (
        step.condition_name_edit,
        step.trigger_code_spin,
        step.modality_combo,
        step.target_repeats_spin,
        step.instructions_edit,
    ):
        assert field.width() == standard_field_width
    timing_option_widths = (
        step.timing_template_combo.fontMetrics().horizontalAdvance(
            step.timing_template_combo.itemText(index)
        )
        for index in range(step.timing_template_combo.count())
    )
    assert standard_field_width >= max(timing_option_widths)
    assert step.base_source_card.metrics.height() == 56
    assert step.oddball_source_card.metrics.height() == 56
    _assert_visible_children_within_parent(step.condition_details_section)
    sources_row = step.findChild(QWidget, "setup_conditions_sources_row")
    assert sources_row is not None
    main_panel = step.findChild(QWidget, "setup_conditions_main_panel")
    assert main_panel is not None
    details_left = step.condition_details_section.mapTo(
        main_panel,
        step.condition_details_section.rect().topLeft(),
    ).x()
    details_right = step.condition_details_section.mapTo(
        main_panel,
        step.condition_details_section.rect().topRight(),
    ).x()
    base_left = step.base_source_card.mapTo(
        main_panel,
        step.base_source_card.rect().topLeft(),
    ).x()
    base_right = step.base_source_card.mapTo(
        main_panel,
        step.base_source_card.rect().topRight(),
    ).x()
    oddball_left = step.oddball_source_card.mapTo(
        main_panel,
        step.oddball_source_card.rect().topLeft(),
    ).x()
    oddball_right = step.oddball_source_card.mapTo(
        main_panel,
        step.oddball_source_card.rect().topRight(),
    ).x()
    assert base_left == details_left
    assert oddball_right == details_right
    assert oddball_left - base_right >= PAGE_SECTION_GAP
    assert step.base_source_card.width() > 210
    assert step.oddball_source_card.width() > 210
    assert step.base_source_card.title_label.alignment() & Qt.AlignmentFlag.AlignHCenter
    assert step.oddball_source_card.title_label.alignment() & Qt.AlignmentFlag.AlignHCenter
    for source_card in (step.base_source_card, step.oddball_source_card):
        header = source_card.title_label.parentWidget()
        assert header is not None
        assert header.height() == 24
        title_top = source_card.title_label.mapTo(
            source_card,
            source_card.title_label.rect().topLeft(),
        ).y()
        assert title_top <= 16
        for _label, value in source_card.metrics._rows:
            assert value.width() >= value.fontMetrics().horizontalAdvance(value.text())
    assert step.base_source_value.alignment() & Qt.AlignmentFlag.AlignHCenter
    assert step.oddball_source_value.alignment() & Qt.AlignmentFlag.AlignHCenter
    assert step.base_source_card.metrics._rows[0][1].alignment() & Qt.AlignmentFlag.AlignHCenter
    assert (
        step.oddball_source_card.metrics._rows[0][1].alignment()
        & Qt.AlignmentFlag.AlignHCenter
    )
    target_label_top = step.target_repeats_label.mapTo(
        step.condition_details_section,
        step.target_repeats_label.rect().topLeft(),
    ).y()
    target_controls_top = step.target_repeats_spin.mapTo(
        step.condition_details_section,
        step.target_repeats_spin.rect().topLeft(),
    ).y()
    instructions_label_top = step.instructions_label.mapTo(
        step.condition_details_section,
        step.instructions_label.rect().topLeft(),
    ).y()
    instructions_editor_top = step.instructions_edit.mapTo(
        step.condition_details_section,
        step.instructions_edit.rect().topLeft(),
    ).y()
    assert abs(target_label_top - target_controls_top) <= 1
    assert abs(instructions_label_top - instructions_editor_top) <= 1
    assert instructions_editor_top > target_controls_top
    info_bottom_right = step.repeat_calculator_button.mapTo(
        step.condition_details_section,
        step.repeat_calculator_button.rect().bottomRight(),
    )
    assert step.condition_details_section.width() - info_bottom_right.x() <= 12
    assert step.condition_details_section.height() - info_bottom_right.y() <= 7
    _assert_visible_children_within_parent(workspace)

    base_bottom = step.base_source_card.mapTo(
        workspace,
        step.base_source_card.rect().bottomLeft(),
    ).y()
    oddball_bottom = step.oddball_source_card.mapTo(
        workspace,
        step.oddball_source_card.rect().bottomLeft(),
    ).y()
    control_bottom = step.create_control_condition_button.mapTo(
        workspace,
        step.create_control_condition_button.rect().bottomLeft(),
    ).y()
    remove_bottom = step.remove_condition_button.mapTo(
        workspace,
        step.remove_condition_button.rect().bottomLeft(),
    ).y()
    assert base_bottom == oddball_bottom == control_bottom == remove_bottom, (
        base_bottom,
        oddball_bottom,
        control_bottom,
        remove_bottom,
    )


def test_setup_wizard_conditions_next_silently_advances_when_images_are_uniform(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Uniform Image Gate")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")
    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    guide._document.update_condition(condition_id, name="Faces", trigger_code=1)
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="base",
        source_dir=_write_image_directory(tmp_path / "uniform-base"),
    )
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=_write_image_directory(tmp_path / "uniform-oddball"),
    )
    QApplication.processEvents()

    def _unexpected_dialog(*_args, **_kwargs):
        raise AssertionError("Normalization dialog should not be shown for uniform images.")

    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.ImageNormalizationDialog",
        _unexpected_dialog,
    )
    monkeypatch.setattr("fpvs_studio.gui.setup_wizard_page.ProgressTask", _ImmediateProgressTask)

    guide.open_wizard(step_key="images")
    assert guide.step_stack.currentWidget() is guide.conditions_step_surface
    qtbot.mouseClick(guide.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert guide.step_stack.currentWidget() is guide.experiment_step_surface


def test_setup_wizard_conditions_next_normalizes_mixed_images_before_advancing(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Mixed Image Gate")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")
    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    guide._document.update_condition(condition_id, name="Faces", trigger_code=1)
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="base",
        source_dir=_write_mixed_image_directory(tmp_path / "mixed-base"),
    )
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=_write_image_directory(tmp_path / "mixed-oddball"),
    )
    QApplication.processEvents()

    class _AcceptDialog:
        def __init__(self, scan, *, parent=None) -> None:
            self.scan = scan

        def exec(self):
            return QDialog.DialogCode.Accepted

        def target_size(self) -> int:
            return 512

    monkeypatch.setattr("fpvs_studio.gui.setup_wizard_page.ProgressTask", _ImmediateProgressTask)
    monkeypatch.setattr("fpvs_studio.gui.setup_wizard_page.ImageNormalizationDialog", _AcceptDialog)

    guide.open_wizard(step_key="images")
    assert guide.step_stack.currentWidget() is guide.conditions_step_surface
    qtbot.mouseClick(guide.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert guide.step_stack.currentWidget() is guide.experiment_step_surface
    base_set = window.document.get_condition_stimulus_set(condition_id, "base")
    oddball_set = window.document.get_condition_stimulus_set(condition_id, "oddball")
    assert base_set.source_dir == "stimuli/normalized-images/condition-1-base"
    assert oddball_set.source_dir == "stimuli/normalized-images/condition-1-oddball"
    assert base_set.resolution is not None
    assert base_set.resolution.as_tuple() == (512, 512)
    assert all(
        path.suffix == ".png"
        for path in (window.document.project_root / Path(base_set.source_dir)).iterdir()
    )


def test_setup_wizard_conditions_next_normalizes_uniform_non_square_images(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Non Square Image Gate")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")
    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    base_dir = tmp_path / "non-square-base"
    oddball_dir = tmp_path / "non-square-oddball"
    base_dir.mkdir()
    oddball_dir.mkdir()
    Image.new("RGB", (128, 96), color=(20, 40, 60)).save(base_dir / "base-01.png")
    Image.new("RGB", (128, 96), color=(60, 40, 20)).save(base_dir / "base-02.png")
    Image.new("RGB", (128, 96), color=(80, 20, 40)).save(oddball_dir / "oddball-01.png")
    Image.new("RGB", (128, 96), color=(40, 80, 20)).save(oddball_dir / "oddball-02.png")
    guide._document.update_condition(condition_id, name="Faces", trigger_code=1)
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="base",
        source_dir=base_dir,
    )
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=oddball_dir,
    )
    QApplication.processEvents()

    dialog_scans = []

    class _AcceptDialog:
        def __init__(self, scan, *, parent=None) -> None:
            dialog_scans.append(scan)

        def exec(self):
            return QDialog.DialogCode.Accepted

        def target_size(self) -> int:
            return 512

    monkeypatch.setattr("fpvs_studio.gui.setup_wizard_page.ProgressTask", _ImmediateProgressTask)
    monkeypatch.setattr("fpvs_studio.gui.setup_wizard_page.ImageNormalizationDialog", _AcceptDialog)

    qtbot.mouseClick(guide.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert dialog_scans[-1].non_square_resolution is True
    assert guide.step_stack.currentWidget() is guide.experiment_step_surface
    base_set = window.document.get_condition_stimulus_set(condition_id, "base")
    assert base_set.resolution is not None
    assert base_set.resolution.as_tuple() == (512, 512)


def test_setup_wizard_conditions_next_stays_put_when_normalization_is_cancelled(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Cancel Image Gate")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")
    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    guide._document.update_condition(condition_id, name="Faces", trigger_code=1)
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="base",
        source_dir=_write_mixed_image_directory(tmp_path / "cancel-base"),
    )
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=_write_image_directory(tmp_path / "cancel-oddball"),
    )
    QApplication.processEvents()

    class _RejectDialog:
        def __init__(self, scan, *, parent=None) -> None:
            self.scan = scan

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("fpvs_studio.gui.setup_wizard_page.ProgressTask", _ImmediateProgressTask)
    monkeypatch.setattr("fpvs_studio.gui.setup_wizard_page.ImageNormalizationDialog", _RejectDialog)

    before_source_dir = window.document.get_condition_stimulus_set(
        condition_id,
        "base",
    ).source_dir
    guide.open_wizard(step_key="images")
    assert guide.step_stack.currentWidget() is guide.conditions_step_surface
    qtbot.mouseClick(guide.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert guide.step_stack.currentWidget() is guide.conditions_step_surface
    assert (
        window.document.get_condition_stimulus_set(condition_id, "base").source_dir
        == before_source_dir
    )


def test_setup_wizard_condition_image_picker_starts_in_project_stimuli_folder(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Wizard Image Picker")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")
    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    guide.open_wizard(step_key="images")
    assert guide.step_stack.currentWidget() is guide.conditions_step_surface

    calls: list[tuple[str, str]] = []

    def _capture_directory(_parent, title: str, directory: str) -> str:
        calls.append((title, directory))
        return ""

    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step.QFileDialog.getExistingDirectory",
        _capture_directory,
    )

    qtbot.mouseClick(step.base_import_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(step.oddball_import_button, Qt.MouseButton.LeftButton)

    expected_start = str(window.document.project_root / "stimuli")
    assert calls == [
        ("Choose Base Stimulus Folder", expected_start),
        ("Choose Oddball Stimulus Folder", expected_start),
    ]


def test_setup_wizard_control_condition_button_requires_assigned_images(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Control Condition Enable")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")

    assert not step.create_control_condition_button.isEnabled()

    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert condition_id is not None
    assert not step.create_control_condition_button.isEnabled()

    base_dir = _write_image_directory(tmp_path / "control-enable-base")
    oddball_dir = _write_image_directory(tmp_path / "control-enable-oddball")
    window.document.import_condition_stimulus_folder(condition_id, role="base", source_dir=base_dir)
    window.document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=oddball_dir,
    )
    qtbot.waitUntil(step.create_control_condition_button.isEnabled)


@pytest.mark.parametrize(
    ("variant", "name"),
    [
        (StimulusVariant.GRAYSCALE, "Faces Grayscale Control"),
        (StimulusVariant.ROT180, "Faces 180 Degree Rotated Control"),
        (StimulusVariant.PHASE_SCRAMBLED, "Faces Phase-Scrambled Control"),
    ],
)
def test_setup_wizard_creates_control_condition_from_existing_stimuli(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
    variant: StimulusVariant,
    name: str,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, f"{variant.value} Control")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")
    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert condition_id is not None
    window.document.update_condition(condition_id, name="Faces")
    base_dir = _write_image_directory(tmp_path / f"{variant.value}-base")
    oddball_dir = _write_image_directory(tmp_path / f"{variant.value}-oddball")
    window.document.import_condition_stimulus_folder(condition_id, role="base", source_dir=base_dir)
    window.document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=oddball_dir,
    )
    qtbot.waitUntil(step.create_control_condition_button.isEnabled)
    materialize_calls = 0

    def _count_materialization() -> None:
        nonlocal materialize_calls
        materialize_calls += 1

    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step.ControlConditionDialog.exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step.ControlConditionDialog.selected_variant",
        lambda self: variant,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step.ControlConditionDialog.condition_name",
        lambda self: name,
    )
    monkeypatch.setattr(step, "_materialize_control_variant", _count_materialization)

    qtbot.mouseClick(step.create_control_condition_button, Qt.MouseButton.LeftButton)

    selected_id = step.selected_condition_id()
    assert selected_id is not None
    source = window.document.get_condition(condition_id)
    control = window.document.get_condition(selected_id)
    assert source is not None
    assert control is not None
    assert control.name == name
    assert control.base_stimulus_set_id == source.base_stimulus_set_id
    assert control.oddball_stimulus_set_id == source.oddball_stimulus_set_id
    assert control.stimulus_variant == variant
    assert control.trigger_code == 2
    assert materialize_calls == 1


def test_advanced_conditions_image_picker_starts_in_project_stimuli_folder(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Advanced Image Picker")
    page = window.conditions_page
    qtbot.mouseClick(page.add_condition_button, Qt.MouseButton.LeftButton)

    calls: list[tuple[str, str]] = []

    def _capture_directory(_parent, title: str, directory: str) -> str:
        calls.append((title, directory))
        return ""

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", _capture_directory)

    qtbot.mouseClick(page.base_import_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(page.oddball_import_button, Qt.MouseButton.LeftButton)

    expected_start = str(window.document.project_root / "stimuli")
    assert calls == [
        ("Choose Base Stimulus Folder", expected_start),
        ("Choose Oddball Stimulus Folder", expected_start),
    ]
