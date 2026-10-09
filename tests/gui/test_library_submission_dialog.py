"""Registered visible-only submission control and geometry coverage."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QLabel
from tests.gui.helpers import assert_visible_children_within_parent
from tests.unit.test_data_sharing_gui_jobs import _Lifecycle

from fpvs_studio.gui.library_submission_controller import LibrarySubmissionController
from fpvs_studio.gui.library_submission_dialog import LibrarySubmissionDialog


@pytest.mark.parametrize(
    "busy,prepared,attempted,completed",
    [
        (False, False, False, False),
        (True, True, True, False),
        (False, True, False, False),
        (False, True, True, False),
        (False, True, True, True),
    ],
)
@pytest.mark.parametrize("size", [(760, 600), (820, 660)])
def test_submission_states_fit_at_minimum(qtbot, busy, prepared, attempted, completed, size):
    dialog = LibrarySubmissionDialog()
    qtbot.addWidget(dialog)
    dialog.title_edit.setText("Long experiment title " * 7)
    dialog.review.setPlainText("C:/Research/a-long-project-folder/stimuli/" * 8)
    dialog.status.setText(
        "Upload was not confirmed. Refresh my requests before retrying the same prepared bundle. "
        * 2
    )
    dialog.rights.setChecked(True)
    dialog.author_edit.setText("Researcher name " * 13)
    dialog.email_edit.setText("researcher" * 20 + "@university.example.edu")
    dialog.set_state(busy, prepared, attempted, completed)
    dialog.resize(*size)
    dialog.show()
    qtbot.wait(25)
    assert_visible_children_within_parent(dialog)
    assert dialog.buttons["submit"].isEnabled() == (not busy and not completed)
    for label in dialog.findChildren(QLabel):
        if label.isVisible() and label.text() and not label.wordWrap():
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
        elif label.isVisible() and label.text() and label.wordWrap():
            required = label.fontMetrics().boundingRect(
                QRect(0, 0, label.contentsRect().width(), 10000),
                int(Qt.TextFlag.TextWordWrap),
                label.text(),
            )
            assert label.height() >= required.height()
    for tab in (1, 2):
        dialog.tabs.setCurrentIndex(tab)
        qtbot.wait(25)
        assert_visible_children_within_parent(dialog)


def test_sharing_requires_explicit_confirmation_and_close_requests_cancellation(qtbot):
    dialog = LibrarySubmissionDialog()
    qtbot.addWidget(dialog)
    dialog.set_state(False, True, False)
    assert not dialog.buttons["submit"].isEnabled()
    dialog.rights.setChecked(True)
    assert dialog.buttons["submit"].isEnabled()
    with qtbot.waitSignal(dialog.closing):
        dialog.close()


def test_long_error_elision_exposes_the_complete_value(qtbot, qapp):
    controller = LibrarySubmissionController(qapp)
    dialog = controller.dialog
    qtbot.addWidget(dialog)
    message = "Project folder with spaces and a long name/" * 30
    controller._status(message)
    dialog.resize(760, 600)
    dialog.show()
    qtbot.wait(25)
    assert dialog.status.text().endswith("…")
    assert dialog.status.toolTip() == dialog.status.accessibleDescription() == message
    assert_visible_children_within_parent(dialog)


def test_prefilled_project_title_is_preserved_for_explicit_validation(qtbot):
    dialog = LibrarySubmissionDialog()
    qtbot.addWidget(dialog)
    title = "A long authored project title " * 10
    dialog.title_edit.setText(title)
    assert dialog.title_edit.text() == title


@pytest.mark.parametrize("size", [(760, 600), (820, 660)])
def test_new_upload_uses_current_project_with_fresh_permission(
    qtbot, qapp, tmp_path, monkeypatch, size,
):
    lifecycle = _Lifecycle()
    monkeypatch.setattr(
        "fpvs_studio.gui.library_submission_controller.update_lifecycle", lambda _app: lifecycle,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.library_submission_controller.publication_review",
        lambda prepared: str(prepared.bundle_path),
    )
    controller = LibrarySubmissionController(qapp, client=object())
    dialog = controller.dialog
    qtbot.addWidget(dialog)
    controller.show(
        project_root=tmp_path / "project-a", title="Project A", description="A",
        save_project=lambda: False,
    )
    old = SimpleNamespace(
        request=SimpleNamespace(item_id=f"submitted-{uuid4()}"),
        bundle_path=tmp_path / "prepared-a.fpvsbundle",
    )
    old_identity = ("Researcher A", "a@example.test")
    controller._prepared, controller._identity = old, old_identity
    controller._attempted, controller._completed = True, True
    dialog.rights.setChecked(True)
    dialog.set_state(False, True, True, True)
    title = "Project B with independently selected authored conditions " * 2
    description = "Description of Project B and its authored protocol. " * 3
    root = tmp_path / "project-b"
    saves, preparations = [], []
    controller.show(
        project_root=root, title=title, description=description,
        save_project=lambda: saves.append("B") or True,
    )
    dialog.resize(*size)
    qtbot.mouseClick(dialog.buttons["new"], Qt.MouseButton.LeftButton)
    qtbot.wait(25)
    assert dialog.title_edit.text() == title
    assert dialog.description.toPlainText() == description
    assert not dialog.rights.isChecked()
    assert not dialog.buttons["submit"].isEnabled()
    assert controller._retained_uploads[old.request.item_id] == (old, old_identity)
    assert_visible_children_within_parent(dialog)

    def prepare(source, request, **_kwargs):
        preparations.append((source, request))
        return SimpleNamespace(request=request, bundle_path=tmp_path / "prepared-b.fpvsbundle")

    monkeypatch.setattr(controller.service, "prepare", prepare)
    monkeypatch.setattr(
        "fpvs_studio.gui.library_submission_controller.submit_project",
        lambda *_args, **_kwargs: SimpleNamespace(
            status="pending", review_notes="", title=title, submission_id=str(uuid4()),
        ),
    )
    dialog.author_edit.setText("Researcher B")
    dialog.email_edit.setText("b@example.test")
    qtbot.mouseClick(
        dialog.rights, Qt.MouseButton.LeftButton, pos=QPoint(10, dialog.rights.height() // 2),
    )
    qtbot.mouseClick(dialog.buttons["submit"], Qt.MouseButton.LeftButton)
    lifecycle.jobs[0].run()
    lifecycle.jobs[1].run()
    assert saves == ["B"]
    assert preparations[0][0] == root
    assert preparations[0][1].title == title.strip()
    assert "awaiting review" in dialog.status.text()
    assert not dialog.buttons["submit"].isEnabled()
    assert_visible_children_within_parent(dialog)
