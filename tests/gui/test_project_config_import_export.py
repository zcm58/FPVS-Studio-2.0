"""GUI smoke tests for Studio `.fpvsconfig` import/export actions."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QAbstractAnimation, QObject, QRect, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QFrame, QLabel, QPushButton, QWidget
from tests.gui.helpers import (
    assert_visible_children_within_parent,
    open_created_project,
    prepare_compile_ready_project,
)
from tests.platform_adapters import set_module_platform

from fpvs_studio.core.models import DisplaySettings
from fpvs_studio.core.project_bundle import (
    ProjectBundleError,
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
from fpvs_studio.core.project_service import create_project
from fpvs_studio.gui import import_display_settings_dialog, processing_page
from fpvs_studio.gui.bundle_export_dialog import BundleExportOptionsDialog
from fpvs_studio.gui.bundle_import_dialog import (
    BundleImportProgressDialog,
    BundleImportReviewDialog,
)
from fpvs_studio.gui.components import apply_studio_theme
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.import_display_settings_dialog import (
    DetectedDisplaySettings,
    ImportDisplaySettingsDialog,
    detect_primary_display_settings,
)
from fpvs_studio.gui.main_window import _BundleExportTaskResult
from fpvs_studio.gui.processing_page import (
    BundleExportProcessingPage,
    BundleExportResultPage,
    BundleImportProcessingPage,
)
from fpvs_studio.runtime.display_mode import DisplayModeError, NativeDisplayMode


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
    assert not isinstance(window.bundle_export_processing_page.context_card, QFrame)
    assert not isinstance(window.bundle_export_processing_page.activity_card, QFrame)
    assert window.bundle_export_processing_page.title_label.text() == "Exporting Bundle Wait"
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
    assert window.bundle_export_processing_page.current_activity_label.text() == "Bundle ready"
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


@pytest.mark.parametrize("size", [(560, 350), (620, 370)], ids=["minimum", "default"])
@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"], ids=["light", "dark"])
def test_bundle_export_options_dialog_previews_import_identity(qtbot, size, background) -> None:
    dialog = BundleExportOptionsDialog(current_project_name="Semantic Categories")
    qtbot.addWidget(dialog)
    dialog.setPalette(QPalette(QColor(background)))
    dialog.resize(*size)
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
    assert dialog.size().toTuple() == size
    assert not any(
        widget.property("bundleWorkflowCard") == "true" for widget in dialog.findChildren(QWidget)
    )
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


def _assert_bundle_processing_geometry(page: QWidget) -> None:
    assert_visible_children_within_parent(page)
    for label in page.findChildren(QLabel):
        if not label.isVisible() or not label.text():
            continue
        if label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width()), label.text()
        else:
            assert label.contentsRect().width() >= label.fontMetrics().horizontalAdvance(
                label.text(),
            ), label.text()
            assert label.contentsRect().height() >= label.fontMetrics().height(), label.text()
    for button in page.findChildren(QPushButton):
        if button.isVisible():
            assert button.width() >= button.fontMetrics().horizontalAdvance(button.text())


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"], ids=["light", "dark"])
@pytest.mark.parametrize("size", [(760, 465), (1120, 665)], ids=["minimum", "default"])
def test_bundle_export_progress_and_result_use_one_frame(qtbot, tmp_path, background, size):
    bundle_path = tmp_path / ("Familiar objects and unfamiliar exemplars " * 3 + ".fpvsbundle")
    export = BundleExportProcessingPage()
    result = BundleExportResultPage()
    export.set_transfer_context(
        title=None,
        source_label="Source",
        source_path=bundle_path,
        destination_label="Destination",
        destination_path=tmp_path / "Review destination",
    )
    export.set_stage("write")
    project_name = "Familiar objects and unfamiliar exemplars " * 3
    result.set_result(project_name=project_name.strip(), bundle_path=bundle_path,
                      packaged_file_count=8)

    for page in (export, result):
        qtbot.addWidget(page)
        page.setPalette(QPalette(QColor(background)))
        apply_studio_theme(page)
        page.resize(*size)
        page.show()
        QApplication.processEvents()
        assert page.size().toTuple() == size
        frames = [frame for frame in page.findChildren(QFrame) if type(frame) is QFrame]
        assert len(frames) == 1
        assert abs(frames[0].geometry().center().x() - page.rect().center().x()) <= 1
        _assert_bundle_processing_geometry(page)

    filename = result.filename_label
    assert filename.toolTip() == filename.accessibleName() == bundle_path.name
    for path_label in (export.source_value_label, result.path_label):
        assert path_label.text().endswith(".fpvsbundle")
        assert path_label.toolTip() == path_label.accessibleName() == str(bundle_path)


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"], ids=["light", "dark"])
@pytest.mark.parametrize("size", [(760, 465), (1120, 665)], ids=["minimum", "default"])
def test_bundle_import_progress_discloses_long_paths_without_clipping(
    qtbot, tmp_path, background, size,
):
    page = BundleImportProcessingPage()
    qtbot.addWidget(page)
    page.setPalette(QPalette(QColor(background)))
    apply_studio_theme(page)
    title = "Importing Familiar objects and unfamiliar exemplars across language groups"
    bundle = tmp_path / ("Long source experiment name with spaces " * 4 + ".fpvsbundle")
    destination = tmp_path / ("FPVS Studio project repository and teaching examples " * 3).strip()
    page.set_transfer_context(
        title=title,
        source_label="Experiment file",
        source_path=bundle,
        destination_label="Destination root",
        destination_path=destination,
    )
    page.set_stage("oddball")
    page.resize(*size)
    page.show()
    QApplication.processEvents()

    assert page.size().toTuple() == size
    assert abs(page.content.geometry().center().x() - page.rect().center().x()) <= 1
    assert page.title_label.text() == title
    assert page.locations_button.text() == "File locations"
    assert not page.context_card.isVisible()
    assert page.locations_button.width() >= page.locations_button.fontMetrics().horizontalAdvance(
        page.locations_button.text(),
    )
    assert page.findChild(QWidget, "processing_spinner") is None
    assert sum(
        label.isVisible() and label.text() == "Checking oddball stimuli…"
        for label in page.findChildren(QLabel)
    ) == 1
    _assert_bundle_processing_geometry(page)

    qtbot.keyClick(page.locations_button, Qt.Key.Key_Space)
    QApplication.processEvents()
    assert page.locations_button.isChecked()
    assert page.context_card.isVisible()
    assert page.source_value_label.text().endswith(".fpvsbundle")
    for label, path in (
        (page.source_value_label, bundle),
        (page.destination_value_label, destination),
    ):
        assert label.toolTip() == label.accessibleName() == str(path)
    _assert_bundle_processing_geometry(page)

    error = "The bundle is missing an oddball image folder. Choose a complete bundle and try again."
    page.set_error(error)
    QApplication.processEvents()
    assert page.outcome_label.isVisible()
    assert page.outcome_label.text() == error
    assert page.context_card.isVisible()
    _assert_bundle_processing_geometry(page)

    qtbot.keyClick(page.locations_button, Qt.Key.Key_Space)
    QApplication.processEvents()
    assert not page.context_card.isVisible()


@pytest.mark.parametrize("reduce_motion", [False, True], ids=["motion", "reduced-motion"])
def test_import_progress_update_uses_real_stages_and_respects_motion(
    qtbot, monkeypatch, reduce_motion,
):
    monkeypatch.setattr(
        processing_page, "widget_animation_duration",
        lambda _widget, limit: 0 if reduce_motion else limit,
    )
    page = BundleImportProcessingPage()
    qtbot.addWidget(page)
    page.set_update_mode(True)
    page.resize(760, 465)
    page.show()
    page.start()
    page.set_stage("verify")
    QApplication.processEvents()
    verify = page.findChild(QWidget, "bundle_import_processing_step_1")
    commit = page.findChild(QWidget, "bundle_import_processing_step_commit")
    assert verify is not None and verify.isVisible()
    assert commit is not None and commit.isVisible()
    assert verify.property("processingStepState") == "active"
    assert commit.property("processingStepState") == "pending"

    page.set_stage("base")  # Update never reports normal import stimulus phases.
    assert verify.property("processingStepState") == "active"
    assert commit.property("processingStepState") == "pending"
    page.set_stage("commit")
    assert verify.property("processingStepState") == "complete"
    assert commit.property("processingStepState") == "active"
    assert all(
        not step.isVisible() for index in (2, 3, 4)
        if (step := page.findChild(QWidget, f"bundle_import_processing_step_{index}")) is not None
    )
    animations = page.findChildren(QVariantAnimation)
    assert animations
    assert any(
        animation.state() == QAbstractAnimation.State.Running for animation in animations
    ) is not reduce_motion

    page.set_stage("complete")
    assert commit.property("processingStepState") == "complete"
    assert page.title_label.text() == "Project updated"
    page.stop()
    assert all(animation.state() == QAbstractAnimation.State.Stopped for animation in animations)
    _assert_bundle_processing_geometry(page)


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


@pytest.mark.parametrize("size", [(720, 560), (780, 610)], ids=["minimum", "default"])
@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"], ids=["light", "dark"])
def test_bundle_import_review_dialog_shows_manifest_destination_and_choices(
    qtbot,
    tmp_path: Path,
    size,
    background,
) -> None:
    bundle_path = tmp_path / ("semantic-categories-" * 8 + "experiment.fpvsbundle")
    root_dir = tmp_path / " - ".join(["Lab project root"] * 7)
    dialog = BundleImportReviewDialog(
        bundle_path=bundle_path,
        root_dir=root_dir,
        manifest=_sample_bundle_manifest(),
    )
    qtbot.addWidget(dialog)
    dialog.setPalette(QPalette(QColor(background)))
    dialog.resize(*size)
    dialog.show()
    QApplication.processEvents()

    assert dialog.manifest_badge.text() == "Manifest readable"
    assert dialog.size().toTuple() == size
    assert not any(
        widget.property("bundleWorkflowCard") == "true" for widget in dialog.findChildren(QWidget)
    )
    for label, full_text in (
        (dialog.filename_label, bundle_path.name),
        (dialog.destination_label, str(root_dir / "semantic-categories")),
    ):
        assert label.toolTip() == label.accessibleName() == full_text
        assert label.fontMetrics().horizontalAdvance(label.text()) <= label.contentsRect().width()
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
    stimulus_sets = imported_window.document.project.stimulus_sets
    assert len(stimulus_sets) == 2
    for stimulus_set in stimulus_sets:
        assert stimulus_set.source_dir is not None
        imported_images = imported_window.document.project_root / stimulus_set.source_dir
        assert len(list(imported_images.glob("*.png"))) == stimulus_set.image_count == 3
    display = imported_window.document.project.settings.display
    assert display.preferred_refresh_hz == 120.0
    assert display.viewing_distance_cm == 75.0
    assert display.screen_width_cm == 60.0
    assert display.screen_width_px == 2560
    assert display.screen_height_px == 1440


def test_import_project_bundle_does_not_open_after_display_dialog_rejection(
    controller: StudioController,
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Current Bundle Project",
    )
    import_root = tmp_path / "import-root"
    scaffold = create_project(import_root, "Rejected Display Project")

    class _RejectedImportDisplaySettingsDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, display, parent=None):
            self.display = display

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "fpvs_studio.gui.controller.ImportDisplaySettingsDialog",
        _RejectedImportDisplaySettingsDialog,
    )
    controller._import_bundle_processing_window = window
    window.start_bundle_import_processing(
        project_name="Rejected Display Project",
        bundle_path=tmp_path / "rejected-display.fpvsbundle",
        root_dir=import_root,
    )

    controller._on_import_project_bundle_succeeded(scaffold)

    assert controller.main_window is window
    assert window.document.project.meta.name == "Current Bundle Project"
    assert window.main_stack.currentWidget() is window.home_page


def test_import_project_bundle_shows_embedded_progress_and_retains_error(
    controller: StudioController,
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path, "Bundle Import Wait")
    window.resize(1120, 720)
    bundle_path = tmp_path / "import.fpvsbundle"
    _DeferredBackgroundTask.instances.clear()
    error_details = []
    monkeypatch.setattr(
        "fpvs_studio.gui.controller.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(bundle_path), ""),
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.controller.BackgroundTask",
        _DeferredBackgroundTask,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.controller._show_error",
        lambda *args: error_details.append(args),
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
    page = window.bundle_import_processing_page
    assert window.main_stack.currentWidget() is page
    assert page.title_label.text() == "Importing Bundle Import Wait"
    assert not page.context_card.isVisible()
    assert not window.import_project_bundle_action.isEnabled()
    assert not page.error_details_button.isVisible()
    page.locations_button.click()
    QApplication.processEvents()
    assert page.source_heading_label.text() == "Experiment file"
    assert page.source_value_label.toolTip() == str(bundle_path)
    assert page.context_card.isVisible()
    _assert_bundle_processing_geometry(page)

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
    assert first_step.findChild(QLabel).text() == "Verifying experiment files…"
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
    assert first_step.findChild(QLabel).text() == "Experiment files validated"
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

    error = ProjectBundleError("Project bundle checksum mismatch: project.json")
    _DeferredBackgroundTask.instances[0].fail(error)
    QApplication.processEvents()
    assert window.main_stack.currentWidget() is page
    assert fourth_step.property("processingStepState") == "failed"
    assert page.outcome_label.isVisible()
    assert "damaged" in page.outcome_label.text().lower()
    assert not window.import_project_bundle_action.isEnabled()
    close_button = page.findChild(QPushButton, "bundle_import_error_close")
    assert close_button is not None and close_button.isVisible()
    assert close_button.text() == "Close"
    _assert_bundle_processing_geometry(page)
    assert error_details == []
    assert page.error_details_button.isVisible()
    page.error_details_button.click()
    assert error_details == [(window, "Import Project Error", error)]

    close_button.click()
    QApplication.processEvents()
    assert window.main_stack.currentWidget() is window.home_page
    assert window.import_project_bundle_action.isEnabled() is True


@pytest.mark.parametrize("size", [(940, 600), (1040, 680)], ids=["minimum", "default"])
def test_bundle_import_progress_dialog_keeps_visible_error_with_close(qtbot, tmp_path, size):
    dialog = BundleImportProgressDialog()
    qtbot.addWidget(dialog)
    dialog.set_context(
        project_name="Expanded Import Project",
        bundle_path=tmp_path / "expanded-import-project.fpvsbundle",
        root_dir=tmp_path / "FPVS Studio Root",
    )

    dialog.resize(*size)
    dialog.start()
    QApplication.processEvents()

    assert dialog.size().toTuple() == size
    assert not dialog.page.context_card.isVisible()
    assert not dialog.cancel_button.isVisible()
    _assert_bundle_processing_geometry(dialog)
    for index in range(1, 5):
        step_label = dialog.findChild(
            QLabel,
            f"bundle_import_processing_step_{index}_label",
        )
        assert step_label is not None
        required_width = step_label.fontMetrics().horizontalAdvance(step_label.text())
        assert step_label.width() >= required_width

    assert dialog.close() is False
    assert dialog.isVisible() is True

    dialog.set_stage("oddball")
    dialog.page.locations_button.click()
    message = "The bundle is missing an oddball image folder. Choose a complete bundle and retry."
    dialog.set_error(message)
    QApplication.processEvents()
    assert dialog.page.context_card.isVisible()
    assert dialog.page.outcome_label.text() == message
    assert dialog.cancel_button.isVisible() and dialog.cancel_button.isEnabled()
    assert dialog.cancel_button.text() == "Close"
    _assert_bundle_processing_geometry(dialog)
    dialog.cancel_button.click()
    assert not dialog.isVisible()


def test_import_display_settings_dialog_detect_button_keeps_edited_width(
    qtbot,
    monkeypatch,
) -> None:
    dialog = ImportDisplaySettingsDialog(DisplaySettings(screen_width_cm=49.5))
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    monkeypatch.setattr(
        "fpvs_studio.gui.import_display_settings_dialog.detect_primary_display_settings",
        lambda: DetectedDisplaySettings(
            refresh_hz=119.88,
            screen_width_px=2560,
            screen_height_px=1440,
        ),
    )

    assert dialog.screen_width_cm_spin.value() == 49.5
    dialog.screen_width_cm_spin.setValue(31.25)
    dialog.detect_button.click()

    assert dialog.refresh_hz_spin.value() == 120.0
    assert dialog.display_updates()["screen_width_cm"] == 31.25
    assert dialog.screen_width_px_spin.value() == 2560
    assert dialog.screen_height_px_spin.value() == 1440
    assert dialog.detected_refresh_label.text() == "119.88 Hz (use 120 Hz)"
    assert dialog.detected_resolution_label.text() == "2560 × 1440 px"
    assert dialog.detected_badge.text() == "Detected"
    assert_visible_children_within_parent(dialog)


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"], ids=["light", "dark"])
def test_import_display_settings_dialog_keeps_approved_value_for_unsupported_refresh(
    qtbot,
    monkeypatch,
    background,
) -> None:
    dialog = ImportDisplaySettingsDialog(DisplaySettings(preferred_refresh_hz=60.0))
    qtbot.addWidget(dialog)
    dialog.setPalette(QPalette(QColor(background)))
    dialog.show()
    QApplication.processEvents()
    monkeypatch.setattr(
        "fpvs_studio.gui.import_display_settings_dialog.detect_primary_display_settings",
        lambda: DetectedDisplaySettings(
            refresh_hz=75.0,
            screen_width_px=2560,
            screen_height_px=1440,
        ),
    )

    dialog.apply_detected_primary_display()

    assert dialog.refresh_hz_spin.value() == 60.0
    assert dialog.detected_refresh_label.text() == (
        "75.00 Hz (not an approved FPVS rate)"
    )
    assert dialog.detected_badge.text() == "Review refresh"
    assert dialog.minimumSize().width() == 720
    assert dialog.minimumSize().height() == 640
    assert dialog.detected_refresh_label.wordWrap() is True
    assert not any(
        widget.property("bundleWorkflowCard") == "true" for widget in dialog.findChildren(QWidget)
    )
    for width, height in ((720, 640), (780, 660)):
        dialog.resize(width, height)
        QApplication.processEvents()
        assert_visible_children_within_parent(dialog)
        required_height = dialog.detected_refresh_label.fontMetrics().boundingRect(
            QRect(0, 0, dialog.detected_refresh_label.width(), 1000),
            Qt.TextFlag.TextWordWrap,
            dialog.detected_refresh_label.text(),
        ).height()
        assert dialog.detected_refresh_label.height() >= required_height


@pytest.mark.parametrize("native_signal_hz", [60.020425, None])
def test_import_display_detects_native_windows_signal_when_qt_rounds_refresh(
    qtbot, monkeypatch, native_signal_hz,
) -> None:
    set_module_platform(monkeypatch, import_display_settings_dialog, "win32")
    screen = SimpleNamespace(
        geometry=lambda: QRect(0, 0, 1536, 864),
        devicePixelRatio=lambda: 1.25,
        refreshRate=lambda: 60.0,
    )
    monkeypatch.setattr(QApplication, "primaryScreen", lambda: screen)

    def get_native_mode():
        if native_signal_hz is None:
            raise DisplayModeError("Native timing unavailable")
        return NativeDisplayMode(
            platform_name="Windows", display_name=r"\\.\DISPLAY1", refresh_hz=60.0,
            source_name="QueryDisplayConfig", exact_refresh=True, mode_reference="60/1",
            signal_refresh_hz=native_signal_hz,
        )

    monkeypatch.setattr(
        import_display_settings_dialog, "query_primary_native_display_mode", get_native_mode,
    )
    dialog = ImportDisplaySettingsDialog(DisplaySettings(preferred_refresh_hz=60.0))
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.detect_button.click()

    assert "native Windows refresh rate" in dialog.detect_button.toolTip()
    if native_signal_hz is None:
        assert dialog.display_updates()["preferred_refresh_hz"] == 60.0
        assert dialog.detected_refresh_label.text() == "Unavailable"
        assert dialog.detected_badge.text() == "Review refresh"
    else:
        assert dialog.display_updates()["preferred_refresh_hz"] == 60.02
        assert dialog.detected_refresh_label.text() == "60.02 Hz (use 60.02 Hz)"
        assert dialog.detected_badge.text() == "Detected"
    assert dialog.detected_resolution_label.text() == "1920 × 1080 px"
    for width, height in ((720, 640), (780, 660)):
        dialog.resize(width, height)
        QApplication.processEvents()
        assert_visible_children_within_parent(dialog)
        label = dialog.detected_refresh_label
        required = label.fontMetrics().boundingRect(
            QRect(0, 0, label.contentsRect().width(), 1000),
            Qt.TextFlag.TextWordWrap,
            label.text(),
        )
        assert label.contentsRect().height() >= required.height()


def test_import_display_settings_dialog_actions_are_explicit(qtbot) -> None:
    unresolved_dialog = ImportDisplaySettingsDialog(DisplaySettings())
    qtbot.addWidget(unresolved_dialog)
    unresolved_dialog.show()
    QApplication.processEvents()

    assert unresolved_dialog.close() is True
    assert unresolved_dialog.result() == int(QDialog.DialogCode.Rejected)

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


@pytest.mark.parametrize("ratio, logical", [
    (1.0, (3840, 2160)), (1.25, (3072, 1728)),
    (1.5, (2560, 1440)), (2.0, (1920, 1080)),
])
def test_import_display_detection_uses_physical_pixels(monkeypatch, ratio, logical):
    from fpvs_studio.gui.runtime_settings_page import _primary_screen_width_px

    set_module_platform(monkeypatch, import_display_settings_dialog, "test")
    screen = SimpleNamespace(
        geometry=lambda: QRect(0, 0, *logical), devicePixelRatio=lambda: ratio,
        refreshRate=lambda: 60.0,
    )
    monkeypatch.setattr(QApplication, "primaryScreen", lambda: screen)
    detected = detect_primary_display_settings()
    assert (detected.screen_width_px, detected.screen_height_px) == (3840, 2160)
    assert detected.refresh_hz == 60.0
    assert _primary_screen_width_px() == 3840


@pytest.mark.skipif(os.name != "nt", reason="Windows namespace behavior")
def test_root_folder_picker_accepts_long_windows_path(controller, tmp_path, monkeypatch):
    from fpvs_studio.core.paths import filesystem_path

    root = tmp_path / ("receiver-root-" * 8) / ("studio-root-" * 8)
    filesystem_path(root).mkdir(parents=True)
    original_is_dir = Path.is_dir
    monkeypatch.setattr(
        Path, "is_dir", lambda path: False if path == root else original_is_dir(path),
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.controller.QFileDialog.getExistingDirectory", lambda *args: str(root),
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.controller.QMessageBox.warning", lambda *args: None,
    )
    assert controller._choose_fpvs_root_dir(parent=None, initial_dir=tmp_path) == root
