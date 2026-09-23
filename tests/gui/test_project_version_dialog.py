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
            assert button.width() >= button.fontMetrics().horizontalAdvance(button.text())


@pytest.mark.parametrize("size", [(760, 680), (820, 720)])
@pytest.mark.parametrize(
    "state", ["unlinked", "relink", "current", "update", "incompatible", "offline", "busy"],
)
def test_project_version_states_fit_and_preserve_full_description(qtbot, size, state):
    dialog = ProjectVersionDialog(
        "Long local project name with individually authored settings " * 2,
    )
    qtbot.addWidget(dialog)
    item = _item(title="Long experiment name " * 7, description="Protocol details. " * 200)
    dialog.set_link_items([item])
    status = {
        "unlinked": "Link this project to check its library version.",
        "relink": "Choose the correct experiment, then link this project.",
        "current": "This project has the latest library version.",
        "update": "A newer library version is available.",
        "incompatible": "The new version requires a newer FPVS Studio application.",
        "offline": "Could not contact the library. Your project remains available offline.",
        "busy": "Downloading and verifying the project. Cancel waits for the operation to stop.",
    }[state]
    dialog.set_state(
        installed_version=None if state == "unlinked" else "1.0.0",
        latest=None if state in {"unlinked", "offline"} else item,
        linked=state != "unlinked", auto_check=True, status=status,
        can_install=state in {"update", "busy"},
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
    assert dialog.install_button.isEnabled() == (state == "update")
    assert dialog.status_label.text() == status
    assert "separate project" in dialog.preservation_label.text()
    assert "participant data" in dialog.preservation_label.text()
    if state == "relink":
        assert item.description in dialog.details.toPlainText()
        assert dialog.link_panel.isVisible()
        assert dialog.relink_button.isVisible()
    elif state not in {"unlinked", "offline"}:
        assert item.description in dialog.details.toPlainText()
        assert item.min_studio_version in dialog.details.toPlainText()
    else:
        dialog.link_combo.setCurrentIndex(1)
        assert item.title in dialog.link_combo.toolTip()


def test_user_actions_and_unknown_installed_version_are_explicit(qtbot):
    dialog = ProjectVersionDialog("Masking")
    qtbot.addWidget(dialog)
    actions = []
    closed = []
    dialog.action_requested.connect(actions.append)
    dialog.closing.connect(lambda: closed.append(True))
    dialog.set_state(installed_version="1.0.0", latest=_item(), linked=True,
                     auto_check=True, can_install=True)
    assert actions == []
    dialog.show()
    dialog.check_button.click()
    dialog.install_button.click()
    dialog.auto_check_checkbox.click()
    assert actions == ["check", "install", "set_auto"]
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
    assert "Loading" not in dialog.status_label.text()
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
