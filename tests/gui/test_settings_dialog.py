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
    assert dialog.height() == (650 if developer else 560)
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


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("state", ["off", "password", "wrong", "pending", "active", "disabling"])
def test_advanced_developer_mode_geometry_and_password(qtbot, tmp_path, background, state):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QLineEdit

    from fpvs_studio.developer.mode import DeveloperMode

    settings = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    if state in {"active", "disabling"}:
        settings.setValue("developer/enabled", True)
    mode = DeveloperMode(settings)
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path, developer_mode_active=mode.active,
        developer_mode_requested=mode.requested, on_developer_mode_changed=mode.configure,
    )
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.tabs.setCurrentIndex(1)
    dialog.show()
    if state in {"password", "wrong", "pending"}:
        dialog.developer_mode_checkbox.click()
        assert not mode.requested
        assert dialog.developer_password.echoMode() == QLineEdit.EchoMode.Password
    if state in {"wrong", "pending"}:
        dialog.developer_password.setText("wrong" if state == "wrong" else "developer")
        dialog.developer_enable_button.click()
        assert not dialog.developer_password.text()
    if state == "wrong":
        assert "Incorrect" in dialog.developer_status.text()
        assert not mode.requested
        dialog.developer_cancel_button.click()
        assert not dialog.developer_mode_checkbox.isChecked()
    if state == "disabling":
        dialog.developer_mode_checkbox.click()
    if state in {"pending", "disabling"}:
        assert "Restart required" in dialog.developer_status.text()
        assert mode.restart_required
    QApplication.processEvents()
    assert_visible_children_within_parent(dialog)
    for checkbox in dialog.findChildren(QCheckBox):
        if checkbox.isVisible():
            assert checkbox.width() >= checkbox.sizeHint().width()
    dialog.close()
    assert settings.value("developer/enabled", False, type=bool) == (state in {"pending", "active"})


def test_password_enter_enables_once_without_closing_settings(qtbot, tmp_path):
    calls = []
    def enable(enabled, password):
        calls.append((enabled, password))
        return password == "developer"
    dialog = AppSettingsDialog(fpvs_root_dir=tmp_path, on_developer_mode_changed=enable)
    qtbot.addWidget(dialog)
    dialog.tabs.setCurrentIndex(1)
    dialog.show()
    dialog.developer_mode_checkbox.click()
    qtbot.keyClicks(dialog.developer_password, "developer")
    qtbot.keyClick(dialog.developer_password, Qt.Key.Key_Return)
    assert calls == [(True, "developer")]
    assert dialog.isVisible()
    assert "Restart required" in dialog.developer_status.text()
