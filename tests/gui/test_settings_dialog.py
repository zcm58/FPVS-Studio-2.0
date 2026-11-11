"""Registered Qt coverage for the shared Settings composition and save semantics."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPalette, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
)
from tests.gui.helpers import assert_visible_children_within_parent, select_settings_category

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
    ("test_mode", "pilot_mode", "library"),
    [(False, False, False), (True, False, False), (True, True, True)],
    ids=["ordinary", "test-mode", "pilot-and-library"],
)
@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"], ids=["light", "dark"])
@pytest.mark.parametrize("size", [(860, 560), (1000, 680)], ids=["minimum", "default"])
def test_settings_categories_fit_minimum_and_default_sizes(
    qtbot, tmp_path, test_mode, pilot_mode, library, background, size,
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
    assert dialog.minimumSize().toTuple() == (860, 560)
    assert dialog.size().toTuple() == (1000, 680)
    dialog.resize(*size)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.show()
    QApplication.processEvents()

    assert [dialog.navigation.item(index).text() for index in range(dialog.navigation.count())] == [
        "General", "Recording", "Appearance", "Workspace", "Advanced", "Diagnostics",
    ]
    assert dialog.navigation.currentRow() == dialog.pages.currentIndex() == 0
    assert dialog.page_title.text() == "General"
    assert dialog.navigation.mapTo(dialog, dialog.navigation.rect().topRight()).x() < (
        dialog.pages.mapTo(dialog, dialog.pages.rect().topLeft()).x()
    )
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
    for index in range(dialog.navigation.count()):
        category = dialog.navigation.item(index).text()
        select_settings_category(dialog, category)
        assert dialog.pages.currentIndex() == index
        assert dialog.size().toTuple() == size, category
        _assert_visible_settings_text_fits(dialog)
        page = dialog.pages.currentWidget()
        assert isinstance(page, QScrollArea)
        assert page.horizontalScrollBar().maximum() == 0, category
        titles = [
            label for label in page.findChildren(QLabel)
            if label.isVisible() and label.property("settingsSectionTitle") == "true"
        ]
        if category != "Workspace":
            assert titles, category
        title_left_edges = {label.mapTo(page, label.rect().topLeft()).x() for label in titles}
        assert len(title_left_edges) <= 1, category
        page.verticalScrollBar().setValue(page.verticalScrollBar().maximum())
        QApplication.processEvents()
        _assert_visible_settings_text_fits(dialog)
        assert page.widget().mapTo(page.viewport(), page.widget().rect().bottomRight()).y() <= (
            page.viewport().height()
        ), category


@pytest.mark.parametrize("initial_mode", ["light", "dark", "auto"])
def test_theme_choices_are_exclusive_and_apply_immediately(qtbot, tmp_path, initial_mode) -> None:
    changes: list[str] = []
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path, theme_mode=initial_mode, on_theme_mode_changed=changes.append,
    )
    qtbot.addWidget(dialog)
    select_settings_category(dialog, "Appearance")
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
    select_settings_category(dialog, "Appearance")
    dialog.show()
    qtbot.mouseClick(dialog.theme_buttons["dark"], Qt.MouseButton.LeftButton)
    assert attempts == ["dark"]
    assert dialog.theme_buttons["auto"].isChecked()
    assert not dialog.theme_buttons["dark"].isChecked()
    assert dialog.theme_status.isVisible()
    assert "Try again" in dialog.theme_status.text()
    QApplication.processEvents()
    assert dialog.size().toTuple() == (1000, 680)
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
    select_settings_category(dialog, "Workspace")
    dialog.show()
    qtbot.mouseClick(dialog.root_folder_setup_button, Qt.MouseButton.LeftButton)
    assert dialog.root_folder_setup_button.toolTip() == str(updated_root)


def test_settings_navigation_supports_mouse_keyboard_and_keeps_saved_choices(qtbot, tmp_path):
    export_changes = []
    theme_changes = []
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path,
        on_detailed_run_exports_changed=export_changes.append,
        on_theme_mode_changed=theme_changes.append,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    qtbot.mouseClick(dialog.detailed_run_exports_checkbox, Qt.MouseButton.LeftButton)
    appearance = dialog.navigation.findItems("Appearance", Qt.MatchFlag.MatchExactly)[0]
    qtbot.mouseClick(
        dialog.navigation.viewport(), Qt.MouseButton.LeftButton,
        pos=dialog.navigation.visualItemRect(appearance).center(),
    )
    assert dialog.page_title.text() == "Appearance"
    qtbot.mouseClick(dialog.theme_buttons["dark"], Qt.MouseButton.LeftButton)
    dialog.navigation.setFocus()
    qtbot.keyClick(dialog.navigation, Qt.Key.Key_Up)
    assert dialog.page_title.text() == "Recording"
    qtbot.keyClick(dialog.navigation, Qt.Key.Key_Up)
    assert dialog.page_title.text() == "General"
    assert dialog.pages.currentIndex() == 0
    assert dialog.detailed_run_exports_checkbox.isChecked()
    qtbot.keyClick(dialog.navigation, Qt.Key.Key_Down)
    qtbot.keyClick(dialog.navigation, Qt.Key.Key_Down)
    assert dialog.page_title.text() == "Appearance"
    assert dialog.theme_buttons["dark"].isChecked()
    assert export_changes == [True]
    assert theme_changes == ["dark"]
    qtbot.keyClick(dialog.navigation, Qt.Key.Key_Tab)
    page = dialog.pages.currentWidget()
    assert page is dialog.focusWidget() or page.isAncestorOf(dialog.focusWidget())
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert not dialog.isVisible()
    assert export_changes == [True]
    assert theme_changes == ["dark"]


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_settings_long_page_scrolls_with_wheel_while_navigation_and_close_stay_fixed(
    qtbot, tmp_path, background,
):
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path,
        automatic_crash_reports_status="\n".join(
            f"Attempt {index}: The report is waiting for a connection and will be retried."
            for index in range(1, 31)
        ),
    )
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.resize(860, 560)
    select_settings_category(dialog, "Diagnostics")
    dialog.show()
    QApplication.processEvents()
    page = dialog.pages.currentWidget()
    assert isinstance(page, QScrollArea)
    scrollbar = page.verticalScrollBar()
    assert scrollbar.maximum() > 0
    assert page.horizontalScrollBar().maximum() == 0
    assert scrollbar.value() == 0
    sidebar = dialog.navigation.parentWidget()
    close_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Close)
    fixed_widgets = (sidebar, dialog.navigation, dialog.page_title, close_button)
    fixed_geometry = [widget.geometry() for widget in fixed_widgets]
    viewport = page.viewport()
    position = viewport.rect().center()
    wheel = QWheelEvent(
        QPointF(position), QPointF(viewport.mapToGlobal(position)),
        QPoint(), QPoint(0, -120), Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False,
    )
    QApplication.sendEvent(viewport, wheel)
    qtbot.waitUntil(lambda: scrollbar.value() > 0)
    scrollbar.setValue(scrollbar.maximum())
    QApplication.processEvents()
    status_bottom = dialog.crash_reports_status.mapTo(
        viewport, dialog.crash_reports_status.rect().bottomRight(),
    )
    assert 0 <= status_bottom.y() < viewport.height()
    assert dialog.page_title.text() == dialog.navigation.currentItem().text() == "Diagnostics"
    assert [widget.geometry() for widget in fixed_widgets] == fixed_geometry
    for widget in fixed_widgets:
        assert widget.isVisible()
        assert dialog.rect().contains(widget.mapTo(dialog, widget.rect().topLeft()))
        assert dialog.rect().contains(widget.mapTo(dialog, widget.rect().bottomRight()))
    assert_visible_children_within_parent(sidebar)
    assert_visible_children_within_parent(dialog.button_box)
    select_settings_category(dialog, "General")
    select_settings_category(dialog, "Diagnostics")
    assert scrollbar.value() == scrollbar.maximum()
    qtbot.mouseClick(close_button, Qt.MouseButton.LeftButton)
    assert not dialog.isVisible()


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
    select_settings_category(dialog, "Advanced")
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
    select_settings_category(dialog, "Advanced")
    dialog.show()
    dialog.developer_mode_checkbox.click()
    qtbot.keyClicks(dialog.developer_password, "developer")
    qtbot.keyClick(dialog.developer_password, Qt.Key.Key_Return)
    assert calls == [(True, "developer")]
    assert dialog.isVisible()
    assert "Restart required" in dialog.developer_status.text()
