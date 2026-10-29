"""Opt-in and comparison surface checks; no service or runtime is launched."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QCheckBox, QLabel, QMessageBox, QPushButton, QWidget
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.core.data_sharing import SharingStudyChoice
from fpvs_studio.data_sharing.storage import CaptureArchiveReview, ReviewedCapture
from fpvs_studio.gui.data_sharing_dialog import (
    ComparisonRow,
    DataSharingDialog,
    SavedReportsDialog,
    StartupReportNotice,
)
from fpvs_studio.gui.packaged_smoke import _verification_palette


def _study(number=1):
    return SharingStudyChoice(
        project_id=f"00000000-0000-0000-0000-{number:012d}",
        title=f"Study {number}: " + "A realistic extended cross-laboratory experiment title " * 2,
        experiment_id=f"shared-study-{number}", experiment_version="2026.10.29+reviewed",
        protocol_sha256="a" * 64,
    )


@pytest.fixture
def sharing_palette(qapp, background):
    original = qapp.palette()
    palette = _verification_palette(dark=background == "#202124")
    qapp.setPalette(palette)
    try:
        yield
    finally:
        qapp.setPalette(original)


@pytest.mark.parametrize("size", [(560, 360), (680, 440)])
@pytest.mark.parametrize("background", ["#202124", "#f4f7fb"])
@pytest.mark.parametrize("count", [1, 20])
def test_saved_reports_notice_lists_full_project_paths_without_clipping(
    qtbot, tmp_path, size, background, count,
):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    notices = tuple(StartupReportNotice(
        tmp_path / f"Lab {index}" / ("Long experimental project folder " * 5),
        "The saved report needs review. <Study details> are shown as plain text.",
    ) for index in range(count))
    dialog = SavedReportsDialog(notices, parent=parent)
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.resize(*size)
    dialog.show()
    qtbot.wait(10)

    assert dialog.size().toTuple() == size
    assert_visible_children_within_parent(dialog)
    assert dialog.isModal()
    assert dialog.windowModality() == Qt.WindowModality.ApplicationModal
    assert dialog.projects_edit.isReadOnly()
    text = dialog.projects_edit.toPlainText()
    for notice in notices:
        assert str(notice.project_root) in text
        assert notice.message in text
    assert dialog.projects_edit.accessibleName()
    if count > 1:
        assert dialog.projects_edit.verticalScrollBar().maximum() > 0
    for label in (dialog.header.title_label, dialog.guidance_label):
        required = label.fontMetrics().boundingRect(
            QRect(0, 0, label.contentsRect().width(), 10000),
            Qt.TextFlag.TextWordWrap, label.text(),
        )
        assert label.contentsRect().height() >= required.height() - 2
    assert dialog.dismiss_button.contentsRect().width() >= (
        dialog.dismiss_button.fontMetrics().horizontalAdvance("Dismiss")
    )


@pytest.mark.parametrize("dismissal", ["button", "escape", "close"])
def test_saved_reports_notice_dismissal_preserves_report_notice(qtbot, tmp_path, dismissal):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    notice = StartupReportNotice(tmp_path / "Study", "A saved report needs review.")
    dialog = SavedReportsDialog((notice,), parent=parent)
    qtbot.addWidget(dialog)
    dialog.show()
    if dismissal == "button":
        dialog.dismiss_button.click()
    elif dismissal == "escape":
        qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    else:
        dialog.close()
    assert not dialog.isVisible()
    assert notice == StartupReportNotice(tmp_path / "Study", "A saved report needs review.")


@pytest.mark.parametrize("project_open", [False, True])
def test_controller_shows_dismissible_report_notice_on_visible_window(
    qtbot, controller, tmp_path, project_open,
):
    if project_open:
        host = QWidget()
        qtbot.addWidget(host)
        host.show()
        controller.main_window = host
    else:
        host = controller.welcome_window
    assert host is not None
    notices = (StartupReportNotice(tmp_path / "Affected Study", "Enrollment needs review."),)
    controller._show_startup_sharing_notice(notices)
    dialog = controller._saved_reports_dialog
    assert dialog is not None
    qtbot.addWidget(dialog)
    assert dialog.parentWidget() is host
    assert dialog.isVisible() and dialog.isModal()
    assert "Affected Study" in dialog.projects_edit.toPlainText()
    assert controller.welcome_window.findChild(QLabel, "welcome_sharing_status") is None
    dialog.dismiss_button.click()
    assert controller._saved_reports_dialog is None
    assert not dialog.isVisible()
    controller._show_startup_sharing_notice(())
    assert controller._saved_reports_dialog is None


@pytest.mark.parametrize("size", [(820, 480), (880, 540)])
@pytest.mark.parametrize(
    "state", [
        "empty", "single", "multiple", "discovering", "approval", "ready", "busy", "error",
        "validation", "offline", "full", "conflict",
    ],
)
@pytest.mark.parametrize("background", ["#202124", "#f4f7fb"])
def test_sharing_dialog_fits_long_content_and_all_tabs(qtbot, size, state, sharing_palette):
    dialog = DataSharingDialog(configured=True)
    qtbot.addWidget(dialog)
    profile = (
        "A registered experimental protocol with a long but realistic study title " * 2
        + "\nExperiment: " + "study-" * 12 + "\nVersion: " + "2026.10.05+reviewed-" * 3
        + "\nProtocol SHA-256: " + "a" * 64
    )
    connected = state in {"ready", "busy", "offline", "full"}
    studies = [] if state == "empty" else [_study(), _study(2)] if state in {
        "multiple", "validation",
    } else [_study()]
    dialog.set_studies(studies)
    dialog.set_state(
        connected=connected, enabled=connected, profile=profile,
        status="The service is temporarily unavailable. Reports remain pending; retry when "
        "the connection is available." if state == "error" else
        "Choose a shared study before connecting."
        if state == "validation" else "Waiting for connection. Reports are saved locally; "
        "Studio will retry on its next launch." if state == "offline" else
        "Sharing capture history is full (512/512). "
        "Use Review captures to archive excluded sessions."
        if state == "full" else
        "A pending connection request uses a different study or lab connection."
        if state == "conflict" else
        "This computer is awaiting administrator approval. Select Connect after approval."
        if state == "approval" else "Sharing is enabled." if connected else
        "Choose an available study or refresh studies using this computer's lab access.",
        pending=9999, held=9999, uploaded=9999,
        captures=512 if state == "full" else 32, capture_limit=512, reviewable_captures=31,
    )
    dialog.set_project_url("https://openfpvs.com/projects/01234567-89ab-cdef-0123-456789abcdef")
    full_name = "Repeated condition with a long experimental label and a demanding task " * 3
    rows = [] if state == "empty" else [ComparisonRow(
        full_name, "condition-id-with-protocol-specific-identity",
        "92.0%\n46 hits / 50 targets · 1 session",
        "89.5%\n8,950 hits / 10,000 targets · 200 sessions · 25 enrollments",
    )]
    dialog.set_comparison(
        rows, scope="Local: latest eligible completed session (2026-10-05T15:30:00+00:00).\n"
        "Shared: same experiment/version/protocol; this device's reports are excluded.",
        notice="Not enough compatible reference data.",
        details="Shared accuracy requires at least 10 "
        "session reports from 3 devices per condition. Task accuracy does not measure EEG quality.",
    )
    dialog.set_busy(
        state in {"busy", "discovering"}, "Updating sharing settings and aggregate comparison…"
        if state == "busy" else "Finding available shared studies…"
        if state == "discovering" else "",
    )
    dialog.resize(*size)
    dialog.show()
    assert "Retained uploaded: 9,999" in dialog.counts_label.text()
    assert "cloud contributions remain" in dialog.counts_label.toolTip()
    assert f"Captures: {512 if state == 'full' else 32}/512" in dialog.counts_label.text()
    assert dialog.review_captures_button.isEnabled() == (state not in {"busy", "discovering"})
    assert dialog.profile_label.text() == profile.partition("\n")[0]
    assert dialog.profile_label.toolTip() == profile
    assert dialog.profile_label.isVisible() == connected
    assert dialog.study_combo.isVisible() != connected
    assert dialog.connect_button.isEnabled() == (
        not connected and state not in {"empty", "multiple", "validation", "discovering"}
    )
    assert not dialog.header.subtitle_label.isVisible()
    assert "Protocol SHA-256" not in dialog.profile_label.text()
    for index in range(dialog.tabs.count()):
        dialog.tabs.setCurrentIndex(index)
        qtbot.wait(10)
        assert dialog.size().toTuple() == size
        assert_visible_children_within_parent(dialog)
        for label in dialog.findChildren(QLabel):
            if not label.isVisible() or not label.text():
                continue
            bounds = label.fontMetrics().boundingRect(
                QRect(0, 0, label.contentsRect().width(), 10000),
                Qt.TextFlag.TextWordWrap, label.text(),
            )
            assert label.contentsRect().height() >= bounds.height() - 2
        for control in dialog.findChildren(QPushButton) + dialog.findChildren(QCheckBox):
            if control.isVisible():
                assert control.contentsRect().width() >= (
                    control.fontMetrics().horizontalAdvance(control.text())
                )
    if rows:
        assert full_name in dialog.comparison_table.item(0, 0).toolTip()
        assert "condition-id-with-protocol-specific-identity" in (
            dialog.comparison_table.item(0, 0).toolTip()
        )
        assert dialog.comparison_table.item(0, 2).toolTip().endswith("25 enrollments")


@pytest.mark.parametrize("count", [0, 1, 2])
def test_study_discovery_selects_only_a_unique_match_and_exposes_full_titles(qtbot, count):
    dialog = DataSharingDialog(configured=True)
    qtbot.addWidget(dialog)
    studies = [_study(index + 1) for index in range(count)]
    actions = []
    dialog.action_requested.connect(actions.append)
    dialog.set_studies(studies)
    assert dialog.study_combo.count() == count
    assert not dialog.study_combo.isEditable()
    assert dialog.study_combo.accessibleName() == "Shared study"
    assert dialog.project_id() == (studies[0].project_id if count == 1 else "")
    assert dialog.connect_button.isEnabled() == (count == 1)
    assert not actions  # Discovery and automatic selection do not enroll.
    for index, study in enumerate(studies):
        tooltip = dialog.study_combo.itemData(index, Qt.ItemDataRole.ToolTipRole)
        assert study.title in tooltip and study.experiment_version in tooltip
        assert study.experiment_id in tooltip and study.project_id in tooltip
    if count:
        dialog.study_combo.setCurrentIndex(count - 1)
        assert dialog.project_id() == studies[-1].project_id
        assert studies[-1].title in dialog.study_combo.toolTip()
        assert studies[-1].title in dialog.study_title()
        assert dialog.connect_button.isEnabled()
        assert not actions
    else:
        assert dialog.study_combo.placeholderText() == "No matching studies available"


def test_study_refresh_preserves_explicit_choice_and_clears_a_removed_ambiguous_choice(qtbot):
    dialog = DataSharingDialog(configured=True)
    qtbot.addWidget(dialog)
    first, second, third = _study(), _study(2), _study(3)
    dialog.set_studies([first, second])
    dialog.study_combo.setCurrentIndex(1)
    dialog.set_studies([second, first])
    assert dialog.project_id() == second.project_id
    assert second.title in dialog.study_combo.toolTip()
    dialog.set_studies([first, third])
    assert dialog.project_id() == ""
    assert dialog.study_combo.toolTip() == ""
    assert not dialog.connect_button.isEnabled()
    dialog.set_studies([third])
    assert dialog.project_id() == third.project_id
    assert dialog.connect_button.isEnabled()


def test_connection_and_checkbox_require_explicit_operator_actions(qtbot):
    dialog = DataSharingDialog(configured=True)
    qtbot.addWidget(dialog)
    actions, enabled = [], []
    dialog.action_requested.connect(actions.append)
    dialog.enabled_requested.connect(enabled.append)
    assert not dialog.enabled_checkbox.isChecked()
    assert not dialog.enabled_checkbox.isEnabled()
    assert not dialog.connect_button.isEnabled()
    assert not dialog.archive_button.isEnabled()
    dialog.refresh_studies_button.click()
    dialog.lab_access_button.click()
    assert actions == ["discover", "lab_access"]
    dialog.set_studies([_study()])
    dialog.connect_button.click()
    assert actions == ["discover", "lab_access", "connect"]
    dialog.set_state(connected=True, enabled=False, profile="Study v1", status="Connected.")
    assert enabled == []
    assert not dialog.enabled_checkbox.isChecked()
    assert dialog.enabled_checkbox.isEnabled()
    assert not dialog.retry_button.isEnabled()
    dialog.enabled_checkbox.click()
    assert enabled == [True]
    dialog.set_state(connected=True, enabled=True, profile="Study v1", status="Enabled.")
    dialog.retry_button.click()
    dialog.disconnect_button.click()
    assert actions[-2:] == ["retry", "disconnect"]
    dialog.set_state(
        connected=True, enabled=True, profile="Study v1", status="Uploaded.", uploaded=12,
    )
    assert dialog.archive_button.isEnabled()
    assert "Research records and shared results remain" in dialog.archive_button.toolTip()
    dialog.archive_button.click()
    assert actions[-1] == "archive"


def test_busy_unconfigured_and_cancel_states(qtbot):
    dialog = DataSharingDialog(configured=False)
    qtbot.addWidget(dialog)
    assert "not configured" in dialog.status_label.text()
    dialog.set_studies([_study()])
    assert not dialog.connect_button.isEnabled()
    assert not dialog.refresh_studies_button.isEnabled()
    assert dialog.lab_access_button.isEnabled()
    dialog.set_state(connected=True, enabled=True, profile="Study v1", status="Offline.",
                     reviewable_captures=1)
    assert dialog.enabled_checkbox.isEnabled()  # Off remains available without a service.
    assert dialog.disconnect_button.isEnabled()
    dialog.show()
    dialog.set_busy(True, "Canceling the previous operation…")
    assert dialog.cancel_button.isVisible()
    for button in (
        dialog.connect_button, dialog.disconnect_button, dialog.retry_button, dialog.archive_button,
        dialog.review_captures_button, dialog.refresh_studies_button, dialog.lab_access_button,
    ):
        assert not button.isEnabled()
    assert dialog.enabled_checkbox.isEnabled()  # Opt-out is available while a transfer is busy.
    actions = []
    dialog.action_requested.connect(actions.append)
    dialog.cancel_button.click()
    assert actions == ["cancel"]
    dialog.set_busy(False, "Refresh studies after reconnecting Lab access.")
    assert not dialog.cancel_button.isVisible()
    assert "Lab access" in dialog.status_label.text()
    assert "No original participant numbers" in dialog.enabled_checkbox.toolTip()
    assert "age, sex, handedness, colorblind status" in dialog.enabled_checkbox.toolTip()
    assert "reviewed removed electrodes" in dialog.enabled_checkbox.toolTip()
    assert "saved an opt-out" in dialog.connect_button.toolTip()
    assert "received reports with the owner" in dialog.disconnect_button.toolTip()
    assert "does not measure EEG quality" in dialog.comparison_table.toolTip()
    assert not dialog.comparison_notice.isVisible()


@pytest.mark.parametrize("answer", [QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes])
def test_excluded_capture_archive_confirmation_is_explicit_and_defaults_to_no(
    qtbot, tmp_path, monkeypatch, answer,
):
    dialog = DataSharingDialog(configured=False)
    qtbot.addWidget(dialog)
    review = CaptureArchiveReview(tmp_path, (
        ReviewedCapture("first", "a" * 64, "incomplete_session"),
        ReviewedCapture("second", "b" * 64, "protocol_mismatch"),
    ))
    questions = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: questions.append(args) or answer)
    assert dialog.confirm_capture_archive(review) is (answer == QMessageBox.StandardButton.Yes)
    question = questions[0]
    assert question[1] == "Archive excluded captures?"
    assert "Archive 2 excluded capture(s)" in question[2]
    assert "Incomplete session: 1" in question[2] and "Protocol mismatch: 1" in question[2]
    assert "captures needing recovery stay unchanged" in question[2]
    assert question[-1] == QMessageBox.StandardButton.No
    dialog.set_state(connected=False, enabled=False, profile="", status="Sharing is off.",
                     captures=2, reviewable_captures=2)
    actions = []
    dialog.action_requested.connect(actions.append)
    assert dialog.review_captures_button.isEnabled()  # Local review works offline and while off.
    dialog.review_captures_button.click()
    assert actions == ["review"]
    dialog.set_state(connected=False, enabled=False, profile="", status="Archived.")
    assert not dialog.review_captures_button.isEnabled()


def test_project_setup_and_website_actions_are_explicit(qtbot):
    dialog = DataSharingDialog(configured=True)
    qtbot.addWidget(dialog)
    actions = []
    dialog.action_requested.connect(actions.append)
    assert not dialog.website_button.isEnabled()
    dialog.set_studies([_study()])
    assert dialog.project_id() == _study().project_id
    dialog.protocol_button.click()
    assert actions == ["protocol"]
    dialog.set_state(
        connected=True, enabled=False, profile="Private lab project", status="Connected.",
    )
    dialog.set_project_url("https://openfpvs.com/projects/01234567-89ab-cdef-0123-456789abcdef")
    assert not dialog.study_combo.isEnabled()
    assert not dialog.enabled_checkbox.isChecked()
    dialog.website_button.click()
    assert actions == ["protocol", "website"]
    dialog.set_busy(True)
    assert not dialog.website_button.isEnabled()
    assert not dialog.protocol_button.isEnabled()


@pytest.mark.parametrize("answer", [QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No])
def test_pending_connection_reset_is_explicit_and_identifies_selected_study(
    qtbot, monkeypatch, answer,
):
    dialog = DataSharingDialog(configured=True)
    qtbot.addWidget(dialog)
    dialog.set_studies([_study().model_copy(update={
        "title": "<b>Literal study title</b> & review",
    })])
    study_title = dialog.study_title()
    questions = []
    monkeypatch.setattr(QMessageBox, "exec", lambda prompt: questions.append(prompt) or int(answer))
    assert dialog.confirm_pending_connection_reset(study_title) is (
        answer == QMessageBox.StandardButton.Yes
    )
    question = questions[0]
    assert question.windowTitle() == "Replace pending connection?"
    assert question.textFormat() == Qt.TextFormat.PlainText
    assert study_title in question.text()
    assert dialog.project_id() not in question.text()
    assert "previous request remains in OpenFPVS" in question.text()
    assert "Saved sharing preferences and reports stay unchanged" in question.text()
    assert question.standardButton(question.defaultButton()) == QMessageBox.StandardButton.No


def test_available_comparison_keeps_details_in_tooltips(qtbot):
    dialog = DataSharingDialog(configured=True)
    qtbot.addWidget(dialog)
    scope = (
        "Local: latest eligible completed session (2026-10-08T15:30:00+00:00).\n"
        "Shared: same experiment/version/protocol; this enrollment's reports are excluded."
    )
    details = (
        "Shared accuracy requires 10 session reports from 3 devices per condition. "
        "Task performance does not measure EEG quality."
    )
    dialog.set_comparison(
        [ComparisonRow("Condition", "condition-1", "92.0%", "89.5%")],
        scope=scope, notice="", details=details,
    )
    dialog.tabs.setCurrentIndex(1)
    dialog.show()
    qtbot.wait(10)
    assert not dialog.comparison_notice.isVisible()
    assert scope in dialog.comparison_table.toolTip()
    assert details in dialog.comparison_table.horizontalHeaderItem(2).toolTip()
    assert dialog.comparison_table.item(0, 2).text() == "89.5%"
    assert not any(
        "does not measure EEG quality" in label.text()
        for label in dialog.findChildren(QLabel) if label.isVisible()
    )
    dialog.set_comparison(
        [], scope=scope, notice="The reference protocol changed.", details=details,
    )
    assert dialog.comparison_notice.isVisible()
    assert dialog.comparison_notice.text() == "The reference protocol changed."
