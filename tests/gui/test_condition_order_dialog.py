"""Registered plain-list order editing, atomic saves and cancellation coverage."""

from __future__ import annotations

from threading import Event

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox
from tests.gui.helpers import assert_visible_children_within_parent
from tests.gui.test_condition_timing_table import _document

from fpvs_studio.core.randomization import RandomizationSeeds, configured_randomization_seeds
from fpvs_studio.gui.condition_order_dialog import ConditionOrderDialog
from fpvs_studio.gui.condition_timing_table import ConditionTimingTable
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.experiment_designer_dialog import ExperimentDesignerWidget
from fpvs_studio.gui.setup_wizard_page import SetupWizardPage
from fpvs_studio.gui.update_lifecycle import UpdateTaskResult


class _PreviewJob(QObject):
    finished = Signal(object)

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.cancel_event = Event()

    def cancel(self):
        self.cancel_event.set()

    def complete(self):
        try:
            value = self.callback(lambda *_args: None, self.cancel_event)
        except Exception as error:
            result = UpdateTaskResult(error=error)
        else:
            result = UpdateTaskResult(value=value, cancelled=self.cancel_event.is_set())
        self.finished.emit(result)


@pytest.fixture
def preview_jobs(monkeypatch):
    jobs = []

    class Lifecycle:
        def start_task(self, callback):
            job = _PreviewJob(callback)
            jobs.append(job)
            return job

    monkeypatch.setattr("fpvs_studio.gui.condition_order_dialog.update_lifecycle", Lifecycle)
    return jobs


