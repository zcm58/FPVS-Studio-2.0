"""GUI smoke tests for Studio `.fpvsconfig` import/export actions."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QWidget
from tests.gui.helpers import (
    assert_visible_children_within_parent,
    open_created_project,
    prepare_compile_ready_project,
)

from fpvs_studio.core.models import DisplaySettings
from fpvs_studio.core.project_bundle import (
    ProjectBundleFileRecord,
    ProjectBundleManifest,
    ProjectBundleProject,
    ProjectBundleValidation,
    read_project_bundle_manifest,
)
from fpvs_studio.core.project_config import (
    export_project_config,
    read_project_config,
    write_project_config,
)
from fpvs_studio.gui.bundle_export_dialog import BundleExportOptionsDialog
from fpvs_studio.gui.bundle_import_dialog import (
    BundleImportProgressDialog,
    BundleImportReviewDialog,
)
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.import_display_settings_dialog import (
    DetectedDisplaySettings,
    ImportDisplaySettingsDialog,
)
from fpvs_studio.gui.main_window import _BundleExportTaskResult


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

    def fail(self, error: Exception) -> None:
        self.failed.emit(error)
        self.finished.emit()


def _sample_bundle_manifest(*, project_name: str = "Semantic Categories") -> ProjectBundleManifest:
    return ProjectBundleManifest(
        project=ProjectBundleProject(
            project_id="semantic-categories",
            name=project_name,
            template_id="default",
        ),
        validation=ProjectBundleValidation(refresh_hz=60.0),
        files=[
            ProjectBundleFileRecord(
                path="project.json",
                size_bytes=512,
                sha256="0" * 64,
            )
        ],
    )


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

    assert window.export_project_bundle(bundle_project_name="Bundle Cancel") is False

    assert not target_path.exists()


def test_export_project_bundle_name_dialog_cancel_skips_save_picker(
    controller: StudioController,
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Bundle Name Cancel",
    )
    prompted: list[str] = []

    class _RejectedBundleExportOptionsDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, *, current_project_name, parent=None):
            prompted.append(current_project_name)

        def exec(self):
            return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.BundleExportOptionsDialog",
        _RejectedBundleExportOptionsDialog,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: pytest.fail("Save picker should not open after Cancel."),
    )

    window.export_project_bundle_action.trigger()

    assert prompted == ["Bundle Name Cancel"]


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

    assert window.export_project_bundle(bundle_project_name="Bundle Export") is True

    bundle_path = target_path.with_suffix(".fpvsbundle")
    assert bundle_path.is_file()
    exported = read_project_bundle_manifest(bundle_path)
    assert exported.project.name == "Bundle Export"
    assert window.main_stack.currentWidget() is window.bundle_export_result_page
    assert window.bundle_export_result_page.filename_label.text() == bundle_path.name

    window.bundle_export_result_page.done_button.click()

    assert window.main_stack.currentWidget() is window.home_page


def test_export_project_bundle_shows_embedded_processing_screen(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Bundle Wait")
    window.resize(1120, 720)
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

    assert window.export_project_bundle(bundle_project_name="Bundle Wait") is True

    assert len(_DeferredBackgroundTask.instances) == 1
    assert _DeferredBackgroundTask.instances[0].started is True
    QApplication.processEvents()
    assert window.main_stack.currentWidget() is window.bundle_export_processing_page
    assert (
        window.bundle_export_processing_page.findChild(
            QWidget,
            "bundle_export_processing_content",
        )
        is not None
    )
    content = window.bundle_export_processing_page.findChild(
        QWidget,
        "bundle_export_processing_content",
    )
    assert content is not None
    assert content.geometry().left() >= 0
    assert content.geometry().right() <= window.bundle_export_processing_page.width()
    assert abs(
        content.geometry().center().x()
        - window.bundle_export_processing_page.rect().center().x()
    ) <= 1
    assert content.property("bundleProcessingCard") == "true"
    assert window.bundle_export_processing_page.message_label.text() == (
        "Preparing a portable copy of this project."
    )
    source_label = window.bundle_export_processing_page.source_value_label
    assert str(window.document.project_root) in (source_label.text(), source_label.toolTip())
    assert window.bundle_export_processing_page.destination_value_label.text().endswith(
        "exported.fpvsbundle"
    )
    first_step = window.bundle_export_processing_page.findChild(
        QWidget,
        "bundle_export_processing_step_1",
    )
    second_step = window.bundle_export_processing_page.findChild(
        QWidget,
        "bundle_export_processing_step_2",
    )
    third_step = window.bundle_export_processing_page.findChild(
        QWidget,
        "bundle_export_processing_step_3",
    )
    assert first_step is not None
    assert second_step is not None
    assert third_step is not None
    assert first_step.property("processingStepState") == "active"
    assert second_step.property("processingStepState") == "pending"
    assert third_step.property("processingStepState") == "pending"
    window._on_bundle_export_stage_changed("stimuli")
    assert first_step.property("processingStepState") == "complete"
    assert second_step.property("processingStepState") == "active"
    assert third_step.property("processingStepState") == "pending"
    window._on_bundle_export_stage_changed("write")
    assert first_step.property("processingStepState") == "complete"
    assert second_step.property("processingStepState") == "complete"
    assert third_step.property("processingStepState") == "active"
    window._on_bundle_export_stage_changed("complete")
    assert first_step.property("processingStepState") == "complete"
    assert second_step.property("processingStepState") == "complete"
    assert third_step.property("processingStepState") == "complete"
    assert_visible_children_within_parent(window.bundle_export_processing_page)
    for index in range(1, 4):
        step_label = window.bundle_export_processing_page.findChild(
            QLabel,
            f"bundle_export_processing_step_{index}_label",
        )
        assert step_label is not None
        required_width = step_label.fontMetrics().horizontalAdvance(step_label.text())
        assert step_label.width() >= required_width
    assert window.export_project_bundle_action.isEnabled() is False

    bundle_path = target_path.with_suffix(".fpvsbundle")
    bundle_path.write_bytes(b"bundle")
    _DeferredBackgroundTask.instances[0].complete_successfully(
        _BundleExportTaskResult(
            path=bundle_path,
            manifest=_sample_bundle_manifest(project_name="Bundle Wait"),
        )
    )

    assert window.main_stack.currentWidget() is window.bundle_export_result_page
    assert window.export_project_bundle_action.isEnabled() is True

    window.bundle_export_result_page.done_button.click()

    assert window.main_stack.currentWidget() is window.home_page


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

    assert (
        window.export_project_bundle(bundle_project_name="Semantic Categories") is False
    )

    assert captured["path"].endswith("semanticcategories.fpvsbundle")


def test_bundle_export_options_dialog_previews_import_identity(qtbot) -> None:
    dialog = BundleExportOptionsDialog(current_project_name="Semantic Categories")
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()

    assert dialog.export_project_name == "Semantic Categories"
    assert dialog.folder_value_label.text() == "semantic-categories"
    assert dialog.filename_value_label.text() == "semanticcategories.fpvsbundle"

    dialog.project_name_edit.setText("Semantic Categories Import Test")

    assert dialog.export_project_name == "Semantic Categories Import Test"
    assert dialog.folder_value_label.text() == "semantic-categories-import-test"
    assert dialog.filename_value_label.text() == (
        "semanticcategoriesimporttest.fpvsbundle"
    )
    assert dialog.continue_button.isEnabled() is True
    assert_visible_children_within_parent(dialog)

    dialog.project_name_edit.setText("   ")

    assert dialog.continue_button.isEnabled() is False
    assert "Enter a project name" in dialog.validation_label.text()


def test_export_project_bundle_dialog_name_changes_portable_copy_only(
    controller: StudioController,
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Bundle Source Name",
    )
    prepare_compile_ready_project(window, tmp_path)
    target_path = tmp_path / "renamed-copy.fpvsbundle"
    captured: dict[str, str] = {}

    class _FakeBundleExportOptionsDialog:
        DialogCode = QDialog.DialogCode
        export_project_name = "Bundle Import Test Copy"

        def __init__(self, *, current_project_name, parent=None):
            assert current_project_name == "Bundle Source Name"

        def exec(self):
            return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.BundleExportOptionsDialog",
        _FakeBundleExportOptionsDialog,
    )
    def _select_bundle_path(*args, **kwargs):
        captured["default_path"] = args[2]
        return str(target_path), ""

    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QFileDialog.getSaveFileName",
        _select_bundle_path,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.BackgroundTask",
        _ImmediateBackgroundTask,
    )

    assert window.export_project_bundle() is True

    exported = read_project_bundle_manifest(target_path)
    assert exported.project.name == "Bundle Import Test Copy"
    assert exported.project.project_id == "bundle-import-test-copy"
    assert captured["default_path"].endswith("bundleimporttestcopy.fpvsbundle")
    assert window.document.project.meta.name == "Bundle Source Name"


def test_bundle_export_result_page_copies_path_opens_folder_and_waits_for_done(
    controller: StudioController,
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Bundle Result")
    bundle_path = tmp_path / "bundle-result.fpvsbundle"
    bundle_path.write_bytes(b"bundle")
    opened: list[Path] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.folder_actions.open_folder",
        lambda path: opened.append(Path(path)) or True,
    )
    window._bundle_export_previous_widget = window.home_page
    page = window.bundle_export_result_page
    page.set_result(
        project_name="Bundle Result",
        bundle_path=bundle_path,
        packaged_file_count=3,
    )
    window.main_stack.setCurrentWidget(page)

    page.copy_path_button.click()
    page.open_folder_button.click()

    assert QApplication.clipboard().text() == str(bundle_path)
    assert opened == [bundle_path.parent]
    assert window.main_stack.currentWidget() is page

    page.done_button.click()

    assert window.main_stack.currentWidget() is window.home_page


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


def test_bundle_import_review_dialog_shows_manifest_destination_and_choices(
    qtbot,
    tmp_path: Path,
) -> None:
    bundle_path = tmp_path / "semanticcategories.fpvsbundle"
    root_dir = tmp_path / "studio-root"
    dialog = BundleImportReviewDialog(
        bundle_path=bundle_path,
        root_dir=root_dir,
        manifest=_sample_bundle_manifest(),
    )
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()

    assert dialog.filename_label.text() == bundle_path.name
    assert dialog.manifest_badge.text() == "Manifest readable"
    assert dialog.destination_label.toolTip() in {"", str(root_dir / "semantic-categories")}
    assert str(root_dir / "semantic-categories") in (
        dialog.destination_label.text(),
        dialog.destination_label.toolTip(),
    )
    assert_visible_children_within_parent(dialog)

    dialog.choose_another_button.click()

    assert dialog.result() == BundleImportReviewDialog.CHOOSE_ANOTHER_RESULT


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
    configured_root = tmp_path / "configured-fpvs-root"
    configured_root.mkdir()
    controller.save_fpvs_root_dir(configured_root)
    assert controller.load_fpvs_root_dir() == configured_root.resolve()
    assert configured_root.resolve() != Path.cwd().resolve()
    monkeypatch.setattr(
        "fpvs_studio.gui.controller.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(bundle_path), ""),
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.controller.BackgroundTask",
        _ImmediateBackgroundTask,
    )
    manifest = read_project_bundle_manifest(bundle_path)
    monkeypatch.setattr(
        controller,
        "_show_project_bundle_import_review",
        lambda *args, **kwargs: (int(QDialog.DialogCode.Accepted), manifest),
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

        @property
        def should_apply_updates(self):
            return True

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
    assert imported_window.document.project_root.parent == configured_root.resolve()
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


def test_import_project_bundle_shows_embedded_processing_screen(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Bundle Import Wait")
    window.resize(1120, 720)
    bundle_path = tmp_path / "import.fpvsbundle"
    _DeferredBackgroundTask.instances.clear()
    monkeypatch.setattr(
        "fpvs_studio.gui.controller.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(bundle_path), ""),
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.controller.BackgroundTask",
        _DeferredBackgroundTask,
    )
    monkeypatch.setattr(
        controller,
        "_show_project_bundle_import_review",
        lambda *args, **kwargs: (
            int(QDialog.DialogCode.Accepted),
            _sample_bundle_manifest(project_name="Bundle Import Wait"),
        ),
    )

    window.import_project_bundle_action.trigger()

    assert len(_DeferredBackgroundTask.instances) == 1
    assert _DeferredBackgroundTask.instances[0].started is True
    QApplication.processEvents()
    assert window.main_stack.currentWidget() is window.bundle_import_processing_page
    assert window.bundle_import_processing_page.message_label.text() == (
        "Creating a local FPVS Studio project from the selected bundle."
    )
    assert window.bundle_import_processing_page.source_value_label.text().endswith(
        "import.fpvsbundle"
    )
    assert window.bundle_import_processing_page.content.width() >= 820
    assert (
        window.bundle_import_processing_page.context_card.property(
            "bundleProcessingContext"
        )
        == "flat"
    )
    assert (
        window.bundle_import_processing_page.activity_card.property(
            "bundleProcessingActivity"
        )
        == "flat"
    )
    assert_visible_children_within_parent(window.bundle_import_processing_page)

    first_step = window.bundle_import_processing_page.findChild(
        QWidget,
        "bundle_import_processing_step_1",
    )
    second_step = window.bundle_import_processing_page.findChild(
        QWidget,
        "bundle_import_processing_step_2",
    )
    third_step = window.bundle_import_processing_page.findChild(
        QWidget,
        "bundle_import_processing_step_3",
    )
    fourth_step = window.bundle_import_processing_page.findChild(
        QWidget,
        "bundle_import_processing_step_4",
    )
    assert first_step is not None
    assert second_step is not None
    assert third_step is not None
    assert fourth_step is not None
    assert first_step.property("processingStepState") == "active"
    assert second_step.property("processingStepState") == "pending"
    assert third_step.property("processingStepState") == "pending"
    assert fourth_step.property("processingStepState") == "pending"
    for index in range(1, 5):
        step_label = window.bundle_import_processing_page.findChild(
            QLabel,
            f"bundle_import_processing_step_{index}_label",
        )
        assert step_label is not None
        required_width = step_label.fontMetrics().horizontalAdvance(step_label.text())
        assert step_label.width() >= required_width

    controller._on_import_project_bundle_stage_changed("base")
    assert first_step.property("processingStepState") == "complete"
    assert second_step.property("processingStepState") == "active"
    assert third_step.property("processingStepState") == "pending"
    assert fourth_step.property("processingStepState") == "pending"
    controller._on_import_project_bundle_stage_changed("oddball")
    assert first_step.property("processingStepState") == "complete"
    assert second_step.property("processingStepState") == "complete"
    assert third_step.property("processingStepState") == "active"
    assert fourth_step.property("processingStepState") == "pending"
    controller._on_import_project_bundle_stage_changed("project")
    assert first_step.property("processingStepState") == "complete"
    assert second_step.property("processingStepState") == "complete"
    assert third_step.property("processingStepState") == "complete"
    assert fourth_step.property("processingStepState") == "active"

    _DeferredBackgroundTask.instances[0].fail(RuntimeError("cancel test import"))

    assert window.main_stack.currentWidget() is window.home_page
    assert window.import_project_bundle_action.isEnabled() is True


def test_bundle_import_progress_dialog_is_expanded_without_clipping(qtbot, tmp_path) -> None:
    dialog = BundleImportProgressDialog()
    qtbot.addWidget(dialog)
    dialog.set_context(
        project_name="Expanded Import Project",
        bundle_path=tmp_path / "expanded-import-project.fpvsbundle",
        root_dir=tmp_path / "FPVS Studio Root",
    )

    dialog.start()
    QApplication.processEvents()

    assert dialog.width() >= 940
    assert dialog.height() >= 600
    assert dialog.page.content.width() >= 820
    assert_visible_children_within_parent(dialog)
    for index in range(1, 5):
        step_label = dialog.findChild(
            QLabel,
            f"bundle_import_processing_step_{index}_label",
        )
        assert step_label is not None
        required_width = step_label.fontMetrics().horizontalAdvance(step_label.text())
        assert step_label.width() >= required_width

    dialog.finish()


def test_import_display_settings_dialog_detect_button_fills_available_values(
    qtbot,
    monkeypatch,
) -> None:
    dialog = ImportDisplaySettingsDialog(DisplaySettings())
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
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
    assert dialog.detected_refresh_label.text() == "119.88 Hz"
    assert dialog.detected_resolution_label.text() == "2560 × 1440 px"
    assert dialog.detected_badge.text() == "Detected"
    assert_visible_children_within_parent(dialog)


def test_import_display_settings_dialog_actions_are_explicit(qtbot) -> None:
    keep_dialog = ImportDisplaySettingsDialog(DisplaySettings())
    qtbot.addWidget(keep_dialog)

    keep_dialog.keep_button.click()

    assert keep_dialog.result() == int(QDialog.DialogCode.Accepted)
    assert keep_dialog.should_apply_updates is False

    apply_dialog = ImportDisplaySettingsDialog(DisplaySettings())
    qtbot.addWidget(apply_dialog)

    apply_dialog.apply_button.click()

    assert apply_dialog.result() == int(QDialog.DialogCode.Accepted)
    assert apply_dialog.should_apply_updates is True
