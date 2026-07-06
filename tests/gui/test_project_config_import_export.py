"""GUI smoke tests for Studio `.fpvsconfig` import/export actions."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog, QWidget
from tests.gui.helpers import open_created_project, prepare_compile_ready_project

from fpvs_studio.core.models import DisplaySettings
from fpvs_studio.core.project_bundle import read_project_bundle_manifest
from fpvs_studio.core.project_config import (
    export_project_config,
    read_project_config,
    write_project_config,
)
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.import_display_settings_dialog import (
    DetectedDisplaySettings,
    ImportDisplaySettingsDialog,
)


class _ImmediateBackgroundTask(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, *, parent_widget, callback) -> None:
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


class _DeferredBackgroundTask(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()
    instances: list[_DeferredBackgroundTask] = []

    def __init__(self, *, parent_widget, callback) -> None:
        super().__init__(parent_widget)
        self._callback = callback
        self.started = False
        self.instances.append(self)

    def start(self) -> None:
        self.started = True

    def complete_successfully(self, result: object) -> None:
        self.succeeded.emit(result)
        self.finished.emit()


def test_export_project_config_cancel_leaves_no_file(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Config Cancel")
    target_path = tmp_path / "cancelled.fpvsconfig"
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: ("", ""),
    )

    assert window.export_project_config() is False

    assert not target_path.exists()


def test_export_project_config_writes_selected_config(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Config Export")
    target_path = tmp_path / "exported"
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(target_path), ""),
    )

    assert window.export_project_config() is True

    config_path = target_path.with_suffix(".fpvsconfig")
    assert config_path.is_file()
    exported = read_project_config(config_path)
    assert exported.project.name == "Config Export"


def test_export_project_config_defaults_to_compact_project_title_filename(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Semantic Categories")
    captured: dict[str, str] = {}

    def _capture_save_path(*args, **kwargs):
        captured["path"] = args[2]
        return "", ""

    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QFileDialog.getSaveFileName",
        _capture_save_path,
    )

    assert window.export_project_config() is False

    assert captured["path"].endswith("semanticcategories.fpvsconfig")


def test_export_project_bundle_cancel_leaves_no_file(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Bundle Cancel")
    target_path = tmp_path / "cancelled.fpvsbundle"
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: ("", ""),
    )

    assert window.export_project_bundle() is False

    assert not target_path.exists()


def test_export_project_bundle_writes_selected_bundle(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Bundle Export")
    prepare_compile_ready_project(window, tmp_path)
    target_path = tmp_path / "exported"
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(target_path), ""),
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.BackgroundTask",
        _ImmediateBackgroundTask,
    )

    assert window.export_project_bundle() is True

    bundle_path = target_path.with_suffix(".fpvsbundle")
    assert bundle_path.is_file()
    exported = read_project_bundle_manifest(bundle_path)
    assert exported.project.name == "Bundle Export"
    assert window.main_stack.currentWidget() is window.home_page


def test_export_project_bundle_shows_embedded_processing_screen(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Bundle Wait")
    target_path = tmp_path / "exported"
    _DeferredBackgroundTask.instances.clear()
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(target_path), ""),
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.BackgroundTask",
        _DeferredBackgroundTask,
    )

    assert window.export_project_bundle() is True

    assert len(_DeferredBackgroundTask.instances) == 1
    assert _DeferredBackgroundTask.instances[0].started is True
    assert window.main_stack.currentWidget() is window.bundle_export_processing_page
    assert (
        window.bundle_export_processing_page.findChild(
            QWidget,
            "bundle_export_processing_content",
        )
        is not None
    )
    assert (
        window.bundle_export_processing_page.findChild(
            QWidget,
            "bundle_export_processing_card",
        )
        is None
    )
    assert "compiling your project into a shareable format" in (
        window.bundle_export_processing_page.message_label.text()
    )
    assert window.export_project_bundle_action.isEnabled() is False

    _DeferredBackgroundTask.instances[0].complete_successfully(
        target_path.with_suffix(".fpvsbundle")
    )

    assert window.main_stack.currentWidget() is window.home_page
    assert window.export_project_bundle_action.isEnabled() is True


def test_export_project_bundle_defaults_to_compact_project_title_filename(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Semantic Categories")
    captured: dict[str, str] = {}

    def _capture_save_path(*args, **kwargs):
        captured["path"] = args[2]
        return "", ""

    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QFileDialog.getSaveFileName",
        _capture_save_path,
    )

    assert window.export_project_bundle() is False

    assert captured["path"].endswith("semanticcategories.fpvsbundle")


def test_export_group_summary_cancel_leaves_no_file(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Group Cancel")
    target_path = tmp_path / "cancelled.xlsx"
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: ("", ""),
    )

    assert window.export_group_summary() is False

    assert not target_path.exists()


def test_export_group_summary_writes_selected_workbook(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Group Export")
    target_path = tmp_path / "group-summary"
    captured_paths: list[object] = []

    def _export_group_summary(path):
        captured_paths.append(path)
        path.write_text("stub workbook", encoding="utf-8")
        return path

    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(target_path), ""),
    )
    monkeypatch.setattr(
        window.document,
        "export_group_summary_file",
        _export_group_summary,
    )

    assert window.export_group_summary() is True

    summary_path = target_path.with_suffix(".xlsx")
    assert captured_paths == [summary_path]
    assert summary_path.read_text(encoding="utf-8") == "stub workbook"


def test_export_group_summary_defaults_to_group_summary_workbook(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Group Default")
    captured: dict[str, str] = {}

    def _capture_save_path(*args, **kwargs):
        captured["path"] = args[2]
        return "", ""

    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QFileDialog.getSaveFileName",
        _capture_save_path,
    )

    assert window.export_group_summary() is False

    assert captured["path"].endswith("group_summary.xlsx")


def test_import_project_config_cancel_leaves_current_project_unchanged(
    controller: StudioController,
    qtbot,
    tmp_path,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Config Current")

    window.import_project_config_action.trigger()

    assert controller.main_window is window
    assert controller.main_window.document.project.meta.name == "Config Current"


def test_import_project_config_creates_and_opens_new_clean_project(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Config Source")
    config = export_project_config(window.document.project, window.document.project_root)
    config_path = tmp_path / "import.fpvsconfig"
    write_project_config(config_path, config)
    monkeypatch.setattr(
        "fpvs_studio.gui.controller.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(config_path), ""),
    )

    window.import_project_config_action.trigger()
    qtbot.waitUntil(lambda: controller.main_window is not window, timeout=1000)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)

    imported_window = controller.main_window
    assert imported_window.document.project.meta.name == "Config Source"
    assert imported_window.document.project_root.parent == controller.load_fpvs_root_dir()
    assert imported_window.document.dirty is False


def test_import_project_bundle_cancel_leaves_current_project_unchanged(
    controller: StudioController,
    qtbot,
    tmp_path,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Bundle Current")

    window.import_project_bundle_action.trigger()

    assert controller.main_window is window
    assert controller.main_window.document.project.meta.name == "Bundle Current"


def test_import_project_bundle_creates_and_opens_complete_project(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Bundle Source")
    prepare_compile_ready_project(window, tmp_path)
    bundle_path = tmp_path / "import.fpvsbundle"
    window.document.save()
    window.document.export_bundle_file(bundle_path)
    monkeypatch.setattr(
        "fpvs_studio.gui.controller.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(bundle_path), ""),
    )

    class _FakeImportDisplaySettingsDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, display, parent=None):
            self.display = display

        def exec(self):
            return QDialog.DialogCode.Accepted

        def display_updates(self):
            return {
                "preferred_refresh_hz": 120.0,
                "viewing_distance_cm": 75.0,
                "screen_width_cm": 60.0,
                "screen_width_px": 2560,
                "screen_height_px": 1440,
                "use_current_screen_resolution": False,
            }

    monkeypatch.setattr(
        "fpvs_studio.gui.controller.ImportDisplaySettingsDialog",
        _FakeImportDisplaySettingsDialog,
    )

    window.import_project_bundle_action.trigger()
    qtbot.waitUntil(lambda: controller.main_window is not window, timeout=1000)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)

    imported_window = controller.main_window
    assert imported_window.document.project.meta.name == "Bundle Source"
    assert imported_window.document.project_root.parent == controller.load_fpvs_root_dir()
    assert imported_window.document.dirty is False
    assert (
        imported_window.document.project_root
        / "stimuli"
        / "original-images"
        / "condition-1-base"
    ).is_dir()
    display = imported_window.document.project.settings.display
    assert display.preferred_refresh_hz == 120.0
    assert display.viewing_distance_cm == 75.0
    assert display.screen_width_cm == 60.0
    assert display.screen_width_px == 2560
    assert display.screen_height_px == 1440


def test_import_display_settings_dialog_detect_button_fills_available_values(
    qtbot,
    monkeypatch,
) -> None:
    dialog = ImportDisplaySettingsDialog(DisplaySettings())
    qtbot.addWidget(dialog)
    monkeypatch.setattr(
        "fpvs_studio.gui.import_display_settings_dialog.detect_primary_display_settings",
        lambda: DetectedDisplaySettings(
            refresh_hz=119.88,
            screen_width_cm=61.2,
            screen_width_px=2560,
            screen_height_px=1440,
        ),
    )

    dialog.apply_detected_primary_display()

    assert dialog.refresh_hz_spin.value() == 119.88
    assert dialog.screen_width_cm_spin.value() == 61.2
    assert dialog.screen_width_px_spin.value() == 2560
    assert dialog.screen_height_px_spin.value() == 1440