def _open_dialog(qtbot, document, *, table=None):
    if table is None:
        table = ConditionTimingTable(document)
        qtbot.addWidget(table)

    def save(order, seeds):
        if not table.apply_condition_order(order, seeds):
            raise ValueError(table.error_label.text() or "Changes were not saved.")

    dialog = ConditionOrderDialog(
        document.project, seeds=configured_randomization_seeds(document.project),
        presentation_counts=table.pending_presentation_counts(),
        current_signature=table.order_edit_signature, save_order=save,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    return dialog, table


def test_preview_needs_no_assets_or_display_and_save_persists_exact_pending_counts(
    qtbot, monkeypatch, tmp_path, preview_jobs,
):
    document, first, second = _document(tmp_path)
    document.update_display_settings(preferred_refresh_hz=None)
    original = document.project.model_copy(deep=True)
    roots = configured_randomization_seeds(original)
    table = ConditionTimingTable(document)
    qtbot.addWidget(table)
    table.presentation_count_spins[first].setValue(3)
    dialog, _table = _open_dialog(qtbot, document, table=table)
    assert document.project == original
    assert not dialog.save_button.isEnabled()
    preview_jobs[-1].complete()
    assert dialog._order == [first, second, first, second, first]
    assert dialog.save_button.isEnabled()
    monkeypatch.setattr(
        "fpvs_studio.gui.condition_order_dialog.generate_randomization_seeds",
        lambda: RandomizationSeeds(condition_order_seed=777, stimulus_seed=888, fixation_seed=999),
    )
    dialog.generate_button.click()
    preview_jobs[-1].complete()
    assert dialog._seeds.stimulus_seed == roots.stimulus_seed
    assert dialog._seeds.fixation_seed == roots.fixation_seed
    dialog.save_button.click()
    assert dialog.result() == int(dialog.DialogCode.Accepted)
    reopened = ProjectDocument.open_existing(document.project_root)
    assert reopened.project.settings.session.saved_condition_order == (
        [first, second, first, second, first]
    )
    assert reopened.project.settings.session.randomization_mode == "fixed"
    assert reopened.project.settings.session.session_seed == 777
    assert reopened.project.settings.session.stimulus_seed == roots.stimulus_seed
    assert reopened.project.settings.session.fixation_seed == roots.fixation_seed
    assert reopened.get_condition(first).presentation_count == 3
    assert reopened.get_condition(first).stream_duration_seconds is None
    assert not document.dirty
    assert not table.has_pending_edits()


def test_manual_move_saves_chosen_list_and_renumbers_occurrences(qtbot, tmp_path, preview_jobs):
    document, first, second = _document(tmp_path)
    third = document.create_condition(name="Third condition")
    source_order = [first, second, third, first, second, third]
    document.update_condition_timing(
        saved_condition_order=source_order,
        order_seeds=configured_randomization_seeds(document.project),
    )
    dialog, _table = _open_dialog(qtbot, document)
    assert not preview_jobs
    dialog.order_list.setCurrentRow(5)
    dialog.move_up_button.click()
    expected = [first, second, third, first, third, second]
    assert dialog._order == expected
    assert "presentation 2" in dialog.order_list.item(4).text()
    assert "presentation 2" in dialog.order_list.item(5).text()
    dialog.save_button.click()
    assert document.project.settings.session.saved_condition_order == expected
    reopened = ProjectDocument.open_existing(document.project_root)
    assert reopened.project.settings.session.saved_condition_order == expected


def test_invalid_manual_adjacency_stays_editable_without_project_mutation(
    qtbot, tmp_path, preview_jobs,
):
    document, first, second = _document(tmp_path)
    order = [first, second, first, second]
    document.update_condition_timing(
        saved_condition_order=order, order_seeds=configured_randomization_seeds(document.project),
    )
    before = document.project.model_copy(deep=True)
    dialog, _table = _open_dialog(qtbot, document)
    dialog.order_list.setCurrentRow(1)
    dialog.move_down_button.click()
    assert not dialog.save_button.isEnabled()
    assert "adjacent" in dialog.error_label.text().lower()
    dialog.save()
    assert document.project == before
    assert dialog.result() != int(dialog.DialogCode.Accepted)
    dialog.move_up_button.click()
    assert dialog.save_button.isEnabled()
    assert dialog._order == order


def test_cancel_preserves_source_and_pending_parent_counts_and_cancels_worker(
    qtbot, tmp_path, preview_jobs,
):
    document, first, _second = _document(tmp_path)
    before = document.project.model_copy(deep=True)
    table = ConditionTimingTable(document)
    qtbot.addWidget(table)
    table.presentation_count_spins[first].setValue(3)
    dialog, _table = _open_dialog(qtbot, document, table=table)
    job = preview_jobs[-1]
    dialog.reject()
    assert job.cancel_event.is_set()
    job.complete()
    assert document.project == before
    assert table.pending_presentation_counts() == {first: 3}
    assert not dialog._order


@pytest.mark.parametrize("change", ["source", "counts"])
def test_stale_worker_and_save_results_never_replace_current_setup(
    qtbot, tmp_path, preview_jobs, change,
):
    document, first, _second = _document(tmp_path)
    dialog, table = _open_dialog(qtbot, document)
    if change == "source":
        document.update_condition(first, name="Updated while the dialog was open")
    else:
        table.presentation_count_spins[first].setValue(3)
    before = document.project.model_copy(deep=True)
    preview_jobs[-1].complete()
    assert "Setup changed" in dialog.error_label.text()
    assert not dialog.save_button.isEnabled()
    dialog.save()
    assert document.project == before
    assert document.project.settings.session.saved_condition_order is None


def test_save_failure_keeps_file_and_model_then_retry_persists_same_list(
    qtbot, monkeypatch, tmp_path, preview_jobs,
):
    from fpvs_studio.gui import document as document_module

    document, first, second = _document(tmp_path)
    document.save()
    before = document.project.model_copy(deep=True)
    saved_bytes = document.project_file_path.read_bytes()
    writer = document_module.save_project_file
    table = ConditionTimingTable(document)
    qtbot.addWidget(table)
    table.presentation_count_spins[first].setValue(3)
    dialog, _table = _open_dialog(qtbot, document, table=table)
    preview_jobs[-1].complete()

    def fail(*_args):
        raise OSError("Disk unavailable. Retry Save.")

    monkeypatch.setattr(document_module, "save_project_file", fail)
    dialog.save()
    assert "Disk unavailable" in dialog.error_label.text()
    assert document.project == before
    assert document.project_file_path.read_bytes() == saved_bytes
    assert table.pending_presentation_counts() == {first: 3}
    monkeypatch.setattr(document_module, "save_project_file", writer)
    dialog.save()
    reopened = ProjectDocument.open_existing(document.project_root)
    assert reopened.project.settings.session.saved_condition_order == (
        [first, second, first, second, first]
    )


def test_declining_frequency_confirmation_preserves_project_and_file(
    qtbot, monkeypatch, tmp_path, preview_jobs,
):
    document, first, _second = _document(tmp_path)
    document.save()
    before = document.project.model_copy(deep=True)
    saved_bytes = document.project_file_path.read_bytes()
    table = ConditionTimingTable(document)
    qtbot.addWidget(table)
    table.frequency_spins[first].setValue(4)
    table.presentation_count_spins[first].setValue(3)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No)
    dialog, _table = _open_dialog(qtbot, document, table=table)
    preview_jobs[-1].complete()
    dialog.save()
    assert document.project == before
    assert document.project_file_path.read_bytes() == saved_bytes
    assert dialog.result() != int(dialog.DialogCode.Accepted)


