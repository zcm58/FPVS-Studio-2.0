"""The shared visual editor fits the dedicated, category-locked Design step."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QLabel, QPushButton, QTabBar
from tests.gui.helpers import assert_visible_children_within_parent
from tests.gui.test_experiment_designer import _populate_sources

from fpvs_studio.core.enums import ExperimentCategory, StimulusModality
from fpvs_studio.gui.design_setup_step import DesignSetupStep
from fpvs_studio.gui.designer_sources import load_designer_thumbnails
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.experiment_designer_dialog import ExperimentDesignerWidget


def _document(tmp_path, category=ExperimentCategory.ATTENTIONAL_BLINK):
    return ProjectDocument.create_new(
        parent_dir=tmp_path, project_name="Design step", experiment_category=category,
    )


def _step(qtbot, monkeypatch, document, *, size=(1000, 600)):
    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda self: None)
    step = DesignSetupStep(document)
    qtbot.addWidget(step)
    step.resize(*size)
    step.show()
    QApplication.processEvents()
    return step


def test_empty_design_step_explains_where_to_add_a_condition(qtbot, monkeypatch, tmp_path):
    step = _step(qtbot, monkeypatch, _document(tmp_path))
    assert step.editor is None
    assert not step.condition_combo.isEnabled()
    assert "Add a condition" in step.status_label.text()
    assert not step.apply_pending_design()


def test_sources_follow_target_order_and_timing_uses_typed_numbers(qtbot, monkeypatch, tmp_path):
    document = _document(tmp_path)
    condition_id = document.create_condition(name="Typed timing")
    _populate_sources(document, condition_id, tmp_path / "sources")
    step = _step(qtbot, monkeypatch, document)
    editor = step.editor
    cards = [editor.base_source, editor.t1_source, editor.isi_source, editor.t2_source]
    assert [editor.source_shelf.layout().itemAt(index).widget() for index in range(4)] == cards
    for field, text in ((editor.rate_spin, "4"), (editor.target_spin, "25"),
                        (editor.isi_spin, "75")):
        assert field.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
        field.setFocus()
        field.selectAll()
        qtbot.keyClicks(field, text)
        qtbot.keyClick(field, Qt.Key.Key_Tab)
        assert field.value() == float(text)
        qtbot.keyClick(field, Qt.Key.Key_Up)
        assert field.value() == float(text)
    assert editor.t2_value.text() == "150 ms"
    assert editor.apply_pending_design()
    settings = document.get_condition(condition_id).attentional_blink
    assert (settings.t1_duration_ms, settings.isi_ms) == (25, 75)


@pytest.mark.parametrize("dark", [False, True])
def test_isi_choice_hides_optional_folder_and_survives_save(qtbot, monkeypatch, tmp_path, dark):
    document = _document(tmp_path)
    condition_id = document.create_condition(name="Separate source pools")
    _populate_sources(document, condition_id, tmp_path / "sources")
    step = _step(qtbot, monkeypatch, document)
    editor = step.editor
    palette = QPalette(step.palette())
    palette.setColor(QPalette.ColorRole.Window, QColor("#202124" if dark else "#f4f7fb"))
    step.setPalette(palette)
    condition = document.get_condition(condition_id)
    assert len({condition.base_stimulus_set_id, condition.oddball_stimulus_set_id,
                condition.t2_stimulus_set_id, condition.isi_stimulus_set_id}) == 4
    assert editor.isi_source.folder_button.isVisible()
    qtbot.mouseClick(editor.isi_blank_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert not editor.isi_source.folder_button.isVisible()
    assert editor.slot_canvas.isi_blank
    editor.preview_button.setChecked(True)
    editor._preview_segments = [("separator", 50.0, 3)]
    editor._preview_index = -1
    editor._advance_preview()
    assert editor.preview_image.pixmap().toImage().pixelColor(0, 0) == QColor(
        document.project.settings.display.background_color
    )
    assert "BLANK ISI" in editor.preview_phase_label.text()
    editor._stop_preview()
    assert editor.apply_pending_design()
    document.save()
    assert document.get_condition(condition_id).attentional_blink.isi_mode == "blank"
    assert_visible_children_within_parent(step)
    qtbot.mouseClick(editor.isi_image_button, Qt.MouseButton.LeftButton)
    assert editor.isi_source.folder_button.isVisible()
    assert editor.apply_pending_design()
    assert document.get_condition(condition_id).attentional_blink.isi_mode == "image"


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("size", [(1120, 820), (1448, 1086)])
def test_full_window_design_fits_taller_default(qtbot, qapp, controller, tmp_path, dark, size):
    original_palette = qapp.palette()
    qapp.setPalette(QPalette(QColor("#202124" if dark else "#f4f7fb")))
    document = _document(tmp_path)
    condition_id = document.create_condition(name="Attentional blink with separate image pools")
    _populate_sources(document, condition_id, tmp_path / "sources")
    document.save()
    controller.open_project(document.project_root)
    window = controller.main_window
    qtbot.addWidget(window)
    window.show_setup_wizard(step_key="design")
    window.setup_wizard_page.open_wizard(step_key="design", allow_step_jumps=True)
    window.resize(*size)
    window.show()
    qtbot.waitUntil(lambda: not window.setup_wizard_page.design_setup_step.is_busy())
    QApplication.processEvents()
    assert (window.width(), window.height()) == size
    step = window.setup_wizard_page.design_setup_step
    assert step.isVisible()
    container = window.setup_wizard_page.shell.page_container.scroll_area
    assert container.widget().width() <= container.viewport().width(), (
        container.widget().size(), container.viewport().size())
    assert_visible_children_within_parent(step)
    assert window.setup_wizard_page.shell.title_label.text() == "Design your sequence"
    assert window.setup_wizard_page.design_step_count_label.isVisible()
    assert not step.editor.apply_button.isVisible()
    assert step.editor.source_heading_widget.isVisible()
    assert step.editor.slot_header_widget.isVisible()
    assert window.setup_wizard_page.step_card.property("wizardProjectStepFrame") == "true"
    if Path("build").is_dir():
        window.grab().save(f"build/isi-design-{'dark' if dark else 'light'}.png")
    qtbot.mouseClick(step.editor.isi_blank_button, Qt.MouseButton.LeftButton)
    step.editor.target_spin.setValue(15)
    QApplication.processEvents()
    assert_visible_children_within_parent(step)
    editor = step.editor
    assert editor.slot_canvas.mapTo(step, editor.slot_canvas.rect().bottomLeft()).y() < (
        editor.timing_controls.mapTo(step, QPoint(0, 0)).y()
    )
    assert editor.t2_value.text() == "185 ms"
    assert editor.used_label.text() == "250 ms · Slot 4"
    assert editor.isi_blank_preview.isVisible()
    assert not editor.isi_source.path_widget.isVisible()
    source_titles = [card.title_label for card in (
        step.editor.base_source, step.editor.t1_source,
        step.editor.isi_source, step.editor.t2_source,
    )]
    title_tops = [label.mapTo(step, QPoint(0, 0)).y() for label in source_titles]
    assert max(title_tops) - min(title_tops) <= 5
    if Path("build").is_dir():
        window.grab().save(f"build/designer-parity-{size[0]}-{'dark' if dark else 'light'}.png")
    qapp.setPalette(original_palette)


def test_next_applies_valid_design_without_saving_and_blocks_invalid_timing(
    qtbot, monkeypatch, controller, tmp_path
):
    document = _document(tmp_path)
    condition_id = document.create_condition(name="Next applies this design")
    _populate_sources(document, condition_id, tmp_path / "sources")
    document.save()
    controller.open_project(document.project_root)
    window = controller.main_window
    qtbot.addWidget(window)
    window.show_setup_wizard(step_key="design", allow_step_jumps=True)
    wizard = window.setup_wizard_page
    editor = wizard.design_setup_step.editor
    qtbot.waitUntil(lambda: not editor.is_busy())
    # Image normalization is a separately covered handoff; no launch or modal here.
    monkeypatch.setattr(
        wizard, "_start_condition_image_readiness_scan", wizard._advance_to_next_step
    )
    editor.target_spin.setValue(15)
    editor.isi_spin.setValue(260)
    qtbot.waitUntil(lambda: not wizard.setup_wizard_next_button.isEnabled())
    qtbot.mouseClick(wizard.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    assert wizard._current_step_key() == "design"
    assert editor._document.get_condition(condition_id).attentional_blink.t1_duration_ms == 50
    editor.isi_spin.setValue(50)
    qtbot.waitUntil(lambda: wizard.setup_wizard_next_button.isEnabled())
    assert wizard.setup_wizard_next_hint_label.text() == "Changes apply when you select Next."
    qtbot.mouseClick(wizard.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: wizard._current_step_key() == "experiment")
    assert editor._document.get_condition(condition_id).attentional_blink.t1_duration_ms == 15
    saved = json.loads((document.project_root / "project.json").read_text(encoding="utf-8"))
    assert saved["conditions"][0]["attentional_blink"]["t1_duration_ms"] == 50
    assert wizard.shell.title_label.text() == "Setup Wizard"
    assert not wizard.design_step_count_label.isVisible()


def test_word_condition_keeps_ordinary_word_authoring(qtbot, monkeypatch, tmp_path):
    document = _document(tmp_path, ExperimentCategory.FPVS_ODDBALL)
    condition_id = document.create_condition(name="Recognition words")
    document.set_condition_stimulus_modality(condition_id, modality=StimulusModality.WORD)
    step = _step(qtbot, monkeypatch, document)
    assert step.editor is None
    assert "word lists" in step.status_label.text()
    assert step.apply_pending_design()
    assert (
        document.get_condition_stimulus_set(condition_id, "base").modality == StimulusModality.WORD
    )


def test_condition_switch_applies_valid_pending_timing_and_blocks_invalid_draft(
    qtbot, monkeypatch, tmp_path
):
    document = _document(tmp_path)
    first = document.create_condition(name="First condition")
    second = document.create_condition(name="Second condition")
    _populate_sources(document, first, tmp_path / "first-sources")
    step = _step(qtbot, monkeypatch, document)
    assert step.selected_condition_id() == first
    assert step.editor is not None
    step.editor.isi_spin.setValue(260.0)

    assert not step.select_condition(second)
    assert step.selected_condition_id() == first
    assert step.condition_combo.currentData() == first
    assert step.has_pending_design()
    QApplication.processEvents()
    assert (step.width(), step.height()) == (1000, 600)
    step.editor.isi_spin.setValue(75.0)
    assert step.select_condition(second), step.validation_message()
    assert document.get_condition(first).attentional_blink.isi_ms == 75.0
    assert document.get_condition(second).attentional_blink.isi_ms == 50.0
    assert step.selected_condition_id() == second
    assert not step.has_pending_design()


def test_missing_image_folders_block_navigation_with_inline_guidance(qtbot, monkeypatch, tmp_path):
    document = _document(tmp_path)
    document.create_condition(name="Select images next")
    step = _step(qtbot, monkeypatch, document)
    assert not step.apply_pending_design()
    assert "Choose images" in step.validation_message()
    assert step.editor is not None
    assert "Choose all image folders" == step.editor.summary_label.text()
    QApplication.processEvents()
    assert (step.width(), step.height()) == (1000, 600)
    assert_visible_children_within_parent(step)


def test_explicit_discard_restores_document_timing_and_waits_for_workers(
    qtbot, monkeypatch, tmp_path
):
    document = _document(tmp_path)
    condition_id = document.create_condition(name="Draft to discard")
    step = _step(qtbot, monkeypatch, document)
    assert step.editor is not None
    step.editor.isi_spin.setValue(260.0)
    step.editor._thumbnail_task = object()
    assert not step.discard_pending_design()
    assert step.has_pending_design()
    step.editor._thumbnail_finished()
    assert step.discard_pending_design()
    assert step.editor is not None
    assert step.editor.isi_spin.value() == 50.0
    assert not step.has_pending_design()
    assert document.get_condition(condition_id).attentional_blink.isi_ms == 50.0


def test_busy_source_import_prevents_condition_switch_and_navigation(
    qtbot, monkeypatch, tmp_path
):
    document = _document(tmp_path)
    first = document.create_condition(name="First condition")
    second = document.create_condition(name="Second condition")
    step = _step(qtbot, monkeypatch, document)
    assert step.editor is not None
    step.editor._task = object()
    step.editor._refresh_preview()
    assert step.is_busy()
    assert step.is_importing()
    assert not step.condition_combo.isEnabled()
    assert not step.select_condition(second)
    assert not step.apply_pending_design()
    assert step.selected_condition_id() == first
    step.editor._import_finished()
    assert not step.is_busy()
    assert step.condition_combo.isEnabled()


def test_thumbnail_decoding_allows_apply_but_defers_condition_disposal(
    qtbot, monkeypatch, tmp_path
):
    document = _document(tmp_path)
    first = document.create_condition(name="First condition")
    second = document.create_condition(name="Second condition")
    _populate_sources(document, first, tmp_path / "first-sources")
    step = _step(qtbot, monkeypatch, document)
    assert step.editor is not None
    step.editor.isi_spin.setValue(75.0)
    step.editor._thumbnail_task = object()
    step.editor._refresh_preview()
    assert step.is_busy()
    assert not step.is_importing()
    assert not step.editor.preview_button.isEnabled()
    assert step.apply_pending_design()
    assert document.get_condition(first).attentional_blink.isi_ms == 75.0
    assert not step.select_condition(second)
    step.editor._thumbnail_finished()
    assert step.select_condition(second)


def test_import_state_changes_notify_navigation_even_during_thumbnail_loading(
    qtbot, monkeypatch, tmp_path
):
    document = _document(tmp_path)
    document.create_condition(name="Concurrent source tasks")
    step = _step(qtbot, monkeypatch, document)
    assert step.editor is not None
    transitions = []
    step.busy_changed.connect(lambda busy: transitions.append((busy, step.is_importing())))
    step.editor._thumbnail_task = object()
    step.editor._refresh_preview()
    step.editor._task = object()
    step.editor._refresh_preview()
    step.editor._import_finished()
    step.editor._thumbnail_finished()
    assert transitions == [(True, False), (True, True), (True, False), (False, False)]


def test_document_source_updates_during_thumbnail_loading_refresh_after_completion(
    qtbot, monkeypatch, tmp_path
):
    document = _document(tmp_path)
    condition_id = document.create_condition(name="Sources change during decoding")
    step = _step(qtbot, monkeypatch, document)
    assert step.editor is not None
    step.editor.isi_spin.setValue(75.0)
    step.editor._thumbnail_task = object()
    step.editor._refresh_preview()

    _populate_sources(document, condition_id, tmp_path / "incoming")

    assert step.editor._refresh_pending
    assert not step.editor.apply_button.isEnabled()
    step.editor._thumbnail_finished()
    assert not step.editor._refresh_pending
    assert all(card.source_count == 2 for card in step.editor._cards().values())
    assert step.editor.apply_button.isEnabled()
    assert step.editor.isi_spin.value() == 75.0
    assert step.has_pending_design()


def test_hidden_embedded_refresh_defers_thumbnail_work_until_shown(
    qtbot, monkeypatch, tmp_path
):
    decoded_sources = []

    def decode(project_root, sources):
        decoded_sources.append(sources)
        return load_designer_thumbnails(project_root, sources)

    monkeypatch.setattr(
        "fpvs_studio.gui.experiment_designer_dialog.load_designer_thumbnails", decode
    )
    document = _document(tmp_path)
    condition_id = document.create_condition(name="Hidden Design sources")
    step = DesignSetupStep(document)
    qtbot.addWidget(step)
    assert step.editor is not None

    _populate_sources(document, condition_id, tmp_path / "incoming")
    document.update_protocol_settings(base_hz=5.0)
    document.save()
    QApplication.processEvents()

    assert decoded_sources == []
    assert not step.is_busy()
    assert step.editor._thumbnail_pending
    assert all(card.source_count == 2 for card in step.editor._cards().values())
    assert step.editor.rate_spin.value() == 5.0
    assert step.editor.t2_value.text() == "100 ms"
    step.resize(1000, 600)
    step.show()
    qtbot.waitUntil(lambda: bool(decoded_sources) and not step.is_busy())
    assert len(decoded_sources) == 1
    assert not step.editor._thumbnail_pending
    assert all(step.editor._pixmaps[role] for role in ("base", "t1", "t2"))
    assert step.editor._pixmaps["t2"][0].toImage().pixelColor(0, 0) == QColor(20, 10, 5)

    step.hide()
    document.save()
    QApplication.processEvents()
    assert len(decoded_sources) == 1
    assert not step.is_busy()
    assert step.editor._thumbnail_pending
    assert step.editor.request_close()
    step.show()
    QApplication.processEvents()
    assert len(decoded_sources) == 1
    assert not step.is_busy()


def test_legacy_mixed_condition_requires_separation_and_is_not_converted(
    qtbot, monkeypatch, tmp_path
):
    document = _document(tmp_path)
    condition_id = document.create_condition(name="Legacy oddball condition")
    condition = document.get_condition(condition_id)
    condition.attentional_blink = None
    before = document.project.model_copy(deep=True)
    step = _step(qtbot, monkeypatch, document)
    assert step.editor is None
    assert "separate" in step.status_label.text().lower()
    assert not step.apply_pending_design()
    assert document.project == before


def test_refresh_retains_pending_edits_and_updates_saved_external_timing(
    qtbot, monkeypatch, tmp_path
):
    document = _document(tmp_path)
    document.create_condition(name="Image condition")
    step = _step(qtbot, monkeypatch, document)
    assert step.editor is not None
    step.editor.isi_spin.setValue(75.0)
    editor = step.editor
    step.refresh()
    assert step.editor is editor
    assert step.editor.isi_spin.value() == 75.0
    assert step.has_pending_design()


@pytest.mark.parametrize(
    "category", [ExperimentCategory.FPVS_ODDBALL, ExperimentCategory.ATTENTIONAL_BLINK]
)
@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("invalid", [False, True])
def test_embedded_design_fits_the_wizard_content_budget(
    qtbot, monkeypatch, tmp_path: Path, category, dark, invalid
):
    document = _document(tmp_path, category)
    document.create_condition(
        name="Long condition name for familiar and unfamiliar natural objects"
    )
    step = _step(qtbot, monkeypatch, document)
    palette = QPalette(step.palette())
    palette.setColor(QPalette.ColorRole.Window, QColor("#202124" if dark else "#f4f7fb"))
    step.setPalette(palette)
    assert step.editor is not None
    for card in step.editor._cards().values():
        card.set_source(1000, "C:/Long source/" + "reviewed picture collections/" * 6, ())
    if invalid:
        step.editor.cycle_canvas.set_roles(("base",))
    QApplication.processEvents()
    assert (step.width(), step.height()) == (1000, 600)
    assert step.minimumSizeHint().height() <= 600
    assert_visible_children_within_parent(step)
    assert not step.findChildren(QTabBar)
    assert step.editor.slot_panel.isVisible() == (category == ExperimentCategory.ATTENTIONAL_BLINK)
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
