"""Bounded project-local sharing settings and immutable, atomic outbox records."""

from __future__ import annotations

import hashlib
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import Field, StrictInt, ValidationError, field_validator, model_validator

from fpvs_studio.core.data_sharing import (
    MAX_REPORT_BYTES,
    DeliveryReceipt,
    Identifier,
    SessionReport,
    Sha256,
    SharingModel,
    SharingSettings,
    VersionText,
    _utc,
    _uuid,
)
from fpvs_studio.core.paths import filesystem_path
from fpvs_studio.core.serialization import atomic_text_write

MAX_RECORDS = 512
MAX_RECORD_BYTES = 256 * 1024
MAX_SETTINGS_BYTES = 16 * 1024
_ModelT = TypeVar("_ModelT", bound=SharingModel)


class SharingStorageError(ValueError):
    """Sharing metadata cannot be read or changed safely; existing files remain intact."""


@contextmanager
def _storage_lock(root: Path) -> Iterator[None]:
    # Runtime's package facade imports the launcher. Import its narrow public
    # lock only after this module is fully initialized, without duplicating it.
    from fpvs_studio.runtime.reporting_lock import project_reporting_lock

    _private_path(root, "logs/.reporting.lock")
    with project_reporting_lock(root):
        yield


class OutboxRecord(SharingModel):
    schema_version: Literal["1.0"] = "1.0"
    report_id: str
    experiment_id: Identifier
    experiment_version: VersionText
    protocol_sha256: Sha256
    payload_sha256: Sha256
    payload_json: str = Field(min_length=1, max_length=MAX_REPORT_BYTES)
    state: Literal["pending", "held", "uploaded", "failed"] = "pending"
    attempt_count: StrictInt = Field(default=0, ge=0, le=1_000_000)
    last_error_code: Identifier | None = None
    next_attempt_at: datetime | None = None
    receipt: DeliveryReceipt | None = None

    _validate_id = field_validator("report_id")(_uuid)

    @field_validator("next_attempt_at")
    @classmethod
    def validate_next_attempt(cls, value: datetime | None) -> datetime | None:
        return _utc(value) if value is not None else None

    @model_validator(mode="after")
    def validate_payload(self) -> OutboxRecord:
        encoded = self.payload_json.encode("utf-8")
        if len(encoded) > MAX_REPORT_BYTES:
            raise ValueError("Outbox payload exceeds its size limit.")
        if hashlib.sha256(encoded).hexdigest() != self.payload_sha256:
            raise ValueError("Outbox payload digest does not match its bytes.")
        report = SessionReport.model_validate_json(encoded)
        for field in ("report_id", "experiment_id", "experiment_version", "protocol_sha256"):
            if getattr(report, field) != getattr(self, field):
                raise ValueError("Outbox identity does not match its immutable report.")
        if self.receipt is not None:
            for field in ("report_id", "experiment_id", "experiment_version", "protocol_sha256"):
                if getattr(self.receipt, field) != getattr(self, field):
                    raise ValueError("Receipt belongs to a different report.")
            if self.receipt.sha256 != self.payload_sha256:
                raise ValueError("Receipt digest does not match the report.")
        if (self.state == "uploaded") != (self.receipt is not None):
            raise ValueError("Uploaded records require an accepted receipt.")
        return self


def _private_path(root: Path, relative: str) -> Path:
    root = filesystem_path(Path(root))
    if not root.is_dir():
        raise SharingStorageError("Sharing requires an existing active project directory.")
    path = root / relative
    candidates = [root]
    for component in Path(relative).parts:
        candidates.append(candidates[-1] / component)
    for candidate in candidates:
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise SharingStorageError("Sharing paths cannot contain links or reparse points.")
        directory = candidate != path or not path.suffix
        regular = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        if not regular or (not directory and info.st_nlink != 1):
            raise SharingStorageError("Sharing metadata must be a private regular project file.")
    if not path.resolve().is_relative_to(root.resolve()):
        raise SharingStorageError("Sharing path escapes the active project directory.")
    return path


def _settings_path(root: Path) -> Path:
    return _private_path(root, ".fpvs-data-sharing/settings.json")


def _outbox_path(root: Path) -> Path:
    return _private_path(root, "logs/data-sharing/outbox")


def _record_path(root: Path, report_id: str) -> Path:
    _uuid(report_id)
    return _private_path(root, f"logs/data-sharing/outbox/{report_id}.json")


def read_bounded_model(path: Path, model: type[_ModelT], limit: int) -> _ModelT:
    """Read validated bounded bytes; callers must first establish project containment."""
    try:
        with path.open("rb") as stream:
            payload = stream.read(limit + 1)
        if len(payload) > limit:
            raise SharingStorageError("Sharing metadata exceeds its size limit.")
        return model.model_validate_json(payload)
    except (ValidationError, UnicodeError) as exc:
        raise SharingStorageError("Sharing metadata is malformed or unsupported.") from exc
    except OSError as exc:
        raise SharingStorageError("Sharing metadata could not be read.") from exc


