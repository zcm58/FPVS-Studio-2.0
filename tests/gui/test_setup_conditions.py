"""Focused GUI workflow tests split from the former layout dashboard suite."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QWidget,
)
from tests.gui.helpers import (
    _assert_visible_children_within_parent,
    _ImmediateProgressTask,
    _open_created_project,
    _write_image_directory,
    _write_mixed_image_directory,
)

from fpvs_studio.core.enums import (
    DutyCycleMode,
    StimulusModality,
    StimulusTransform,
    StimulusVariant,
)
from fpvs_studio.core.models import (
    ConditionPresentationSettings,
    StimulusPresentationOverride,
)
from fpvs_studio.gui.controller import StudioController


def _open_image_design_step(qtbot, guide) -> None:
    qtbot.waitUntil(lambda: not guide.design_setup_step.is_busy())
    guide.open_wizard(step_key="design")
    qtbot.waitUntil(lambda: not guide.design_setup_step.is_busy())
    guide.refresh()


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
    assert "Finish in Design" in step.condition_list.currentItem().toolTip()
    assert "Continuous Display" in step.condition_list.currentItem().text()


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


def test_setup_wizard_design_next_scans_images_without_blocking_gui(
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
    _open_image_design_step(qtbot, guide)
    QApplication.processEvents()

    assert len(background_tasks) == 1
    assert background_tasks[0].started is True
    assert scan_calls == 0
    assert guide.step_stack.currentWidget() is guide.design_step_surface
    assert guide.setup_wizard_next_button.isEnabled()

    qtbot.mouseClick(guide.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert progress_tasks == []
    assert scan_calls == 0
    assert guide.step_stack.currentWidget() is guide.design_step_surface
    assert not guide.setup_wizard_next_button.isEnabled()
    assert guide.setup_wizard_next_hint_label.text() == "Checking image readiness..."

    background_tasks[0].finish_success()
    QApplication.processEvents()

    assert scan_calls == 1
    qtbot.waitUntil(lambda: guide.step_stack.currentWidget() is guide.experiment_step_surface)


def test_setup_wizard_design_next_uses_cached_background_image_check(
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
    _open_image_design_step(qtbot, guide)
    QApplication.processEvents()

    assert background_calls == 1
    assert scan_calls == 1

    qtbot.mouseClick(guide.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert scan_calls == 1
    qtbot.waitUntil(lambda: guide.step_stack.currentWidget() is guide.experiment_step_surface)


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


@pytest.mark.parametrize("source", [StimulusModality.IMAGE, StimulusModality.WORD])
@pytest.mark.parametrize("accept", [False, True])
def test_setup_wizard_confirms_populated_modality_switch(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
    source: StimulusModality,
    accept: bool,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Stimulus Type Switch")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    window.show_setup_wizard(step_key="conditions")
    window.resize(1120, 820)
    errors: list[str] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step._show_error_dialog",
        lambda _parent, _title, error: errors.append(str(error)),
    )

    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    if source == StimulusModality.WORD:
        step.modality_combo.setCurrentIndex(step.modality_combo.findData(source.value))
        step.base_words_edit.setPlainText("cat")
        step.oddball_words_edit.setPlainText("chair")
        # Switch before the debounce timers commit either word list.
    else:
        for role in ("base", "oddball"):
            window.document.import_condition_stimulus_folder(
                condition_id, role=role,
                source_dir=_write_image_directory(tmp_path / role),
            )
    target = StimulusModality.WORD if source == StimulusModality.IMAGE else StimulusModality.IMAGE
    prompts: list[str] = []

    def confirm(_parent, _title, text, buttons, default):
        prompts.append(text)
        assert buttons == QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        assert default == QMessageBox.StandardButton.No
        for role in ("base", "oddball"):
            current = window.document.get_condition_stimulus_set(condition_id, role)
            assert current.modality == source
            assert current.image_count > 0 or current.word_count > 0
        return QMessageBox.StandardButton.Yes if accept else QMessageBox.StandardButton.No

    monkeypatch.setattr("fpvs_studio.gui.condition_setup_step.QMessageBox.warning", confirm)
    step.modality_combo.setCurrentIndex(step.modality_combo.findData(target.value))
    QApplication.processEvents()

    assert errors == []
    source_label = "images" if source == StimulusModality.IMAGE else "words"
    target_label = "words" if source == StimulusModality.IMAGE else "images"
    assert prompts == [
        f"Warning: changing your stimuli type from {source_label} to {target_label} "
        "will clear previous selections for this condition. "
        "Are you sure you want to continue?"
    ]
    expected = target if accept else source
    assert step.modality_combo.currentData() == expected.value
    assert step.words_panel.isVisible() == (expected == StimulusModality.WORD)
    for role in ("base", "oddball"):
        current = window.document.get_condition_stimulus_set(condition_id, role)
        assert current.modality == expected
        if accept:
            assert current.image_count == current.word_count == 0
        elif source == StimulusModality.WORD:
            assert current.words == (["cat"] if role == "base" else ["chair"])
        else:
            assert current.image_count == 3
    assert not step._base_words_committer.pending
    assert not step._oddball_words_committer.pending
    _assert_visible_children_within_parent(step)


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
    assert "Continuous Display" in step.condition_list.currentItem().text()
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
    assert next_button.isEnabled()
    assert not step.sources_row.isVisible()

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
    assert "50% Blank" in step.condition_list.currentItem().text()


def test_setup_wizard_contrast_modulation_is_available_for_images_only(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Image Presentation Modes")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")

    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    assert [
        step.timing_template_combo.itemText(index)
        for index in range(step.timing_template_combo.count())
    ] == [
        "Continuous Display",
        "50% Blank",
        "Sinusoidal Contrast Modulation",
    ]
    sinusoidal_index = step.timing_template_combo.findData(DutyCycleMode.SINUSOIDAL)
    assert sinusoidal_index >= 0
    assert "Neutral Gray (#808080)" in step.timing_template_combo.toolTip()

    step.timing_template_combo.setCurrentIndex(sinusoidal_index)
    QApplication.processEvents()
    condition = window.document.get_condition(condition_id)
    assert condition is not None
    assert condition.duty_cycle_mode == DutyCycleMode.SINUSOIDAL
    assert "Neutral Gray" in step.presentation_mode_help.text()
    assert "Timing" in step.presentation_mode_help.text()

    step.modality_combo.setCurrentIndex(step.modality_combo.findData(StimulusModality.WORD.value))
    QApplication.processEvents()

    condition = window.document.get_condition(condition_id)
    assert condition is not None
    assert condition.duty_cycle_mode == DutyCycleMode.CONTINUOUS
    assert [
        step.timing_template_combo.itemText(index)
        for index in range(step.timing_template_combo.count())
    ] == ["Continuous Display", "50% Blank"]
    assert step.timing_template_combo.findData(DutyCycleMode.SINUSOIDAL) == -1
    assert step.timing_template_combo.currentData() == DutyCycleMode.CONTINUOUS
    assert "resets Sinusoidal Contrast Modulation" in step.timing_template_combo.toolTip()
    assert "Neutral Gray" not in step.presentation_mode_help.text()
    assert "words" in step.condition_list_hint.text()

    step.modality_combo.setCurrentIndex(step.modality_combo.findData(StimulusModality.IMAGE.value))
    QApplication.processEvents()
    assert step.timing_template_combo.count() == 3
    assert step.timing_template_combo.findData(DutyCycleMode.SINUSOIDAL) >= 0


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


def test_setup_wizard_conditions_step_keeps_metadata_geometry_for_incomplete_condition(
    qtbot, controller: StudioController, tmp_path: Path
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Condition Geometry")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    window.resize(1120, 720)
    window.show_setup_wizard(step_key="conditions")
    first = window.document.create_condition(name="Faces")
    step._select_condition(first)
    QApplication.processEvents()
    metadata_size = step.condition_details_section.size()
    instructions_size = step.instructions_edit.size()
    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert step.condition_details_section.size() == metadata_size
    assert step.instructions_edit.size() == instructions_size
    assert step.instructions_edit.height() >= 80
    assert not step.sources_row.isVisible()
    assert step.condition_name_edit.width() == step.instructions_edit.width()
    assert "Design" in step.condition_list_hint.text()
    _assert_visible_children_within_parent(step.condition_details_section)
    _assert_visible_children_within_parent(step)


@pytest.mark.parametrize("modality", [StimulusModality.IMAGE, StimulusModality.WORD])
def test_condition_scope_and_long_content_fit_minimum_setup_size(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    modality: StimulusModality,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Condition Scope")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    window.resize(1120, 820)
    window.show_setup_wizard(step_key="conditions")
    assert step.target_repeats_spin.isEnabled()
    step.target_repeats_spin.setValue(10000)
    assert window.document.project.settings.condition_defaults.target_repeats_per_image == 10000

    condition_id = window.document.create_condition()
    long_name = ("Semantic categories with familiar and unfamiliar exemplars " * 3).strip()
    window.document.update_condition(condition_id, name=long_name, trigger_code=255)
    step._select_condition(condition_id)
    step.modality_combo.setCurrentIndex(step.modality_combo.findData(modality.value))
    if modality == StimulusModality.IMAGE:
        step.timing_template_combo.setCurrentIndex(
            step.timing_template_combo.findData(DutyCycleMode.SINUSOIDAL)
        )
    else:
        step.base_words_edit.setPlainText("familiar category exemplar\n" * 40)
        step.flush_pending_edits()
    step.instructions_edit.setPlainText(
        "Look at each stimulus and follow the task instructions. " * 20
    )
    step.flush_pending_edits()
    QApplication.processEvents()

    assert window.size().width() == 1120
    assert window.size().height() == 820
    assert step.condition_scope_label.text() == "This condition"
    assert step.condition_scope_label.toolTip() == long_name.strip()
    assert long_name.strip() in step.condition_list.currentItem().toolTip()
    assert step.condition_name_edit.toolTip() == long_name.strip()
    assert step.presentation_mode_label.text() == "Presentation mode"
    assert step.target_repeats_spin.parentWidget() is step.all_conditions_section
    assert step.presentation_button.accessibleDescription()
    assert step.target_repeats_spin.value() == 10000
    for label in (step.condition_scope_label, step.all_conditions_label, step.target_repeats_label):
        assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    for label in (step.presentation_mode_help, step.condition_list_hint):
        required_height = label.heightForWidth(label.width())
        assert required_height <= label.height()
    for parent in (step, step.condition_details_section, step.all_conditions_section):
        _assert_visible_children_within_parent(parent)
    if modality == StimulusModality.IMAGE:
        for card in (step.base_source_card, step.oddball_source_card):
            _assert_visible_children_within_parent(card)
    else:
        _assert_visible_children_within_parent(step.words_panel)


def test_legacy_source_details_preserves_full_project_path(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    copied: list[str] = []
    clipboard = SimpleNamespace(setText=copied.append, text=lambda: copied[-1] if copied else "")
    monkeypatch.setattr(QApplication, "clipboard", lambda: clipboard)
    _, window = _open_created_project(controller, qtbot, tmp_path, "Inspectable Sources")
    step = window.setup_wizard_page.condition_setup_step
    window.resize(1120, 720)
    window.show_setup_wizard(step_key="conditions")
    condition_id = window.document.create_condition()
    step._select_condition(condition_id)
    assert not step.base_source_card.source_details_button.isEnabled()
    source = window.document.get_condition_stimulus_set(condition_id, "base")
    # Retained metadata can reference a missing folder; inspection does no filesystem work.
    source.source_dir = "stimuli/original-images/" + "long-category-source-folder/" * 8
    source.image_count = 2
    step.refresh()
    QApplication.processEvents()
    expected_path = str(window.document.project_root / source.source_dir)
    button = step.base_source_card.source_details_button
    assert button.isEnabled()
    # Hidden compatibility source details remain usable by the existing advanced editor.
    assert not step.sources_row.isVisible()
    button.click()
    QApplication.processEvents()
    dialog = step.base_source_card.findChild(
        QDialog, "setup_conditions_base_source_card_source_details_dialog"
    )
    assert dialog is not None and dialog.isVisible()
    qtbot.addWidget(dialog)
    path_text = dialog.findChild(QTextEdit, "source_details_path")
    assert path_text is not None and path_text.toPlainText() == expected_path
    copy_button = dialog.findChild(QPushButton, "source_details_copy_path")
    assert copy_button is not None
    copy_button.setFocus()
    qtbot.keyClick(copy_button, Qt.Key.Key_Space)
    assert QApplication.clipboard().text() == expected_path
    dialog.close()


def test_condition_blocker_focus_selects_missing_word_role_without_opening_dialog(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Condition Correction")
    step = window.setup_wizard_page.condition_setup_step
    window.show_setup_wizard(step_key="conditions")
    condition_id = window.document.create_condition()
    step._select_condition(condition_id)
    window.raise_()
    window.activateWindow()
    QApplication.processEvents()
    step.focus_setup_blocker()
    assert step.condition_name_edit.hasFocus()
    window.document.update_condition(condition_id, name="Animal words")
    step.modality_combo.setCurrentIndex(step.modality_combo.findData(StimulusModality.WORD.value))
    step.base_words_edit.setPlainText("cat\ndog")
    step.flush_pending_edits()
    other_id = window.document.create_condition()
    step._select_condition(other_id)

    step.focus_setup_blocker()

    assert step.selected_condition_id() == condition_id
    assert step.oddball_words_edit.hasFocus()
    assert "words" in step.condition_list_hint.text()


@pytest.mark.parametrize("window_size", [(1120, 820), (1120, 960), (1448, 1086)])
@pytest.mark.parametrize(
    ("modality", "mode"),
    [
        (StimulusModality.IMAGE, DutyCycleMode.CONTINUOUS),
        (StimulusModality.IMAGE, DutyCycleMode.SINUSOIDAL),
        (StimulusModality.WORD, DutyCycleMode.CONTINUOUS),
    ],
)
def test_conditions_six_condition_layout_expands_with_aligned_panels(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
    window_size: tuple[int, int],
    modality: StimulusModality,
    mode: DutyCycleMode,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Conditions Clipping")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    monkeypatch.setattr(guide, "_ensure_condition_image_prescan_started", lambda: None)
    window.document.update_project_description("Compare six semantic stimulus categories.")
    base_dir = _write_image_directory(tmp_path / "base-sources", count=10, size=(512, 512))
    oddball_dir = _write_image_directory(tmp_path / "oddball-sources", count=5, size=(512, 512))
    condition_ids = []
    instructions = (
        "Watch the fixation cross and press Space when it changes from blue to red.\n\n"
        "Please remain as still as possible throughout the experiment. "
        "Wait for the researcher before continuing to the next session."
    )
    for name in (
        "Positive valence",
        "Negative valence",
        "Erotic valence",
        "Neutral happy",
        "Neutral sad",
        "Familiar animal words and unfamiliar semantic exemplars",
    ):
        condition_id = window.document.create_condition(name=name)
        condition_ids.append(condition_id)
        window.document.update_condition(condition_id, instructions=instructions)
        if modality == StimulusModality.WORD:
            window.document.set_condition_stimulus_modality(condition_id, modality=modality)
            window.document.update_condition_words(
                condition_id, role="base", words=["familiar animal", "domestic cat", "small dog"]
            )
            window.document.update_condition_words(
                condition_id, role="oddball", words=["hammer", "table"]
            )
        else:
            window.document.import_condition_stimulus_folder(
                condition_id, role="base", source_dir=base_dir
            )
            window.document.import_condition_stimulus_folder(
                condition_id, role="oddball", source_dir=oddball_dir
            )
            window.document.update_condition_timing_template(condition_id, mode)

    window.document.update_condition(condition_ids[0], trigger_code=255)
    window.show_setup_wizard(step_key="conditions")
    window.resize(*window_size)
    window.show()
    for selected_id in (condition_ids[0], condition_ids[-1]):
        step._select_condition(selected_id)
        guide.refresh()
        QApplication.processEvents()
        # The queued wizard refresh can hide the hint and post another layout pass.
        qtbot.waitUntil(lambda: step.condition_list.y() == 0)
        assert (window.width(), window.height()) == window_size
        assert step.condition_list.count() == 6
        assert step.instructions_edit.toPlainText() == instructions
        assert step.instructions_edit.height() >= 80
        assert not step.condition_list_hint.isVisible()
        assert step.condition_list_hint.text() == ""
        assert step.words_panel.isVisible() == (modality == StimulusModality.WORD)
        trigger_edit = step.trigger_code_spin.lineEdit()
        assert trigger_edit is not None
        assert trigger_edit.width() >= trigger_edit.fontMetrics().horizontalAdvance(
            trigger_edit.text()
        )
        if selected_id == condition_ids[0]:
            assert step.trigger_code_spin.value() == 255
        for state_label in (
            step.name_check_status,
            step.trigger_check_status,
            step.base_check_status,
            step.oddball_check_status,
            step.base_count_value,
            step.base_resolution_value,
            step.oddball_count_value,
            step.oddball_resolution_value,
        ):
            assert not state_label.isVisible(), state_label.objectName()
        _assert_visible_children_within_parent(step)
        labels = [label for label in step.findChildren(QLabel) if label.isVisible()]
        for index, label in enumerate(labels):
            if label.wordWrap():
                assert label.heightForWidth(label.width()) <= label.height(), label.objectName()
            else:
                assert label.height() >= label.fontMetrics().height(), label.objectName()
                assert label.width() >= label.fontMetrics().horizontalAdvance(label.text()), (
                    label.objectName()
                )
            label_rect = label.rect().translated(label.mapTo(step, label.rect().topLeft()))
            for other in labels[index + 1 :]:
                other_rect = other.rect().translated(other.mapTo(step, other.rect().topLeft()))
                assert not label_rect.intersects(other_rect), (
                    label.objectName(),
                    other.objectName(),
                )
        list_top = step.condition_list.mapTo(step, step.condition_list.rect().topLeft()).y()
        details_top = step.condition_details_section.mapTo(
            step, step.condition_details_section.rect().topLeft()
        ).y()
        assert abs(list_top - details_top) <= 1
        surface = guide.conditions_step_surface
        content_top = step.mapTo(surface, step.rect().topLeft()).y()
        assert abs(content_top - 16) <= 1
        assert abs(surface.height() - step.height() - 32) <= 2
        assert step.condition_list.height() >= 300
        if modality == StimulusModality.WORD and window_size[1] >= 960:
            assert step.base_words_edit.height() > 124
            assert step.oddball_words_edit.height() > 124
            assert step.instructions_edit.height() > 80
        instructions_bottom = step.instructions_edit.mapTo(
            step.condition_details_section, step.instructions_edit.rect().bottomLeft()
        ).y()
        assert instructions_bottom <= step.condition_details_section.height() - 4
        assert not guide.shell.page_container.scroll_area.verticalScrollBar().isEnabled()


def test_setup_wizard_design_next_silently_advances_when_images_are_uniform(
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
    _open_image_design_step(qtbot, guide)
    QApplication.processEvents()

    def _unexpected_dialog(*_args, **_kwargs):
        raise AssertionError("Normalization dialog should not be shown for uniform images.")

    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.ImageNormalizationDialog",
        _unexpected_dialog,
    )
    monkeypatch.setattr("fpvs_studio.gui.setup_wizard_page.ProgressTask", _ImmediateProgressTask)

    guide.open_wizard(step_key="images")
    assert guide.step_stack.currentWidget() is guide.design_step_surface
    qtbot.mouseClick(guide.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    qtbot.waitUntil(lambda: guide.step_stack.currentWidget() is guide.experiment_step_surface)


def test_setup_wizard_design_next_normalizes_mixed_images_before_advancing(
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
        source_dir=_write_image_directory(
            tmp_path / "mixed-oddball",
            size=(160, 120),
        ),
    )
    original_oddball = window.document.get_condition_stimulus_set(condition_id, "oddball")
    _open_image_design_step(qtbot, guide)
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
    assert guide.step_stack.currentWidget() is guide.design_step_surface
    qtbot.mouseClick(guide.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    qtbot.waitUntil(lambda: guide.step_stack.currentWidget() is guide.experiment_step_surface)
    base_set = window.document.get_condition_stimulus_set(condition_id, "base")
    oddball_set = window.document.get_condition_stimulus_set(condition_id, "oddball")
    assert Path(base_set.source_dir).parent.as_posix() == "stimuli/normalized-images"
    assert Path(base_set.source_dir).name.startswith("condition-1-base-")
    assert oddball_set == original_oddball
    assert base_set.resolution is not None
    assert base_set.resolution.as_tuple() == (512, 512)
    assert oddball_set.resolution is not None
    assert oddball_set.resolution.as_tuple() == (160, 120)
    assert not (
        window.document.project_root / "stimuli" / "normalized-images" / "condition-1-oddball"
    ).exists()
    assert all(
        path.suffix == ".png"
        for path in (window.document.project_root / Path(base_set.source_dir)).iterdir()
    )


def test_setup_wizard_design_next_preserves_uniform_non_square_images(
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
    _open_image_design_step(qtbot, guide)
    QApplication.processEvents()

    def _unexpected_dialog(*_args, **_kwargs):
        raise AssertionError("Uniform rectangular images should not require square normalization.")

    monkeypatch.setattr("fpvs_studio.gui.setup_wizard_page.ProgressTask", _ImmediateProgressTask)
    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.ImageNormalizationDialog",
        _unexpected_dialog,
    )

    qtbot.mouseClick(guide.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    qtbot.waitUntil(lambda: guide.step_stack.currentWidget() is guide.experiment_step_surface)
    base_set = window.document.get_condition_stimulus_set(condition_id, "base")
    assert base_set.resolution is not None
    assert base_set.resolution.as_tuple() == (128, 96)
    assert base_set.source_dir != "stimuli/normalized-images/condition-1-base"


def test_setup_wizard_preserves_different_uniform_base_and_oddball_rectangles(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Role Rectangles")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    monkeypatch.setattr(guide, "_ensure_condition_image_prescan_started", lambda: None)
    guide.open_wizard(step_key="conditions")
    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert condition_id is not None
    guide._document.update_condition(condition_id, name="Faces and Objects", trigger_code=1)
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="base",
        source_dir=_write_image_directory(
            tmp_path / "role-rectangle-base",
            size=(500, 400),
        ),
    )
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=_write_image_directory(
            tmp_path / "role-rectangle-oddball",
            size=(158, 197),
        ),
    )
    guide.refresh()
    _open_image_design_step(qtbot, guide)
    QApplication.processEvents()
    assert guide.setup_wizard_next_button.isEnabled()
    normalization_scan = guide._document.scan_condition_image_normalization()

    def _unexpected_dialog(*_args, **_kwargs):
        raise AssertionError("Uniform role-specific rectangles must remain native.")

    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.ImageNormalizationDialog",
        _unexpected_dialog,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.ProgressTask",
        _ImmediateProgressTask,
    )
    monkeypatch.setattr(
        guide,
        "_start_condition_image_readiness_scan",
        lambda: guide._on_condition_image_readiness_scan_succeeded(normalization_scan),
    )
    qtbot.mouseClick(guide.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    qtbot.waitUntil(lambda: guide.step_stack.currentWidget() is guide.experiment_step_surface)
    base = window.document.get_condition_stimulus_set(condition_id, "base")
    oddball = window.document.get_condition_stimulus_set(condition_id, "oddball")
    assert base.resolution is not None and base.resolution.as_tuple() == (500, 400)
    assert oddball.resolution is not None and oddball.resolution.as_tuple() == (158, 197)


def test_setup_wizard_design_next_stays_put_when_normalization_is_cancelled(
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
    _open_image_design_step(qtbot, guide)
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
    assert guide.step_stack.currentWidget() is guide.design_step_surface
    qtbot.mouseClick(guide.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert guide.step_stack.currentWidget() is guide.design_step_surface
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
    assert guide.step_stack.currentWidget() is guide.design_step_surface

    calls: list[tuple[str, str]] = []

    def _capture_directory(_parent, title: str, directory: str) -> str:
        calls.append((title, directory))
        return ""

    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step.QFileDialog.getExistingDirectory",
        _capture_directory,
    )

    step.base_import_button.click()
    step.oddball_import_button.click()

    assert not step.sources_row.isVisible()
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


def test_setup_wizard_rotated_runtime_control_reuses_originals_without_materializing(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Runtime Rotated Control")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")
    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    source_id = step.selected_condition_id()
    assert source_id is not None
    window.document.update_condition(source_id, name="Faces")
    window.document.update_condition(
        source_id,
        presentation=ConditionPresentationSettings(
            base=StimulusPresentationOverride(transform=StimulusTransform.MIRROR_VERTICAL),
            oddball=StimulusPresentationOverride(transform=StimulusTransform.MIRROR_HORIZONTAL),
        ),
    )
    window.document.import_condition_stimulus_folder(
        source_id,
        role="base",
        source_dir=_write_image_directory(tmp_path / "runtime-rotated-base"),
    )
    window.document.import_condition_stimulus_folder(
        source_id,
        role="oddball",
        source_dir=_write_image_directory(tmp_path / "runtime-rotated-oddball"),
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
        lambda self: StimulusVariant.ORIGINAL,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step.ControlConditionDialog.selected_transform",
        lambda self: StimulusTransform.ROT180,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step.ControlConditionDialog.condition_name",
        lambda self: "Faces 180 Degree Rotated Control",
    )
    monkeypatch.setattr(step, "_materialize_control_variant", _count_materialization)

    qtbot.mouseClick(step.create_control_condition_button, Qt.MouseButton.LeftButton)

    control_id = step.selected_condition_id()
    assert control_id is not None and control_id != source_id
    source = window.document.get_condition(source_id)
    control = window.document.get_condition(control_id)
    assert source is not None
    assert control is not None
    assert control.stimulus_variant == StimulusVariant.ORIGINAL
    assert control.presentation.common.transform == StimulusTransform.ROT180
    assert control.presentation.base.transform is None
    assert control.presentation.oddball.transform is None
    assert control.base_stimulus_set_id == source.base_stimulus_set_id
    assert control.oddball_stimulus_set_id == source.oddball_stimulus_set_id
    assert materialize_calls == 0


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
