"""Registered visible authoring checks for real, once-per-block catch conditions."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from tests.gui.helpers import _open_created_project, assert_visible_children_within_parent
from tests.unit.test_masking import masking_project

from fpvs_studio.core.enums import ProjectSchemaVersion
from fpvs_studio.core.masking import MaskingCatchTrialSettings
from fpvs_studio.gui import condition_setup_step
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.document import ProjectDocument


def _open_masking_setup(qtbot, controller, tmp_path, *, automatic_catches=False):
    _, window = _open_created_project(controller, qtbot, tmp_path, "Visible Masking catches")
    project = masking_project(("color", "faces", "number"))
    project.meta = window.document.project.meta.model_copy(deep=True)
    for code, condition in enumerate(project.conditions, start=1):
        condition.trigger_code = code
    if automatic_catches:
        for modifier in project.condition_modifiers:
            settings = modifier.masking
            settings.catch_trial = MaskingCatchTrialSettings(
                trigger_code={"color": 10, "faces": 11, "number": 12}[settings.variant],
            )
        project.schema_version = ProjectSchemaVersion.V1_8
    window.document.apply_condition_modifier_project(project)
    window.resize(1120, 820)
    window.show_setup_wizard(step_key="conditions")
    return window, window.setup_wizard_page.condition_setup_step


def _assert_fit(window, step):
    QApplication.processEvents()
    assert (window.width(), window.height()) == (1120, 820)
    assert_visible_children_within_parent(step)
    assert_visible_children_within_parent(step.condition_details_section)
    for label in (step.condition_list_hint, step.catch_schedule_summary):
        assert label.height() >= label.heightForWidth(label.width()), label.text()
    assert step.add_catch_condition_button.width() >= (
        step.add_catch_condition_button.fontMetrics().horizontalAdvance(
            step.add_catch_condition_button.text()
        )
    )


def test_masking_catches_are_real_rows_with_saved_identity_and_markers(
    qtbot, controller: StudioController, tmp_path: Path,
) -> None:
    window, step = _open_masking_setup(qtbot, controller, tmp_path)
    original_modifiers = [
        item.model_dump() for item in window.document.project.condition_modifiers
    ]
    catch_ids = []
    for variant, code in (("color", 10), ("faces", 11), ("number", 12)):
        step._select_condition(f"{variant}-1")
        assert step.add_catch_condition_button.isVisible()
        assert step.add_catch_condition_button.isEnabled()
        assert not step.create_control_condition_button.isVisible()
        _assert_fit(window, step)
        qtbot.mouseClick(step.add_catch_condition_button, Qt.MouseButton.LeftButton)
        catch_id = step.selected_condition_id()
        catch_ids.append(catch_id)
        catch = window.document.get_condition(catch_id)
        assert catch.masking_catch
        assert catch.trigger_code == code
        assert step.trigger_code_spin.value() == code
        assert f"Catch · EEG {code} · random SOA" in step.condition_list.currentItem().text()
        assert "once per variant block" in step.condition_list_hint.text()
        assert "When launched alone" in step.catch_schedule_summary.text()
        assert "selected ordinary conditions" in step.catch_schedule_summary.text()
        assert not step.add_catch_condition_button.isEnabled()
        assert not step.duplicate_condition_button.isEnabled()
        _assert_fit(window, step)
    assert step.condition_list.count() == 12
    assert len(window.document.project.conditions) == 12
    assert [item.model_dump() for item in window.document.project.condition_modifiers] == (
        original_modifiers
    )
    step.trigger_code_spin.setValue(42)
    assert window.document.get_condition(catch_ids[-1]).trigger_code == 42
    window.document.save()
    reopened = ProjectDocument.open_existing(window.document.project_root)
    assert [item.condition_id for item in reopened.project.conditions if item.masking_catch] == (
        catch_ids
    )
    assert [item.trigger_code for item in reopened.project.conditions if item.masking_catch] == (
        [10, 11, 42]
    )
    assert reopened.project.schema_version == ProjectSchemaVersion.V1_9


@pytest.mark.parametrize("automatic_catches", [False, True])
def test_catch_action_explains_existing_catch_without_changing_shared_settings(
    qtbot, controller: StudioController, tmp_path: Path, automatic_catches,
) -> None:
    window, step = _open_masking_setup(
        qtbot, controller, tmp_path, automatic_catches=automatic_catches,
    )
    if not automatic_catches:
        window.document.add_masking_catch_condition("color-1")
    before = window.document.project.model_dump()
    step._select_condition("color-2")
    assert not step.add_catch_condition_button.isEnabled()
    if automatic_catches:
        assert "Disable automatic catch trials" in step.add_catch_condition_button.toolTip()
    else:
        assert "catch" in step.add_catch_condition_button.toolTip().lower()
    assert step.catch_schedule_summary.text() == step.add_catch_condition_button.toolTip()
    _assert_fit(window, step)
    qtbot.mouseClick(step.add_catch_condition_button, Qt.MouseButton.LeftButton)
    assert window.document.project.model_dump() == before


def test_rejected_catch_creation_reports_error_without_mutation(
    qtbot, controller: StudioController, tmp_path: Path, monkeypatch,
) -> None:
    window, step = _open_masking_setup(qtbot, controller, tmp_path)
    step._select_condition("number-1")
    before = window.document.project.model_dump()
    errors = []

    def reject_creation(_source_id):
        raise ValueError("Catch source settings changed; review the selected variant.")

    monkeypatch.setattr(window.document, "add_masking_catch_condition", reject_creation)
    monkeypatch.setattr(
        condition_setup_step, "_show_error_dialog",
        lambda _parent, title, error: errors.append((title, str(error))),
    )
    qtbot.mouseClick(step.add_catch_condition_button, Qt.MouseButton.LeftButton)
    assert errors == [("Catch Condition Error",
                       "Catch source settings changed; review the selected variant.")]
    assert window.document.project.model_dump() == before


def test_catch_creation_is_hidden_for_ordinary_experiments(
    qtbot, controller: StudioController, tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Ordinary conditions")
    window.show_setup_wizard(step_key="conditions")
    step = window.setup_wizard_page.condition_setup_step
    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    assert not step.add_catch_condition_button.isVisible()
    assert not step.catch_schedule_summary.isVisible()
    assert step.create_control_condition_button.isVisible()
