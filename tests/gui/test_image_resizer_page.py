"""Focused GUI workflow tests split from the former layout dashboard suite."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from tests.gui.helpers import (
    _assert_visible_children_within_parent,
    _ImmediateProgressTask,
    _open_created_project,
    _write_image_directory,
)

from fpvs_studio.gui.components import image_resizer_stylesheet
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.design_system import resolve_studio_theme
from fpvs_studio.gui.image_resizer_page import ImageResizerPage


@pytest.mark.parametrize("dark", [False, True])
def test_return_home_stays_in_bottom_footer_when_resized(qtbot, dark):
    returns = []
    page = ImageResizerPage(on_return_home=lambda: returns.append(True))
    qtbot.addWidget(page)
    page.setPalette(QPalette(QColor("#202124" if dark else "#f4f7fb")))
    page.show()
    for width, height in ((960, 640), (1120, 720), (1120, 900)):
        page.resize(width, height)
        QApplication.processEvents()
        button = page.return_home_button
        assert button.parentWidget() is page
        assert page.height() - button.geometry().bottom() == 17
        assert button.x() == 32
        assert button.y() > page.surface_frame.geometry().bottom()
        _assert_visible_children_within_parent(page)
    qtbot.mouseClick(page.return_home_button, Qt.MouseButton.LeftButton)
    assert returns == [True]


def test_open_image_resizer_tracks_application_palette(qtbot, qapp):
    original_palette = QPalette(qapp.palette())
    page = ImageResizerPage()
    qtbot.addWidget(page)
    page.resize(960, 640)
    page.show()
    heading = page.findChild(QLabel, "image_resizer_controls_heading")
    assert heading is not None
    try:
        for background in ("#f4f7fb", "#202124", "#f4f7fb"):
            palette = QPalette(original_palette)
            palette.setColor(QPalette.ColorRole.Window, QColor(background))
            qapp.setPalette(palette)
            QApplication.processEvents()

            theme = resolve_studio_theme(palette)
            assert page.styleSheet() == image_resizer_stylesheet(theme)
            heading_color = heading.palette().color(QPalette.ColorRole.WindowText).name()
            assert heading_color == theme.text_primary
            _assert_visible_children_within_parent(page)
    finally:
        qapp.setPalette(original_palette)
        QApplication.processEvents()


def test_tools_menu_exposes_in_window_image_resizer(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Image Resizer Menu")

    assert [action.text() for action in window.menuBar().actions()] == [
        "File",
        "View",
        "Tools",
    ]
    assert [
        action.text() for action in window.tools_menu.actions() if not action.isSeparator()
    ] == [
        "Image Resizer", "Trigger Tester", "Condition Figure",
    ]

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


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"], ids=["light", "dark"])
def test_image_resizer_uses_wide_two_column_workbench(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    background: str,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Image Resizer Layout")

    window.setPalette(QPalette(QColor(background)))
    window.image_resizer_action.trigger()
    QApplication.processEvents()
    page = window.image_resizer_page
    surface_frame = page.findChild(QWidget, "image_resizer_surface_frame")
    workbench = page.findChild(QWidget, "image_resizer_workbench")
    controls_panel = page.findChild(QWidget, "image_resizer_controls_panel")
    results_panel = page.findChild(QWidget, "image_resizer_results_panel")

    assert page.shell.page_container.width_preset == "full"
    assert page.property("launchSurfaceRoot") == "true"
    assert surface_frame is page.surface_frame
    assert surface_frame.property("launchSurfaceFrame") == "true"
    assert 'QFrame[launchSurfaceFrame="true"]' in page.styleSheet()
    assert "QScrollArea#page_container_scroll_area" in page.styleSheet()
    assert "QWidget#qt_scrollarea_viewport" in page.styleSheet()
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
    assert workbench.width() >= int(surface_frame.width() * 0.8)
    assert page.size_combo.accessibleName() == "Output size in pixels"
    assert page.size_combo.currentText() == "512 × 512"
    assert page.findChild(QLabel, "image_resizer_controls_copy") is None
    assert page.findChild(QLabel, "image_resizer_results_copy") is None

    window.resize(960, 640)
    QApplication.processEvents()
    empty_size_row_top = page.size_combo.y()
    source_dir = tmp_path / "Participant calibration images" / "Original stimulus images"
    source_dir.mkdir(parents=True)
    output_dir = tmp_path / "Prepared experimental stimuli" / "Resized stimulus images"
    page._set_source_dir(source_dir)
    page._set_output_dir(output_dir, user_selected=True)
    QApplication.processEvents()
    assert page.size_combo.y() == empty_size_row_top

    for size in ((960, 640), (1120, 720), (960, 640)):
        window.resize(*size)
        QApplication.processEvents()
        assert window.size().toTuple() == size
        for label, path in ((page.source_value, source_dir), (page.output_value, output_dir)):
            assert not label.wordWrap()
            assert "…" in label.text()
            assert label.toolTip() == str(path)
            assert label.accessibleName() == str(path)
            text_width = label.fontMetrics().horizontalAdvance(label.text())
            assert text_width <= label.contentsRect().width()
        for button in (page.source_button, page.output_button, page.optimize_button):
            assert button.width() >= button.fontMetrics().horizontalAdvance(button.text())
        _assert_visible_children_within_parent(page)


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
    assert page.result_label.text() == "Choose a source folder."

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

    assert page.result_label.text() == "Resized 1 image to 512 × 512 px."
    assert page.copy_output_button.text() == "Copy Folder Path"
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
    page._set_output_dir(tmp_path / "Another output folder", user_selected=True)
    assert page.result_label.text() == "No batch results yet."
    assert page.open_output_button.isHidden()
    assert page.copy_output_button.isHidden()


@pytest.mark.parametrize("size", [(960, 640), (1120, 720)], ids=["minimum", "default"])
def test_image_resizer_retains_failure_until_inputs_change(qtbot, tmp_path, monkeypatch, size):
    from fpvs_studio.gui import image_resizer_page

    page = ImageResizerPage()
    qtbot.addWidget(page)
    page.resize(*size)
    page.show()
    errors = []

    def fail_batch(**_kwargs):
        assert page.result_label.text() == "Resizing images…"
        assert not page.optimize_button.isEnabled()
        raise RuntimeError("Output folder cannot be opened.")

    monkeypatch.setattr(image_resizer_page, "ProgressTask", _ImmediateProgressTask)
    monkeypatch.setattr(image_resizer_page, "optimize_image_folder_for_fpvs", fail_batch)
    monkeypatch.setattr(
        image_resizer_page,
        "_show_error_dialog",
        lambda _parent, _title, error: errors.append(error),
    )
    source_dir = tmp_path / "Participant calibration images" / "Original stimulus images"
    source_dir.mkdir(parents=True)
    page._set_source_dir(source_dir)
    QApplication.processEvents()

    qtbot.mouseClick(page.optimize_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert page.size().toTuple() == size
    assert page.result_label.text() == "Batch failed."
    assert [str(error) for error in errors] == ["Output folder cannot be opened."]
    assert page.optimize_button.isEnabled()
    assert page.open_output_button.isHidden()
    assert page.copy_output_button.isHidden()
    for label in (page.source_value, page.output_value, page.result_label):
        assert label.height() >= label.heightForWidth(label.width())
    assert str(page._output_dir) in (page.output_value.text(), page.output_value.toolTip())
    _assert_visible_children_within_parent(page)

    page._set_output_dir(tmp_path / "Resized images", user_selected=True)
    assert page.result_label.text() == "No batch results yet."
