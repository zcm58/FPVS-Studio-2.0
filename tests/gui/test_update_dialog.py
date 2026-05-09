"""GUI smoke tests for the in-app update flow."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QMessageBox
from tests.gui.helpers import open_created_project

from fpvs_studio.gui.update_dialog import UpdateDialog
from fpvs_studio.updates.models import DownloadedInstaller, InstallerAsset, UpdateCheckResult


def _available_update() -> UpdateCheckResult:
    asset = InstallerAsset(
        name="FPVS-Studio-Setup-0.9.0b2.exe",
        download_url="https://github.com/downloads/FPVS-Studio-Setup-0.9.0b2.exe",
        size_bytes=10,
    )
    return UpdateCheckResult(
        current_version="0.9.0b1",
        latest_version="0.9.0b2",
        update_available=True,
        release_url="https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v0.9.0b2",
        release_notes_summary="Improved update flow",
        installer_asset=asset,
        is_prerelease=True,
    )


def test_main_window_exposes_file_check_for_updates_action(
    controller,
    qtbot,
    tmp_path: Path,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path)

    actions = [action.text() for action in window.file_menu.actions()]

    assert window.check_updates_action.text() == "Check for Updates"
    assert "Check for Updates" in actions


def test_update_dialog_downloads_then_launches_installer(
    qtbot,
    monkeypatch,
    tmp_path: Path,
) -> None:
    installer_path = tmp_path / "FPVS-Studio-Setup-0.9.0b2.exe"
    installer_path.write_bytes(b"installer")
    launched: list[Path] = []
    quit_calls: list[str] = []

    dialog = UpdateDialog(
        auto_check=False,
        check_callback=_available_update,
        download_callback=lambda _asset, progress: _download_with_progress(
            installer_path,
            progress,
        ),
        installer_launcher=lambda path: launched.append(path),
        quit_app=lambda: quit_calls.append("quit"),
    )
    qtbot.addWidget(dialog)
    dialog.show()

    dialog.start_update_check()
    qtbot.waitUntil(lambda: dialog.download_button.isEnabled())
    assert dialog.status_label.text() == "A new FPVS Studio version is available."
    assert "0.9.0b2" in dialog.latest_version_label.text()
    assert "Improved update flow" in dialog.notes_label.text()

    dialog.start_download()
    qtbot.waitUntil(lambda: dialog.install_button.isEnabled())
    assert dialog.progress_bar.value() == installer_path.stat().st_size

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    dialog.install_and_restart()

    assert launched == [installer_path]
    assert quit_calls == ["quit"]


def test_update_dialog_reports_no_update(qtbot) -> None:
    dialog = UpdateDialog(
        auto_check=False,
        check_callback=lambda: UpdateCheckResult(
            current_version="0.9.0b1",
            latest_version="0.9.0b1",
            update_available=False,
            release_url=None,
            release_notes_summary="",
            installer_asset=None,
            is_prerelease=True,
        ),
    )
    qtbot.addWidget(dialog)
    dialog.show()

    dialog.start_update_check()
    qtbot.waitUntil(lambda: dialog.status_label.text() == "FPVS Studio is up to date.")

    assert dialog.download_button.isEnabled() is False
    assert dialog.install_button.isEnabled() is False


def _download_with_progress(
    installer_path: Path,
    progress: Callable[[int, int | None], None],
) -> DownloadedInstaller:
    size = installer_path.stat().st_size
    progress(size // 2, size)
    progress(size, size)
    return DownloadedInstaller(path=installer_path, size_bytes=size)
