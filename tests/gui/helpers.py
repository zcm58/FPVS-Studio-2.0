"""Shared helpers for PySide6 GUI workflow tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image
from PySide6.QtCore import QObject, QPoint, Qt, Signal
from PySide6.QtWidgets import QListWidget, QWidget

from fpvs_studio.core.enums import RunMode
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.gui.condition_template_manager_dialog import ConditionTemplateManagerDialog
from fpvs_studio.gui.controller import StudioController


class ImmediateProgressTask(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(
        self,
        *,
        parent_widget: QWidget,
        label: str,
        callback,
        dialog_factory=None,
        window_title: str | None = None,
        persistent_thread: bool = False,
    ) -> None:
        super().__init__(parent_widget)
        self._callback = callback

    def start(self) -> None:
        try:
            result = self._callback()
        except Exception as error:
            self.failed.emit(error)
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()


def write_image_directory(
    target_dir: Path,
    *,
    size: tuple[int, int] = (96, 96),
    count: int = 3,
) -> Path:
    """Create a small deterministic source-image directory."""

    target_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        Image.new(
            "RGB",
            size,
            color=((index * 20) % 255, (index * 10) % 255, (index * 5) % 255),
        ).save(target_dir / f"stimulus-{index:02d}.png")
    return target_dir


def write_mixed_image_directory(target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (96, 96), color=(20, 40, 60)).save(target_dir / "stimulus-01.png")
    Image.new("RGB", (128, 96), color=(60, 40, 20)).save(target_dir / "stimulus-02.jpg")
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


def assert_balanced_setup_stepper(wizard: Any) -> None:
    assert wizard.progress_panel.maximumWidth() == 1120
    assert wizard.progress_panel.width() <= 1120
    circle_centers: list[int] = []
    for circle, label in zip(
        wizard.progress_steps.step_circles,
        wizard.progress_steps.step_labels,
        strict=True,
    ):
        circle_center = circle.mapTo(
            wizard.progress_steps,
            QPoint(circle.width() // 2, 0),
        ).x()
        label_center = label.mapTo(
            wizard.progress_steps,
            QPoint(label.width() // 2, 0),
        ).x()
        circle_centers.append(circle_center)
        assert abs(label_center - circle_center) <= 2
    center_gaps = [
        right - left for left, right in zip(circle_centers, circle_centers[1:], strict=False)
    ]
    assert max(center_gaps) - min(center_gaps) <= 2


def assert_setup_wizard_vertical_scrolling_disabled(wizard: Any) -> None:
    scroll_area = wizard.shell.page_container.scroll_area
    assert scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert not scroll_area.verticalScrollBar().isEnabled()


def assert_visible_children_within_parent(root: QWidget) -> None:
    for child in root.findChildren(QWidget):
        parent = child.parentWidget()
        if parent is None or not child.isVisible():
            continue
        top_left = child.mapTo(parent, child.rect().topLeft())
        bottom_right = child.mapTo(parent, child.rect().bottomRight())
        assert top_left.x() >= -1, child.objectName()
        assert top_left.y() >= -1, child.objectName()
        assert bottom_right.x() <= parent.width() + 1, child.objectName()
        assert bottom_right.y() <= parent.height() + 1, child.objectName()


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
        run_mode=RunMode.SESSION,
        participant_number=participant_number,
        random_seed=session_plan.random_seed,
        started_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 3, 8, 10, 1, tzinfo=timezone.utc),
        total_condition_count=session_plan.total_runs,
        completed_condition_count=session_plan.total_runs,
        output_dir=output_dir or f"runs/{session_plan.session_id}",
    )


_write_image_directory = write_image_directory
_write_mixed_image_directory = write_mixed_image_directory
_open_created_project = open_created_project
_list_widget_text = list_widget_text
_assert_balanced_setup_stepper = assert_balanced_setup_stepper
_assert_setup_wizard_vertical_scrolling_disabled = (
    assert_setup_wizard_vertical_scrolling_disabled
)
_assert_visible_children_within_parent = assert_visible_children_within_parent
_find_profile_row = find_profile_row
_prepare_compile_ready_project = prepare_compile_ready_project
_ImmediateProgressTask = ImmediateProgressTask
