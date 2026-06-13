"""GUI smoke tests for Studio `.fpvsconfig` import/export actions."""

from __future__ import annotations

from tests.gui.helpers import open_created_project

from fpvs_studio.core.project_config import (
    export_project_config,
    read_project_config,
    write_project_config,
)
from fpvs_studio.gui.controller import StudioController


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
