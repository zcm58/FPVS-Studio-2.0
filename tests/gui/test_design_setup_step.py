"""The shared visual editor fits the dedicated, category-locked Design step."""

from __future__ import annotations

from pathlib import Path
from threading import Event

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTabBar
from tests.gui.helpers import assert_visible_children_within_parent, write_image_directory
from tests.gui.test_experiment_designer import _populate_sources

from fpvs_studio.core.enums import ExperimentCategory, StimulusModality
from fpvs_studio.gui.design_setup_step import DesignSetupStep
from fpvs_studio.gui.designer_sources import load_designer_thumbnails
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.experiment_designer_dialog import ExperimentDesignerWidget


def _document(tmp_path, category=ExperimentCategory.FPVS_ODDBALL):
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


def test_missing_image_folders_block_navigation_with_inline_guidance(qtbot, monkeypatch, tmp_path):
    document = _document(tmp_path)
    document.create_condition(name="Select images next")
    step = _step(qtbot, monkeypatch, document)
    assert not step.apply_pending_design()
    assert "Choose Base and Oddball images" in step.validation_message()
    assert step.editor is not None
    assert "Choose all image folders" == step.editor.summary_label.text()
    QApplication.processEvents()
    assert (step.width(), step.height()) == (1000, 600)
    assert_visible_children_within_parent(step)


def test_explicit_discard_restores_document_timing_and_waits_for_workers(
    qtbot, monkeypatch, tmp_path
):
    document = _document(tmp_path)
    document.create_condition(name="Draft to discard")
    step = _step(qtbot, monkeypatch, document)
    assert step.editor is not None
    step.editor.rate_spin.setValue(4.0)
    step.editor._thumbnail_task = object()
    assert not step.discard_pending_design()
    assert step.has_pending_design()
    step.editor._thumbnail_finished()
    assert step.discard_pending_design()
    assert step.editor is not None
    assert step.editor.rate_spin.value() == 6.0
    assert not step.has_pending_design()
    assert document.project.settings.protocol.base_hz == 6.0


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
    step.editor.rate_spin.setValue(4.0)
    step.editor._thumbnail_task = object()
    step.editor._refresh_preview()
    assert step.is_busy()
    assert not step.is_importing()
    assert not step.editor.preview_button.isEnabled()
    assert step.apply_pending_design()
    assert document.project.settings.protocol.base_hz == 4.0
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
    step.editor.rate_spin.setValue(4.0)
    step.editor._thumbnail_task = object()
    step.editor._refresh_preview()

    _populate_sources(document, condition_id, tmp_path / "incoming")

    assert step.editor._refresh_pending
    assert not step.editor.apply_button.isEnabled()
    step.editor._thumbnail_finished()
    assert not step.editor._refresh_pending
    assert all(card.source_count == 2 for card in step.editor._cards().values())
    assert step.editor.apply_button.isEnabled()
    assert step.editor.rate_spin.value() == 4.0
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
    step.resize(1000, 600)
    step.show()
    qtbot.waitUntil(lambda: bool(decoded_sources) and not step.is_busy())
    assert len(decoded_sources) == 1
    assert not step.editor._thumbnail_pending
    assert all(step.editor._pixmaps[role] for role in ("base", "t1"))
    assert step.editor._pixmaps["t1"][0].toImage().pixelColor(0, 0) == QColor(20, 10, 5)

    step.hide()
    document.save()
    QApplication.processEvents()
    assert len(decoded_sources) == 1
    assert not step.is_busy()
    assert not step.editor._thumbnail_pending
    assert step.editor.request_close()
    step.show()
    QApplication.processEvents()
    assert len(decoded_sources) == 1
    assert not step.is_busy()


def test_refresh_retains_pending_edits_and_updates_saved_external_timing(
    qtbot, monkeypatch, tmp_path
):
    document = _document(tmp_path)
    document.create_condition(name="Image condition")
    step = _step(qtbot, monkeypatch, document)
    assert step.editor is not None
    step.editor.rate_spin.setValue(4.0)
    editor = step.editor
    step.refresh()
    assert step.editor is editor
    assert step.editor.rate_spin.value() == 4.0
    assert step.has_pending_design()


