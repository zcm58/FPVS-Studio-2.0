"""Registered Qt coverage for the shared Settings composition and save semantics."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QCheckBox, QDialogButtonBox, QLabel
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.gui.settings_dialog import AppSettingsDialog


@pytest.mark.parametrize("developer", [False, True])
@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_settings_sections_fit_minimum_size(qtbot, tmp_path, developer, background) -> None:
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path / ("Long research project root " * 5),
        experiment_test_mode_available=developer,
        on_show_root_folder_setup=lambda _: None,
        on_manage_condition_templates=lambda: None,
    )
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.resize(dialog.minimumSize())
    dialog.show()
    QApplication.processEvents()

    assert dialog.width() == 700
    assert dialog.height() == (610 if developer else 520)
    assert_visible_children_within_parent(dialog)
    for label in dialog.findChildren(QLabel):
        if label.isVisible() and not label.wordWrap():
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    for checkbox in dialog.findChildren(QCheckBox):
        if checkbox.isVisible():
            assert checkbox.width() >= checkbox.sizeHint().width()
    assert "saved immediately" in dialog.header.subtitle_label.text()


def test_settings_changes_are_immediate_and_close_keeps_them(qtbot, tmp_path) -> None:
    changes: list[bool] = []
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path,
        detailed_run_exports_enabled=False,
        on_detailed_run_exports_changed=changes.append,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.mouseClick(dialog.detailed_run_exports_checkbox, Qt.MouseButton.LeftButton)
    assert changes == [True]
    qtbot.mouseClick(
        dialog.button_box.button(QDialogButtonBox.StandardButton.Close),
        Qt.MouseButton.LeftButton,
    )
    assert changes == [True]


def test_settings_root_details_follow_new_root_selection(qtbot, tmp_path) -> None:
    updated_root = tmp_path / "New research root"
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path,
        on_show_root_folder_setup=lambda _: updated_root,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.mouseClick(dialog.root_folder_setup_button, Qt.MouseButton.LeftButton)
    assert dialog.root_folder_setup_button.toolTip() == str(updated_root)
