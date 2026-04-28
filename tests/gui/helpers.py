"""Shared helpers for PySide6 GUI workflow tests."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget

from fpvs_studio.gui.condition_template_manager_dialog import ConditionTemplateManagerDialog
from fpvs_studio.gui.controller import StudioController


def _write_image_directory(target_dir: Path, *, size: tuple[int, int] = (96, 96)) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, 4):
        Image.new("RGB", size, color=(index * 20, index * 10, index * 5)).save(
            target_dir / f"stimulus-{index:02d}.png"
        )
    return target_dir


def _open_created_project(
    controller: StudioController, qtbot, tmp_path: Path, name: str = "Demo Project"
):
    document = controller.create_project(name, tmp_path)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)
    return document, controller.main_window


def _list_widget_text(list_widget: QListWidget) -> str:
    return "\n".join(list_widget.item(index).text() for index in range(list_widget.count()))


def _find_profile_row(dialog: ConditionTemplateManagerDialog, profile_id: str) -> int:
    for index in range(dialog.profile_list.count()):
        item = dialog.profile_list.item(index)
        if item.data(Qt.ItemDataRole.UserRole) == profile_id:
            return index
    raise AssertionError(f"Profile id '{profile_id}' not found in manager list.")


def _prepare_compile_ready_project(window, tmp_path: Path) -> None:
    window.conditions_page._add_condition()
    base_dir = _write_image_directory(tmp_path / "base")
    oddball_dir = _write_image_directory(tmp_path / "oddball")
    condition_id = window.conditions_page.selected_condition_id()
    assert condition_id is not None
    window.document.import_condition_stimulus_folder(condition_id, role="base", source_dir=base_dir)
    window.document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=oddball_dir,
    )
