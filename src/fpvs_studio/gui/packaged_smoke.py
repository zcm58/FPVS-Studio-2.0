"""GUI-owned packaged smoke checks for FPVS Studio release packaging."""

from __future__ import annotations

import os
import re
import sys
import tempfile
from collections.abc import Callable
from dataclasses import replace
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fpvs_studio.core.run_spec import RunSpec


def _verification_palette(*, dark: bool) -> Any:
    """Build a complete synthetic palette only for approved GUI verification."""
    from PySide6.QtGui import QColor, QPalette

    from fpvs_studio.gui.design_system import DARK_STUDIO_THEME, LIGHT_STUDIO_THEME

    theme_tokens = DARK_STUDIO_THEME if dark else LIGHT_STUDIO_THEME
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, theme_tokens.page_background),
        (QPalette.ColorRole.WindowText, theme_tokens.text_primary),
        (QPalette.ColorRole.Base, theme_tokens.surface),
        (QPalette.ColorRole.AlternateBase, theme_tokens.surface_alt),
        (QPalette.ColorRole.Text, theme_tokens.text_primary),
        (QPalette.ColorRole.Button, theme_tokens.surface_elevated),
        (QPalette.ColorRole.ButtonText, theme_tokens.text_primary),
        (QPalette.ColorRole.ToolTipBase, theme_tokens.surface),
        (QPalette.ColorRole.ToolTipText, theme_tokens.text_primary),
        (QPalette.ColorRole.Highlight, theme_tokens.primary),
        (QPalette.ColorRole.HighlightedText, theme_tokens.selected_text),
        (QPalette.ColorRole.PlaceholderText, theme_tokens.text_hint),
    ):
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(
            QPalette.ColorGroup.Disabled, role, QColor(theme_tokens.disabled_text),
        )
    return palette


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
            size_bytes=742_800_000,
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

    update_dialog_copy_ok = (
        dialog.title_label.text() == "Update available"
        and dialog.download_size_label.isVisible()
        and dialog.download_size_label.text() == "742.8 MB"
        and dialog.release_notes_button.isVisible()
        and dialog.release_notes_button.isEnabled()
    )

    button_reports = []
    for button in (
        dialog.release_notes_button,
        dialog.check_button,
        dialog.download_button,
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
        installer_asset=replace(
            result.installer_asset, kind="patch", size_bytes=1_700_000, from_version=__version__,
        ),
        selection_reason="Smaller patch verified for your installed version.",
    )
    patch_dialog = UpdateDialog(auto_check=False, initial_result=patch_result)
    patch_dialog.show()
    app.processEvents()
    patch_copy_ok = (
        patch_dialog.title_label.text() == "Update available"
        and patch_dialog.download_size_label.isVisible()
        and patch_dialog.download_size_label.text() == "1.7 MB"
        and patch_result.selection_reason in patch_dialog.download_size_label.toolTip()
    )
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
    settings.resize(1000, 680)
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
    settings_layout = _settings_layout_report(app, settings, smoke_root)
    settings.close()
    app.processEvents()
    online_workflows = _online_workflow_report(app, smoke_root)
    dist_info_count_ok = len(dist_info_names) == 1
    runtime_dependency_report = _runtime_dependency_report()
    runtime_dependencies_ok = runtime_dependency_report["ok"]

    report = {
        "ok": (
            version_match
            and styled
            and update_dialog_copy_ok
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
            and settings_layout["ok"]
            and online_workflows["ok"]
        ),
        "app_version": __version__,
        "metadata_version": metadata_version,
        "version_match": version_match,
        "dist_info_count_ok": dist_info_count_ok,
        "dist_info_names": dist_info_names,
        "update_dialog_style_applied": styled,
        "update_dialog_copy_ok": update_dialog_copy_ok,
        "remind_later_dismissed": remind_later_dismissed,
        "buttons_fit": buttons_fit,
        "button_reports": button_reports,
        "patch_copy_ok": patch_copy_ok,
        "test_mode_visible": test_mode_visible,
        "test_mode_toggle_ok": test_mode_toggle_ok,
        "pilot_mode_visible": pilot_mode_visible,
        "pilot_mode_fits": pilot_mode_fits,
        "pilot_mode_toggle_ok": pilot_mode_toggle_ok,
        "settings_layout": settings_layout,
        "psychopy_user_dirs": psychopy_user_dirs,
        "frozen": True,
        "qt_settings_paths": qt_settings_paths,
        "online_workflows": online_workflows,
        "runtime_dependencies_ok": runtime_dependencies_ok,
        "runtime_dependency_report": runtime_dependency_report,
    }
    if os.environ.get("FPVS_PACKAGED_PLAYBACK_SMOKE") == "1":
        report["packaged_playback"] = _packaged_playback_report(smoke_root / "playback-project")
    return report


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


