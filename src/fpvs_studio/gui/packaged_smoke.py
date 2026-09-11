"""GUI-owned packaged smoke checks for FPVS Studio release packaging."""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import replace
from importlib import import_module
from pathlib import Path
from typing import Any


def collect_packaged_smoke_report() -> dict[str, Any]:
    """Show native dialogs in an explicitly approved visible verification session."""

    if os.environ.get("FPVS_ALLOW_QT_TESTS") != "1":
        raise RuntimeError("Packaged GUI verification requires explicit visible-session approval.")
    if os.environ.get("QT_QPA_PLATFORM", "").lower() in {"offscreen", "minimal"}:
        raise RuntimeError("Packaged GUI verification requires the native visible Qt platform.")
    psychopy_user_dirs = _isolate_psychopy_user_dirs()

    from PySide6.QtWidgets import QApplication

    from fpvs_studio import __version__, _installed_version
    from fpvs_studio.gui.controller import experiment_test_mode_available
    from fpvs_studio.gui.settings_dialog import AppSettingsDialog
    from fpvs_studio.gui.update_dialog import UpdateDialog
    from fpvs_studio.updates.models import InstallerAsset, UpdateCheckResult

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication(["fpvs-studio-packaged-smoke"])

    metadata_version = _installed_version()
    dist_info_names = _fpvs_studio_dist_info_names()
    result = UpdateCheckResult(
        current_version=__version__,
        latest_version="999.0.0",
        update_available=True,
        release_url="https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v999.0.0",
        release_notes_summary="Packaging smoke test.",
        installer_asset=InstallerAsset(
            name="FPVS-Studio-Setup-999.0.0.exe",
            download_url=(
                "https://github.com/zcm58/FPVS-Studio-2.0/releases/download/"
                "v999.0.0/FPVS-Studio-Setup-999.0.0.exe"
            ),
            size_bytes=1,
            sha256="a" * 64,
            version="999.0.0",
            asset_id=1,
        ),
        is_prerelease=True,
    )
    dialog = UpdateDialog(auto_check=False, initial_result=result)
    dialog.resize(dialog.minimumSizeHint())
    dialog.show()
    app.processEvents()

    button_reports = []
    for button in (
        dialog.check_button,
        dialog.download_button,
        dialog.install_button,
        dialog.close_button,
    ):
        needed_width = button.fontMetrics().horizontalAdvance(button.text()) + 20
        button_reports.append(
            {
                "object_name": button.objectName(),
                "text": button.text(),
                "width": button.width(),
                "needed_width": needed_width,
                "fits": button.width() >= needed_width,
            }
        )

    dialog.close_button.click()
    app.processEvents()
    remind_later_dismissed = not dialog.isVisible()

    style_sheet = dialog.styleSheet()
    version_match = __version__ == metadata_version
    styled = "QDialog#update_dialog" in style_sheet and "QPushButton" in style_sheet
    buttons_fit = all(button["fits"] for button in button_reports)
    assert result.installer_asset is not None
    patch_result = replace(
        result,
        installer_asset=replace(result.installer_asset, kind="patch"),
    )
    patch_dialog = UpdateDialog(auto_check=False, initial_result=patch_result)
    patch_dialog.show()
    app.processEvents()
    patch_copy_ok = "Patch (" in patch_dialog.status_label.text()
    patch_dialog.close()

    toggled: list[bool] = []
    settings = AppSettingsDialog(
        fpvs_root_dir=Path(psychopy_user_dirs["LOCALAPPDATA"]),
        experiment_test_mode_available=experiment_test_mode_available(),
        on_experiment_test_mode_changed=toggled.append,
    )
    settings.resize(700, 610)
    settings.show()
    app.processEvents()
    checkbox = settings.experiment_test_mode_checkbox
    test_mode_visible = checkbox is not None and checkbox.isVisible() and checkbox.isEnabled()
    if checkbox is not None:
        checkbox.setChecked(True)
        checkbox.setChecked(False)
    test_mode_toggle_ok = toggled == [True, False]
    settings.close()
    app.processEvents()
    dist_info_count_ok = len(dist_info_names) == 1
    runtime_dependency_report = _runtime_dependency_report()
    runtime_dependencies_ok = runtime_dependency_report["ok"]

    return {
        "ok": (
            version_match
            and styled
            and buttons_fit
            and remind_later_dismissed
            and dist_info_count_ok
            and runtime_dependencies_ok
            and patch_copy_ok
            and test_mode_visible
            and test_mode_toggle_ok
        ),
        "app_version": __version__,
        "metadata_version": metadata_version,
        "version_match": version_match,
        "dist_info_count_ok": dist_info_count_ok,
        "dist_info_names": dist_info_names,
        "update_dialog_style_applied": styled,
        "remind_later_dismissed": remind_later_dismissed,
        "buttons_fit": buttons_fit,
        "button_reports": button_reports,
        "patch_copy_ok": patch_copy_ok,
        "test_mode_visible": test_mode_visible,
        "test_mode_toggle_ok": test_mode_toggle_ok,
        "psychopy_user_dirs": psychopy_user_dirs,
        "runtime_dependencies_ok": runtime_dependencies_ok,
        "runtime_dependency_report": runtime_dependency_report,
    }


def _isolate_psychopy_user_dirs() -> dict[str, str]:
    smoke_root = Path(tempfile.gettempdir()) / "fpvs-studio-packaged-smoke" / str(os.getpid())
    paths = {
        "APPDATA": smoke_root / "appdata",
        "LOCALAPPDATA": smoke_root / "localappdata",
        "HOME": smoke_root / "home",
        "USERPROFILE": smoke_root / "userprofile",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    for key, path in paths.items():
        os.environ[key] = str(path)
    return {key: str(path) for key, path in paths.items()}


def _fpvs_studio_dist_info_names() -> list[str]:
    bundle_internal = getattr(sys, "_MEIPASS", None)
    if bundle_internal is None:
        return []
    internal_path = Path(bundle_internal)
    return sorted(
        path.name
        for path in internal_path.glob("fpvs_studio-*.dist-info")
        if (path / "METADATA").is_file()
    )


def _runtime_dependency_report() -> dict[str, Any]:
    modules = (
        "fpvs_studio.engines.registry",
        "fpvs_studio.engines.psychopy_loader",
        "psychopy",
        "psychopy.core",
        "psychopy.visual",
        "psychopy.visual.backends.pygletbackend",
        "psychopy.visual.backends.glfwbackend",
        "psychopy.visual.line",
        "psychopy.hardware.keyboard",
        "psychtoolbox",
        "pyglet",
        "sounddevice",
        "serial",
    )
    imports: list[dict[str, object]] = []
    ok = True
    for module_name in modules:
        try:
            import_module(module_name)
        except Exception as error:
            ok = False
            imports.append(
                {
                    "module": module_name,
                    "ok": False,
                    "error": f"{type(error).__name__}: {error}",
                }
            )
        else:
            imports.append({"module": module_name, "ok": True})

    return {
        "ok": ok,
        "imports": imports,
    }
