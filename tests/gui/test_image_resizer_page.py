"""Focused GUI workflow tests split from the former layout dashboard suite."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QWidget
from tests.gui.helpers import (
    _ImmediateProgressTask,
    _open_created_project,
    _write_image_directory,
)

from fpvs_studio.gui.controller import StudioController


def test_tools_menu_exposes_in_window_image_resizer(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Image Resizer Menu")

    assert [action.text() for action in window.menuBar().actions()] == ["File", "Tools"]
    assert [action.text() for action in window.tools_menu.actions()] == ["Image Resizer"]

    window.image_resizer_action.trigger()

    assert window.main_stack.currentWidget() is window.image_resizer_page
    assert window.minimumWidth() == 960
    assert window.minimumHeight() == 640
    assert window.width() == 1120
    assert window.height() == 720
    qtbot.mouseClick(
        window.image_resizer_page.return_home_button,
        Qt.MouseButton.LeftButton,
    )
    assert window.main_stack.currentWidget() is window.home_page


def test_image_resizer_uses_wide_two_column_workbench(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Image Resizer Layout")

    window.image_resizer_action.trigger()
    QApplication.processEvents()
    page = window.image_resizer_page
    workbench = page.findChild(QWidget, "image_resizer_workbench")
    controls_panel = page.findChild(QWidget, "image_resizer_controls_panel")
    results_panel = page.findChild(QWidget, "image_resizer_results_panel")

    assert page.shell.page_container.width_preset == "full"
    assert page.findChild(QWidget, "image_resizer_setup_card") is None
    assert page.findChild(QWidget, "image_resizer_result_card") is None
    assert workbench is not None
    assert controls_panel is not None
    assert results_panel is not None
    qtbot.waitUntil(
        lambda: workbench.width() > 0
        and controls_panel.width() > 0
        and results_panel.width() > 0
    )

    controls_right = controls_panel.mapTo(
        workbench,
        QPoint(controls_panel.width(), 0),
    ).x()
    results_left = results_panel.mapTo(workbench, QPoint(0, 0)).x()
    assert results_left > controls_right
    assert controls_panel.width() > results_panel.width()
    assert workbench.width() >= int(window.main_stack.width() * 0.9)


def test_image_resizer_source_selection_suggests_output_folder(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Image Resizer Source")
    page = window.image_resizer_page
    source_dir = tmp_path / "raw-images"
    _write_image_directory(source_dir)
    monkeypatch.setattr(
        "fpvs_studio.gui.image_resizer_page.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(source_dir),
    )

    qtbot.mouseClick(page.source_button, Qt.MouseButton.LeftButton)

    expected_output = tmp_path / "raw-images-fpvs-optimized"
    assert page._source_dir == source_dir
    assert page._output_dir == expected_output
    assert page.optimize_button.isEnabled()


def test_image_resizer_disabled_state_explains_unavailable_optimization(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Image Resizer Disabled")
    page = window.image_resizer_page

    assert page.optimize_button.isEnabled() is False
    assert page.open_output_button.isHidden()
    assert "source folder and an output folder" in page.result_label.text().lower()

    source_dir = tmp_path / "raw-images"
    _write_image_directory(source_dir)
    page._set_source_dir(source_dir)
    page._set_output_dir(source_dir, user_selected=True)

    assert page.optimize_button.isEnabled() is False
    assert "different from the source folder" in page.result_label.text().lower()


def test_image_resizer_optimizes_folder_and_updates_results(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Image Resizer Run")
    page = window.image_resizer_page
    source_dir = tmp_path / "raw-images"
    output_dir = tmp_path / "optimized"
    opened_paths: list[Path] = []
    source_dir.mkdir(parents=True)
    Image.new("RGB", (96, 96), color=(20, 40, 60)).save(source_dir / "stimulus-01.png")
    monkeypatch.setattr(
        "fpvs_studio.gui.image_resizer_page.ProgressTask",
        _ImmediateProgressTask,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.folder_actions.open_folder",
        lambda path: opened_paths.append(Path(path)) or True,
    )

    page._set_source_dir(source_dir)
    page._set_output_dir(output_dir, user_selected=True)
    qtbot.mouseClick(page.optimize_button, Qt.MouseButton.LeftButton)

    assert page.status_badge.text() == "Optimization complete"
    assert "Optimized 1 image(s)" in page.result_label.text()
    assert not page.open_output_button.isHidden()
    assert not page.copy_output_button.isHidden()
    assert page.open_output_button.isEnabled()
    assert page.copy_output_button.isEnabled()
    qtbot.mouseClick(page.copy_output_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(page.open_output_button, Qt.MouseButton.LeftButton)
    assert QApplication.clipboard().text() == str(output_dir)
    assert opened_paths == [output_dir]
    output_paths = sorted(output_dir.iterdir())
    assert len(output_paths) == 1
    assert output_paths[0].suffix == ".png"
