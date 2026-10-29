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
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Packaged GUI verification requires the compiled application.")
    psychopy_user_dirs = _isolate_psychopy_user_dirs()
    smoke_root = Path(psychopy_user_dirs["LOCALAPPDATA"]).parent
    qt_settings_paths = _isolate_qt_settings(smoke_root)

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
    pilot_toggled: list[bool] = []
    settings = AppSettingsDialog(
        fpvs_root_dir=Path(psychopy_user_dirs["LOCALAPPDATA"]),
        experiment_test_mode_available=experiment_test_mode_available(),
        on_experiment_test_mode_changed=toggled.append,
        attentional_blink_pilot_mode_available=experiment_test_mode_available(),
        on_attentional_blink_pilot_mode_changed=pilot_toggled.append,
    )
    settings.resize(700, 680)
    settings.show()
    app.processEvents()
    checkbox = settings.experiment_test_mode_checkbox
    test_mode_visible = checkbox is not None and checkbox.isVisible() and checkbox.isEnabled()
    if checkbox is not None:
        checkbox.setChecked(True)
        checkbox.setChecked(False)
    test_mode_toggle_ok = toggled == [True, False]
    pilot = settings.attentional_blink_pilot_mode_checkbox
    pilot_mode_visible = pilot is not None and pilot.isVisible() and pilot.isEnabled()
    pilot_mode_fits = (
        pilot is not None
        and pilot.width() >= pilot.fontMetrics().horizontalAdvance(pilot.text()) + 24
        and settings.rect().contains(pilot.mapTo(settings, pilot.rect().bottomRight()))
    )
    if pilot is not None:
        pilot.setChecked(True)
        pilot.setChecked(False)
    pilot_mode_toggle_ok = pilot_toggled == [True, False]
    settings.close()
    app.processEvents()
    online_workflows = _online_workflow_report(app, smoke_root)
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
            and pilot_mode_visible
            and pilot_mode_fits
            and pilot_mode_toggle_ok
            and online_workflows["ok"]
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
        "pilot_mode_visible": pilot_mode_visible,
        "pilot_mode_fits": pilot_mode_fits,
        "pilot_mode_toggle_ok": pilot_mode_toggle_ok,
        "psychopy_user_dirs": psychopy_user_dirs,
        "frozen": True,
        "qt_settings_paths": qt_settings_paths,
        "online_workflows": online_workflows,
        "runtime_dependencies_ok": runtime_dependencies_ok,
        "runtime_dependency_report": runtime_dependency_report,
    }


def _isolate_qt_settings(smoke_root: Path) -> dict[str, str]:
    """Redirect Windows native known-folder lookups before constructing dialogs."""
    from PySide6.QtCore import QSettings

    paths = {}
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    for scope, name in (
        (QSettings.Scope.UserScope, "user"),
        (QSettings.Scope.SystemScope, "system"),
    ):
        path = smoke_root / "qt-settings" / name
        path.mkdir(parents=True, exist_ok=True)
        QSettings.setPath(QSettings.Format.IniFormat, scope, str(path))
        paths[name] = str(path)
    return paths