def _visible_layout_issues(dialog: Any, *, allow_vertical_scroll: bool = False) -> list[str]:
    """Check the same widget, text and contrast bounds across packaged dialogs."""
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QAbstractButton, QLabel, QScrollArea, QWidget

    from fpvs_studio.gui.design_system import contrast_ratio, resolve_studio_theme

    issues = []
    theme = resolve_studio_theme(dialog.palette())
    for child in dialog.findChildren(QWidget):
        parent = child.parentWidget()
        if parent is None or not child.isVisible():
            continue
        bounds = child.geometry()
        name = child.objectName() or type(child).__name__
        scroll = parent.parentWidget()
        scrolling_content = (
            allow_vertical_scroll and isinstance(scroll, QScrollArea)
            and scroll.widget() is child and scroll.viewport() is parent
        )
        if (bounds.left() < -1
                or bounds.right() > parent.width() + 1
                or (not scrolling_content and (
                    bounds.top() < -1 or bounds.bottom() > parent.height() + 1
                ))):
            issues.append(f"{name} exceeds its parent: {bounds.getRect()}")
        if isinstance(child, QAbstractButton) and child.text():
            if child.width() < child.fontMetrics().horizontalAdvance(child.text()):
                issues.append(f"{name} truncates button text")
        if isinstance(child, QLabel) and child.text():
            foreground = child.palette().color(QPalette.ColorRole.WindowText).name()
            if contrast_ratio(foreground, theme.page_background) < 4.5:
                issues.append(f"{name} has insufficient label contrast: {foreground}")
            needed = child.heightForWidth(child.width()) if child.wordWrap() else 0
            if needed > child.height():
                issues.append(f"{name} clips wrapped label text")
    return issues


def _wait_for_positive_scroll_value(read_value: Callable[[], int]) -> bool:
    """Allow bounded native scrollbar event delivery during GUI smoke checks."""
    from PySide6.QtCore import QEventLoop, QTimer

    if read_value() > 0:
        return True
    loop = QEventLoop()
    poll = QTimer(loop)
    deadline = QTimer(loop)
    deadline.setSingleShot(True)

    def check() -> None:
        if read_value() > 0:
            loop.quit()

    poll.timeout.connect(check)
    deadline.timeout.connect(loop.quit)
    poll.start(10)
    deadline.start(1000)
    loop.exec()
    poll.stop()
    deadline.stop()
    return read_value() > 0


