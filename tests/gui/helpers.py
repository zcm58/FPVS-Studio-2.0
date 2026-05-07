"""Shared helpers for PySide6 GUI workflow tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget

from fpvs_studio.core.enums import RunMode
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.gui.condition_template_manager_dialog import ConditionTemplateManagerDialog
from fpvs_studio.gui.controller import StudioController


def write_image_directory(target_dir: Path, *, size: tuple[int, int] = (96, 96)) -> Path:
    """Create a small deterministic source-image directory."""

    target_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, 4):
        Image.new("RGB", size, color=(index * 20, index * 10, index * 5)).save(
            target_dir / f"stimulus-{index:02d}.png"
        )
    return target_dir


def open_created_project(
    controller: StudioController, qtbot, tmp_path: Path, name: str = "Demo Project"
) -> tuple[object, object]:
    """Create a project through the controller and register its main window."""

    document = controller.create_project(name, tmp_path)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)
    return document, controller.main_window


def list_widget_text(list_widget: QListWidget) -> str:
    """Return all visible list-widget text for simple assertions."""

    return "\n".join(list_widget.item(index).text() for index in range(list_widget.count()))


def find_profile_row(dialog: ConditionTemplateManagerDialog, profile_id: str) -> int:
    """Return the list row for one condition-template profile id."""

    for index in range(dialog.profile_list.count()):
        item = dialog.profile_list.item(index)
        if item.data(Qt.ItemDataRole.UserRole) == profile_id:
            return index
    raise AssertionError(f"Profile id '{profile_id}' not found in manager list.")


def prepare_compile_ready_project(window: Any, tmp_path: Path) -> None:
    """Add one condition and import base/oddball image folders."""

    window.conditions_page._add_condition()
    base_dir = write_image_directory(tmp_path / "base")
    oddball_dir = write_image_directory(tmp_path / "oddball")
    condition_id = window.conditions_page.selected_condition_id()
    assert condition_id is not None
    window.document.import_condition_stimulus_folder(condition_id, role="base", source_dir=base_dir)
    window.document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=oddball_dir,
    )


def configure_fixation_task(
    page: Any,
    *,
    enabled: bool = True,
    accuracy_enabled: bool = False,
    target_count_mode: str = "fixed",
    changes_per_sequence: int = 4,
    target_count_min: int = 2,
    target_count_max: int = 5,
    no_immediate_repeat_count: bool = False,
    target_duration_ms: int = 250,
    min_gap_ms: int = 1000,
    max_gap_ms: int = 2000,
    response_key: str = "space",
    response_window_seconds: float = 1.0,
) -> None:
    """Apply common fixation-task settings through the GUI page controls."""

    page.fixation_enabled_checkbox.setChecked(enabled)
    page.fixation_accuracy_checkbox.setChecked(accuracy_enabled)
    page.target_count_mode_combo.setCurrentIndex(
        page.target_count_mode_combo.findData(target_count_mode)
    )
    page.changes_per_sequence_spin.setValue(changes_per_sequence)
    page.target_count_min_spin.setValue(target_count_min)
    page.target_count_max_spin.setValue(target_count_max)
    page.no_repeat_count_checkbox.setChecked(no_immediate_repeat_count)
    page.target_duration_spin.setValue(target_duration_ms)
    page.min_gap_spin.setValue(min_gap_ms)
    page.max_gap_spin.setValue(max_gap_ms)
    page._set_response_key(response_key)
    page.response_window_spin.setValue(response_window_seconds)


def build_successful_session_summary(
    session_plan: SessionPlan,
    *,
    participant_number: str = "00001",
    engine_name: str = "stub",
    output_dir: str | None = None,
) -> SessionExecutionSummary:
    """Build a successful runtime summary for GUI launch tests."""

    return SessionExecutionSummary(
        project_id=session_plan.project_id,
        session_id=session_plan.session_id,
        engine_name=engine_name,
        run_mode=RunMode.TEST,
        participant_number=participant_number,
        random_seed=session_plan.random_seed,
        started_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 3, 8, 10, 1, tzinfo=timezone.utc),
        total_condition_count=session_plan.total_runs,
        completed_condition_count=session_plan.total_runs,
        output_dir=output_dir or f"runs/{session_plan.session_id}",
    )


_write_image_directory = write_image_directory
_open_created_project = open_created_project
_list_widget_text = list_widget_text
_find_profile_row = find_profile_row
_prepare_compile_ready_project = prepare_compile_ready_project
