"""Condition image sources fit the dedicated, category-locked Design step."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTabBar
from tests.gui.helpers import assert_visible_children_within_parent, write_image_directory
from tests.gui.test_experiment_designer import _populate_sources

from fpvs_studio.core.condition_modifiers import assign_modifier, remove_modifier
from fpvs_studio.core.enums import DutyCycleMode, ExperimentCategory, StimulusModality
from fpvs_studio.core.masking import condition_masking
from fpvs_studio.core.masking_presets import apply_masking_timing_defaults, create_masking_modifier
from fpvs_studio.core.models import Condition, ProjectFile, ProjectMeta
from fpvs_studio.gui.design_setup_step import DesignSetupStep
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.experiment_designer_dialog import ExperimentDesignerWidget
from fpvs_studio.gui.image_sources_editor import ImageSourcesEditor
from fpvs_studio.gui.setup_wizard_page import SetupWizardPage
from fpvs_studio.gui.window_helpers import (
    _conditions_have_assigned_assets,
    _launcher_readiness_report,
)


def _document(tmp_path, category=ExperimentCategory.FPVS_ODDBALL):
    return ProjectDocument.create_new(
        parent_dir=tmp_path, project_name="Design step", experiment_category=category,
    )


def _step(qtbot, document, *, size=(1000, 600)):
    step = DesignSetupStep(document)
    qtbot.addWidget(step)
    step.resize(*size)
    step.show()
    QApplication.processEvents()
    return step


@pytest.fixture
def source_tasks(monkeypatch):
    tasks = []

    class SourceTask(QObject):
        succeeded = Signal(object)
        failed = Signal(object)
        finished = Signal()

        def __init__(self, *, parent_widget, callback):
            super().__init__(parent_widget)
            self._callback = callback

        def start(self):
            tasks.append(self)

        def complete(self):
            try:
                self.succeeded.emit(self._callback())
            except Exception as error:
                self.failed.emit(error)
            finally:
                self.finished.emit()

    monkeypatch.setattr("fpvs_studio.gui.image_sources_editor.BackgroundTask", SourceTask)
    return tasks


def _masking_document(tmp_path):
    project = ProjectFile(
        meta=ProjectMeta(project_id="masking", name="Masking", template_id="fpvs_6hz_every5_v1"),
        conditions=[Condition(
            condition_id="color", name="Color Masking with native source-owned circles",
            base_stimulus_set_id="modifier-owned-base",
            oddball_stimulus_set_id="modifier-owned-target",
            sequence_count=1, trigger_code=1,
        )],
    )
    project = assign_modifier(
        project, create_masking_modifier(variant="color", modifier_id="color-mask"), ["color"],
    )
    project = apply_masking_timing_defaults(project)
    return ProjectDocument(project_root=tmp_path, project=project)


def test_masking_design_routes_to_modifier_and_removal_exposes_missing_sources(
    qtbot, tmp_path,
):
    document = _masking_document(tmp_path)
    step = _step(qtbot, document)
    assert document.project.stimulus_sets == []
    assert step.editor is None
    assert step.masking_edit_button.isVisible()
    assert "target-to-mask SOA" in step.status_label.text()
    assert step.validation_message() == ""
    assert _conditions_have_assigned_assets(document, document.ordered_conditions())
    assert _launcher_readiness_report(document, refresh_hz=60).status_label == "Ready to Launch"
    assert_visible_children_within_parent(step)

    document.apply_condition_modifier_project(
        remove_modifier(document.project, "color-mask", ["color"]),
    )
    QApplication.processEvents()
    assert step.editor is None
    assert not step.masking_edit_button.isVisible()
    assert "no stimulus sources" in step.status_label.text()
    assert not step.apply_pending_design()
    assert not _conditions_have_assigned_assets(document, document.ordered_conditions())


def test_masking_duplicate_keeps_modifier_assignment_without_creating_image_sets(tmp_path):
    document = _masking_document(tmp_path)
    source = document.project.conditions[0]
    duplicate_id = document.duplicate_condition(source.condition_id)
    duplicate = document.get_condition(duplicate_id)
    assert duplicate is not None
    assert duplicate.name == source.name + " Copy"
    assert duplicate.pre_task_bindings == source.pre_task_bindings
    assert duplicate.post_task_bindings == source.post_task_bindings
    assert condition_masking(document.project, duplicate) == condition_masking(
        document.project, source,
    )
    assert len(document.project.condition_modifiers) == 1
    assert document.project.stimulus_sets == []


def test_masking_wizard_uses_modifier_sources_and_preserves_display_calibration(qtbot, tmp_path):
    document = _masking_document(tmp_path)
    wizard = SetupWizardPage(
        document, load_condition_template_profiles=lambda: [],
        manage_condition_templates=lambda: [],
    )
    qtbot.addWidget(wizard)
    wizard.resize(1120, 820)
    wizard.show()
    assert wizard._condition_setup_blocker() == ""
    for step_key in ("conditions", "image_size", "review"):
        wizard.open_wizard(step_key=step_key, allow_step_jumps=True)
        QApplication.processEvents()
        assert_visible_children_within_parent(wizard.step_stack.currentWidget())
        assert wizard.shell.page_container.scroll_area.verticalScrollBar().maximum() == 0
    wizard.open_wizard(step_key="image_size", allow_step_jumps=True)
    QApplication.processEvents()
    editor = wizard.image_display_size_editor
    assert not editor.width_degrees_spin.isVisible()
    assert not editor.configure_presentation_button.isVisible()
    assert editor.viewing_distance_spin.isVisible()
    assert editor.screen_width_spin.isVisible()
    assert "Calibrate" in editor.preview_value_label.text()
    document.project.conditions[0].duty_cycle_mode = DutyCycleMode.BLANK_50
    wizard.open_wizard(step_key="conditions")
    assert "continuous" in wizard._condition_setup_blocker()
    assert not wizard.setup_wizard_next_button.isEnabled()


def test_empty_design_step_explains_where_to_add_a_condition(qtbot, tmp_path):
    step = _step(qtbot, _document(tmp_path))
    assert step.editor is None
    assert not step.condition_combo.isEnabled()
    assert "Add a condition" in step.status_label.text()
    assert not step.apply_pending_design()


def test_word_condition_keeps_ordinary_word_authoring(qtbot, tmp_path):
    document = _document(tmp_path, ExperimentCategory.FPVS_ODDBALL)
    condition_id = document.create_condition(name="Recognition words")
    document.set_condition_stimulus_modality(condition_id, modality=StimulusModality.WORD)
    step = _step(qtbot, document)
    assert step.editor is None
    assert "word lists" in step.status_label.text()
    assert step.apply_pending_design()
    assert (
        document.get_condition_stimulus_set(condition_id, "base").modality == StimulusModality.WORD
    )


def test_selected_condition_modality_changes_replace_the_image_source_controls(qtbot, tmp_path):
    document = _document(tmp_path)
    condition_id = document.create_condition(name="Switch between image and word sources")
    step = _step(qtbot, document)
    assert isinstance(step.editor, ImageSourcesEditor)

    document.set_condition_stimulus_modality(condition_id, modality=StimulusModality.WORD)
    QApplication.processEvents()
    assert step.selected_condition_id() == condition_id
    assert step.editor is None
    assert step.editor_layout.count() == 0
    assert step.status_label.isVisible()
    assert "word lists" in step.status_label.text()
    assert step.apply_pending_design()

    document.set_condition_stimulus_modality(condition_id, modality=StimulusModality.IMAGE)
    QApplication.processEvents()
    assert step.selected_condition_id() == condition_id
    assert isinstance(step.editor, ImageSourcesEditor)
    assert step.editor.base_source.isVisible()
    assert step.editor.oddball_source.isVisible()
    assert not step.status_label.isVisible()
    assert not step.apply_pending_design()
    assert "Base and Oddball images" in step.validation_message()


def test_missing_image_folders_block_navigation_with_inline_guidance(qtbot, tmp_path):
    document = _document(tmp_path)
    document.create_condition(name="Select images next")
    step = _step(qtbot, document)
    assert isinstance(step.editor, ImageSourcesEditor)
    assert not step.apply_pending_design()
    assert "Base" in step.validation_message()
    assert "Oddball" in step.validation_message()
    assert step.editor.status_label.isVisible()
    assert not step.has_pending_design()
    assert_visible_children_within_parent(step)


@pytest.mark.parametrize("role", ["base", "oddball"])
def test_image_selection_updates_only_the_selected_condition_and_role(
    qtbot, monkeypatch, tmp_path, source_tasks, role,
):
    document = _document(tmp_path)
    first = document.create_condition(name="First condition")
    second = document.create_condition(name="Second condition")
    _populate_sources(document, first, tmp_path / "existing")
    untouched = document.get_condition(second).model_dump()
    other_role = "oddball" if role == "base" else "base"
    other_source = document.get_condition_stimulus_set(first, other_role).model_dump()
    before_protocol = document.project.settings.protocol.model_dump()
    folder = write_image_directory(tmp_path / "selected-images", count=3)
    monkeypatch.setattr(
        "fpvs_studio.gui.image_sources_editor.QFileDialog.getExistingDirectory",
        lambda *_args: str(folder),
    )
    step = _step(qtbot, document)
    editor = step.editor
    assert isinstance(editor, ImageSourcesEditor)
    card = editor.base_source if role == "base" else editor.oddball_source
    card.choose_button.click()
    assert step.is_importing()
    source_tasks[-1].complete()

    source = document.get_condition_stimulus_set(first, role)
    assert source.image_count == 3
    assert role in source.set_id
    assert any(label.text() == "3 images" for label in card.findChildren(QLabel))
    assert (card.folder_value.toolTip() or card.folder_value.text()) == str(
        document.project_root / source.source_dir
    )
    assert document.get_condition_stimulus_set(first, other_role).model_dump() == other_source
    assert document.get_condition(second).model_dump() == untouched
    assert document.project.settings.protocol.model_dump() == before_protocol
    assert step.apply_pending_design()
    assert not step.has_pending_design()
    assert step.select_condition(second)
    assert step.condition_combo.toolTip() == document.get_condition(second).name
    assert not step.apply_pending_design()
    assert step.select_condition(first)
    assert step.condition_combo.toolTip() == document.get_condition(first).name
    assert step.apply_pending_design()
    document.save()


@pytest.mark.parametrize("role", ["base", "oddball"])
def test_cancelled_image_picker_preserves_sources_and_starts_in_project_stimuli(
    qtbot, monkeypatch, tmp_path, source_tasks, role,
):
    document = _document(tmp_path)
    condition_id = document.create_condition(name="Keep source images")
    _populate_sources(document, condition_id, tmp_path / "existing")
    before = document.project.model_dump()
    calls = []

    def choose(_parent, title, directory):
        calls.append((title, directory))
        return ""

    monkeypatch.setattr(
        "fpvs_studio.gui.image_sources_editor.QFileDialog.getExistingDirectory", choose,
    )
    step = _step(qtbot, document)
    step.editor._choose_source(role)
    assert len(calls) == 1
    assert role.capitalize() in calls[0][0]
    assert calls[0][1] == str(document.project_root / "stimuli")
    assert source_tasks == []
    assert not step.is_busy()
    assert document.project.model_dump() == before


def test_replacing_an_image_folder_keeps_a_fresh_pool_without_merging(
    qtbot, tmp_path, source_tasks,
):
    document = _document(tmp_path)
    condition_id = document.create_condition(name="Replace images")
    _populate_sources(document, condition_id, tmp_path / "existing")
    previous = document.get_condition_stimulus_set(condition_id, "base")
    replacement = write_image_directory(tmp_path / "replacement", count=1)
    (replacement / "stimulus-01.png").rename(replacement / "replacement.png")
    step = _step(qtbot, document)
    step.editor._start_source_import("base", replacement)
    source_tasks[-1].complete()

    source = document.get_condition_stimulus_set(condition_id, "base")
    assert source.set_id != previous.set_id
    assert source.image_count == 1
    manifest_set = next(item for item in document.manifest.sets if item.set_id == source.set_id)
    assert [Path(item.source.relative_path).name for item in manifest_set.assets] == [
        "replacement.png"
    ]
    assert len(list((document.project_root / previous.source_dir).glob("*.png"))) == 2
    assert step.apply_pending_design()


def test_busy_source_import_prevents_condition_switch_navigation_and_close(
    qtbot, tmp_path, source_tasks,
):
    document = _document(tmp_path)
    first = document.create_condition(name="First condition")
    second = document.create_condition(name="Second condition")
    folder = write_image_directory(tmp_path / "selected-images", count=2)
    step = _step(qtbot, document)
    editor = step.editor
    transitions = []
    step.busy_changed.connect(lambda busy: transitions.append((busy, step.is_importing())))
    editor._start_source_import("base", folder)
    assert step.is_busy()
    assert step.is_importing()
    assert not step.condition_combo.isEnabled()
    assert not editor.base_source.choose_button.isEnabled()
    assert not editor.oddball_source.choose_button.isEnabled()
    assert not step.select_condition(second)
    assert not step.apply_pending_design()
    assert not step.discard_pending_design()
    assert not editor.request_close()
    assert step.selected_condition_id() == first
    source_tasks[-1].complete()
    assert transitions == [(True, True), (False, False)]
    assert not step.is_busy()
    assert step.condition_combo.isEnabled()
    assert editor.base_source.choose_button.isEnabled()
    assert editor.oddball_source.choose_button.isEnabled()
    assert editor.request_close()
    assert step.select_condition(second)


def test_failed_import_preserves_sources_and_retry_clears_the_error(
    qtbot, monkeypatch, tmp_path, source_tasks,
):
    from fpvs_studio.gui.designer_sources import import_designer_source

    document = _document(tmp_path)
    condition_id = document.create_condition(name="Retry image import")
    _populate_sources(document, condition_id, tmp_path / "existing")
    before = document.project.model_dump()
    folder = write_image_directory(tmp_path / "replacement", count=3)
    calls = []

    def import_source(*args):
        calls.append(args)
        if len(calls) == 1:
            raise ValueError("The selected image folder is unavailable. Choose it again.")
        return import_designer_source(*args)

    monkeypatch.setattr(
        "fpvs_studio.gui.image_sources_editor.import_designer_source", import_source,
    )
    step = _step(qtbot, document)
    editor = step.editor
    editor._start_source_import("base", folder)
    source_tasks[-1].complete()
    assert "unavailable" in editor.status_label.text()
    assert editor.status_label.isVisible()
    assert not step.is_busy()
    assert document.project.model_dump() == before
    assert editor.base_source.choose_button.isEnabled()
    editor._start_source_import("base", folder)
    source_tasks[-1].complete()
    assert len(calls) == 2
    assert document.get_condition_stimulus_set(condition_id, "base").image_count == 3
    assert "unavailable" not in editor.status_label.text()
    assert not editor.status_label.isVisible()
    assert step.apply_pending_design()


def test_image_sources_never_construct_or_decode_a_visual_preview(
    qtbot, monkeypatch, tmp_path,
):
    def unexpected_preview(*_args, **_kwargs):
        raise AssertionError("Setup image selection must not create an image preview")

    monkeypatch.setattr(ExperimentDesignerWidget, "__init__", unexpected_preview)
    monkeypatch.setattr(
        "fpvs_studio.gui.designer_sources.load_designer_thumbnails", unexpected_preview,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.experiment_designer_dialog.load_designer_thumbnails", unexpected_preview,
    )
    document = _document(tmp_path)
    first = document.create_condition(name="Source-only image condition")
    second = document.create_condition(name="Another image condition")
    _populate_sources(document, first, tmp_path / "existing")
    step = _step(qtbot, document)
    for _ in range(2):
        step.hide()
        document.update_project_description("Keep selected sources while editing metadata")
        document.update_protocol_settings(base_hz=5.0)
        document.save()
        step.refresh()
        step.show()
        QApplication.processEvents()
        assert isinstance(step.editor, ImageSourcesEditor)
        assert not step.is_busy()
        assert not step.has_pending_design()
        assert not hasattr(step.editor, "cycle_canvas")
        assert not hasattr(step.editor, "preview_window")
        assert not hasattr(step.editor, "_thumbnail_task")
        assert step.apply_pending_design()
        assert step.select_condition(second)
        assert step.select_condition(first)


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("state", ["empty", "populated", "error", "importing"])
def test_image_sources_fit_the_wizard_content_budget(
    qtbot, tmp_path: Path, source_tasks, dark, state,
):
    document = _document(tmp_path)
    condition_id = document.create_condition(
        name="Long condition name for familiar and unfamiliar natural objects"
    )
    if state != "empty":
        _populate_sources(document, condition_id, tmp_path / "existing")
        for role in ("base", "oddball"):
            document.get_condition_stimulus_set(condition_id, role).source_dir = (
                "stimuli/" + "reviewed picture collections/" * 6 + role
            )
    step = _step(qtbot, document)
    palette = QPalette(step.palette())
    palette.setColor(QPalette.ColorRole.Window, QColor("#202124" if dark else "#f4f7fb"))
    step.setPalette(palette)
    editor = step.editor
    assert isinstance(editor, ImageSourcesEditor)
    if state == "error":
        editor._task_failed(ValueError(
            "The selected image folder is unavailable. Choose another Base image folder to retry."
        ))
    elif state == "importing":
        editor._start_source_import("base", tmp_path / "incoming-images")
    elif state == "empty":
        assert not step.apply_pending_design()
    QApplication.processEvents()
    assert (step.width(), step.height()) == (1000, 600)
    assert step.minimumSizeHint().height() <= 600
    assert_visible_children_within_parent(step)
    assert not step.findChildren(QTabBar)
    assert step.condition_combo.toolTip() == document.get_condition(condition_id).name
    assert editor.base_source.isVisible()
    assert editor.oddball_source.isVisible()
    if state != "empty":
        for role, card in (("base", editor.base_source), ("oddball", editor.oddball_source)):
            source = document.get_condition_stimulus_set(condition_id, role)
            full_path = str(document.project_root / source.source_dir)
            assert card.folder_value.toolTip() == full_path
            assert card.source_details_button.isEnabled()
    for label in step.findChildren(QLabel):
        if not label.isVisible() or not label.text():
            continue
        if label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width()), label.text()
        else:
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text()), (
                label.text()
            )
    for button in step.findChildren(QPushButton):
        if button.isVisible():
            rendered = button.text().replace("&&", "\0").replace("&", "").replace("\0", "&")
            assert button.width() >= button.fontMetrics().horizontalAdvance(rendered) + 12
    if state == "importing":
        editor._import_finished()


def test_retired_image_pairs_show_explanation_instead_of_editor(qtbot, tmp_path):
    from fpvs_studio.core.models import AttentionalBlinkSettings

    document = _document(tmp_path)
    condition_id = document.create_condition(name="Archived image pairs")
    document._project = document.project.model_copy(
        update={"experiment_category": ExperimentCategory.ATTENTIONAL_BLINK}, deep=True
    )
    document.get_condition(condition_id).attentional_blink = AttentionalBlinkSettings()
    before = document.project.model_dump()
    step = _step(qtbot, document)
    assert step.editor is None
    assert "no longer supported" in step.status_label.text()
    assert not step.apply_pending_design()
    with pytest.raises(ValueError, match="no longer supported"):
        ExperimentDesignerWidget(document, condition_id=condition_id)
    assert document.project.model_dump() == before
