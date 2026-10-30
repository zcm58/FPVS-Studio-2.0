"""Read-only Results readiness before replacing a project's authored protocol."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event

from fpvs_studio.data_sharing.errors import DataSharingCancelled, DataSharingError
from fpvs_studio.data_sharing.storage import SharingStorageError, list_records, load_settings

_REPORTS_MESSAGE = (
    "Send or resolve saved Results reports in Data Sharing & Comparison before updating "
    "this project. Download separately to keep the current version and its queued reports."
)
_CAPTURES_MESSAGE = (
    "Unfinished Results captures need attention before updating this project. "
    "Open Data Sharing & Comparison, or download separately to keep the current version."
)


@dataclass(frozen=True)
class ProjectUpdateReporting:
    """A saved Results connection stays bound to its original registered version."""

    reconnect_required: bool


def _check_cancel(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise DataSharingCancelled()


def inspect_project_update_reporting(
    root: Path, *, cancel_event: Event | None = None,
) -> ProjectUpdateReporting:
    """Reject unresolved reporting without sending, relabeling or changing any state.

    Call on a worker before transfer and again immediately before the update commit.
    Every active scope is inspected, including held reports after opting out and
    reports belonging to an earlier connection. Accepted receipts and terminal
    excluded captures remain preserved but do not prevent a new local protocol.
    """
    _check_cancel(cancel_event)
    try:
        settings = load_settings(root)
        _check_cancel(cancel_event)
        records = list_records(root)
        _check_cancel(cancel_event)
        for record in records:
            _check_cancel(cancel_event)
            if record.state != "uploaded":
                raise DataSharingError(_REPORTS_MESSAGE, code="pending_results")
        # Runtime owns capture evidence. Match the narrow lazy reader used by
        # service.load_view; neither transport nor secure-store access is needed.
        from fpvs_studio.runtime.data_sharing import read_capture_intents

        intents = read_capture_intents(root)
        _check_cancel(cancel_event)
        for intent in intents:
            _check_cancel(cancel_event)
            if intent.state in {"running", "eligible"}:
                raise DataSharingError(_CAPTURES_MESSAGE, code="pending_results")
    except (SharingStorageError, OSError) as error:
        raise DataSharingError(
            "Saved Results reporting data needs review before updating this project. "
            "Open Data Sharing & Comparison, or download separately. " + str(error),
            code="pending_results",
        ) from error
    return ProjectUpdateReporting(reconnect_required=settings.profile is not None)
