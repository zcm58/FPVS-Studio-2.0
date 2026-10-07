"""Registered visible-only submission control and geometry coverage."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.gui.library_submission_dialog import LibrarySubmissionDialog


@pytest.mark.parametrize(
    "busy,prepared,attempted",
    [(False, False, False), (True, True, True), (False, True, False), (False, True, True)],
)
def test_submission_states_fit_at_minimum(qtbot, busy, prepared, attempted):
    dialog = LibrarySubmissionDialog()
    qtbot.addWidget(dialog)
    name = "Condition with a realistic very long descriptive name " * 4
    dialog.conditions.addItem(name, "condition")
    dialog.conditions.setItemData(0, name, Qt.ItemDataRole.ToolTipRole)
    dialog.title_edit.setText("Long experiment title " * 7)
    dialog.review.setPlainText("C:/Research/a-long-project-folder/stimuli/" * 8)
    dialog.status.setText(
        "Upload was not confirmed. Refresh my requests before retrying the same prepared bundle. "
        * 2
    )
    dialog.rights.setChecked(True)
    dialog.set_state(busy, prepared, attempted)
    dialog.resize(860, 740)
    dialog.show()
    qtbot.wait(25)
    assert_visible_children_within_parent(dialog)
    assert dialog.conditions.toolTip() == name
    assert dialog.buttons["submit"].isEnabled() == (prepared and not busy)
    for label in dialog.findChildren(QLabel):
        if label.isVisible() and label.text() and not label.wordWrap():
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    dialog.tabs.setCurrentIndex(1)
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