def test_pending_count_change_can_replace_stale_saved_order_in_one_save(
    qtbot, tmp_path, preview_jobs,
):
    document, first, second = _document(tmp_path)
    document.update_condition_timing(
        saved_condition_order=[first, second, first, second],
        order_seeds=configured_randomization_seeds(document.project), persist=True,
    )
    before = document.project.model_copy(deep=True)
    table = ConditionTimingTable(document)
    qtbot.addWidget(table)
    table.presentation_count_spins[first].setValue(3)
    assert not table.apply_pending_edits()
    assert document.project == before
    dialog, _table = _open_dialog(qtbot, document, table=table)
    assert not dialog.save_button.isEnabled()
    assert "current counts" in dialog.error_label.text()
    dialog.generate_button.click()
    preview_jobs[-1].complete()
    assert dialog._order == [first, second, first, second, first]
    dialog.save()
    assert document.get_condition(first).presentation_count == 3
    assert document.project.settings.session.saved_condition_order == dialog._order
    assert not table.has_pending_edits()


def test_structural_edits_keep_stale_fixed_order_visible_and_repairable(
    qtbot, tmp_path, preview_jobs,
):
    document, first, second = _document(tmp_path)
    document.update_condition_timing(
        saved_condition_order=[first, second, first, second],
        order_seeds=configured_randomization_seeds(document.project),
    )
    third = document.create_condition(name="Third condition")
    table = ConditionTimingTable(document)
    qtbot.addWidget(table)
    assert "current counts" in table.presentation_count_blocker()
    dialog, _table = _open_dialog(qtbot, document, table=table)
    dialog.generate_button.click()
    preview_jobs[-1].complete()
    assert dialog._order.count(third) == 2
    dialog.save()
    assert not table.presentation_count_blocker()


