"""Visible library-project version review, passive notices and guarded menu actions."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.home_page import HomePage
from fpvs_studio.gui.main_window import StudioMainWindow
from fpvs_studio.gui.project_version_dialog import ProjectVersionDialog
from fpvs_studio.library.models import LibraryItem

_SHORT_UPDATE_WARNING = (
    "If data collection has started, review changes before switching versions.\n"
    "Updating replaces experiment settings and stimuli. Participant data and local "
    "recording/display setup are kept, with a backup of the previous version."
)


def _item(**updates) -> LibraryItem:
    values = dict(
        item_id="masking", version="2.0.0", title="Masking",
        description="Native colors, faces and numbers with editable visibility questions.",
        experiment_category="cognitive_load_fpvs", filename="masking.fpvsbundle",
        size_bytes=1024, uncompressed_size_bytes=2048, file_count=4,
        sha256="a" * 64, min_studio_version="1.0.0",
    )
    values.update(updates)
    return LibraryItem(**values)


def _fit(widget) -> None:
    QApplication.processEvents()
    assert_visible_children_within_parent(widget)
    for label in widget.findChildren(QLabel):
        if label.isVisible() and label.wordWrap() and label.text():
            assert label.height() >= label.heightForWidth(label.width()), label.text()
    for button in widget.findChildren(QPushButton):
        if button.isVisible():
            assert button.width() >= button.sizeHint().width(), button.text()


@pytest.mark.parametrize("size", [(760, 680), (820, 720)])
@pytest.mark.parametrize(
    "state", [
        "unlinked", "unknown", "relink", "current", "update", "incompatible", "offline", "busy",
        "reporting-blocked", "updated",
    ],
)
def test_project_version_states_fit_and_preserve_full_description(qtbot, size, state):
    project_name = "Long local project name with individually authored settings " * 2
    dialog = ProjectVersionDialog(project_name)
    qtbot.addWidget(dialog)
    item = _item(title="Long experiment name " * 7, description="Protocol details. " * 200)
    dialog.set_link_items([item])
    status = {
        "unlinked": "Link this project to check its library version.",
        "unknown": "The installed library version is unknown. Review the new version separately.",
        "relink": "Choose the correct experiment, then link this project.",
        "current": "This project has the latest library version.",
        "update": "A newer library version is available.",
        "incompatible": "The new version requires a newer FPVS Studio application.",
        "offline": "Could not contact the library. Your project remains available offline.",
        "busy": "Downloading and verifying the project. Cancel waits for the operation to stop.",
        "reporting-blocked": "Send or resolve saved Results reports before updating. "
                             "Download separately to retain the current version and its reports.",
        "updated": "Previous version backup: D:/A realistic long Studio Root Folder/"
                   + "subfolder with a long study name/" * 5 + ".fpvs-studio/project-backups/"
                   "study/20261030T140000Z-123456abcdef",
    }[state]
    dialog.set_state(
        installed_version=(None if state in {"unlinked", "unknown"} else
                           "2.0.0" if state == "updated" else "1.0.0"),
        latest=None if state in {"unlinked", "offline"} else item,
        linked=state != "unlinked", auto_check=True, status=status,
        can_install=state in {"unknown", "update", "busy", "reporting-blocked"},
        can_update=state in {"update", "busy"},
    )
    if state == "busy":
        dialog.set_busy(True, status)
    elif state == "relink":
        dialog.begin_linking()
        dialog.link_combo.setCurrentIndex(1)
    dialog.resize(*size)
    dialog.show()
    _fit(dialog)
    assert (dialog.width(), dialog.height()) == size
    assert not dialog.isModal()
    assert dialog.install_button.isEnabled() == (
        state in {"unknown", "update", "reporting-blocked"}
    )
    assert dialog.header.title_label.text() == project_name
    assert not dialog.header.subtitle_label.isVisible()
    assert dialog.status_label.text() == ("" if state == "relink" else status)
    assert dialog.status_label.isVisible() == (state != "relink")
    if state in {"update", "busy"}:
        assert dialog.preservation_label.text() == _SHORT_UPDATE_WARNING
    assert dialog.preservation_label.textFormat() == Qt.TextFormat.PlainText
    assert dialog.preservation_label.wordWrap()
    assert dialog.preservation_label.isVisible() == (
        state in {"unknown", "update", "busy", "reporting-blocked"}
    )
    for control in (dialog.preservation_label, dialog.install_button, dialog.update_button):
        assert control.accessibleDescription() == control.toolTip()
    assert "separate folder" in dialog.install_button.toolTip()
    assert "backup" in dialog.update_button.toolTip()
    assert "participant data" in dialog.update_button.toolTip()
    assert dialog.update_button.text() == "Update current project"
    assert dialog.update_button.isEnabled() == (state == "update")
    assert dialog.update_button.isDefault() == (state == "update")
    assert dialog.install_button.text() == "Download separately"
    assert dialog.check_button.text() == "Check for updates"
    assert dialog.auto_check_checkbox.text() == "Check for updates automatically"
    assert dialog.auto_check_checkbox.isVisible() == (state not in {"unlinked", "relink"})
    assert dialog.close_button.text() == "Keep current version"
    assert dialog.close_button.isVisible() == (state != "busy")
    assert dialog.cancel_button.isVisible() == (state == "busy")
    if state in {"update", "busy"}:
        assert "participant data" in dialog.preservation_label.text()
    elif state == "unknown":
        assert "installed version is unknown" in dialog.preservation_label.text()
    assert dialog.details.isReadOnly()
    assert dialog.details.isVisible() == (state not in {"unlinked", "offline"})
    if state == "relink":
        assert item.description in dialog.details.toPlainText()
        assert dialog.link_panel.isVisible()
        assert not dialog.relink_button.isVisible()
    elif state == "unknown":
        assert "Installed: Unknown" in dialog.versions_label.text()
        assert dialog.link_panel.isVisible()
        assert item.description in dialog.details.toPlainText()
    elif state not in {"unlinked", "offline"}:
        assert item.description in dialog.details.toPlainText()
        assert item.min_studio_version in dialog.details.toPlainText()
    else:
        assert dialog.details.toPlainText() == ""
        dialog.link_combo.setCurrentIndex(1)
        assert item.title in dialog.link_combo.toolTip()


def test_unlinked_review_shows_only_link_inputs_until_an_experiment_is_selected(qtbot):
    dialog = ProjectVersionDialog("Masking")
    qtbot.addWidget(dialog)
    item = _item()
    dialog.set_link_items([item])
    dialog.show()
    _fit(dialog)

    assert dialog.versions_label.text() == "Installed: Not linked\nLatest: Not checked"
    assert dialog.link_panel.isVisible()
    assert not dialog.auto_check_checkbox.isVisible()
    assert not dialog.details.isVisible()
    assert dialog.details.toPlainText() == ""
    assert not dialog.status_label.isVisible()
    assert not dialog.preservation_label.isVisible()
    assert not dialog.link_button.isEnabled()
    assert dialog.installed_version_edit.placeholderText() == "Unknown"
    assert dialog.installed_version_edit.accessibleDescription() == (
        "Leave blank if the installed Library version is unknown."
    )
    assert dialog.installed_version_edit.toolTip() == (
        dialog.installed_version_edit.accessibleDescription()
    )

    dialog.link_combo.setCurrentIndex(1)
    _fit(dialog)
    assert dialog.details.isVisible()
    assert item.title in dialog.details.toPlainText()
    assert item.version in dialog.details.toPlainText()
    assert item.description in dialog.details.toPlainText()
    assert dialog.link_button.isEnabled()

    dialog.link_combo.setCurrentIndex(0)
    _fit(dialog)
    assert not dialog.details.isVisible()
    assert dialog.details.toPlainText() == ""
    assert not dialog.link_button.isEnabled()


def test_review_retains_error_feedback_and_hides_empty_status_after_refresh(qtbot):
    dialog = ProjectVersionDialog("Masking")
    qtbot.addWidget(dialog)
    dialog.show()
    error = "Could not contact the Library. Reconnect and check again."
    dialog.set_state(
        installed_version="1.0.0", latest=None, linked=True, auto_check=True, status=error,
    )
    _fit(dialog)
    assert dialog.status_label.isVisible()
    assert dialog.status_label.text() == error
    assert "Installed: 1.0.0\nLatest: Not checked" == dialog.versions_label.text()
    assert not dialog.details.isVisible()

    dialog.set_state(
        installed_version="1.0.0", latest=_item(), linked=True, auto_check=True,
        can_install=True,
    )
    _fit(dialog)
    assert not dialog.status_label.isVisible()
    assert dialog.details.isVisible()
    assert dialog.preservation_label.isVisible()
    assert dialog.install_button.isEnabled()
    dialog.clear_install_candidate()
    assert not dialog.preservation_label.isVisible()
    assert not dialog.install_button.isEnabled()


def test_user_actions_and_unknown_installed_version_are_explicit(qtbot):
    dialog = ProjectVersionDialog("Masking")
    qtbot.addWidget(dialog)
    actions = []
    closed = []
    dialog.action_requested.connect(actions.append)
    dialog.closing.connect(lambda: closed.append(True))
    dialog.set_state(installed_version="1.0.0", latest=_item(), linked=True,
                     auto_check=True, can_install=True, can_update=True)
    assert actions == []
    dialog.show()
    dialog.check_button.click()
    dialog.update_button.click()
    dialog.install_button.click()
    dialog.auto_check_checkbox.click()
    assert actions == ["check", "update", "install", "set_auto"]
    assert not dialog.auto_check_enabled()
    dialog.set_state(installed_version=None, latest=None, linked=False, auto_check=True)
    dialog.set_link_items([_item()])
    assert not dialog.link_button.isEnabled()
    assert dialog.selected_link_item() is None
    dialog.link_combo.setCurrentIndex(1)
    assert dialog.link_installed_version() is None
    assert dialog.installed_version_edit.text() == ""
    dialog.link_button.click()
    assert actions[-1] == "link"
    dialog.installed_version_edit.setText(" 1.2.3 ")
    assert dialog.link_installed_version() == "1.2.3"
    dialog.set_busy(True, "Checking…")
    assert not dialog.check_button.isEnabled()
    assert not dialog.link_button.isEnabled()
    assert not dialog.auto_check_checkbox.isEnabled()
    dialog.cancel_button.click()
    assert actions[-1] == "cancel"
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert closed == [True]


@pytest.mark.parametrize("state", ["unknown", "update", "relink"])
def test_keep_current_version_closes_without_requesting_changes(qtbot, state):
    dialog = ProjectVersionDialog("Masking")
    qtbot.addWidget(dialog)
    actions = []
    closed = []
    dialog.action_requested.connect(actions.append)
    dialog.closing.connect(lambda: closed.append(True))
    dialog.set_state(
        installed_version=None if state == "unknown" else "1.0.0",
        latest=_item(), linked=True, auto_check=True, can_install=state == "update",
    )
    if state == "relink":
        dialog.begin_linking()
    dialog.show()
    assert dialog.close_button.isVisible()
    dialog.close_button.click()
    assert actions == []
    assert closed == [True]
    assert dialog.result() == dialog.DialogCode.Rejected
    assert dialog.auto_check_enabled()
    assert not dialog.isVisible()


def test_existing_library_link_can_be_replaced_without_guessing(qtbot):
    dialog = ProjectVersionDialog("Masking")
    qtbot.addWidget(dialog)
    actions = []
    dialog.action_requested.connect(actions.append)
    dialog.set_link_items([_item()])
    dialog.link_combo.setCurrentIndex(1)
    dialog.installed_version_edit.setText("1.0.0")
    dialog.set_state(installed_version="1.0.0", latest=_item(), linked=True,
                     auto_check=True, can_install=True)
    dialog.show()
    assert dialog.relink_button.isVisible()
    assert not dialog.link_panel.isVisible()
    dialog.relink_button.click()
    assert actions == ["relink"]
    assert not dialog.link_panel.isVisible()

    dialog.set_busy(True, "Loading Library experiments…")
    dialog.set_busy(False)
    dialog.begin_linking()
    assert dialog.link_panel.isVisible()
    assert dialog.status_label.text() == ""
    assert not dialog.status_label.isVisible()
    assert dialog.details.toPlainText() == ""
    assert not dialog.details.isVisible()
    assert not dialog.auto_check_checkbox.isVisible()
    assert not dialog.relink_button.isVisible()
    assert dialog.selected_link_item() is None
    assert dialog.link_installed_version() is None
    assert not dialog.link_button.isEnabled()
    assert not dialog.install_button.isEnabled()
    replacement = _item(item_id="different-experiment", title="Correct experiment")
    dialog.set_link_items([replacement])
    dialog.link_combo.setCurrentIndex(1)
    assert dialog.selected_link_item() == replacement
    assert replacement.title in dialog.details.toPlainText()
    assert dialog.link_installed_version() is None
    assert actions == ["relink"]
    dialog.link_button.click()
    assert actions == ["relink", "link"]
    dialog.set_busy(True)
    assert not dialog.relink_button.isEnabled()
    dialog.set_busy(False)
    dialog.set_state(installed_version="2.0.0", latest=replacement, linked=True,
                     auto_check=True)
    assert not dialog.link_panel.isVisible()


@pytest.mark.parametrize(
    ("close_method", "busy"),
    [("window", False), ("window", True), ("button", False), ("escape", True)],
)
def test_all_dialog_close_paths_notify_controller_once(qtbot, close_method, busy):
    dialog = ProjectVersionDialog("Masking")
    qtbot.addWidget(dialog)
    closed = []
    dialog.closing.connect(lambda: closed.append(True))
    dialog.set_busy(busy)
    dialog.show()
    if close_method == "window":
        dialog.close()
    elif close_method == "button":
        dialog.close_button.click()
    else:
        qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert closed == [True]
    assert not dialog.isVisible()


@pytest.mark.parametrize("size", [(760, 520), (1120, 720)])
@pytest.mark.parametrize("long_versions", [False, True])
def test_home_version_notice_survives_readiness_refresh_and_fits(
    qtbot, tmp_path: Path, size, long_versions,
):
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Masking")
    page = HomePage(document, load_condition_template_profiles=lambda: [])
    qtbot.addWidget(page)
    page.resize(*size)
    page.show()
    assert not page.project_update_notice.isVisible()
    message = "Library version 2.0.0 is available. Review it before opening a separate project."
    if long_versions:
        installed = "1.0.0+" + "w" * 58
        latest = "2.0.0+" + "w" * 58
        message = f"Project update available: {installed} → {latest}."
    page.set_project_update_notice(message)
    page.refresh()
    assert page.project_update_label.toolTip() == message
    assert page.project_update_label.accessibleDescription() == message
    assert page.project_update_notice.isVisible()
    _fit(page)
    label = page.project_update_label
    assert label.fontMetrics().horizontalAdvance(label.text()) <= label.contentsRect().width()
    assert message.startswith(label.text().removesuffix("…"))
    if long_versions:
        assert label.text() != message
    assert (page.width(), page.height()) == size
    page.set_project_update_notice("")
    assert not page.project_update_notice.isVisible()


def test_project_update_menu_and_notice_respect_busy_guards(qtbot, tmp_path, monkeypatch):
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Masking")
    requested = []
    window = StudioMainWindow(
        document=document, on_request_new_project=lambda: None,
        on_request_open_project=lambda: None, on_request_manage_projects=lambda: None,
        on_request_import_project_config=lambda: None,
        on_request_import_project_bundle=lambda: None, on_request_settings=lambda: None,
        on_load_condition_template_profiles=lambda: [],
        on_manage_condition_templates=lambda: [],
        on_request_project_update=lambda: requested.append(True),
    )
    qtbot.addWidget(window)
    assert window.project_update_action in window.file_menu.actions()
    window.project_update_action.trigger()
    assert requested == [True]
    window.set_project_update_notice("A new library version is available.")
    window.home_page.project_update_button.click()
    assert requested == [True, True]
    window._set_bundle_processing_busy(True)
    assert not window.project_update_action.isEnabled()
    assert not window.home_page.project_update_button.isEnabled()
    window._set_bundle_processing_busy(False)
    assert window.project_update_action.isEnabled()
    monkeypatch.setattr(window, "_allow_project_handoff_during_launch", lambda: False)
    window.project_update_action.trigger()
    assert requested == [True, True]
    monkeypatch.setattr(window, "_allow_project_handoff_during_launch", lambda: True)
    monkeypatch.setattr(window, "_allow_project_handoff_during_fixation_load", lambda: False)
    window.project_update_action.trigger()
    assert requested == [True, True]
    monkeypatch.setattr(window, "_allow_project_handoff_during_fixation_load", lambda: True)


@pytest.mark.parametrize("size", [(760, 680), (820, 720)])
def test_primary_update_keeps_separate_download_secondary_and_blocks_unknown(qtbot, size):
    dialog = ProjectVersionDialog("Long current project name " * 4)
    qtbot.addWidget(dialog)
    dialog.set_state(installed_version="1.0.0", latest=_item(), linked=True,
                     auto_check=True, can_install=True, can_update=True,
                     can_download_separately=False)
    dialog.resize(*size)
    dialog.show()
    _fit(dialog)
    assert dialog.update_button.isEnabled() and dialog.update_button.isDefault()
    assert not dialog.install_button.isEnabled()
    dialog.set_state(installed_version=None, latest=_item(), linked=True,
                     auto_check=True, can_install=True, can_update=True)
    _fit(dialog)
    assert not dialog.update_button.isEnabled()
    assert dialog.install_button.isEnabled() and dialog.install_button.isDefault()
    assert "installed version is unknown" in dialog.preservation_label.text()


def _update_window(qtbot, tmp_path):
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Current project")
    window = StudioMainWindow(
        document=document, on_request_new_project=lambda: None,
        on_request_open_project=lambda: None, on_request_manage_projects=lambda: None,
        on_request_import_project_config=lambda: None,
        on_request_import_project_bundle=lambda: None, on_request_settings=lambda: None,
        on_load_condition_template_profiles=lambda: [], on_manage_condition_templates=lambda: [],
    )
    qtbot.addWidget(window)
    return window


def test_committed_update_discards_old_editor_drafts_before_save(qtbot, tmp_path):
    from fpvs_studio.core.serialization import load_project_file
    from fpvs_studio.preprocessing.manifest import create_empty_manifest

    window = _update_window(qtbot, tmp_path)
    old_setup = window.setup_wizard_page
    old_setup.condition_setup_step.condition_name_edit.setText("Stale editor draft")
    old_setup.condition_setup_step.instructions_edit.setPlainText("Stale pending instructions")
    assert old_setup.condition_setup_step._instructions_committer.pending
    project = window.document.project.model_copy(deep=True)
    project.conditions[0].name = "Updated Library condition"
    project.conditions[0].instructions = "Updated Library instructions"
    manifest = create_empty_manifest(project.meta.project_id)
    window.start_bundle_import_processing(project_name=project.meta.name,
        bundle_path=tmp_path / "new.fpvsbundle", root_dir=window.document.project_root,
        updating_current=True)
    window.accept_library_project_update(project, manifest)
    assert window._setup_wizard_page is None
    assert not window.document.dirty
    window.finish_bundle_import_processing(restore_previous=False)
    window.show_home()
    assert window.save_project()
    saved = load_project_file(window.document.project_root / "project.json")
    assert saved.conditions[0].name == "Updated Library condition"
    assert saved.conditions[0].instructions == "Updated Library instructions"
    assert window.document.manifest is manifest


def test_failed_update_reload_blocks_stale_save_and_allows_close(qtbot, tmp_path, monkeypatch):
    window = _update_window(qtbot, tmp_path)
    monkeypatch.setattr(window.document, "save", lambda: pytest.fail("Stale model saved"))
    window.start_bundle_import_processing(project_name="Current project",
        bundle_path=tmp_path / "new.fpvsbundle", root_dir=window.document.project_root,
        updating_current=True)
    window.fail_library_project_update()
    assert not window.save_project()
    assert not window.save_project_action.isEnabled()
    assert not window.launch_action.isEnabled()
    window.show_setup_wizard()
    assert window._setup_wizard_page is None
    assert window.maybe_save_changes()
    assert window.close()


@pytest.mark.parametrize("failed_reload", [False, True])
def test_project_update_blocks_existing_recovery_dialog_and_direct_rerun(
    qtbot, tmp_path, monkeypatch, failed_reload,
):
    from fpvs_studio.gui.condition_recovery_dialog import ConditionRecoveryDialog
    from fpvs_studio.runtime.condition_recovery import ConditionRecoveryReport

    window = _update_window(qtbot, tmp_path)
    monkeypatch.setattr(window, "start_deferred_open_tasks", lambda: None)
    monkeypatch.setattr(window.document, "validate_recording_launch",
                        lambda: pytest.fail("Recovery launch reached the runtime safeguards"))
    recovery = window._condition_recovery
    monkeypatch.setattr(recovery, "_rerun", lambda _record: pytest.fail("Recovery dispatched"))
    dialog = ConditionRecoveryDialog(ConditionRecoveryReport(), window)
    recovery._dialog = dialog
    window.show()
    dialog.show()
    QApplication.processEvents()
    assert dialog.isVisible()

    window.start_bundle_import_processing(project_name="Current project",
        bundle_path=tmp_path / "new.fpvsbundle", root_dir=window.document.project_root,
        updating_current=True)
    if failed_reload:
        window.fail_library_project_update()
    assert not dialog.isVisible()
    assert not window.interrupted_sessions_action.isEnabled()
    assert not recovery._available()
    recovery.check()
    assert recovery._task is None
    recovery._request_rerun(object())
    window._launch_recovered_condition(object())

    if not failed_reload:
        window.finish_bundle_import_processing(restore_previous=True)
        assert window.interrupted_sessions_action.isEnabled()
        assert recovery._available()
    assert window.close()
