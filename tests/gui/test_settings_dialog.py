"""Registered Qt coverage for the shared Settings composition and save semantics."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QPushButton,
    QWidget,
)
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.gui.components import SectionCard
from fpvs_studio.gui.settings_dialog import AppSettingsDialog


def _assert_visible_settings_text_fits(dialog: AppSettingsDialog) -> None:
    assert_visible_children_within_parent(dialog)
    for label in dialog.findChildren(QLabel):
        if not label.isVisible() or not label.text():
            continue
        context = f"{label.objectName() or label.text()}: {label.size().toTuple()}"
        if label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width()), context
        else:
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text()), context
        if label.property("settingsSectionTitle") == "true":
            assert label.alignment() & Qt.AlignmentFlag.AlignLeft, context
    for control_type in (QCheckBox, QPushButton):
        for control in dialog.findChildren(control_type):
            if control.isVisible():
                assert control.width() >= control.sizeHint().width(), control.text()


@pytest.mark.parametrize(
    ("test_mode", "pilot_mode", "library", "height"),
    [(False, False, False, 560), (True, False, False, 650), (True, True, True, 764)],
    ids=["ordinary", "test-mode", "pilot-and-library"],
)
@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"], ids=["light", "dark"])
def test_settings_sections_fit_minimum_size(
    qtbot, tmp_path, test_mode, pilot_mode, library, height, background,
) -> None:
    root_path = tmp_path / ("Long research project root " * 5)
    dialog = AppSettingsDialog(
        fpvs_root_dir=root_path,
        theme_mode="auto",
        experiment_test_mode_available=test_mode,
        attentional_blink_pilot_mode_available=pilot_mode,
        on_show_library=(lambda: None) if library else None,
        on_show_root_folder_setup=lambda _: None,
        on_manage_condition_templates=lambda: None,
        automatic_crash_reports_status=(
            "Crash reporting is enabled. The last report could not be sent while this "
            "computer was offline. It will be retried when a connection is available."
        ),
    )
    qtbot.addWidget(dialog)
    assert dialog.size() == dialog.minimumSize()
    assert dialog.minimumSize().toTuple() == (700, height)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.show()
    QApplication.processEvents()

    assert dialog.tabs.documentMode()
    assert [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())] == [
        "General", "Advanced", "Recording", "Diagnostics",
    ]
    section_names = [
        "settings_appearance_section", "settings_workspace_section", "settings_participant_section",
    ]
    if test_mode:
        section_names.append("settings_developer_section")
    for name in section_names:
        section = dialog.findChild(QWidget, name)
        assert section is not None, name
        assert not isinstance(section, QFrame), name
        assert section.property("sectionCard") not in (True, "true"), name
        ancestor = section.parentWidget()
        while ancestor is not None:
            assert not isinstance(ancestor, SectionCard), name
            ancestor = ancestor.parentWidget()

    assert dialog.root_folder_setup_button.toolTip() == str(root_path)
    assert not dialog.detailed_run_exports_checkbox.isChecked()
    assert "participant_summary.xlsx" in dialog.detailed_run_exports_checkbox.toolTip()
    assert "always saved" in dialog.detailed_run_exports_checkbox.toolTip()
    assert "saved immediately" in dialog.header.subtitle_label.text()
    for index in range(dialog.tabs.count()):
        dialog.tabs.setCurrentIndex(index)
        QApplication.processEvents()
        assert dialog.size().toTuple() == (700, height), dialog.tabs.tabText(index)
        _assert_visible_settings_text_fits(dialog)
        page = dialog.tabs.currentWidget()
        titles = [
            label for label in page.findChildren(QLabel)
            if label.isVisible() and label.property("settingsSectionTitle") == "true"
        ]
        assert titles, dialog.tabs.tabText(index)
        title_left_edges = {label.mapTo(page, label.rect().topLeft()).x() for label in titles}
        assert len(title_left_edges) == 1, dialog.tabs.tabText(index)


@pytest.mark.parametrize("initial_mode", ["light", "dark", "auto"])
def test_theme_choices_are_exclusive_and_apply_immediately(qtbot, tmp_path, initial_mode) -> None:
    changes: list[str] = []
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path, theme_mode=initial_mode, on_theme_mode_changed=changes.append,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()

    assert set(dialog.theme_buttons) == {"light", "dark", "auto"}
    assert all(isinstance(button, QPushButton) for button in dialog.theme_buttons.values())
    assert all(button.isCheckable() for button in dialog.theme_buttons.values())
    assert dialog.theme_button_group.exclusive()
    assert dialog.theme_buttons[initial_mode].isChecked()
    assert "system" in dialog.theme_buttons["auto"].toolTip().lower()
    assert any(label.text() == "Appearance" for label in dialog.findChildren(QLabel))
    assert changes == []

    modes = [mode for mode in ("light", "dark", "auto") if mode != initial_mode]
    modes.append(initial_mode)
    for index, mode in enumerate(modes, start=1):
        button = dialog.theme_buttons[mode]
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        assert changes == modes[:index]
        assert [key for key, value in dialog.theme_buttons.items() if value.isChecked()] == [mode]
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        assert button.isChecked()
        assert changes == modes[:index]
        assert not dialog.theme_status.isVisible()
    _assert_visible_settings_text_fits(dialog)
    qtbot.mouseClick(
        dialog.button_box.button(QDialogButtonBox.StandardButton.Close),
        Qt.MouseButton.LeftButton,
    )
    assert changes == modes
    assert dialog.theme_buttons[initial_mode].isChecked()


@pytest.mark.parametrize("failure_type", [ValueError, OSError])
def test_theme_save_failure_restores_selection_and_can_retry(
    qtbot, tmp_path, failure_type,
) -> None:
    attempts: list[str] = []

    def save(mode: str) -> None:
        attempts.append(mode)
        if len(attempts) == 1:
            raise failure_type("Synthetic preference save failure")

    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path, theme_mode="auto", on_theme_mode_changed=save,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.mouseClick(dialog.theme_buttons["dark"], Qt.MouseButton.LeftButton)
    assert attempts == ["dark"]
    assert dialog.theme_buttons["auto"].isChecked()
    assert not dialog.theme_buttons["dark"].isChecked()
    assert dialog.theme_status.isVisible()
    assert "Try again" in dialog.theme_status.text()
    QApplication.processEvents()
    assert dialog.size().toTuple() == (700, 560)
    _assert_visible_settings_text_fits(dialog)

    dialog.theme_buttons["dark"].setFocus()
    qtbot.keyClick(dialog.theme_buttons["dark"], Qt.Key.Key_Space)
    assert attempts == ["dark", "dark"]
    assert dialog.theme_buttons["dark"].isChecked()
    assert not dialog.theme_buttons["auto"].isChecked()
    assert not dialog.theme_status.isVisible()


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
