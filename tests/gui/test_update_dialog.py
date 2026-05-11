"""GUI smoke tests for the in-app update flow."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox
from tests.gui.helpers import open_created_project

from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.main_window import _TUTORIALS_URL
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


def test_main_window_exposes_file_about_action(
    controller,
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path)
    messages: list[tuple[str, str]] = []

    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, message: messages.append((title, message)),
    )

    actions = [action.text() for action in window.file_menu.actions()]
    assert window.about_action.text() == "About"
    assert "About" in actions

    window.about_action.trigger()

    assert messages
    assert messages[0][0] == "About FPVS Studio"
    assert "FPVS Studio version" in messages[0][1]
    assert "Zack Murphy" in messages[0][1]
    assert "Neural Engineering Research Division, Mississippi State University" in messages[0][1]


def test_main_window_exposes_file_tutorials_action(
    controller,
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path)
    opened_urls: list[str] = []

    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QDesktopServices.openUrl",
        lambda url: opened_urls.append(url.toString()),
    )

    actions = [action.text() for action in window.file_menu.actions()]
    assert window.tutorials_action.text() == "Tutorials"
    assert "Tutorials" in actions

    window.tutorials_action.trigger()

    assert opened_urls == [_TUTORIALS_URL]


def test_startup_update_check_prompts_only_when_update_available(
    qapp,
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    controller = StudioController(qapp)
    fpvs_root_dir = tmp_path / "fpvs-root"
    fpvs_root_dir.mkdir(parents=True, exist_ok=True)
    controller.save_fpvs_root_dir(fpvs_root_dir)
    controller._startup_update_check_callback = _available_update
    dialogs: list[UpdateDialog] = []

    def _capture_exec(dialog: UpdateDialog) -> int:
        dialogs.append(dialog)
        return int(dialog.DialogCode.Accepted)

    monkeypatch.setattr("fpvs_studio.gui.controller.UpdateDialog.exec", _capture_exec)

    controller.show_welcome()
    assert controller.welcome_window is not None
    qtbot.addWidget(controller.welcome_window)

    qtbot.waitUntil(lambda: bool(dialogs), timeout=5000)

    dialog = dialogs[0]
    assert "A new FPVS Studio version is available." in dialog.status_label.text()
    assert "projects, templates, settings, run history, and logs" in dialog.status_label.text()
    assert dialog.download_button.isEnabled()
    assert dialog.close_button.text() == "Remind Me Later"


def test_update_dialog_initial_result_is_themed_and_remind_later_dismisses(qtbot) -> None:
    dialog = UpdateDialog(auto_check=False, initial_result=_available_update())
    qtbot.addWidget(dialog)
    dialog.show()

    qtbot.waitUntil(lambda: dialog.close_button.text() == "Remind Me Later")
    assert "QDialog#update_dialog" in dialog.styleSheet()
    assert "QPushButton" in dialog.styleSheet()

    dialog.close_button.click()

    qtbot.waitUntil(lambda: not dialog.isVisible())


def test_startup_update_prompt_remind_later_returns_to_welcome(
    qapp,
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    controller = StudioController(qapp)
    fpvs_root_dir = tmp_path / "fpvs-root"
    fpvs_root_dir.mkdir(parents=True, exist_ok=True)
    controller.save_fpvs_root_dir(fpvs_root_dir)
    controller._startup_update_check_callback = _available_update
    original_exec = UpdateDialog.exec
    dialog_versions: list[str] = []

    def _click_remind_later(dialog: UpdateDialog) -> int:
        dialog_versions.append(dialog.current_version_label.text())
        QTimer.singleShot(0, dialog.close_button.click)
        return original_exec(dialog)

    monkeypatch.setattr(UpdateDialog, "exec", _click_remind_later)

    controller.show_welcome()
    assert controller.welcome_window is not None
    qtbot.addWidget(controller.welcome_window)

    qtbot.waitUntil(lambda: bool(dialog_versions), timeout=5000)
    qtbot.waitUntil(lambda: controller._startup_update_thread is None, timeout=5000)

    assert dialog_versions == ["Current version: 0.9.0b1"]
    assert controller.welcome_window.isVisible()


def test_update_dialog_action_buttons_fit_text_at_compact_width(qtbot) -> None:
    dialog = UpdateDialog(auto_check=False, initial_result=_available_update())
    qtbot.addWidget(dialog)
    dialog.resize(dialog.minimumSizeHint())
    dialog.show()
    qtbot.waitUntil(lambda: dialog.close_button.width() > 0)

    for button in (
        dialog.check_button,
        dialog.download_button,
        dialog.install_button,
        dialog.close_button,
    ):
        required_width = button.fontMetrics().horizontalAdvance(button.text()) + 20
        assert button.width() >= required_width, button.text()


def test_startup_update_check_is_silent_when_no_update_or_error(
    qapp,
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    exec_calls: list[str] = []

    monkeypatch.setattr(
        "fpvs_studio.gui.controller.UpdateDialog.exec",
        lambda _dialog: exec_calls.append("dialog"),
    )

    callbacks: list[Callable[[], UpdateCheckResult]] = []
    callback_calls: list[int] = []

    def _no_update() -> UpdateCheckResult:
        callback_calls.append(0)
        return UpdateCheckResult(
            current_version="0.9.1b4",
            latest_version="0.9.1b4",
            update_available=False,
            release_url=None,
            release_notes_summary="",
            installer_asset=None,
            is_prerelease=True,
        )

    def _update_error() -> UpdateCheckResult:
        callback_calls.append(1)
        raise RuntimeError("network unavailable")

    callbacks.extend((_no_update, _update_error))
    for index, callback in enumerate(callbacks):
        controller = StudioController(qapp)
        fpvs_root_dir = tmp_path / f"fpvs-root-{index}"
        fpvs_root_dir.mkdir(parents=True, exist_ok=True)
        controller.save_fpvs_root_dir(fpvs_root_dir)
        controller._startup_update_check_callback = callback

        controller.show_welcome()
        assert controller.welcome_window is not None
        qtbot.addWidget(controller.welcome_window)

        qtbot.waitUntil(
            lambda target=controller, expected_index=index: (
                expected_index in callback_calls
                and target._startup_update_check_started
                and target._startup_update_thread is None
            ),
            timeout=5000,
        )

    assert exec_calls == []


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
    assert "A new FPVS Studio version is available." in dialog.status_label.text()
    assert "projects, templates, settings, run history, and logs" in dialog.status_label.text()
    assert "0.9.0b1" in dialog.current_version_label.text()
    assert "0.9.0b2" in dialog.latest_version_label.text()
    assert "Improved update flow" in dialog.notes_label.text()
    assert dialog.release_notes_button.isEnabled()
    assert dialog.close_button.text() == "Remind Me Later"

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
    assert dialog.close_button.text() == "Close"


def test_update_dialog_reports_manual_server_error(qtbot) -> None:
    dialog = UpdateDialog(
        auto_check=False,
        check_callback=lambda: (_ for _ in ()).throw(RuntimeError("network unavailable")),
    )
    qtbot.addWidget(dialog)
    dialog.show()

    dialog.start_update_check()
    qtbot.waitUntil(
        lambda: "try again later from File > Check for Updates" in dialog.status_label.text()
    )

    assert "network unavailable" in dialog.notes_label.text()
    assert dialog.download_button.isEnabled() is False
    assert dialog.install_button.isEnabled() is False
    assert dialog.close_button.text() == "Close"


def _download_with_progress(
    installer_path: Path,
    progress: Callable[[int, int | None], None],
) -> DownloadedInstaller:
    size = installer_path.stat().st_size
    progress(size // 2, size)
    progress(size, size)
    return DownloadedInstaller(path=installer_path, size_bytes=size)