def _settings_layout_report(app: Any, settings: Any, smoke_root: Path) -> dict[str, Any]:
    """Exercise compiled Settings pages and native wheel scrolling with isolated data."""
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel

    categories = [
        "General", "Recording", "Appearance", "Workspace", "Advanced", "Diagnostics", "Account",
    ]
    actual_categories = [settings.navigation.item(index).text()
                         for index in range(settings.navigation.count())]
    screenshots = smoke_root / "settings-layout"
    screenshots.mkdir(parents=True, exist_ok=True)
    pages = []
    scrolling = []
    original_palette = app.palette()
    general = settings.pages.widget(categories.index("General")).widget()
    long_note = QLabel("\n".join(f"Example note {index}" for index in range(30)), general)
    long_note.setWordWrap(True)
    general.layout().insertWidget(general.layout().count() - 1, long_note)
    long_note.hide()
    try:
        for theme, dark in (("light", False), ("dark", True)):
            app.setPalette(_verification_palette(dark=dark))
            for size in ((860, 560), (1000, 680)):
                settings.resize(*size)
                for index, category in enumerate(actual_categories):
                    settings.navigation.setCurrentRow(index)
                    app.processEvents()
                    page = settings.pages.currentWidget()
                    checks = {
                        "size_matches": settings.size().toTuple() == size,
                        "selected_page_matches": settings.pages.currentIndex() == index,
                        "heading_matches": settings.page_title.text() == category,
                        "page_visible": page.isVisible(),
                        "no_horizontal_scroll": page.horizontalScrollBar().maximum() == 0,
                    }
                    issues = _visible_layout_issues(settings, allow_vertical_scroll=True)
                    screenshot = screenshots / f"{theme}-{category.lower()}-{size[0]}x{size[1]}.png"
                    saved = settings.grab().save(str(screenshot))
                    pages.append({
                        "category": category, "theme": theme, "size": list(size),
                        "checks": checks, "layout_issues": issues, "screenshot": str(screenshot),
                        "ok": saved and not issues and all(checks.values()),
                    })

            settings.resize(860, 560)
            settings.navigation.setCurrentRow(categories.index("General"))
            long_note.show()
            app.processEvents()
            page = settings.pages.currentWidget()
            viewport = page.viewport()
            scrollbar = page.verticalScrollBar()
            overflow_ready = _wait_for_positive_scroll_value(scrollbar.maximum)
            scrollbar.setValue(0)
            sidebar = settings.navigation.parentWidget()
            close_button = settings.button_box.button(QDialogButtonBox.StandardButton.Close)
            fixed_widgets = (sidebar, settings.navigation, settings.page_title, close_button)
            fixed_geometry = [widget.geometry() for widget in fixed_widgets]
            position = viewport.rect().center()
            wheel = QWheelEvent(
                QPointF(position), QPointF(viewport.mapToGlobal(position)),
                QPoint(), QPoint(0, -120),
                Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                Qt.ScrollPhase.NoScrollPhase, False,
            )
            QApplication.sendEvent(viewport, wheel)
            wheel_moved = _wait_for_positive_scroll_value(scrollbar.value)
            scrollbar.setValue(scrollbar.maximum())
            app.processEvents()
            bottom = long_note.mapTo(viewport, long_note.rect().bottomRight())
            checks = {
                "vertical_overflow": overflow_ready,
                "no_horizontal_scroll": page.horizontalScrollBar().maximum() == 0,
                "wheel_moved": wheel_moved,
                "last_content_visible": 0 <= bottom.y() < viewport.height(),
                "navigation_and_close_fixed": [widget.geometry() for widget in fixed_widgets]
                == fixed_geometry,
                "fixed_controls_reachable": all(
                    widget.isVisible()
                    and settings.rect().contains(widget.mapTo(settings, widget.rect().topLeft()))
                    and settings.rect().contains(
                        widget.mapTo(settings, widget.rect().bottomRight()),
                    )
                    for widget in fixed_widgets
                ),
            }
            settings.navigation.setCurrentRow(categories.index("Diagnostics"))
            settings.navigation.setCurrentRow(categories.index("General"))
            app.processEvents()
            checks["scroll_position_retained"] = scrollbar.value() == scrollbar.maximum()
            screenshot = screenshots / f"{theme}-general-scrolled-860x560.png"
            saved = settings.grab().save(str(screenshot))
            scrolling.append({"theme": theme, "checks": checks, "screenshot": str(screenshot),
                              "ok": saved and all(checks.values())})
            long_note.hide()
            app.processEvents()
    finally:
        general.layout().removeWidget(long_note)
        long_note.deleteLater()
        app.setPalette(original_palette)
        app.processEvents()
    return {
        "ok": actual_categories == categories and all(page["ok"] for page in pages)
        and all(report["ok"] for report in scrolling),
        "categories": actual_categories, "pages": pages, "scrolling": scrolling,
    }


