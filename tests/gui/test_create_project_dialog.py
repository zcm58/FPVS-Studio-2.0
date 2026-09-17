"""Registered Qt coverage for new-experiment source choice and manual setup."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFileDialog, QLabel
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.core.condition_template_profiles import (
    ATTENTIONAL_BLINK_STREAM_PROFILE_ID,
    built_in_condition_template_profiles,
)
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.gui.create_project_dialog import CreateProjectDialog


def _assert_details_fit(dialog: CreateProjectDialog) -> None:
    QApplication.processEvents()
    assert_visible_children_within_parent(dialog)
    for label in dialog.findChildren(QLabel):
        if not label.isVisible() or not label.text():
            continue
        if label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width()), label.objectName()
        else:
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text()), (
                label.objectName()
            )


@pytest.mark.parametrize("size", [(760, 500), (800, 500)])
@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_creation_source_choice_fits_and_requires_an_explicit_route(
    qtbot, size, background
) -> None:
    dialog = CreateProjectDialog()
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.resize(*size)
    dialog.show()
    _assert_details_fit(dialog)
    assert (dialog.width(), dialog.height()) == size
    assert dialog.category_stack.currentWidget() is dialog.source_page
    assert not dialog.from_library
    assert not dialog.back_button.isVisible()
    ok_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)
    assert ok_button is not None and not ok_button.isVisible()
    assert not dialog.project_name_edit.isVisible()
    for button, text in (
        (dialog.manual_button, "Create manually"),
        (dialog.library_button, "Download from library"),
    ):
        assert button.isVisible() and button.isEnabled()
        assert button.text() == text
        assert button.width() >= button.sizeHint().width()
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert dialog.category_stack.currentWidget() is dialog.source_page
    dialog.manual_button.setFocus()
    qtbot.keyClick(dialog.manual_button, Qt.Key.Key_Tab)
    assert dialog.focusWidget() is dialog.library_button


@pytest.mark.parametrize("key", [None, Qt.Key.Key_Space, Qt.Key.Key_Return])
def test_creation_library_choice_needs_no_manual_fields(qtbot, tmp_path, key) -> None:
    dialog = CreateProjectDialog()
    qtbot.addWidget(dialog)
    dialog.set_parent_directory(tmp_path)
    dialog.show()
    dialog.library_button.setFocus()
    if key is None:
        qtbot.mouseClick(dialog.library_button, Qt.MouseButton.LeftButton)
    else:
        qtbot.keyClick(dialog.library_button, key)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.from_library
    assert dialog.project_name == ""
    assert dialog.condition_profile_id is None
    assert list(tmp_path.iterdir()) == []


def test_creation_back_navigation_preserves_manual_draft(qtbot, tmp_path) -> None:
    dialog = CreateProjectDialog(condition_template_profiles=built_in_condition_template_profiles())
    qtbot.addWidget(dialog)
    dialog.set_parent_directory(tmp_path)
    dialog.show()
    dialog.manual_button.click()
    assert dialog.category_stack.currentWidget() is dialog.category_page
    assert dialog.back_button.isVisible()
    dialog.select_category(ExperimentCategory.ATTENTIONAL_BLINK)
    dialog.accept()
    dialog.project_name_edit.setText("Recognition Study")
    dialog.condition_profile_combo.setCurrentIndex(1)
    selected_profile = dialog.condition_profile_id
    dialog.back_button.click()
    assert dialog.category_stack.currentWidget() is dialog.category_page
    dialog.back_button.click()
    assert dialog.category_stack.currentWidget() is dialog.source_page
    assert not dialog.back_button.isVisible()
    dialog.manual_button.click()
    dialog.accept()
    assert dialog.category_stack.currentWidget() is dialog.details_page
    assert dialog.project_name == "Recognition Study"
    assert dialog.parent_directory == tmp_path
    assert dialog.condition_profile_id == selected_profile
    assert not dialog.from_library
    dialog.reject()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("size", [(760, 500), (800, 500)])
@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_creation_details_fit_with_long_content(qtbot, size, background) -> None:
    profiles = built_in_condition_template_profiles()
    stream = next(
        profile for profile in profiles if profile.profile_id == ATTENTIONAL_BLINK_STREAM_PROFILE_ID
    ).model_copy(
        update={
            "display_name": "Digits and letter targets with several target intervals",
            "description": (
                "A rapid digit stream with two letter targets. Compare target recognition "
                "at several onset-to-onset intervals while keeping the same character pools."
            ),
        }
    )
    dialog = CreateProjectDialog(condition_template_profiles=[stream])
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.select_category(ExperimentCategory.ATTENTIONAL_BLINK)
    dialog.accept()
    dialog.project_name_edit.setText("Attentional Blink Target Recognition Follow Up Study")
    full_path = (
        "C:/Users/Researcher/OneDrive - Mississippi State University/Research Projects/"
        "Attention and Visual Cognition/FPVS Studio Project Root"
    )
    dialog.project_root_edit.setText(full_path)
    dialog.resize(*size)
    dialog.show()

    _assert_details_fit(dialog)
    assert (dialog.width(), dialog.height()) == size
    assert dialog.category_summary_label.text() == "Attentional-Blink"
    assert dialog.template_description_label.text() == stream.description
    assert dialog.template_description_label.textFormat() == Qt.TextFormat.PlainText
    assert dialog.condition_profile_combo.toolTip() == stream.display_name
    assert dialog.folder_hint_label.text() == (
        "New folder: attentional-blink-target-recognition-follow-up-study"
    )
    assert dialog.folder_hint_label.toolTip() == str(
        Path(full_path) / "attentional-blink-target-recognition-follow-up-study"
    )
    assert dialog.project_root_edit.toolTip() == full_path
    assert full_path in dialog.project_root_edit.accessibleDescription()
    assert not dialog.project_root_edit.isReadOnly()
    dialog.project_root_edit.selectAll()
    assert dialog.project_root_edit.selectedText() == full_path
    visible_labels = [label.text() for label in dialog.findChildren(QLabel) if label.isVisible()]
    assert "Name your experiment" in visible_labels
    assert "Experiment Template" in visible_labels

    create_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)
    cancel_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel)
    assert create_button is not None and cancel_button is not None
    assert create_button.text() == "Create Experiment"
    assert create_button.property("primaryActionRole") == "true"
    for button in (dialog.back_button, create_button, cancel_button):
        assert button.width() >= button.sizeHint().width()
    assert dialog.back_button.mapTo(dialog, QPoint(dialog.back_button.width(), 0)).x() < (
        create_button.mapTo(dialog, QPoint(0, 0)).x()
    )


def test_creation_summaries_follow_name_template_and_category(qtbot) -> None:
    profiles = built_in_condition_template_profiles()
    dialog = CreateProjectDialog(condition_template_profiles=profiles)
    qtbot.addWidget(dialog)
    dialog.select_category(ExperimentCategory.ATTENTIONAL_BLINK)
    dialog.accept()
    dialog.show()
    assert dialog.condition_profile_id == ATTENTIONAL_BLINK_STREAM_PROFILE_ID
    empty_hint = dialog.folder_hint_label.text()
    assert empty_hint and "New folder:" not in empty_hint
    dialog.project_name_edit.setText("  Recognition Study 2  ")
    assert dialog.folder_hint_label.text() == "New folder: recognition-study-2"
    dialog.project_name_edit.clear()
    assert dialog.folder_hint_label.text() == empty_hint

    dialog.condition_profile_combo.setCurrentIndex(1)
    selected = next(
        profile for profile in profiles if profile.profile_id == dialog.condition_profile_id
    )
    assert dialog.template_description_label.text() == selected.description
    qtbot.mouseClick(dialog.back_button, Qt.MouseButton.LeftButton)
    assert dialog.category_stack.currentWidget() is dialog.category_page
    assert dialog.back_button.isVisible()
    dialog.select_category(ExperimentCategory.FPVS_ODDBALL)
    dialog.accept()
    selected = next(
        profile for profile in profiles if profile.profile_id == dialog.condition_profile_id
    )
    assert dialog.template_description_label.text() == selected.description
    _assert_details_fit(dialog)

    dialog.set_condition_template_profiles([], preserve_selection=False)
    assert dialog.condition_profile_id is None
    assert dialog.template_description_label.text() != selected.description
    _assert_details_fit(dialog)


def test_creation_template_summary_refreshes_after_managing_templates(qtbot) -> None:
    profile = next(
        profile
        for profile in built_in_condition_template_profiles()
        if profile.profile_id == ATTENTIONAL_BLINK_STREAM_PROFILE_ID
    )
    updated = profile.model_copy(update={"description": "Updated target intervals for this study."})
    dialog = CreateProjectDialog(
        condition_template_profiles=[profile], on_manage_templates=lambda: [updated]
    )
    qtbot.addWidget(dialog)
    dialog.select_category(ExperimentCategory.ATTENTIONAL_BLINK)
    dialog.accept()
    dialog.show()
    qtbot.mouseClick(dialog.manage_templates_button, Qt.MouseButton.LeftButton)
    assert dialog.condition_profile_id == profile.profile_id
    assert dialog.template_description_label.text() == updated.description


def test_creation_tab_order_follows_visible_field_order(qtbot) -> None:
    profiles = built_in_condition_template_profiles()
    dialog = CreateProjectDialog(
        condition_template_profiles=profiles, on_manage_templates=lambda: profiles
    )
    qtbot.addWidget(dialog)
    dialog.select_category(ExperimentCategory.ATTENTIONAL_BLINK)
    dialog.accept()
    dialog.show()
    QApplication.processEvents()
    dialog.project_name_edit.setFocus()
    field_order = (
        dialog.project_name_edit,
        dialog.condition_profile_combo,
        dialog.manage_templates_button,
        dialog.project_root_edit,
        dialog.project_root_browse_button,
    )
    assert dialog.focusWidget() is field_order[0]
    for current, following in zip(field_order[:-1], field_order[1:], strict=True):
        qtbot.keyClick(current, Qt.Key.Key_Tab)
        assert dialog.focusWidget() is following


def test_creation_folder_preview_and_cancel_do_not_create_files(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    dialog = CreateProjectDialog(condition_template_profiles=built_in_condition_template_profiles())
    qtbot.addWidget(dialog)
    dialog.set_parent_directory(tmp_path)
    dialog.select_category(ExperimentCategory.ATTENTIONAL_BLINK)
    dialog.accept()
    dialog.project_name_edit.setText("Recognition Study")
    dialog.show()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args, **kwargs: "")
    qtbot.mouseClick(dialog.project_root_browse_button, Qt.MouseButton.LeftButton)
    assert dialog.parent_directory == tmp_path
    assert dialog.project_root_edit.toolTip() == str(tmp_path)

    selected_folder = tmp_path / "Selected parent"
    selected_folder.mkdir()
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *args, **kwargs: str(selected_folder)
    )
    qtbot.mouseClick(dialog.project_root_browse_button, Qt.MouseButton.LeftButton)
    assert dialog.parent_directory == selected_folder
    assert dialog.project_root_edit.toolTip() == str(selected_folder)
    assert str(selected_folder) in dialog.project_root_edit.accessibleDescription()
    cancel_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel)
    assert cancel_button is not None
    qtbot.mouseClick(cancel_button, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert list(selected_folder.iterdir()) == []
    assert not (tmp_path / "recognition-study").exists()
