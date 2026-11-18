"""Exercise the protected authoring workflow through real native Qt dialogs."""

import json

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QLineEdit, QMessageBox, QPushButton
from tests.gui.helpers import open_created_project

from fpvs_studio.core.study_versions import current_version, list_versions
from fpvs_studio.gui.study_versions import ProtocolReviewCancelled

_MESSAGE_BOX_EXEC = QMessageBox.exec


@pytest.mark.parametrize("decision", ["cancel", "confirm"])
def test_partial_visit_requires_two_decisions(qtbot, controller, tmp_path, monkeypatch, decision):
    monkeypatch.setattr(QMessageBox, "exec", _MESSAGE_BOX_EXEC)
    document, window = open_created_project(controller, qtbot, tmp_path, "Version review")
    root = document.project_root
    before = current_version(root)
    original_count = len(list_versions(root))
    evidence = root / "logs/.participant-results"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "partial.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "participant_number": "synthetic",
                "session_id": "visit",
                "protocol_version_id": before.version_id,
                "runs": [{"run_id": "r", "completed_frames": 1}],
            }
        )
    )
    project = document.project.model_copy(deep=True)
    project.settings.protocol.base_hz = 8
    seen = []
    timer = QTimer(window)

    def choose():
        dialog = QApplication.activeModalWidget()
        if (
            isinstance(dialog, QMessageBox)
            and dialog.windowTitle() == "Review changes to this study"
        ):
            seen.append(("first", dialog.detailedText()))
            next(b for b in dialog.buttons() if "continue in this study" in b.text()).click()
        elif (
            isinstance(dialog, QDialog)
            and dialog.windowTitle() == "Confirm the risk to earlier data"
        ):
            apply = next(
                b for b in dialog.findChildren(QPushButton) if b.text() == "Apply to future visits"
            )
            enabled_before = apply.isEnabled()
            dialog.findChild(QCheckBox).setChecked(True)
            enabled_without_reason = apply.isEnabled()
            dialog.findChild(QLineEdit).setText("Separate the two acquisition periods")
            seen.append(("second", (enabled_before, enabled_without_reason, apply.isEnabled())))
            if decision == "confirm":
                apply.click()
            else:
                dialog.reject()

    timer.timeout.connect(choose)
    timer.start(20)
    try:
        if decision == "cancel":
            with pytest.raises(ProtocolReviewCancelled):
                window._study_versions.save(project)
            assert current_version(root) == before
        else:
            window._study_versions.save(project)
            assert current_version(root).reason == "Separate the two acquisition periods"
            assert len(list_versions(root)) == original_count + 1
    finally:
        timer.stop()
    assert [step for step, _ in seen] == ["first", "second"]
    assert "6.0 Hz" in seen[0][1] and "8.0 Hz" in seen[0][1]
    assert seen[1][1] == (False, False, True)