def _online_workflow_report(app: Any, smoke_root: Path) -> dict[str, Any]:
    """Render synthetic dialog states without a controller, credentials or HTTP."""
    from PySide6.QtCore import Qt, QTimer, QUrl
    from PySide6.QtGui import QTextDocument
    from PySide6.QtWidgets import QDialog, QMessageBox

    from fpvs_studio.core.data_sharing import SharingStudyChoice
    from fpvs_studio.core.library_origin import LibraryProjectOrigin
    from fpvs_studio.gui.data_sharing_dialog import ComparisonRow, DataSharingDialog
    from fpvs_studio.gui.design_system import (
        DARK_STUDIO_THEME,
        LIGHT_STUDIO_THEME,
    )
    from fpvs_studio.gui.library_dialog import LibraryDialog
    from fpvs_studio.gui.project_version_dialog import (
        DEFAULT_SIZE,
        MINIMUM_SIZE,
        ProjectVersionDialog,
    )
    from fpvs_studio.library.models import LibraryCatalog, LibraryConnection, LibraryItem
    from fpvs_studio.library.project_updates import select_project_update

    screenshots = smoke_root / "online-workflows"
    screenshots.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, Any]] = []

    def record(dialog: QDialog, state: str, size: tuple[int, int], checks: dict[str, bool]) -> None:
        dialog.resize(*size)
        dialog.show()
        app.processEvents()
        issues = _visible_layout_issues(dialog)
        if dialog.size().toTuple() != size:
            issues.append(f"Requested {size}; rendered {dialog.size().toTuple()}")
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

    demo = LibraryDialog()
    demo_item = item.model_copy(update={
        "item_id": "color-oddball-demo",
        "version": "1.0.0",
        "title": "Color Oddball Demo",
        "filename": "color-oddball-demo.fpvsbundle",
    })
    demo.set_public_catalog(LibraryCatalog(
        schema_version="1.0", library_name="Public projects", items=[demo_item],
    ))
    demo.resize(900, 640)
    demo.show()
    app.processEvents()
    preview_document = demo.details.document()
    preview_sources = [QUrl(url) for url in re.findall(
        r'<img\b[^>]*\bsrc="([^"]+)"', preview_document.toHtml(),
    )]
    record(demo, "color-oddball-preview", (900, 640), {
        "bundled_images_rendered": (
            [url.fileName() for url in preview_sources] == ["red.png", "green.png"]
            and all(preview_document.resource(QTextDocument.ResourceType.ImageResource, url)
                    for url in preview_sources)
        ),
    })
    demo.close()

    origin = LibraryProjectOrigin(
        service_url="https://openfpvs.com", item_id=item.item_id,
        installed_version="1.0.0", local_project_id="synthetic-project",
    )
    versions = ProjectVersionDialog(item.title)
    for size in (MINIMUM_SIZE, DEFAULT_SIZE):
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
                "latest_retained": item.description in versions.details.toPlainText(),
                "view_only_explained": permission == "download" or "view-only" in update.message,
            })
    versions.close()

    study = SharingStudyChoice(
        project_id="01234567-89ab-cdef-0123-456789abcdef",
        title="Synthetic cross-laboratory experiment with a realistic extended title " * 2,
        experiment_id=item.item_id, experiment_version=item.version, protocol_sha256="a" * 64,
    )
    second_study = study.model_copy(update={
        "project_id": "01234567-89ab-cdef-0123-456789abcde0",
        "title": "Second shared study with the same protocol, requiring an explicit selection",
    })
    original_palette = app.palette()
    try:
        for theme_tokens in (DARK_STUDIO_THEME, LIGHT_STUDIO_THEME):
            theme = theme_tokens.scheme.value
            palette = _verification_palette(dark=theme == "dark")
            app.setPalette(palette)
            sharing = DataSharingDialog(configured=True)
            sharing.set_comparison([ComparisonRow(
                "Synthetic condition with a long protocol-specific display name",
                "synthetic-condition",
                "92.0%\n46 hits / 50 targets · 1 session",
                "89.5%\n8,950 hits / 10,000 targets · 200 sessions · 25 enrollments",
            )], scope="Same experiment, version and protocol; this enrollment is excluded.",
                notice="", details="At least 10 sessions from 3 other enrollments are required.")
            for size in ((820, 480), (880, 540)):
                sharing.tabs.setCurrentIndex(0)
                sharing.set_state(
                    connected=False, enabled=False, profile="No experiment enrollment.",
                    status="No studies match this experiment. Check Lab access or refresh studies.",
                )
                sharing.set_studies([])
                record(sharing, f"no-studies-{theme}", size, {
                    "no_selection": not sharing.project_id(),
                    "connect_blocked": not sharing.connect_button.isEnabled(),
                    "recovery_available": sharing.refresh_studies_button.isEnabled()
                    and sharing.lab_access_button.isEnabled(),
                })
                sharing.set_studies([study])
                sharing.status_label.setText(
                    "A matching study is available. Select Connect to continue.",
                )
                record(sharing, f"one-study-{theme}", size, {
                    "unique_selected": sharing.project_id() == study.project_id,
                    "connect_available": sharing.connect_button.isEnabled(),
                    "full_title_available": study.title in sharing.study_combo.toolTip(),
                    "sharing_disabled": not sharing.enabled_checkbox.isEnabled(),
                })
                sharing.set_studies([])
                sharing.set_studies([study, second_study])
                sharing.status_label.setText("Choose the shared study to connect to.")
                record(sharing, f"multiple-studies-{theme}", size, {
                    "explicit_choice_required": not sharing.project_id(),
                    "connect_blocked": not sharing.connect_button.isEnabled(),
                    "full_title_available": study.title in sharing.study_combo.itemData(
                        0, Qt.ItemDataRole.ToolTipRole,
                    ),
                })
                sharing.study_combo.setCurrentIndex(1)
                record(sharing, f"study-selected-{theme}", size, {
                    "selected_study": sharing.project_id() == second_study.project_id,
                    "connect_available": sharing.connect_button.isEnabled(),
                    "full_title_available": second_study.title in sharing.study_combo.toolTip(),
                })
                sharing.set_busy(True, "Finding available shared studies…")
                record(sharing, f"discovering-{theme}", size, {
                    "choice_blocked": not sharing.study_combo.isEnabled(),
                    "connect_blocked": not sharing.connect_button.isEnabled(),
                    "refresh_blocked": not sharing.refresh_studies_button.isEnabled(),
                    "cancel_available": sharing.cancel_button.isEnabled(),
                })
                sharing.set_busy(False)
                for state, status in (
                    ("approval", "This computer is awaiting administrator approval. "
                     "Select Connect after approval."),
                    ("error", "The service is temporarily unavailable. "
                     "Refresh studies when the connection is available."),
                    ("pending-enrollment", "A pending connection request uses a different "
                     "study or lab connection."),
                ):
                    sharing.set_state(connected=False, enabled=False, profile="", status=status)
                    record(sharing, f"{state}-{theme}", size, {
                        "retry_connection_available": sharing.connect_button.isEnabled(),
                        "refresh_available": sharing.refresh_studies_button.isEnabled(),
                        "sharing_disabled": not sharing.enabled_checkbox.isEnabled(),
                    })

                def dismiss_pending_confirmation(
                    state: str = f"pending-reset-{theme}-{size[0]}",
                    study_title: str = sharing.study_title(),
                ) -> None:
                    message_box = app.activeModalWidget()
                    if not isinstance(message_box, QMessageBox):
                        raise RuntimeError("Pending enrollment confirmation did not open.")
                    default_button = message_box.defaultButton()
                    try:
                        record(message_box, state, message_box.size().toTuple(), {
                            "default_no": default_button is not None and message_box.standardButton(
                                default_button,
                            ) == QMessageBox.StandardButton.No,
                            "selected_study_visible": study_title in message_box.text(),
                            "pending_request_explained": "OpenFPVS" in message_box.text(),
                        })
                    finally:
                        message_box.done(int(QMessageBox.StandardButton.No))

                QTimer.singleShot(0, dismiss_pending_confirmation)
                replaced = sharing.confirm_pending_connection_reset(sharing.study_title())
                reports[-1]["checks"]["dismissed_without_replacement"] = not replaced
                reports[-1]["ok"] = reports[-1]["ok"] and not replaced
                sharing.set_state(
                    connected=True, enabled=True,
                    profile=item.title + "\nProtocol SHA-256: " + "a" * 64,
                    status="Sharing is enabled.", pending=12, held=3, uploaded=9999, captures=32,
                )
                record(sharing, f"connected-{theme}", size, {
                    "sharing_enabled": sharing.enabled_checkbox.isEnabled(),
                    "retry_available": sharing.retry_button.isEnabled(),
                    "full_profile_available": "Protocol SHA-256" in sharing.profile_label.toolTip(),
                })
                sharing.set_busy(True, "Updating sharing settings and aggregate comparison…")
                record(sharing, f"busy-{theme}", size, {
                    "retry_blocked": not sharing.retry_button.isEnabled(),
                    "opt_out_available": sharing.enabled_checkbox.isEnabled(),
                })
                sharing.set_busy(False, "Sharing is enabled.")
                sharing.tabs.setCurrentIndex(1)
                record(sharing, f"comparison-{theme}", size, {
                    "comparison_present": sharing.comparison_table.rowCount() == 1,
                })
            sharing.close()
    finally:
        app.setPalette(original_palette)
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
        "psychopy.monitors",
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

    try:
        monitors = import_module("psychopy.monitors")
        calibration = monitors.Monitor("testMonitor")
        monitor_size = list(calibration.getSizePix() or ())
        monitor_ok = (
            "testMonitor" in monitors.getAllMonitors()
            and len(monitor_size) == 2 and all(value > 0 for value in monitor_size)
        )
        monitor_report = {"ok": monitor_ok, "test_monitor_pixels": monitor_size}
    except Exception as error:
        monitor_report = {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return {"ok": ok and monitor_report["ok"], "imports": imports, "monitors": monitor_report}


def _compile_packaged_playback(project_root: Path) -> RunSpec:
    """Compile a tiny local two-pool condition without importing a renderer."""
    from PIL import Image

    from fpvs_studio.core.compiler import compile_run_spec
    from fpvs_studio.core.enums import DutyCycleMode
    from fpvs_studio.core.models import (
        Condition,
        FixationTaskSettings,
        ImageResolution,
        ProjectFile,
        ProjectMeta,
        ProjectSettings,
        StimulusSet,
    )
    from fpvs_studio.core.paths import stimulus_originals_dir

    size = (64, 64)
    sets = []
    for role, colors in (("base", ((120, 120, 120), (150, 150, 150))),
                         ("oddball", ((150, 60, 40), (50, 110, 80)))):
        source = stimulus_originals_dir(project_root, role)
        source.mkdir(parents=True)
        for index, color in enumerate(colors):
            Image.new("RGB", size, color).save(source / f"{role}-{index}.png")
        sets.append(StimulusSet(
            set_id=role, name=role.title(), source_dir=source.relative_to(project_root).as_posix(),
            resolution=ImageResolution(width_px=size[0], height_px=size[1]),
            image_count=len(colors),
        ))
    project = ProjectFile(
        meta=ProjectMeta(project_id="packaged-playback", name="Packaged playback smoke",
                         template_id="fpvs_6hz_every5_v1"),
        settings=ProjectSettings(fixation_task=FixationTaskSettings(
            enabled=False, accuracy_task_enabled=False, participant_tutorial_enabled=False,
        )),
        stimulus_sets=sets,
        conditions=[Condition(
            condition_id="playback", name="Playback", base_stimulus_set_id="base",
            oddball_stimulus_set_id="oddball", sequence_count=1,
            oddball_cycle_repeats_per_sequence=1, duty_cycle_mode=DutyCycleMode.CONTINUOUS,
        )],
    )
    return compile_run_spec(
        project, project_root=project_root, refresh_hz=60.0, random_seed=12,
        run_id="packaged-playback-smoke",
    )


def _known_host_graphics_failure(error: BaseException) -> bool:
    """Identify only Pyglet's explicit unsupported display/context errors."""
    current: BaseException | None = error
    while current is not None:
        error_type = type(current)
        if error_type.__module__.startswith("pyglet.") and error_type.__name__ in {
            "NoSuchDisplayException", "NoSuchConfigException", "ContextException",
        }:
            return True
        current = current.__cause__ or current.__context__
    return False


def _packaged_playback_report(project_root: Path) -> dict[str, Any]:
    """Exercise frozen fullscreen rendering without enrolling a participant or emitting triggers."""
    report: dict[str, Any] = {
        "status": "failed", "stage": "fixture", "fullscreen": True, "experiment_test_mode": True,
    }
    try:
        run_spec = _compile_packaged_playback(project_root)
        report.update(planned_frames=run_spec.display.total_frames, stage="engine initialization")
        from fpvs_studio.engines.psychopy_engine import PsychoPyEngine
        from fpvs_studio.triggers.null_backend import NullBackend

        engine = PsychoPyEngine()
    except Exception as error:
        return {**report, "error": f"{type(error).__name__}: {error}"}

    options = {
        "fullscreen": True, "display_index": 0, "experiment_test_mode": True,
        "strict_timing": False, "strict_timing_warmup": False,
    }
    try:
        report["stage"] = "open presentation window"
        engine.open_session(runtime_options=options)
        report["stage"] = "playback"
        display_size = engine.current_display_size_px()
        if display_size is None:
            raise RuntimeError("PsychoPy did not report the fullscreen display size.")
        report["display_size_px"] = display_size
        summary = engine.run_condition(
            run_spec, project_root, runtime_options=options, trigger_backend=NullBackend(),
        )
        report.update(completed_frames=summary.completed_frames, aborted=summary.aborted)
        if summary.aborted or summary.completed_frames != run_spec.display.total_frames:
            raise RuntimeError("The synthetic condition did not complete every compiled frame.")
        report["status"] = "passed"
    except Exception as error:
        if report["stage"] == "open presentation window" and _known_host_graphics_failure(error):
            report["status"] = "host_graphics_unavailable"
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        try:
            engine.close_session()
        except Exception as error:
            report.update(status="failed", cleanup_error=f"{type(error).__name__}: {error}")
    return report