def test_design_reuses_thumbnails_until_image_sources_change(qtbot, monkeypatch, tmp_path):
    decoded_sources = []

    def decode(root, sources):
        decoded_sources.append(sources)
        return load_designer_thumbnails(root, sources)

    monkeypatch.setattr(
        "fpvs_studio.gui.experiment_designer_dialog.load_designer_thumbnails", decode,
    )
    document = _document(tmp_path)
    condition_id = document.create_condition(name="Cached source previews")
    _populate_sources(document, condition_id, tmp_path / "first")
    step = DesignSetupStep(document)
    qtbot.addWidget(step)
    step.resize(1000, 600)
    step.show()
    qtbot.waitUntil(lambda: bool(decoded_sources) and not step.is_busy())
    editor = step.editor
    assert editor is not None
    initial = len(decoded_sources)
    pixmap_key = editor._pixmaps["base"][0].cacheKey()
    for _ in range(3):
        document.update_project_description("Only the description changed")
        editor.refresh_sources()
        step.hide()
        step.show()
        QApplication.processEvents()
        qtbot.waitUntil(lambda: not step.is_busy())
    assert len(decoded_sources) == initial
    assert editor._pixmaps["base"][0].cacheKey() == pixmap_key

    replacement = write_image_directory(tmp_path / "replacement", count=3)
    monkeypatch.setattr(
        "fpvs_studio.gui.experiment_designer_dialog.QFileDialog.getExistingDirectory",
        lambda *args: str(replacement),
    )
    editor._choose_source("base")
    qtbot.waitUntil(lambda: len(decoded_sources) > initial and not step.is_busy())
    assert editor._pixmaps["base"][0].cacheKey() != pixmap_key


def test_thumbnail_retry_clears_the_previous_error(qtbot, monkeypatch, tmp_path):
    calls = []

    def decode(root, sources):
        calls.append(sources)
        if len(calls) == 1:
            raise ValueError("Temporarily unavailable image")
        return load_designer_thumbnails(root, sources)

    monkeypatch.setattr(
        "fpvs_studio.gui.experiment_designer_dialog.load_designer_thumbnails", decode,
    )
    document = _document(tmp_path)
    condition_id = document.create_condition(name="Preview retry")
    _populate_sources(document, condition_id, tmp_path / "images")
    step = DesignSetupStep(document)
    qtbot.addWidget(step)
    step.show()
    qtbot.waitUntil(lambda: len(calls) == 1 and not step.is_busy())
    editor = step.editor
    assert "Temporarily unavailable" in editor.status_label.text()
    editor.refresh_sources()
    qtbot.waitUntil(lambda: len(calls) == 2 and not step.is_busy())
    assert editor._pixmaps["base"]
    assert not editor.status_label.isVisible()


def test_preview_loading_is_visible_and_fits_the_design_surface(qtbot, monkeypatch, tmp_path):
    entered, release = Event(), Event()

    def decode(root, sources):
        entered.set()
        assert release.wait(5)
        return load_designer_thumbnails(root, sources)

    monkeypatch.setattr(
        "fpvs_studio.gui.experiment_designer_dialog.load_designer_thumbnails", decode,
    )
    document = _document(tmp_path)
    condition_id = document.create_condition(name="Loading previews")
    _populate_sources(document, condition_id, tmp_path / "images")
    step = DesignSetupStep(document)
    qtbot.addWidget(step)
    step.resize(1000, 570)
    step.show()
    try:
        qtbot.waitUntil(entered.is_set)
        QApplication.processEvents()
        assert_visible_children_within_parent(step)
        for card in step.editor._cards().values():
            assert card.count_label.text() == "Loading previews…"
            assert card.count_label.width() >= card.count_label.fontMetrics().horizontalAdvance(
                card.count_label.text()
            )
    finally:
        release.set()
        qtbot.waitUntil(lambda: not step.is_busy())
    assert all(card.count_label.text() == "2 images" for card in step.editor._cards().values())


@pytest.mark.parametrize(
    "category", [ExperimentCategory.FPVS_ODDBALL]
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


def test_retired_image_pairs_show_explanation_instead_of_editor(qtbot, monkeypatch, tmp_path):
    from fpvs_studio.core.models import AttentionalBlinkSettings

    document = _document(tmp_path)
    condition_id = document.create_condition(name="Archived image pairs")
    document._project = document.project.model_copy(
        update={"experiment_category": ExperimentCategory.ATTENTIONAL_BLINK}, deep=True
    )
    document.get_condition(condition_id).attentional_blink = AttentionalBlinkSettings()
    before = document.project.model_dump()
    step = _step(qtbot, monkeypatch, document)
    assert step.editor is None
    assert "no longer supported" in step.status_label.text()
    assert not step.apply_pending_design()
    with pytest.raises(ValueError, match="no longer supported"):
        ExperimentDesignerWidget(document, condition_id=condition_id)
    assert document.project.model_dump() == before
