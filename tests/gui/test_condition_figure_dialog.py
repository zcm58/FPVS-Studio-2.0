"""Registered visible coverage for the Condition Figure tool and its worker states."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QLabel
from tests.gui.helpers import (
    assert_visible_children_within_parent,
    open_created_project,
    write_image_directory,
)

from fpvs_studio.gui import condition_figure_dialog as figure_dialog
from fpvs_studio.gui.action_palette import ActionPaletteDialog
from fpvs_studio.gui.condition_figure_dialog import ConditionFigureDialog
from fpvs_studio.tools.condition_figure import ConditionFigureResult
from fpvs_studio.tools.condition_figure_project import ConditionFigureSources


class _HeldTask(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def start(self) -> None:
        pass

    def deliver(self) -> None:
        try:
            result = self.callback()
        except Exception as error:
            self.failed.emit(error)
        else:
            self.succeeded.emit(result)

    def complete(self) -> None:
        self.deliver()
        self.finished.emit()


@pytest.fixture
def figure_jobs(monkeypatch, tmp_path):
    tasks = []

    def task(*, callback, **_kwargs):
        held = _HeldTask(callback)
        tasks.append(held)
        return held

    base_dir = write_image_directory(tmp_path / "base", count=5)
    oddball_dir = write_image_directory(tmp_path / "oddball", size=(112, 96), count=2)
    sources = ConditionFigureSources(
        "Faces", 6.0, 5,
        tuple(sorted(base_dir.glob("*.png"))),
        tuple(sorted(oddball_dir.glob("*.png"))),
    )
    load = Mock(return_value=sources)
    choose = Mock(return_value=None)
    guard = Mock()
    render = Mock(side_effect=lambda spec, path: ConditionFigureResult(
        path, ("Base 1 has limited source resolution.",),
    ))
    monkeypatch.setattr(figure_dialog, "BackgroundTask", task)
    monkeypatch.setattr(figure_dialog, "load_condition_figure_sources", load)
    monkeypatch.setattr(figure_dialog, "_choose_figure_path", choose)
    monkeypatch.setattr(figure_dialog, "validate_condition_figure_destination", guard)
    monkeypatch.setattr(figure_dialog, "render_condition_figure", render)
    return SimpleNamespace(
        tasks=tasks, sources=sources, load=load, choose=choose, guard=guard, render=render,
    )


def _open_dialog(qtbot, project, project_root):
    dialog = ConditionFigureDialog(project, project_root)
    qtbot.addWidget(dialog)
    dialog.open()
    QApplication.processEvents()
    return dialog


def _assert_geometry(qtbot, dialog, size):
    QApplication.processEvents()
    assert dialog.minimumSize().toTuple() == (860, 520)
    assert dialog.size().toTuple() == size
    labels = [label for label in dialog.findChildren(QLabel) if label.isVisible() and label.text()]
    qtbot.waitUntil(lambda: all(
        label.height() >= label.heightForWidth(label.width())
        for label in labels if label.wordWrap()
    ))
    assert_visible_children_within_parent(dialog)
    for label in labels:
        if not label.wordWrap():
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())


def test_automatic_defaults_load_five_previews_and_fit_both_sizes(
    qtbot, sample_project, tmp_path, figure_jobs,
):
    long_name = "Longest realistic condition label " * 9
    sample_project.conditions[0].name = long_name
    dialog = _open_dialog(qtbot, sample_project, tmp_path)
    assert dialog.has_active_task
    assert dialog.mode_combo.currentText() == "Automatic"
    assert not dialog.export_button.isEnabled()
    _assert_geometry(qtbot, dialog, (920, 560))
    figure_jobs.tasks[-1].complete()

    assert [combo.currentIndex() for combo in dialog.stimulus_combos] == [0, 1, 2, 3, 0]
    assert not any(combo.isEnabled() for combo in dialog.stimulus_combos)
    assert all(not preview.pixmap().isNull() for preview in dialog.preview_labels)
    assert dialog.export_button.isEnabled()
    assert long_name in dialog.condition_combo.toolTip()
    assert str(figure_jobs.sources.base_stimuli[0]) in dialog.stimulus_combos[0].toolTip()
    assert "Some slots have no unused stimulus." in dialog.status_label.text()
    dialog.resize(860, 520)
    _assert_geometry(qtbot, dialog, (860, 520))


def test_short_automatic_pool_marks_missing_previews_and_reuses_worker_picks(
    qtbot, sample_project, tmp_path, figure_jobs, monkeypatch,
):
    sources = replace(figure_jobs.sources, base_stimuli=figure_jobs.sources.base_stimuli[:2])
    figure_jobs.load.return_value = sources
    automatic_spec = Mock(wraps=sources.automatic_spec)
    monkeypatch.setattr(ConditionFigureSources, "automatic_spec", automatic_spec)
    dialog = _open_dialog(qtbot, sample_project, tmp_path)
    automatic_spec.assert_not_called()
    figure_jobs.tasks[-1].complete()

    assert [combo.currentIndex() for combo in dialog.stimulus_combos] == [0, 1, -1, -1, 0]
    for preview in dialog.preview_labels[2:4]:
        assert preview.text() == "No example"
        assert preview.accessibleDescription() == "No example"
    assert dialog.export_button.isEnabled()
    dialog.resize(860, 520)
    _assert_geometry(qtbot, dialog, (860, 520))

    dialog.mode_combo.setCurrentText("Manual")
    figure_jobs.tasks[-1].complete()
    assert [combo.currentIndex() for combo in dialog.stimulus_combos] == [0, 1, 0, 1, 0]
    assert all(not preview.pixmap().isNull() for preview in dialog.preview_labels)

    dialog.mode_combo.setCurrentText("Automatic")
    assert not dialog.has_active_task
    assert dialog.preview_labels[2].text() == "No example"
    figure_jobs.choose.return_value = tmp_path / "automatic.png"
    qtbot.mouseClick(dialog.export_button, Qt.MouseButton.LeftButton)
    figure_jobs.tasks[-1].complete()

    spec, _ = figure_jobs.render.call_args.args
    samples = [sample for sample in spec.sequence_stimuli if sample is not None]
    assert len(samples) == len(set(samples)) == 4
    automatic_spec.assert_called_once_with()


def test_manual_export_snapshots_choices_and_waits_for_cleanup(
    qtbot, sample_project, tmp_path, figure_jobs,
):
    dialog = _open_dialog(qtbot, sample_project, tmp_path)
    figure_jobs.tasks[-1].complete()
    dialog.mode_combo.setCurrentText("Manual")
    assert all(combo.isEnabled() for combo in dialog.stimulus_combos)
    dialog.stimulus_combos[0].setCurrentIndex(4)
    figure_jobs.tasks[-1].complete()
    dialog.stimulus_combos[-1].setCurrentIndex(1)
    figure_jobs.tasks[-1].complete()

    qtbot.mouseClick(dialog.export_button, Qt.MouseButton.LeftButton)
    assert len(figure_jobs.tasks) == 3  # Canceled Save As leaves the selection in place.
    figure_jobs.guard.assert_not_called()
    figure_jobs.render.assert_not_called()

    output = tmp_path / ("long-figure-filename-" * 6 + "final.png")
    figure_jobs.choose.return_value = output
    qtbot.mouseClick(dialog.export_button, Qt.MouseButton.LeftButton)
    assert dialog.has_active_task
    assert not dialog.close_button.isEnabled()
    assert not dialog.export_button.isEnabled()
    dialog.close()
    assert dialog.isVisible()
    export_task = figure_jobs.tasks[-1]
    export_task.deliver()
    assert dialog.has_active_task
    export_task.finished.emit()
    assert not dialog.has_active_task

    spec, selected_path = figure_jobs.render.call_args.args
    assert selected_path == output
    assert spec.sequence_stimuli is None
    assert spec.base_stimuli[0] == figure_jobs.sources.base_stimuli[4]
    assert spec.oddball_stimulus == figure_jobs.sources.oddball_stimuli[1]
    assert figure_jobs.guard.call_args.args[1:] == (tmp_path, output)
    assert str(output) in dialog.output_path_label.toolTip()
    assert "limited source resolution" in dialog.status_label.text()
    dialog.resize(860, 520)
    _assert_geometry(qtbot, dialog, (860, 520))

    dialog.mode_combo.setCurrentText("Automatic")
    assert not dialog.has_active_task
    assert [combo.currentIndex() for combo in dialog.stimulus_combos] == [0, 1, 2, 3, 0]
    assert not dialog.output_path_label.isVisible()


def test_rejected_output_keeps_choices_available(qtbot, sample_project, tmp_path, figure_jobs):
    dialog = _open_dialog(qtbot, sample_project, tmp_path)
    figure_jobs.tasks[-1].complete()
    figure_jobs.choose.return_value = tmp_path / "stimuli" / "image.png"
    figure_jobs.guard.side_effect = ValueError("Choose a location outside the stimulus folders.")
    qtbot.mouseClick(dialog.export_button, Qt.MouseButton.LeftButton)
    figure_jobs.tasks[-1].complete()

    figure_jobs.render.assert_not_called()
    assert "outside the stimulus folders" in dialog.status_label.accessibleDescription()
    assert dialog.export_button.isEnabled()
    assert dialog.close_button.isEnabled()
    dialog.resize(860, 520)
    _assert_geometry(qtbot, dialog, (860, 520))


def test_stale_condition_load_does_not_show_old_stimuli(
    qtbot, sample_project, tmp_path, figure_jobs,
):
    sample_project.conditions.append(sample_project.conditions[0].model_copy(update={
        "condition_id": "second-condition", "name": "Second condition", "order_index": 1,
    }))
    dialog = _open_dialog(qtbot, sample_project, tmp_path)
    first_task = figure_jobs.tasks[-1]
    dialog.condition_combo.setCurrentIndex(1)
    first_task.complete()
    assert len(figure_jobs.tasks) == 2
    assert dialog.stimulus_combos[0].count() == 0
    figure_jobs.tasks[-1].complete()
    assert figure_jobs.load.call_args.args[2] == "second-condition"
    assert dialog.export_button.isEnabled()


def test_tools_and_find_action_open_the_current_project_without_writes(
    qtbot, controller, tmp_path, figure_jobs,
):
    document, window = open_created_project(controller, qtbot, tmp_path, "Figure Tool")
    before = document.project.model_dump(mode="json")
    assert window.condition_figure_action in window.tools_menu.actions()
    window.condition_figure_action.trigger()
    dialog = window.findChild(ConditionFigureDialog)
    assert dialog is not None and dialog.isVisible()
    if figure_jobs.tasks:
        figure_jobs.tasks[-1].complete()
    assert dialog._project_root == document.project_root
    assert dialog._project.model_dump(mode="json") == before
    dialog.close()
    qtbot.waitUntil(lambda: window.findChild(ConditionFigureDialog) is None)

    window.find_action_action.trigger()
    palette = window.findChild(ActionPaletteDialog)
    assert palette is not None and palette.isVisible()
    palette.search_edit.setText("condition figure")
    qtbot.keyClick(palette.search_edit, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: window.findChild(ConditionFigureDialog) is not None)
    reopened = window.findChild(ConditionFigureDialog)
    assert reopened is not None and reopened.isVisible()
    if reopened.has_active_task:
        figure_jobs.tasks[-1].complete()
    assert document.project.model_dump(mode="json") == before
    figure_jobs.guard.assert_not_called()
    figure_jobs.render.assert_not_called()
    reopened.close()