def _write(root: Path, relative: str, model: SharingModel, limit: int) -> None:
    payload = model.model_dump_json()
    if len(payload.encode("utf-8")) > limit:
        raise SharingStorageError("Sharing metadata exceeds its size limit.")
    try:
        path = _private_path(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        _private_path(root, relative)
        atomic_text_write(path, payload)
    except OSError as exc:
        raise SharingStorageError("Sharing metadata could not be saved.") from exc


def load_settings(root: Path) -> SharingSettings:
    path = _settings_path(root)
    return (
        read_bounded_model(path, SharingSettings, MAX_SETTINGS_BYTES)
        if path.exists()
        else SharingSettings()
    )


def _records(root: Path) -> tuple[OutboxRecord, ...]:
    directory = _outbox_path(root)
    if not directory.exists():
        return ()
    paths = list(directory.glob("*.json"))
    if len(paths) > MAX_RECORDS:
        raise SharingStorageError(
            "Sharing outbox exceeds its record limit; review existing reports."
        )
    records = []
    for path in sorted(paths):
        checked = _record_path(root, path.stem)
        record = read_bounded_model(checked, OutboxRecord, MAX_RECORD_BYTES)
        if record.report_id != path.stem:
            raise SharingStorageError("Sharing record filename does not match its report ID.")
        records.append(record)
    return tuple(records)


def list_records(root: Path) -> tuple[OutboxRecord, ...]:
    return _records(root)


def list_pending(root: Path, *, include_held: bool = False) -> tuple[OutboxRecord, ...]:
    states = {"pending", "held"} if include_held else {"pending"}
    return tuple(record for record in _records(root) if record.state in states)


def _save_record(root: Path, record: OutboxRecord) -> None:
    _write(root, f"logs/data-sharing/outbox/{record.report_id}.json", record, MAX_RECORD_BYTES)


def save_settings(root: Path, settings: SharingSettings) -> None:
    settings = SharingSettings.model_validate(settings.model_dump())
    _settings_path(root)
    with _storage_lock(root):
        previous = load_settings(root)
        # Opt-out closes the send gate even if an outbox record needs repair.
        if not settings.enabled:
            _write(root, ".fpvs-data-sharing/settings.json", settings, MAX_SETTINGS_BYTES)
        records = _records(root)
        if not settings.enabled or not previous.enabled or settings.profile != previous.profile:
            for record in records:
                if record.state == "pending":
                    _save_record(root, record.model_copy(update={"state": "held"}))
        if settings.enabled:
            _write(root, ".fpvs-data-sharing/settings.json", settings, MAX_SETTINGS_BYTES)


def queue_report(root: Path, report: SessionReport) -> OutboxRecord:
    report = SessionReport.model_validate(report.model_dump())
    payload = report.model_dump_json()
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    _record_path(root, report.report_id)
    with _storage_lock(root):
        existing = {record.report_id: record for record in _records(root)}
        if report.report_id in existing:
            record = existing[report.report_id]
            if record.payload_sha256 != digest or record.payload_json != payload:
                raise SharingStorageError("The report UUID already has different immutable bytes.")
            return record
        if len(existing) >= MAX_RECORDS:
            raise SharingStorageError(
                "Sharing outbox is full; review existing reports before queuing."
            )
        settings = load_settings(root)
        profile = settings.profile
        matching = profile is not None and all(
            getattr(profile, field) == getattr(report, field)
            for field in ("experiment_id", "experiment_version", "protocol_sha256")
        )
        record = OutboxRecord(
            report_id=report.report_id,
            experiment_id=report.experiment_id,
            experiment_version=report.experiment_version,
            protocol_sha256=report.protocol_sha256,
            payload_sha256=digest,
            payload_json=payload,
            state="pending" if settings.enabled and matching else "held",
        )
        _save_record(root, record)
        return record


def read_payload(root: Path, report_id: str) -> bytes:
    record = read_bounded_model(_record_path(root, report_id), OutboxRecord, MAX_RECORD_BYTES)
    return record.payload_json.encode("utf-8")


def update_record(root: Path, record: OutboxRecord) -> None:
    record = OutboxRecord.model_validate(record.model_dump())
    path = _record_path(root, record.report_id)
    with _storage_lock(root):
        previous = read_bounded_model(path, OutboxRecord, MAX_RECORD_BYTES)
        for field in (
            "payload_json",
            "payload_sha256",
            "experiment_id",
            "experiment_version",
            "protocol_sha256",
        ):
            if getattr(previous, field) != getattr(record, field):
                raise SharingStorageError("Queued report bytes and identity are immutable.")
        if previous.state == "uploaded" and record != previous:
            raise SharingStorageError("An accepted report receipt cannot be overwritten.")
        # Opt-out can happen while an HTTP request is in flight. Its receipt must
        # still be saved, but retry state must not undo the operator's pause.
        if previous.state == "held" and record.state == "pending":
            record = record.model_copy(update={"state": "held"})
        _save_record(root, record)


def release_held(root: Path) -> None:
    _settings_path(root)
    with _storage_lock(root):
        settings = load_settings(root)
        if not settings.enabled or settings.profile is None:
            raise SharingStorageError("Enable sharing before explicitly retrying held reports.")
        for record in _records(root):
            if record.state in {"held", "failed"} and all(
                getattr(record, field) == getattr(settings.profile, field)
                for field in ("experiment_id", "experiment_version", "protocol_sha256")
            ):
                _save_record(
                    root,
                    record.model_copy(
                        update={
                            "state": "pending",
                            "last_error_code": None,
                            "next_attempt_at": None,
                        }
                    ),
                )


def delete_pending(root: Path, report_id: str) -> None:
    path = _record_path(root, report_id)
    with _storage_lock(root):
        record = read_bounded_model(path, OutboxRecord, MAX_RECORD_BYTES)
        if record.state == "uploaded":
            raise SharingStorageError("Accepted receipts cannot be deleted as pending reports.")
        path.unlink()


def archive_uploaded(root: Path) -> int:
    """Explicitly archive older acknowledged caches, preserving each scope's latest.

    This never deletes research exports or changes the shared dataset. Finalized
    capture intents cannot be recovered again, so their acknowledged caches may
    move together. Receipt and private join evidence remain available for audit.
    Any unfinished intent preserves its active receipt.
    """
    from fpvs_studio.runtime.data_sharing import MAX_INTENT_BYTES, CaptureIntent

    with _storage_lock(root):
        records = _records(root)
        uploaded = [record for record in records if record.state == "uploaded"]
        latest: dict[tuple[str, str, str], str] = {}
        reports = {
            record.report_id: SessionReport.model_validate_json(record.payload_json)
            for record in uploaded
        }
        for record in sorted(
            uploaded,
            key=lambda item: (
                reports[item.report_id].completed_at,
                item.report_id,
            ),
        ):
            scope = (record.experiment_id, record.experiment_version, record.protocol_sha256)
            latest[scope] = record.report_id
        selected: list[tuple[Path, Path, Path | None, Path]] = []
        for record in uploaded:
            scope = (record.experiment_id, record.experiment_version, record.protocol_sha256)
            if latest[scope] == record.report_id:
                continue
            record_path = _record_path(root, record.report_id)
            intent_path: Path | None = _private_path(
                root,
                f"logs/data-sharing/intents/{record.report_id}.json",
            )
            archive_report = _private_path(
                root,
                f"logs/data-sharing/archive/{record.report_id}/report.json",
            )
            archive_intent = _private_path(
                root,
                f"logs/data-sharing/archive/{record.report_id}/capture.json",
            )
            if archive_report.exists():
                raise SharingStorageError(
                    "An archived receipt already exists; review before retrying."
                )
            if intent_path is not None and intent_path.exists():
                intent = read_bounded_model(intent_path, CaptureIntent, MAX_INTENT_BYTES)
                if intent.report_id != record.report_id:
                    raise SharingStorageError("Capture filename does not match its report UUID.")
                if intent.state != "finalized":
                    continue
                if intent.report is None or intent.report.model_dump_json() != record.payload_json:
                    raise SharingStorageError(
                        "Acknowledged cache differs from its finalized capture."
                    )
                if archive_intent.exists():
                    raise SharingStorageError(
                        "An archived capture already exists; review before retrying."
                    )
            else:
                intent_path = None
                if archive_intent.exists():
                    archived = read_bounded_model(archive_intent, CaptureIntent, MAX_INTENT_BYTES)
                    if (
                        archived.state != "finalized"
                        or archived.report_id != record.report_id
                        or archived.report is None
                        or archived.report.model_dump_json() != record.payload_json
                    ):
                        raise SharingStorageError(
                            "A partial archive has conflicting capture evidence."
                        )
            selected.append((record_path, archive_report, intent_path, archive_intent))
        # Validate every source and destination before moving recognized files.
        # Move the intent first so a failed report move can resume from its still
        # active receipt on the next explicit archive action, without overwrites.
        try:
            for record_path, archive_report, intent_path, archive_intent in selected:
                archive_report.parent.mkdir(parents=True, exist_ok=True)
                _private_path(root, f"logs/data-sharing/archive/{record_path.stem}/report.json")
                _private_path(root, f"logs/data-sharing/archive/{record_path.stem}/capture.json")
                if intent_path is not None:
                    intent_path.rename(archive_intent)
                record_path.rename(archive_report)
        except OSError as exc:
            raise SharingStorageError(
                "Local archive could not finish. Receipts remain recoverable; retry the archive.",
            ) from exc
        return len(selected)
