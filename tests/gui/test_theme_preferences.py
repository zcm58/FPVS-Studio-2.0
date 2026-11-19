"""Visible native theme preference, persistence and shared-style integration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image, ImageChops
from PySide6.QtCore import QAbstractAnimation, QEvent, QSettings, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QWidget
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.enums import StimulusVariant
from fpvs_studio.core.paths import project_json_path
from fpvs_studio.core.serialization import save_project_file
from fpvs_studio.gui import condition_figure_dialog as figure_module
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
from fpvs_studio.preprocessing.importer import materialize_project_assets


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


def test_appearance_changes_preserve_project_compilation_and_figure(
    qtbot, qapp, isolated_theme, monkeypatch, tmp_path, sample_project, sample_project_root,
):
    settings = sample_project.settings
    settings.display.background_color = "#39465D"
    settings.fixation_task.base_color = "#2DABA0"
    settings.fixation_task.target_color = "#F6A642"
    settings.session.randomization_mode = "fixed"
    settings.session.session_seed = 1234
    settings.session.stimulus_seed = 5678
    settings.session.fixation_seed = 9012
    save_project_file(sample_project, project_json_path(sample_project_root))
    materialize_project_assets(
        sample_project, project_root=sample_project_root, variants=[StimulusVariant.ORIGINAL],
    )

    create, _ = isolated_theme
    control = create()
    control.save_fpvs_root_dir(tmp_path)
    monkeypatch.setattr(control, "_data_sharing", lambda: SimpleNamespace(opened=Mock()))
    document = control.open_project(sample_project_root)
    window = control.main_window
    assert document is not None and window is not None
    qtbot.addWidget(window)

    def authored_files():
        return {
            path.relative_to(sample_project_root): path.read_bytes()
            for path in sample_project_root.rglob("*") if path.is_file()
        }

    def compile_plan():
        return compile_session_plan(
            document.project, project_root=document.project_root, manifest=document.manifest,
            refresh_hz=60.0, session_id="theme-isolation",
        )

    def export_in_theme(mode, scheme):
        settings_dialog = AppSettingsDialog(
            fpvs_root_dir=tmp_path, initial_category="Appearance",
            theme_mode=control.load_theme_mode(),
            on_theme_mode_changed=control.set_theme_mode, parent=window,
        )
        qtbot.addWidget(settings_dialog)
        settings_dialog.open()
        qtbot.mouseClick(settings_dialog.theme_buttons[mode], Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: resolve_studio_theme(qapp.palette()).scheme is scheme)
        assert control.load_theme_mode() == mode
        settings_dialog.close()

        output = tmp_path / f"{mode}-condition.png"
        monkeypatch.setattr(figure_module, "_choose_figure_path", lambda *_args: output)
        window.condition_figure_action.trigger()
        dialog = window.findChild(figure_module.ConditionFigureDialog)
        assert dialog is not None and dialog.isVisible()
        qtbot.waitUntil(dialog.export_button.isEnabled, timeout=10000)
        qtbot.mouseClick(dialog.export_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: not dialog.has_active_task, timeout=10000)
        assert dialog.status_label.text().startswith("Saved 600-DPI PNG.")
        dialog.close()
        qtbot.waitUntil(lambda: window.findChild(figure_module.ConditionFigureDialog) is None)
        return output

    QApplication.processEvents()
    original_files = authored_files()
    original_project = document.project.model_dump(mode="json")
    plan = compile_plan()
    original_plan = plan.model_dump(mode="json")
    run = plan.blocks[0].entries[0].run_spec
    assert run.display.background_color == "#39465D"
    assert run.fixation.default_color == "#2DABA0"
    assert run.fixation.target_color == "#F6A642"
    assert run.fixation_events
    exports = []
    for mode, scheme in (("light", StudioColorScheme.LIGHT), ("dark", StudioColorScheme.DARK)):
        exports.append(export_in_theme(mode, scheme))
        assert compile_plan().model_dump(mode="json") == original_plan
        assert not document.dirty
        assert document.project.model_dump(mode="json") == original_project
        assert authored_files() == original_files

    light, dark = exports
    with Image.open(light) as light_image, Image.open(dark) as dark_image:
        assert light_image.mode == dark_image.mode
        assert light_image.size == dark_image.size
        assert light_image.info["dpi"] == dark_image.info["dpi"]
        assert ImageChops.difference(light_image, dark_image).getbbox(alpha_only=False) is None


@pytest.mark.parametrize("theme_mode", ["light", "dark"])
@pytest.mark.parametrize("size", [(860, 560), (1000, 680)])
def test_reduce_motion_stops_active_effects_and_persists(
    qtbot, qapp, isolated_theme, monkeypatch, theme_mode, size,
):
    monkeypatch.setattr("fpvs_studio.gui.components._system_motion_enabled", lambda: True)
    create, settings_factory = isolated_theme
    control = create()
    control.set_theme_mode(theme_mode)
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

    def open_settings():
        dialog = AppSettingsDialog(
            fpvs_root_dir=control._projects_parent_dir, initial_category="Appearance",
            theme_mode=control.load_theme_mode(), reduce_motion=control.load_reduce_motion(),
            on_reduce_motion_changed=control.set_reduce_motion,
            on_automatic_crash_reports_changed=lambda _enabled: None,
        )
        qtbot.addWidget(dialog)
        dialog.resize(*size)
        dialog.show()
        QApplication.processEvents()
        assert dialog.size().toTuple() == size
        return dialog

    def check_keyboard_navigation(dialog):
        dialog.navigation.setFocus()
        qtbot.keyClick(dialog.navigation, Qt.Key.Key_Tab)
        assert dialog.theme_selector.isAncestorOf(dialog.focusWidget())
        dialog.navigation.setFocus()
        qtbot.keyClick(dialog.navigation, Qt.Key.Key_End)
        qtbot.keyClick(dialog.navigation, Qt.Key.Key_Up)
        assert dialog.page_title.text() == "Diagnostics"
        qtbot.keyClick(dialog.navigation, Qt.Key.Key_Tab)
        assert dialog.focusWidget() is dialog.crash_reports_checkbox
        dialog.navigation.setFocus()
        for _ in range(3):
            qtbot.keyClick(dialog.navigation, Qt.Key.Key_Up)
        assert dialog.page_title.text() == "Appearance"

    dialog = open_settings()
    check_keyboard_navigation(dialog)
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
    dialog.close()
    dialog = open_settings()
    assert dialog.reduce_motion_checkbox.isChecked()
    check_keyboard_navigation(dialog)
    dialog.reduce_motion_checkbox.click()
    assert qapp.property("studioReduceMotion") is False
    assert all(timer.isActive() for timer in timers)
    assert progress._animation.state() == QAbstractAnimation.State.Running
