"""Background contribution jobs and read-only local/global comparison views."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event

from fpvs_studio.core.data_sharing import (
    FixationOccurrence,
    SessionReport,
    SharingProfile,
    SharingSettings,
    protocol_fingerprint,
)
from fpvs_studio.core.paths import filesystem_path, project_json_path
from fpvs_studio.core.serialization import load_project_file
from fpvs_studio.data_sharing.client import DataSharingClient, check_cancel
from fpvs_studio.data_sharing.errors import DataSharingCancelled, DataSharingError
from fpvs_studio.data_sharing.library_scope import validate_library_scope
from fpvs_studio.data_sharing.storage import (
    OutboxRecord,
    SharingStorageError,
    archive_uploaded,
    list_pending,
    list_records,
    load_settings,
    read_payload,
    save_settings,
    update_record,
)


@dataclass(frozen=True)
class ConditionAggregate:
    condition_id: str
    label: str
    fixation_targets: int | None
    fixation_hits: int | None
    session_count: int
    mean_rt_ms: float | None
    accuracy_percent: float | None
    device_count: int = 0
    eligible: bool = True
    scoring_source: str | None = None
    response_window_ms: float | None = None


@dataclass(frozen=True)
class ComparisonView:
    status: str
    experiment_id: str
    experiment_version: str
    protocol_sha256: str
    conditions: tuple[ConditionAggregate, ...]
    minimum_sessions: int
    minimum_devices: int
    message: str


@dataclass(frozen=True)
class SharingView:
    settings: SharingSettings
    local_conditions: tuple[ConditionAggregate, ...] = ()
    latest_completed_at: str | None = None
    status: str = "off"
    error: str = ""
    pending_count: int = 0
    held_count: int = 0
    uploaded_count: int = 0
    remote: ComparisonView | None = None


def configured() -> bool:
    return DataSharingClient.configured().enabled


def _same_scope(record: OutboxRecord, profile: SharingProfile) -> bool:
    return (
        record.experiment_id == profile.experiment_id
        and record.experiment_version == profile.experiment_version
        and record.protocol_sha256 == profile.protocol_sha256
        and record.project_id == profile.project_id
    )


def _local_rows(report: SessionReport) -> tuple[ConditionAggregate, ...]:
    groups: dict[str, list[FixationOccurrence]] = defaultdict(list)
    for occurrence in report.occurrences:
        groups[occurrence.condition_id].append(occurrence)
    rows = []
    for condition_id, occurrences in sorted(groups.items()):
        targets = sum(item.total_targets for item in occurrences)
        hits = sum(item.hit_count for item in occurrences)
        rt_count = sum(item.rt_count for item in occurrences)
        methods = {(item.scoring_source, item.response_window_ms) for item in occurrences}
        rt = (
            sum((item.mean_rt_ms or 0) * item.rt_count for item in occurrences) / rt_count
            if rt_count and len(methods) == 1
            else None
        )
        rows.append(
            ConditionAggregate(
                condition_id=condition_id,
                label=condition_id,
                fixation_targets=targets,
                fixation_hits=hits,
                session_count=1,
                mean_rt_ms=rt,
                accuracy_percent=100 * hits / targets if targets else None,
                device_count=1,
                eligible=bool(targets) and len(methods) == 1,
                scoring_source=next(iter(methods))[0] if len(methods) == 1 else None,
                response_window_ms=next(iter(methods))[1] if len(methods) == 1 else None,
            )
        )
    return tuple(rows)


def load_view(
    root: Path,
    protocol_sha256: str,
    cancel: Event,
    *,
    client: DataSharingClient | None = None,
) -> SharingView:
    """Read only; opening the dialog never enrolls, uploads, or edits research files."""
    check_cancel(cancel)
    settings = load_settings(root)
    records = list_records(root)
    scoped = (
        tuple(record for record in records if _same_scope(record, settings.profile))
        if settings.profile is not None
        else ()
    )
    reports = [SessionReport.model_validate_json(record.payload_json) for record in scoped]
    latest = max(reports, key=lambda report: report.completed_at) if reports else None
    status = "pending" if settings.enabled else "off"
    error = ""
    if settings.profile is not None:
        try:
            validate_library_scope(root, settings.profile)
        except DataSharingError as scope_error:
            status = "protocol_mismatch"
            error = str(scope_error)
            latest = None
    if settings.profile is not None and settings.profile.protocol_sha256 != protocol_sha256:
        status = "protocol_mismatch"
        error = "This experiment has changed. Its current protocol needs a new registered version."
        latest = None
    if any(record.state == "failed" for record in scoped):
        status = "failed" if status != "protocol_mismatch" else status
        error = (
            error or (
                "The OpenFPVS project or lab has reached its reporting budget. "
                "Ask its administrator to review capacity, then Retry pending."
                if any(record.state == "failed" and record.last_error_code == "storage_limit"
                       for record in scoped)
                else "A contribution needs attention. Reconnect if access was revoked, then Retry."
            )
        )
    counts = {
        state: sum(record.state == state for record in scoped)
        for state in ("pending", "held", "uploaded")
    }
    if settings.enabled and counts["pending"] and not error and status != "protocol_mismatch":
        if any(
            record.state == "pending" and record.last_error_code in {"network", "timeout"}
            for record in scoped
        ):
            status = "waiting_connection"
    if settings.enabled and not counts["pending"] and not error:
        status = "uploaded" if counts["uploaded"] else "ready"
    from fpvs_studio.runtime.data_sharing import capture_errors

    capture_issues = capture_errors(root)
    if capture_issues:
        status = "failed" if status != "protocol_mismatch" else status
        error = error or f"{len(capture_issues)} local capture(s) need review: {capture_issues[0]}"
    return SharingView(
        settings=settings,
        local_conditions=_local_rows(latest) if latest else (),
        latest_completed_at=latest.completed_at.isoformat() if latest else None,
        status=status,
        error=error,
        pending_count=counts["pending"],
        held_count=counts["held"],
        uploaded_count=counts["uploaded"],
    )


def enroll_project(
    root: Path,
    code: str,
    protocol_sha256: str,
    cancel: Event,
    *,
    client: DataSharingClient | None = None,
    project_id: str | None = None,
) -> SharingView:
    transport = client or DataSharingClient.configured()
    previous = load_settings(root)
    if previous.profile is not None:
        raise DataSharingError(
            "Disconnect the current enrollment before reconnecting.", code="enrollment"
        )
    profile = transport.enroll(root, code, protocol_sha256, cancel, project_id=project_id)
    # Completing enrollment, including a late cancellation, never grants opt-in.
    save_settings(root, SharingSettings(profile=profile, enabled=False))
    return load_view(root, protocol_sha256, Event(), client=transport)


def set_sharing_enabled(
    root: Path,
    enabled: bool,
    protocol_sha256: str,
    cancel: Event,
    *,
    client: DataSharingClient | None = None,
) -> SharingView:
    check_cancel(cancel)
    settings = load_settings(root)
    if enabled and (
        settings.profile is None or settings.profile.protocol_sha256 != protocol_sha256
    ):
        raise DataSharingError(
            "Connect the matching experiment version before opting in.", code="protocol"
        )
    if enabled and settings.profile is not None:
        validate_library_scope(root, settings.profile)
    save_settings(root, settings.model_copy(update={"enabled": enabled}))
    return load_view(root, protocol_sha256, Event(), client=client)


def _may_send(root: Path, profile: SharingProfile, protocol_sha256: str, cancel: Event) -> bool:
    if cancel.is_set():
        return False
    current = load_settings(root)
    allowed = bool(
        current.enabled
        and current.profile == profile
        and profile.protocol_sha256 == protocol_sha256
    )
    if allowed:
        validate_library_scope(root, profile)
    return allowed


def sync_startup_project(
    root: Path, cancel: Event, *, client: DataSharingClient | None = None,
) -> SharingView | None:
    """Recover one known project without opening widgets or requesting comparisons."""
    check_cancel(cancel)
    if not filesystem_path(project_json_path(root)).is_file():
        return None
    settings = load_settings(root)
    profile = settings.profile
    protocol = profile.protocol_sha256 if profile is not None else ""
    try:
        archive_uploaded(root, cancel=cancel)
    except SharingStorageError as error:
        return replace(load_view(root, protocol, cancel),
                       error=f"Local uploaded-history cleanup needs attention: {error}")
    view = load_view(root, protocol, cancel)
    if not settings.enabled or profile is None or view.status == "protocol_mismatch":
        return view
    from fpvs_studio.runtime.data_sharing import capture_errors

    if not view.pending_count and not capture_errors(root):
        return view
    project = load_project_file(project_json_path(root))
    protocol = protocol_fingerprint(project, root, cancelled=cancel.is_set)
    return sync_project(root, protocol, cancel, client=client,
                        fetch_comparison=False, retry_offline=True)


def sync_project(
    root: Path,
    protocol_sha256: str,
    cancel: Event,
    *,
    release_held: bool = False,
    fetch_comparison: bool = True,
    retry_offline: bool = False,
    client: DataSharingClient | None = None,
) -> SharingView:
    """Retry exact persisted bytes; outcomes cannot alter experiment completion."""
    from fpvs_studio.data_sharing.storage import release_held as release_held_records

    transport = client or DataSharingClient.configured()
    cleanup_error = ""
    try:
        archive_uploaded(root, cancel=cancel)
    except SharingStorageError as error:
        cleanup_error = f"Local uploaded-history cleanup needs attention: {error}"
    view = load_view(root, protocol_sha256, cancel, client=transport)
    if cleanup_error:
        return replace(view, error=cleanup_error)
    profile = view.settings.profile
    if (
        not view.settings.enabled or profile is None
        or view.status == "protocol_mismatch" or profile.protocol_sha256 != protocol_sha256
    ):
        return view
    if not transport.enabled:
        return replace(view, status="unavailable", error="The results service is not configured.")
    from fpvs_studio.runtime.data_sharing import recover_captures

    recover_captures(root)
    if release_held:
        release_held_records(root)
    now = datetime.now(timezone.utc)
    failure = ""
    for record in list_pending(root):
        check_cancel(cancel)
        if not _same_scope(record, profile) or not _may_send(
            root, profile, protocol_sha256, cancel
        ):
            continue
        if (
            record.next_attempt_at is not None and record.next_attempt_at > now
            and not release_held
            and not (retry_offline and record.last_error_code in {"network", "timeout"})
        ):
            continue
        attempted = record.model_copy(update={"attempt_count": record.attempt_count + 1})
        update_record(root, attempted)
        try:
            receipt = transport.submit(
                root,
                profile,
                read_payload(root, record.report_id),
                cancel,
                before_send=lambda: _may_send(root, profile, protocol_sha256, cancel),
            )
            update_record(
                root,
                attempted.model_copy(
                    update={
                        "state": "uploaded",
                        "receipt": receipt,
                        "last_error_code": None,
                        "next_attempt_at": None,
                    }
                ),
            )
        except DataSharingCancelled:
            # A later send reuses this identity; receipt loss cannot create a duplicate.
            raise
        except DataSharingError as error:
            delay = min(3600, 30 * 2 ** min(attempted.attempt_count - 1, 7))
            update_record(
                root,
                attempted.model_copy(
                    update={
                        "state": "pending" if error.retryable else "failed",
                        "last_error_code": error.code,
                        "next_attempt_at": now + timedelta(seconds=delay)
                        if error.retryable
                        else None,
                    }
                ),
            )
            failure = str(error)
            # One inaccessible service/credential should not consume the entire outbox.
            break
        # The receipt is already durable. An archive failure must never enter the
        # upload-error handler or reclassify an accepted contribution.
        try:
            archive_uploaded(root, cancel=cancel)
        except SharingStorageError as error:
            cleanup_error = f"Local uploaded-history cleanup needs attention: {error}"
            break
    view = load_view(root, protocol_sha256, cancel, client=transport)
    if cleanup_error:
        return replace(view, error=cleanup_error)
    if failure:
        if view.status == "waiting_connection":
            return replace(view, error="Waiting for connection. Reports are saved locally; "
                           "Studio will retry on its next launch. " + failure)
        return replace(view, status="pending" if view.pending_count else "failed", error=failure)
    if not fetch_comparison:
        return view
    if not _may_send(root, profile, protocol_sha256, cancel):
        return view
    try:
        snapshot = transport.comparison(root, profile, cancel)
    except DataSharingCancelled:
        raise
    except DataSharingError as error:
        return replace(view, error=str(error), status="unavailable")
    rows = tuple(
        ConditionAggregate(
            condition_id=item.condition_id,
            label=item.condition_id,
            fixation_targets=item.total_targets,
            fixation_hits=item.hit_count,
            session_count=item.session_count,
            device_count=item.device_count,
            mean_rt_ms=item.mean_rt_ms,
            accuracy_percent=item.accuracy_percent,
            eligible=item.eligible,
            scoring_source=item.scoring_source,
            response_window_ms=item.response_window_ms,
        )
        for item in snapshot.conditions
    )
    local_by_condition = {row.condition_id: row for row in view.local_conditions}
    rows = tuple(
        replace(
            row,
            eligible=False,
            fixation_targets=None,
            fixation_hits=None,
            mean_rt_ms=None,
            accuracy_percent=None,
        )
        if row.condition_id in local_by_condition
        and (
            not local_by_condition[row.condition_id].eligible
            or row.scoring_source != local_by_condition[row.condition_id].scoring_source
            or row.response_window_ms != local_by_condition[row.condition_id].response_window_ms
        )
        else row
        for row in rows
    )
    available = any(row.eligible for row in rows)
    remote = ComparisonView(
        status="available" if available else "insufficient_cohort",
        experiment_id=snapshot.experiment_id,
        experiment_version=snapshot.experiment_version,
        protocol_sha256=snapshot.protocol_sha256,
        conditions=rows,
        minimum_sessions=snapshot.minimum_sessions,
        minimum_devices=snapshot.minimum_devices,
        message="Reference results exclude this enrollment's contributions."
        if available
        else "Not enough compatible reference data yet. Each condition needs "
        f"{snapshot.minimum_sessions} sessions from {snapshot.minimum_devices} "
        "other enrolled devices.",
    )
    return replace(view, remote=remote)


def disconnect_project(
    root: Path,
    protocol_sha256: str,
    cancel: Event,
    *,
    client: DataSharingClient | None = None,
) -> SharingView:
    settings = load_settings(root)
    save_settings(root, settings.model_copy(update={"enabled": False}))
    confirmed = True
    if settings.profile is not None:
        confirmed = (client or DataSharingClient.configured()).disconnect(
            root, settings.profile, cancel
        )
    save_settings(root, SharingSettings())
    view = load_view(root, protocol_sha256, Event(), client=client)
    return (
        view
        if confirmed
        else replace(
            view,
            error="Local enrollment removed; service access was already rejected. "
            "Previously received records remain.",
        )
    )


def archive_project(
    root: Path,
    protocol_sha256: str,
    cancel: Event,
    *,
    client: DataSharingClient | None = None,
) -> SharingView:
    """Move older accepted local caches; preserve research data and latest results."""
    check_cancel(cancel)
    archived = archive_uploaded(root)
    view = load_view(root, protocol_sha256, Event(), client=client)
    return replace(view, error=f"Archived {archived} older accepted report(s) locally.")