def test_wizard_timing_order_action_repairs_staged_counts_before_advancing(
    qtbot, monkeypatch, tmp_path, preview_jobs,
):
    document, first, second = _document(tmp_path)
    document.update_condition_timing(
        saved_condition_order=[first, second, first, second],
        order_seeds=configured_randomization_seeds(document.project), persist=True,
    )
    wizard = SetupWizardPage(
        document, load_condition_template_profiles=lambda: [],
        manage_condition_templates=lambda: [],
    )
    qtbot.addWidget(wizard)
    monkeypatch.setattr(wizard.runtime_settings_editor, "timing_is_compatible", lambda: True)
    wizard.resize(1120, 820)
    wizard.show()
    wizard.open_wizard(step_key="experiment", allow_step_jumps=True)
    before = document.project.model_copy(deep=True)
    table = wizard.condition_timing_table
    table.presentation_count_spins[first].setValue(3)
    QApplication.processEvents()
    assert wizard.setup_wizard_next_button.isEnabled()
    qtbot.mouseClick(wizard.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    assert wizard.step_stack.currentWidget() is wizard.experiment_step_surface
    assert "current counts" in table.error_label.text()
    assert table.pending_presentation_counts() == {first: 3}
    assert document.project == before
    dialogs = []

    def generate_and_save(dialog):
        dialogs.append(dialog)
        dialog.show()
        QApplication.processEvents()
        assert not dialog.save_button.isEnabled()
        assert dialog._pending_counts == {first: 3}
        dialog.generate_button.click()
        preview_jobs[-1].complete()
        assert dialog._order == [first, second, first, second, first]
        assert document.project == before
        dialog.save_button.click()
        assert dialog.result() == int(dialog.DialogCode.Accepted)
        return dialog.result()

    monkeypatch.setattr(ConditionOrderDialog, "exec", generate_and_save)
    assert table.condition_order_button.isVisible()
    qtbot.mouseClick(table.condition_order_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert len(dialogs) == 1
    assert not table.has_pending_edits()
    reopened = ProjectDocument.open_existing(document.project_root)
    assert reopened.get_condition(first).presentation_count == 3
    assert reopened.project.settings.session.saved_condition_order == dialogs[0]._order
    assert wizard.setup_wizard_next_button.isEnabled()
    qtbot.mouseClick(wizard.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    assert wizard.step_stack.currentWidget() is wizard.session_step_surface


def test_wizard_timing_order_action_repairs_persisted_structural_mismatch(
    qtbot, monkeypatch, tmp_path, preview_jobs,
):
    document, first, second = _document(tmp_path)
    document.update_condition_timing(
        saved_condition_order=[first, second, first, second],
        order_seeds=configured_randomization_seeds(document.project), persist=True,
    )
    third = document.create_condition(name="New condition missing from the saved order")
    document.save()
    document = ProjectDocument.open_existing(document.project_root)
    wizard = SetupWizardPage(
        document, load_condition_template_profiles=lambda: [],
        manage_condition_templates=lambda: [],
    )
    qtbot.addWidget(wizard)
    monkeypatch.setattr(wizard.runtime_settings_editor, "timing_is_compatible", lambda: True)
    wizard.resize(1120, 820)
    wizard.show()
    wizard.open_wizard(step_key="experiment", allow_step_jumps=True)
    QApplication.processEvents()
    before = document.project.model_copy(deep=True)
    table = wizard.condition_timing_table
    assert "current counts" in table.presentation_count_blocker()
    assert not wizard.setup_wizard_next_button.isEnabled()
    dialogs = []

    def generate_and_save(dialog):
        dialogs.append(dialog)
        dialog.show()
        QApplication.processEvents()
        assert not dialog.save_button.isEnabled()
        assert "current counts" in dialog.error_label.text()
        dialog.generate_button.click()
        preview_jobs[-1].complete()
        assert all(
            dialog._order.count(condition_id) == 2 for condition_id in (first, second, third)
        )
        assert document.project == before
        dialog.save_button.click()
        assert dialog.result() == int(dialog.DialogCode.Accepted)
        return dialog.result()

    monkeypatch.setattr(ConditionOrderDialog, "exec", generate_and_save)
    assert table.condition_order_button.isVisible()
    qtbot.mouseClick(table.condition_order_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert len(dialogs) == 1
    assert not table.presentation_count_blocker()
    reopened = ProjectDocument.open_existing(document.project_root)
    assert reopened.project.settings.session.saved_condition_order == dialogs[0]._order
    assert wizard.setup_wizard_next_button.isEnabled()
    qtbot.mouseClick(wizard.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    assert wizard.step_stack.currentWidget() is wizard.session_step_surface


@pytest.mark.parametrize("seconds", [0, 20])
def test_order_save_validates_frequency_duration_and_count_drafts_together(
    qtbot, monkeypatch, tmp_path, preview_jobs, seconds,
):
    document, first, _second = _document(tmp_path)
    document.save()
    before = document.project.model_copy(deep=True)
    saved_bytes = document.project_file_path.read_bytes()
    table = ConditionTimingTable(document)
    qtbot.addWidget(table)
    table.frequency_spins[first].setValue(4)
    table.duration_spins[first].setValue(seconds)
    table.presentation_count_spins[first].setValue(3)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    dialog, _table = _open_dialog(qtbot, document, table=table)
    preview_jobs[-1].complete()
    dialog.save()
    if seconds == 0:
        assert document.project == before
        assert document.project_file_path.read_bytes() == saved_bytes
        assert "stream duration" in dialog.error_label.text().lower()
        assert table.has_pending_edits()
    else:
        reopened = ProjectDocument.open_existing(document.project_root)
        condition = reopened.get_condition(first)
        assert condition.base_hz == 4
        assert condition.stream_duration_seconds == 20
        assert condition.presentation_count == 3
        assert reopened.project.settings.session.randomization_mode == "fixed"


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("size", [(700, 520), (780, 620)])
@pytest.mark.parametrize("state", ["valid", "invalid", "busy", "stale"])
def test_order_editor_plain_list_and_long_names_fit_documented_sizes(
    qtbot, tmp_path, preview_jobs, background, size, state,
):
    document, first, _second = _document(tmp_path)
    long_name = "Semantic categories with low visual similarity and high emotional salience"
    document.update_condition(first, name=long_name)
    dialog, _table = _open_dialog(qtbot, document)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.resize(*size)
    if state != "busy":
        if state == "stale":
            document.update_condition(first, name="Different current condition name")
        preview_jobs[-1].complete()
    if state == "invalid":
        dialog._order = [first] * 4
        dialog._render()
    QApplication.processEvents()
    assert dialog.size().toTuple() == size
    assert dialog.minimumSize().toTuple() == (700, 520)
    assert_visible_children_within_parent(dialog)
    assert dialog.effect_label.text() == "Save selects Same for every participant."
    if state == "valid":
        item = next(dialog.order_list.item(row) for row in range(dialog.order_list.count())
                    if dialog.order_list.item(row).data(Qt.ItemDataRole.UserRole) == first)
        assert long_name in item.toolTip()
        assert item.data(Qt.ItemDataRole.AccessibleTextRole) == item.toolTip()
    for label in dialog.findChildren(QLabel):
        if label.isVisible() and label.text():
            assert label.height() >= label.heightForWidth(label.width()) if label.wordWrap() else (
                label.width() >= label.fontMetrics().horizontalAdvance(label.text())
            )
    for button in (dialog.generate_button, dialog.move_up_button, dialog.move_down_button,
                   dialog.save_button, dialog.cancel_button):
        assert button.width() >= button.sizeHint().width()


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("expanded", [False, True])
def test_main_order_action_and_optional_seed_details_fit_wizard(
    qtbot, monkeypatch, tmp_path, background, expanded,
):
    document, first, second = _document(tmp_path)
    document.update_condition_timing(
        saved_condition_order=[first, second, first, second],
        order_seeds=configured_randomization_seeds(document.project),
    )
    document.update_randomization_settings(mode="new")
    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda _self: None)
    wizard = SetupWizardPage(
        document, load_condition_template_profiles=lambda: [],
        manage_condition_templates=lambda: [],
    )
    qtbot.addWidget(wizard)
    palette = wizard.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    wizard.setPalette(palette)
    wizard.resize(1120, 820)
    wizard.show()
    wizard.open_wizard(step_key="session", allow_step_jumps=True)
    editor = wizard.session_structure_editor.randomization_editor
    assert not editor.seed_details_button.isChecked()
    editor.seed_details_button.setChecked(expanded)
    QApplication.processEvents()
    assert editor.condition_order_button.isVisible()
    assert editor.seed_details.isVisible() == expanded
    assert editor.generate_button.isVisible() == expanded
    assert editor.clear_saved_order_button.isVisible() == expanded
    assert "inactive" in editor.condition_order_button.toolTip()
    assert "saved arrangement" in editor.seed_edits["condition_order_seed"].toolTip()
    assert_visible_children_within_parent(wizard.session_step_surface)
    if expanded:
        editor.clear_saved_order_button.click()
        assert document.project.settings.session.saved_condition_order is None
        assert document.project.settings.session.randomization_mode == "new"
