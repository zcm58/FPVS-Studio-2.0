"""GUI-owned packaged smoke checks for FPVS Studio release packaging."""

from __future__ import annotations

import os
import sys
import tempfile
from importlib import import_module
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any


def collect_packaged_smoke_report() -> dict[str, Any]:
    """Create the update dialog offscreen and verify package-only contracts."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    psychopy_user_dirs = _isolate_psychopy_user_dirs()

    from PySide6.QtWidgets import QApplication

    from fpvs_studio import __version__
    from fpvs_studio.gui.update_dialog import UpdateDialog
    from fpvs_studio.updates.models import InstallerAsset, UpdateCheckResult

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication(["fpvs-studio-packaged-smoke"])

    metadata_version = package_version("fpvs-studio")
    dist_info_names = _fpvs_studio_dist_info_names()
    result = UpdateCheckResult(
        current_version=__version__,
        latest_version="999.0.0",
        update_available=True,
        release_url="https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v999.0.0",
        release_notes_summary="Packaging smoke test.",
        installer_asset=InstallerAsset(
            name="FPVS-Studio-Setup-999.0.0.exe",
            download_url="https://github.com/downloads/FPVS-Studio-Setup-999.0.0.exe",
            size_bytes=1,
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
    return sorted(path.name for path in internal_path.glob("fpvs_studio-*.dist-info"))


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
