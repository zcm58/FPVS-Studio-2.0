"""Opt-in and comparison surface checks; no service or runtime is launched."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QLabel, QLineEdit
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.gui.data_sharing_dialog import ComparisonRow, DataSharingDialog


@pytest.mark.parametrize("size", [(820, 620), (880, 700)])
@pytest.mark.parametrize("state", ["empty", "ready", "busy", "error", "validation", "offline"])
def test_sharing_dialog_fits_long_content_and_all_tabs(qtbot, size, state):
    dialog = DataSharingDialog(configured=True)
    qtbot.addWidget(dialog)
    profile = (
        "A registered experimental protocol with a long but realistic study title " * 2
        + "\nExperiment: " + "study-" * 12 + "\nVersion: " + "2026.10.05+reviewed-" * 3
        + "\nProtocol SHA-256: " + "a" * 64
    )
    dialog.set_state(
        connected=state not in {"empty", "validation"},
        enabled=state not in {"empty", "validation"}, profile=profile,
        status="The service is temporarily unavailable. Reports remain pending; retry when "
        "the connection is available." if state == "error" else
        "Enter the lab-issued invitation code for the reviewed experiment version."
        if state == "validation" else "Waiting for connection. Reports are saved locally; "
        "Studio will retry on its next launch." if state == "offline" else "Sharing is enabled.",
        pending=9999, held=9999, uploaded=9999,
    )
    dialog.project_id_edit.setText("01234567-89ab-cdef-0123-456789abcdef")
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
        notice="Not enough compatible reference data. Shared accuracy requires at least 10 "
        "session reports from 3 devices per condition. Task accuracy does not measure EEG quality.",
    )
    dialog.set_busy(
        state == "busy", "Updating sharing settings and aggregate comparison…"
        if state == "busy" else "",
    )
    dialog.resize(*size)
    dialog.show()
    assert "Retained uploaded: 9,999" in dialog.counts_label.text()
    assert "cloud contributions remain" in dialog.counts_label.toolTip()
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
    if rows:
        assert full_name in dialog.comparison_table.item(0, 0).toolTip()
        assert "condition-id-with-protocol-specific-identity" in (
            dialog.comparison_table.item(0, 0).toolTip()
        )
        assert dialog.comparison_table.item(0, 2).toolTip().endswith("25 enrollments")


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
    assert dialog.invitation_edit.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.invitation_edit.maxLength() == 128
    dialog.invitation_edit.setText("  lab-issued-private-code  ")
    assert dialog.invitation_code() == "lab-issued-private-code"
    dialog.connect_button.click()
    assert actions == ["connect"]
    dialog.set_state(connected=True, enabled=False, profile="Study v1", status="Connected.")
    assert enabled == []
    assert not dialog.enabled_checkbox.isChecked()
    assert dialog.enabled_checkbox.isEnabled()
    assert not dialog.retry_button.isEnabled()
    dialog.enabled_checkbox.click()
    assert enabled == [True]
    dialog.clear_invitation()
    assert dialog.invitation_code() == ""
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
    dialog.invitation_edit.setText("private-code")
    assert not dialog.connect_button.isEnabled()
    dialog.set_state(connected=True, enabled=True, profile="Study v1", status="Offline.")
    assert dialog.enabled_checkbox.isEnabled()  # Off remains available without a service.
    assert dialog.disconnect_button.isEnabled()
    dialog.show()
    dialog.set_busy(True, "Canceling the previous operation…")
    assert dialog.cancel_button.isVisible()
    for button in (
        dialog.connect_button, dialog.disconnect_button, dialog.retry_button, dialog.archive_button,
    ):
        assert not button.isEnabled()
    assert dialog.enabled_checkbox.isEnabled()  # Opt-out is available while a transfer is busy.
    actions = []
    dialog.action_requested.connect(actions.append)
    dialog.cancel_button.click()
    assert actions == ["cancel"]
    dialog.set_busy(False, "Enter the lab-issued invitation code.")
    assert not dialog.cancel_button.isVisible()
    assert "invitation code" in dialog.status_label.text()
    assert "No participant IDs" in dialog.consent_label.text()
    assert "does not measure EEG quality" in dialog.comparison_notice.text()


def test_project_setup_and_website_actions_are_explicit(qtbot):
    dialog = DataSharingDialog(configured=True)
    qtbot.addWidget(dialog)
    actions = []
    dialog.action_requested.connect(actions.append)
    assert not dialog.website_button.isEnabled()
    dialog.project_id_edit.setText("01234567-89ab-cdef-0123-456789abcdef")
    assert dialog.project_id() == "01234567-89ab-cdef-0123-456789abcdef"
    dialog.protocol_button.click()
    assert actions == ["protocol"]
    dialog.set_state(
        connected=True, enabled=False, profile="Private lab project", status="Connected.",
    )
    dialog.set_project_url("https://openfpvs.com/projects/01234567-89ab-cdef-0123-456789abcdef")
    assert not dialog.project_id_edit.isEnabled()
    assert not dialog.enabled_checkbox.isChecked()
    dialog.website_button.click()
    assert actions == ["protocol", "website"]
    dialog.set_busy(True)
    assert not dialog.website_button.isEnabled()
    assert not dialog.protocol_button.isEnabled()