def _online_workflow_report(app: Any, smoke_root: Path) -> dict[str, Any]:
    """Render synthetic dialog states without a controller, credentials or HTTP."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QAbstractButton, QDialog, QLabel, QMessageBox, QWidget

    from fpvs_studio.core.library_origin import LibraryProjectOrigin
    from fpvs_studio.gui.data_sharing_dialog import ComparisonRow, DataSharingDialog
    from fpvs_studio.gui.library_dialog import LibraryDialog
    from fpvs_studio.gui.project_version_dialog import ProjectVersionDialog
    from fpvs_studio.library.models import LibraryCatalog, LibraryConnection, LibraryItem
    from fpvs_studio.library.project_updates import select_project_update

    screenshots = smoke_root / "online-workflows"
    screenshots.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, Any]] = []

    def record(dialog: QDialog, state: str, size: tuple[int, int], checks: dict[str, bool]) -> None:
        dialog.resize(*size)
        dialog.show()
        app.processEvents()
        issues = []
        if dialog.size().toTuple() != size:
            issues.append(f"Requested {size}; rendered {dialog.size().toTuple()}")
        for child in dialog.findChildren(QWidget):
            parent = child.parentWidget()
            if parent is None or not child.isVisible():
                continue
            bounds = child.geometry()
            name = child.objectName() or type(child).__name__
            if (bounds.left() < -1 or bounds.top() < -1
                    or bounds.right() > parent.width() + 1
                    or bounds.bottom() > parent.height() + 1):
                issues.append(f"{name} exceeds its parent: {bounds.getRect()}")
            if isinstance(child, QAbstractButton) and child.text():
                if child.width() < child.fontMetrics().horizontalAdvance(child.text()):
                    issues.append(f"{name} truncates button text")
            if isinstance(child, QLabel) and child.text():
                needed = child.heightForWidth(child.width()) if child.wordWrap() else 0
                if needed > child.height():
                    issues.append(f"{name} clips wrapped label text")
        screenshot = screenshots / f"{dialog.objectName()}-{state}-{size[0]}x{size[1]}.png"
        saved = dialog.grab().save(str(screenshot))
        reports.append({
            "dialog": dialog.objectName(), "state": state, "size": list(size),
            "checks": checks, "layout_issues": issues, "screenshot": str(screenshot),
            "ok": saved and not issues and all(checks.values()),
        })

    item = LibraryItem(
        item_id="packaged-smoke", version="2.0.0",
        title="Synthetic cross-laboratory experiment with a realistic extended title",
        description="Synthetic protocol metadata for compiled dialog verification. " * 20,
        experiment_category="fpvs_oddball", filename="packaged-smoke.fpvsbundle",
        size_bytes=1024, uncompressed_size_bytes=4096, file_count=3,
        sha256="a" * 64, min_studio_version="1.0.0",
    )
    catalog = LibraryCatalog(
        schema_version="1.0", library_name="Synthetic research experiment library",
        lab_name="Synthetic laboratory for compiled workflow verification", items=[item],
        access_level="view",
    )
    library = LibraryDialog()
    library.set_connection(LibraryConnection(
        device_id="synthetic-device", library_name=catalog.library_name,
        device_name="Synthetic laboratory workstation", access_level="download",
    ))
    library.set_installations((), "https://openfpvs.com")
    for size in ((900, 640), (1040, 760)):
        library.set_catalog(catalog)
        record(library, "view-only", size, {
            "download_blocked": not library.install_button.isEnabled(),
            "permission_visible": "View-only" in library.connection_label.text(),
            "metadata_retained": item.title in library.details.toPlainText(),
        })
        library.set_catalog(catalog.model_copy(update={"access_level": "download"}))
        record(library, "download-ready", size, {
            "download_enabled": library.install_button.isEnabled(),
        })
        library.set_busy(True, "Downloading and verifying the experiment…", downloading=True)
        library.show_progress(512, 1024)
        record(library, "downloading", size, {
            "download_blocked": not library.install_button.isEnabled(),
            "cancel_available": library.cancel_button.isEnabled(),
            "progress": library.progress_bar.value() == 50,
        })
        library.set_busy(False)
    library.close()

    origin = LibraryProjectOrigin(
        service_url="https://openfpvs.com", item_id=item.item_id,
        installed_version="1.0.0", local_project_id="synthetic-project",
    )
    versions = ProjectVersionDialog(item.title)
    for size in ((760, 680), (820, 720)):
        for permission in ("view", "download"):
            update = select_project_update(origin, catalog.model_copy(
                update={"access_level": permission},
            ))
            versions.set_state(
                installed_version=origin.installed_version, latest=update.latest_item,
                linked=True, auto_check=True, status=update.message, can_install=update.can_install,
            )
            record(versions, f"{permission}-permission", size, {
                "permission_enforced": (
                    versions.install_button.isEnabled() == (permission == "download")
                ),
                "latest_retained": item.title in versions.details.toPlainText(),
                "view_only_explained": permission == "download" or "view-only" in update.message,
            })
    versions.close()

    sharing = DataSharingDialog(configured=True)
    sharing.project_id_edit.setText("01234567-89ab-cdef-0123-456789abcdef")
    sharing.invitation_edit.setText("synthetic-not-a-real-lab-code")
    sharing.set_comparison([ComparisonRow(
        "Synthetic condition with a long protocol-specific display name", "synthetic-condition",
        "92.0%\n46 hits / 50 targets · 1 session",
        "89.5%\n8,950 hits / 10,000 targets · 200 sessions · 25 enrollments",
    )], scope="Same experiment, version and protocol; this enrollment is excluded.",
        notice="", details="At least 10 sessions from 3 other enrollments are required.")
    for size in ((820, 480), (880, 540)):
        sharing.tabs.setCurrentIndex(0)
        sharing.set_state(
            connected=False, enabled=False, profile="No experiment enrollment.",
            status="A pending connection request uses a different project or lab code.",
        )
        record(sharing, "pending-enrollment", size, {
            "retry_connection_available": sharing.connect_button.isEnabled(),
            "sharing_disabled": not sharing.enabled_checkbox.isEnabled(),
        })
        def dismiss_pending_confirmation(state: str = f"pending-reset-{size[0]}") -> None:
            message_box = app.activeModalWidget()
            if not isinstance(message_box, QMessageBox):
                raise RuntimeError("Pending enrollment confirmation did not open.")
            default_button = message_box.defaultButton()
            try:
                record(message_box, state, message_box.size().toTuple(), {
                    "default_no": default_button is not None and message_box.standardButton(
                        default_button,
                    ) == QMessageBox.StandardButton.No,
                    "selected_project_visible": sharing.project_id() in message_box.text(),
                    "pending_request_explained": "OpenFPVS" in message_box.text(),
                })
            finally:
                message_box.done(int(QMessageBox.StandardButton.No))

        QTimer.singleShot(0, dismiss_pending_confirmation)
        replaced = sharing.confirm_pending_connection_reset(sharing.project_id())
        reports[-1]["checks"]["dismissed_without_replacement"] = not replaced
        reports[-1]["ok"] = reports[-1]["ok"] and not replaced
        sharing.set_state(
            connected=True, enabled=True, profile=item.title + "\nProtocol SHA-256: " + "a" * 64,
            status="Sharing is enabled.", pending=12, held=3, uploaded=9999, captures=32,
        )
        record(sharing, "connected", size, {
            "sharing_enabled": sharing.enabled_checkbox.isEnabled(),
            "retry_available": sharing.retry_button.isEnabled(),
            "full_profile_available": "Protocol SHA-256" in sharing.profile_label.toolTip(),
        })
        sharing.set_busy(True, "Updating sharing settings and aggregate comparison…")
        record(sharing, "busy", size, {
            "retry_blocked": not sharing.retry_button.isEnabled(),
            "opt_out_available": sharing.enabled_checkbox.isEnabled(),
        })
        sharing.set_busy(False)
        sharing.tabs.setCurrentIndex(1)
        record(sharing, "comparison", size, {
            "comparison_present": sharing.comparison_table.rowCount() == 1,
        })
    sharing.close()
    app.processEvents()
    return {"ok": all(report["ok"] for report in reports), "states": reports}


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
