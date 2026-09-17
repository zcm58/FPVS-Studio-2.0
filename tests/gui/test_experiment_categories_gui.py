"""Category-specific Conditions, presentation, and external save behavior."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox
from tests.gui.helpers import ImmediateProgressTask, open_created_project

from fpvs_studio.core.condition_template_profiles import built_in_condition_template_profiles
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.serialization import load_project_file
from fpvs_studio.gui.condition_setup_step import ConditionSetupStep
from fpvs_studio.gui.condition_template_profile_editor_dialog import (
    ConditionTemplateProfileEditorDialog,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.runtime_settings_page import DisplaySettingsEditor


@pytest.fixture
def ab_document(tmp_path):
    return ProjectDocument.create_new(
        parent_dir=tmp_path, project_name="Letter targets",
        experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
    )


def test_ab_conditions_hide_oddball_only_choices_and_image_pickers(qtbot, ab_document):
    widget = ConditionSetupStep(ab_document)
    qtbot.addWidget(widget)
    widget.resize(1000, 440)
    widget.show()
    assert widget.modality_combo.isHidden()
    assert widget.presentation_mode_row.isHidden()
    assert widget.all_conditions_section.isHidden()
    assert widget.sources_row.isHidden()
    assert not widget.condition_name_edit.isHidden()
    assert not widget.task_button.isHidden()


def test_legacy_separation_cancel_preserves_document(qtbot, ab_document, monkeypatch):
    legacy = ab_document.project.conditions[0].model_copy(update={
        "condition_id": "old-oddball", "name": "Old oddball",
        "attentional_blink": None, "t2_stimulus_set_id": None,
    }, deep=True)
    ab_document.project.conditions[:] = [ab_document.project.conditions[0], legacy]
    widget = ConditionSetupStep(ab_document)
    qtbot.addWidget(widget)
    widget.show()
    assert not widget.separate_conditions_button.isHidden()
    before = ab_document.project.model_dump()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel)
    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step.separate_legacy_mixed_project",
        lambda *args: pytest.fail("Cancel must not copy or save any files"),
    )
    widget.separate_conditions_button.click()
    assert ab_document.project.model_dump() == before


def test_legacy_separation_adopts_saved_ab_experiment(qtbot, ab_document, monkeypatch):
    legacy = ab_document.project.conditions[0].model_copy(update={
        "condition_id": "old-oddball", "name": "Old oddball",
        "attentional_blink": None, "t2_stimulus_set_id": None,
    }, deep=True)
    ab_document.project.conditions[:] = [ab_document.project.conditions[0], legacy]
    widget = ConditionSetupStep(ab_document)
    qtbot.addWidget(widget)
    widget.show()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step.ProgressTask", ImmediateProgressTask,
    )
    with qtbot.waitSignal(ab_document.saved, timeout=1000):
        widget.separate_conditions_button.click()
    assert widget._active_task is None
    assert not ab_document.dirty
    assert len(ab_document.project.conditions) == 1
    assert ab_document.project.conditions[0].attentional_blink is not None
    assert load_project_file(ab_document.project_file_path) == ab_document.project
    assert widget.separate_conditions_button.isHidden()
    sibling_files = [
        path for path in ab_document.project_root.parent.glob("*/project.json")
        if path != ab_document.project_file_path
    ]
    assert len(sibling_files) == 1
    sibling = load_project_file(sibling_files[0])
    assert sibling.experiment_category == ExperimentCategory.FPVS_ODDBALL


@pytest.mark.parametrize("accept", [False, True])
def test_legacy_oddball_t2_cleanup_requires_explicit_choice(
    qtbot, sample_project, sample_project_root, monkeypatch, accept,
):
    sample_project.conditions[0].t2_stimulus_set_id = (
        sample_project.conditions[0].oddball_stimulus_set_id
    )
    document = ProjectDocument(project_root=sample_project_root, project=sample_project)
    widget = ConditionSetupStep(document)
    qtbot.addWidget(widget)
    widget.show()
    assert widget.separate_conditions_button.text() == "Clear unused T2 assignments..."
    assert not widget.separate_conditions_button.isHidden()
    before = document.project.model_dump()
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *args: (
            QMessageBox.StandardButton.Yes if accept else QMessageBox.StandardButton.Cancel
        ),
    )
    widget.separate_conditions_button.click()
    expected = before
    if accept:
        expected["conditions"][0]["t2_stimulus_set_id"] = None
        expected["meta"]["updated_at"] = document.project.meta.updated_at
        assert document.dirty
        assert widget.separate_conditions_button.isHidden()
    assert document.project.model_dump() == expected




def test_ab_timing_uses_target_pair_language_and_design_owns_cadence(qtbot, ab_document):
    widget = DisplaySettingsEditor(ab_document)
    qtbot.addWidget(widget)
    widget.show()
    assert widget.base_hz_spin.isHidden()
    assert widget.oddball_every_n_spin.isHidden()
    assert "oddball" not in widget.timing_summary_label.text().casefold()
    assert "10" in widget.timing_summary_label.text()


def test_editing_ab_template_preserves_category_and_cadence(qtbot):
    profile = next(
        item for item in built_in_condition_template_profiles()
        if item.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
    )
    dialog = ConditionTemplateProfileEditorDialog(
        existing_profile_ids=set(), initial_profile=profile,
    )
    qtbot.addWidget(dialog)
    result = dialog._build_profile()
    assert result.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
    assert result.defaults.protocol == profile.defaults.protocol
    assert dialog.duty_cycle_combo.count() == 1


@pytest.mark.parametrize("worker", ["designer", "conditions"])
def test_changing_experiments_waits_for_image_workers(
    qtbot, controller, tmp_path, monkeypatch, worker,
):
    _document, window = open_created_project(controller, qtbot, tmp_path, "Worker Guard")
    wizard = window.setup_wizard_page
    notices = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: notices.append(args[2]))
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *args: pytest.fail("Discard cannot destroy a widget with an active image worker"),
    )
    owner, method = (
        (wizard.design_setup_step, "is_busy") if worker == "designer"
        else (wizard, "_condition_image_task_active")
    )
    monkeypatch.setattr(owner, method, lambda: True)
    assert not window.maybe_save_changes()
    assert len(notices) == 1
    monkeypatch.setattr(owner, method, lambda: False)


@pytest.mark.parametrize("dark", [False, True])
def test_creation_names_categories_and_hides_injected_image_pair_templates(qtbot, dark):
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication
    from tests.gui.helpers import assert_visible_children_within_parent

    from fpvs_studio.core.models import ConditionTemplateProfile
    from fpvs_studio.gui.create_project_dialog import CreateProjectDialog

    retired = ConditionTemplateProfile(
        profile_id="old-pairs", display_name="Image pairs",
        experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
    )
    dialog = CreateProjectDialog(
        condition_template_profiles=[*built_in_condition_template_profiles(), retired],
    )
    qtbot.addWidget(dialog)
    dialog.setPalette(QPalette(QColor("#202124" if dark else "#f4f7fb")))
    dialog.resize(760, 500)
    dialog.show()
    dialog.manual_button.click()
    QApplication.processEvents()
    assert dialog.category_buttons[ExperimentCategory.FPVS].text() == "Standard FPVS\nComing soon"
    assert not dialog.category_buttons[ExperimentCategory.FPVS].isEnabled()
    oddball = dialog.category_buttons[ExperimentCategory.FPVS_ODDBALL]
    assert oddball.text().splitlines()[0] == "FPVS Oddball Paradigm"
    cognitive_load = dialog.category_buttons[ExperimentCategory.COGNITIVE_LOAD_FPVS]
    assert cognitive_load.isEnabled()
    assert cognitive_load.text().splitlines()[0] == "Cognitive Load FPVS"
    assert_visible_children_within_parent(dialog)
    for button in dialog.category_buttons.values():
        assert max(button.fontMetrics().horizontalAdvance(line)
                   for line in button.text().splitlines()) + 12 <= button.width()
    dialog.select_category(ExperimentCategory.ATTENTIONAL_BLINK)
    assert dialog.condition_profile_combo.count() == 1
    assert dialog.condition_profile_combo.currentText() == "Digits & letter targets"
    assert_visible_children_within_parent(dialog)


def test_cognitive_load_uses_image_design_and_shared_condition_pairs(qtbot, tmp_path):
    from fpvs_studio.gui.design_setup_step import DesignSetupStep
    from fpvs_studio.gui.experiment_designer_dialog import ExperimentDesignerWidget

    document = ProjectDocument.create_new(
        parent_dir=tmp_path,
        project_name="Cognitive Load FPVS",
        experiment_category=ExperimentCategory.COGNITIVE_LOAD_FPVS,
    )
    conditions = ConditionSetupStep(document)
    qtbot.addWidget(conditions)
    conditions.resize(1000, 560)
    conditions.show()
    assert conditions.condition_list.count() == 6
    assert not conditions.task_button.isHidden()
    assert not conditions.modality_combo.isHidden()
    designer = DesignSetupStep(document)
    qtbot.addWidget(designer)
    assert isinstance(designer.editor, ExperimentDesignerWidget)
    assert designer.category_label.text() == "Cognitive Load FPVS"
