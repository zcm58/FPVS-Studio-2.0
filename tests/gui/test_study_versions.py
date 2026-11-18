"""Exercise the protected authoring workflow through real native Qt dialogs."""

import json

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QLineEdit, QMessageBox, QPushButton
from tests.gui.helpers import open_created_project

from fpvs_studio.core.study_lifecycle import get_study
from fpvs_studio.core.study_versions import current_version, list_versions
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.study_versions import ProtocolReviewCancelled

_MESSAGE_BOX_EXEC = QMessageBox.exec


def test_only_final_setup_save_captures_stimuli(qtbot, controller, tmp_path, monkeypatch):
    from fpvs_studio.core import study_versions

    capture = study_versions._assets
    calls = []

    def count_capture(*args, **kwargs):
        calls.append("capture")
        return capture(*args, **kwargs)

    monkeypatch.setattr(study_versions, "_assets", count_capture)
    document, window = open_created_project(controller, qtbot, tmp_path, "Manual versions")
    root = document.project_root
    window.show_setup_wizard()
    document.update_protocol_settings(base_hz=8)
    document.save()
    assert not list_versions(root) and not calls

    wizard = window.setup_wizard_page
    wizard.review_save_button.click()
    first, = list_versions(root)
    protocol = study_versions.read_version_protocol(root, first.version_id)
    assert protocol["settings"]["protocol"]["base_hz"] == 8
    assert calls == ["capture"]

    choices = []

    def choose(keep):
        choices.append(keep)
        return keep

    monkeypatch.setattr(window._study_versions, "_choose_checkpoint", lambda: choose(False))
    document.update_protocol_settings(base_hz=10)
    document.save()  # Ctrl+S can persist a draft before the final Setup save.
    document.save(completed_setup=True)
    assert choices == [False] and list_versions(root) == [first]
    assert calls == ["capture"]
    reopened = ProjectDocument.open_existing(root)
    assert reopened.project.settings.protocol.base_hz == 10
    document.save(completed_setup=True)
    document.update_manual_removed_electrodes("1", ["Fz"])
    document.save(completed_setup=True)
    assert choices == [False] and calls == ["capture"]

    monkeypatch.setattr(window._study_versions, "_choose_checkpoint", lambda: choose(True))
    document.update_protocol_settings(base_hz=12)
    document.save(completed_setup=True)
    assert choices == [False, True] and len(list_versions(root)) == 2
    assert calls == ["capture", "capture"]


def test_cancel_or_save_changes_only_in_native_prompt(qtbot, controller, tmp_path, monkeypatch):
    document, window = open_created_project(controller, qtbot, tmp_path, "Working setup")
    document.save(completed_setup=True)
    document.update_protocol_settings(base_hz=8)
    choices = iter(["Cancel", "Save changes only"])
    defaults = []

    def choose(dialog):
        assert dialog.windowTitle() == "Save a project version?"
        defaults.append(dialog.defaultButton().text())
        wanted = next(choices)
        button = next(b for b in dialog.buttons() if b.text().replace("&", "") == wanted)
        QTimer.singleShot(0, button.click)
        return _MESSAGE_BOX_EXEC(dialog)

    monkeypatch.setattr(QMessageBox, "exec", choose)
    with pytest.raises(ProtocolReviewCancelled):
        document.save(completed_setup=True)
    previous = ProjectDocument.open_existing(document.project_root)
    assert previous.project.settings.protocol.base_hz == 6
    document.save(completed_setup=True)
    loaded = ProjectDocument.open_existing(document.project_root)
    assert loaded.project.settings.protocol.base_hz == 8
    assert len(list_versions(document.project_root)) == 1
    assert defaults == ["Save changes only", "Save changes only"]


def test_save_as_new_switches_only_after_copy(qtbot, controller, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QMessageBox, "exec", _MESSAGE_BOX_EXEC)
    document, window = open_created_project(controller, qtbot, tmp_path, "Original study")
    root = document.project_root
    document.save(completed_setup=True)
    before = current_version(root)
    data = root / "logs/.participant-results"
    data.mkdir()
    (data / "partial.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "participant_number": "synthetic",
                "session_id": "visit",
                "protocol_version_id": before.version_id,
                "runs": [{"completed_frames": 2}],
            }
        )
    )
    document.update_protocol_settings(base_hz=8)
    timer = QTimer(window)

    def fork():
        dialog = QApplication.activeModalWidget()
        if (
            isinstance(dialog, QMessageBox)
            and dialog.windowTitle() == "Review changes to this study"
        ):
            next(b for b in dialog.buttons() if b.text().startswith("Save as new")).click()
        elif isinstance(dialog, QInputDialog) and dialog.windowTitle() == "Save as new study":
            dialog.setTextValue("New independent cohort")
            dialog.accept()

    timer.timeout.connect(fork)
    timer.start(20)
    try:
        with pytest.raises(ProtocolReviewCancelled):
            document.save(completed_setup=True)
    finally:
        timer.stop()
    qtbot.waitUntil(lambda: controller.main_window.document.project_root != root)
    copied = controller.main_window.document
    qtbot.addWidget(controller.main_window)
    assert copied.project.settings.protocol.base_hz == 8
    assert get_study(copied.project_root).study_id != get_study(root).study_id
    assert current_version(root) == before
    assert not (copied.project_root / "logs/.participant-results/partial.json").exists()


@pytest.mark.parametrize("decision", ["cancel", "confirm", "changes only"])
def test_partial_visit_requires_two_decisions(qtbot, controller, tmp_path, monkeypatch, decision):
    monkeypatch.setattr(QMessageBox, "exec", _MESSAGE_BOX_EXEC)
    document, window = open_created_project(controller, qtbot, tmp_path, "Version review")
    root = document.project_root
    document.save(completed_setup=True)
    monkeypatch.setattr(window._study_versions, "_choose_checkpoint", lambda: decision == "confirm")
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
    document.update_protocol_settings(base_hz=8)
    seen = []
    timer = QTimer(window)

    def choose():
        dialog = QApplication.activeModalWidget()
        if (
            isinstance(dialog, QMessageBox)
            and dialog.windowTitle() == "Review changes to this study"
        ):
            seen.append(("first", dialog.informativeText()))
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
            if decision == "cancel":
                dialog.reject()
            else:
                apply.click()

    timer.timeout.connect(choose)
    timer.start(20)
    try:
        if decision == "cancel":
            with pytest.raises(ProtocolReviewCancelled):
                document.save(completed_setup=True)
            assert current_version(root) == before
        else:
            document.save(completed_setup=True)
            assert current_version(root).reason == "Separate the two acquisition periods"
            assert current_version(root).version_id != before.version_id
            assert len(list_versions(root)) == original_count + (decision == "confirm")
    finally:
        timer.stop()
    assert [step for step, _ in seen] == ["first", "second"]
    assert "6.0 Hz" in seen[0][1] and "8.0 Hz" in seen[0][1]
    assert seen[1][1] == (False, False, True)
