"""Visible native theme preference, persistence and shared-style integration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QAbstractAnimation, QEvent, QSettings, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QWidget
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.gui import controller as controller_module
from fpvs_studio.gui import crash_report_controller as crash_module
from fpvs_studio.gui.components import ActionFeedbackButton, welcome_window_stylesheet
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.design_system import StudioColorScheme, resolve_studio_theme
from fpvs_studio.gui.home_page import SophiaModeTicker
from fpvs_studio.gui.processing_page import SpinnerWidget, _ProcessingStep
from fpvs_studio.gui.settings_dialog import AppSettingsDialog
from fpvs_studio.gui.update_progress import UpdateProgressBar
from fpvs_studio.gui.welcome_window import WelcomeWindow


@pytest.fixture
def isolated_theme(qapp, monkeypatch, tmp_path):
    hints = qapp.styleHints()
    original_mode = qapp.property("studioThemeMode")
    original_motion = qapp.property("studioReduceMotion")
    original_palette = QPalette(qapp.palette())
    file = tmp_path / "appearance.ini"

    class LocalSettings(QSettings):
        def __init__(self, *_args, **_kwargs):
            super().__init__(str(file), QSettings.Format.IniFormat)

    monkeypatch.setattr(controller_module, "QSettings", LocalSettings)
    controllers = []

    def create():
        item = StudioController(qapp)
        controllers.append(item)
        return item

    yield create, LocalSettings
    for item in controllers:
        item.deleteLater()
    hints.setColorScheme({
        "light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark,
    }.get(original_mode, Qt.ColorScheme.Unknown))
    qapp.setPalette(original_palette)
    qapp.setProperty("studioThemeMode", original_mode)
    qapp.setProperty("studioReduceMotion", original_motion)
    QApplication.processEvents()


def test_native_theme_changes_refresh_existing_welcome_and_auto_restores_system(
    qtbot, qapp, isolated_theme,
):
    create, settings_factory = isolated_theme
    hints = qapp.styleHints()
    hints.setColorScheme(Qt.ColorScheme.Unknown)
    QApplication.processEvents()
    system_scheme = hints.colorScheme()
    settings = settings_factory()
    settings.setValue("appearance/theme_mode", "dark")
    settings.sync()
    control = create()
    welcome = WelcomeWindow()
    qtbot.addWidget(welcome)
    welcome.resize(760, 520)
    welcome.show()

    def verify(mode):
        expected = StudioColorScheme.DARK if mode == "dark" else StudioColorScheme.LIGHT
        qtbot.waitUntil(lambda: resolve_studio_theme(qapp.palette()).scheme is expected,
                        timeout=3000)
        qtbot.waitUntil(
            lambda: welcome.styleSheet() == welcome_window_stylesheet(qapp.palette()),
            timeout=3000,
        )
        assert_visible_children_within_parent(welcome)

    verify("dark")
    assert control.load_theme_mode() == "dark"
    control.set_theme_mode("light")
    verify("light")
    assert create().load_theme_mode() == "light"
    control.set_theme_mode("dark")
    verify("dark")
    # Simulate an OS theme notification, without changing the Windows setting.
    QApplication.sendEvent(qapp, QEvent(QEvent.Type.ThemeChange))
    QApplication.sendEvent(welcome, QEvent(QEvent.Type.ThemeChange))
    QApplication.processEvents()
    assert hints.colorScheme() == Qt.ColorScheme.Dark
    assert qapp.property("studioThemeMode") == "dark"
    verify("dark")
    control.set_theme_mode("auto")
    qtbot.waitUntil(lambda: hints.colorScheme() == system_scheme, timeout=3000)
    assert control.load_theme_mode() == "auto"
    assert qapp.property("studioThemeMode") == "auto"


def test_settings_controller_binds_current_theme_and_persists_callback(
    qapp, isolated_theme, monkeypatch, tmp_path,
):
    create, _ = isolated_theme
    control = create()
    control._fpvs_root_dir = tmp_path
    monkeypatch.setattr(control, "ensure_fpvs_root_configured", lambda: True)
    monkeypatch.setattr(control, "_normalize_fpvs_root_layout", lambda: True)
    control.set_theme_mode("dark")
    report = SimpleNamespace(
        enabled=False, status="", busy=False, configure=Mock(),
        changed=SimpleNamespace(connect=Mock(), disconnect=Mock()),
    )
    monkeypatch.setattr(crash_module, "crash_report_controller", lambda: report)
    received = {}

    class Dialog:
        def __init__(self, **values):
            received.update(values)

        def set_crash_reporting_state(self, *_args):
            pass

        def exec(self):
            received["on_theme_mode_changed"]("light")
            return 0

    monkeypatch.setattr(controller_module, "AppSettingsDialog", Dialog)
    control.show_settings_dialog()
    assert received["theme_mode"] == "dark"
    assert control.load_theme_mode() == "light"
    assert qapp.property("studioThemeMode") == "light"
    assert create().load_theme_mode() == "light"


def test_reduce_motion_stops_active_effects_and_persists(qtbot, qapp, isolated_theme, monkeypatch):
    monkeypatch.setattr("fpvs_studio.gui.components._system_motion_enabled", lambda: True)
    create, settings_factory = isolated_theme
    control = create()
    assert control.load_reduce_motion() is False
    panel = QWidget()
    qtbot.addWidget(panel)
    ticker = SophiaModeTicker(panel)
    spinner = SpinnerWidget(parent=panel)
    step = _ProcessingStep("test", "1", "Working", parent=panel)
    progress = UpdateProgressBar(panel)
    button = ActionFeedbackButton("Save", "Saved", panel)
    panel.show()
    ticker.set_sophia_mode_enabled(True)
    spinner.start()
    step.set_state("active")
    progress.setRange(0, 0)
    button.confirm()
    timers = (ticker._timer, spinner._timer, step._pulse_timer)
    assert all(timer.isActive() for timer in timers)
    assert progress._animation.state() == QAbstractAnimation.State.Running
    assert button._accent_animation.state() == QAbstractAnimation.State.Running

    dialog = AppSettingsDialog(
        fpvs_root_dir=control._projects_parent_dir, initial_category="Appearance",
        reduce_motion=control.load_reduce_motion(),
        on_reduce_motion_changed=control.set_reduce_motion,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.reduce_motion_checkbox.click()
    assert qapp.property("studioReduceMotion") is True
    assert settings_factory().value("appearance/reduce_motion", type=bool) is True
    assert not any(timer.isActive() for timer in timers)
    assert ticker.isVisible()
    assert step.property("processingStepState") == "active"
    assert progress._animation.state() == QAbstractAnimation.State.Stopped
    assert button._accent_animation.state() == QAbstractAnimation.State.Stopped
    assert button.text() == "Saved"
    dialog.navigation.setCurrentRow(0)
    assert dialog.navigation._indicator_animation.state() == QAbstractAnimation.State.Stopped
    assert create().load_reduce_motion() is True
    dialog.reduce_motion_checkbox.click()
    assert qapp.property("studioReduceMotion") is False
    assert all(timer.isActive() for timer in timers)
    assert progress._animation.state() == QAbstractAnimation.State.Running
