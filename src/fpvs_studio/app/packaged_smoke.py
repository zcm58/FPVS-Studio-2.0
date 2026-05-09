"""Installed-bundle smoke checks for FPVS Studio release packaging."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Sequence
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any


def run_packaged_smoke(argv: Sequence[str]) -> int:
    """Run a bounded installed-app smoke check and write a JSON report."""

    output_path = _parse_output_path(argv)
    try:
        report = collect_packaged_smoke_report()
    except Exception as error:
        report = {
            "ok": False,
            "error": f"{type(error).__name__}: {error}",
        }
    _write_report(output_path, report)
    return 0 if report.get("ok") is True else 1


def collect_packaged_smoke_report() -> dict[str, Any]:
    """Create the update dialog offscreen and verify package-only contracts."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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

    return {
        "ok": (
            version_match
            and styled
            and buttons_fit
            and remind_later_dismissed
            and dist_info_count_ok
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
    }


def _parse_output_path(argv: Sequence[str]) -> Path | None:
    args = list(argv)
    try:
        output_index = args.index("--packaged-smoke-output")
    except ValueError:
        return None
    try:
        return Path(args[output_index + 1])
    except IndexError as error:
        raise ValueError("--packaged-smoke-output requires a path.") from error


def _write_report(output_path: Path | None, report: dict[str, Any]) -> None:
    report_text = json.dumps(report, indent=2, sort_keys=True)
    if output_path is None:
        print(report_text)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text + "\n", encoding="utf-8")


def _fpvs_studio_dist_info_names() -> list[str]:
    bundle_internal = getattr(sys, "_MEIPASS", None)
    if bundle_internal is None:
        return []
    internal_path = Path(bundle_internal)
    return sorted(path.name for path in internal_path.glob("fpvs_studio-*.dist-info"))
