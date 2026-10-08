"""Condition review contracts and bounded, enrolled-device submission transport."""

from __future__ import annotations

import hashlib
import json
import time
import zipfile
from threading import Event
from typing import BinaryIO, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fpvs_studio import __version__
from fpvs_studio.developer.library_publisher import PreparedPublication
from fpvs_studio.library.cache import check_cancel
from fpvs_studio.library.client import METADATA_TOTAL_SECONDS, LibraryClient
from fpvs_studio.library.errors import LibraryError

MAX_SUBMISSION_BYTES = 64 * 1024 * 1024


class SubmissionStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    submission_id: UUID
    project_id: str = Field(max_length=200)
    condition_id: str = Field(max_length=200)
    condition_name: str = Field(max_length=200)
    title: str = Field(max_length=160)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["uploading", "pending", "publishing", "accepted", "rejected"]
    review_notes: str = Field(max_length=2000)
    tested_studio_version: str | None
    item_id: str
    version: str
    created_at: int


class SubmissionList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"]
    submissions: list[SubmissionStatus] = Field(max_length=100)


class SubmissionReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"]
    submission: SubmissionStatus


class _UploadReader:
    def __init__(self, source: BinaryIO, cancel: Event | None) -> None:
        self.source = source
        self.cancel = cancel
        self.deadline = time.monotonic() + 10 * 60

    def read(self, size: int = -1) -> bytes:
        check_cancel(self.cancel)
        if time.monotonic() >= self.deadline:
            raise LibraryError("The submission upload timed out. Retry the same prepared bundle.")
        return self.source.read(min(size, 65536) if size > 0 else 65536)


def _receipt(raw: object) -> SubmissionStatus:
    try:
        return SubmissionReceipt.model_validate(raw).submission
    except ValidationError:
        raise LibraryError("OpenFPVS returned invalid submission metadata.") from None


def list_submissions(client: LibraryClient, cancel_event: Event | None = None) -> SubmissionList:
    with client._operation(cancel_event):
        raw = client._json_request(
            "GET",
            "/v2/submissions",
            token=client._credential().token,
            cancel_event=cancel_event,
        )
        try:
            return SubmissionList.model_validate(raw)
        except ValidationError:
            raise LibraryError("OpenFPVS returned invalid submission statuses.") from None


def submit_condition(
    client: LibraryClient,
    prepared: PreparedPublication,
    *,
    condition_id: str,
    condition_name: str,
    author_name: str,
    author_email: str,
    cancel_event: Event | None = None,
) -> SubmissionStatus:
    """Retry the same UUID and exact bytes after uncertain network completion."""
    submission_id = str(UUID(prepared.request.item_id.removeprefix("reviewed-")))
    report = prepared.report
    if report.condition_count != 1 or not 0 < report.size_bytes <= MAX_SUBMISSION_BYTES:
        raise LibraryError("Submit one condition in a bundle no larger than 64 MiB.")
    if not author_name.strip() or len(author_name) > 200:
        raise LibraryError("Enter your name (up to 200 characters).")
    if not author_email.strip() or len(author_email) > 254 or "@" not in author_email:
        raise LibraryError("Enter a contact email address.")
    with client._operation(cancel_event), prepared.bundle_path.open("rb") as source:
        digest = hashlib.sha256()
        for chunk in iter(lambda: source.read(65536), b""):
            check_cancel(cancel_event)
            digest.update(chunk)
        if digest.hexdigest() != report.sha256 or source.tell() != report.size_bytes:
            raise LibraryError("The prepared bundle changed. Prepare a new submission.")
        source.seek(0)
        with zipfile.ZipFile(source) as archive:
            uncompressed = sum(info.file_size for info in archive.infolist())
        source.seek(0)
        metadata = {
            "schema_version": "1.0",
            "submission_id": submission_id,
            "project_id": report.project_id,
            "condition_id": condition_id,
            "condition_name": condition_name,
            "author_name": author_name,
            "author_email": author_email,
            "rights_confirmed": True,
            "studio_version": __version__,
            "item": {
                "item_id": prepared.request.item_id,
                "kind": "experiment",
                "version": prepared.request.version,
                "title": prepared.request.title,
                "description": prepared.request.summary,
                "experiment_category": report.category,
                "filename": prepared.bundle_path.name,
                "size_bytes": report.size_bytes,
                "uncompressed_size_bytes": uncompressed,
                "file_count": report.file_count,
                "sha256": report.sha256,
                "min_studio_version": report.minimum_studio_version,
            },
        }
        token = client._credential().token
        raw = client._json_request(
            "POST",
            "/v2/submissions",
            token=token,
            payload=metadata,
            cancel_event=cancel_event,
        )
        status = _receipt(raw)
        if str(status.submission_id) != submission_id or status.sha256 != report.sha256:
            raise LibraryError("OpenFPVS returned a receipt for a different submission.")
        if status.status != "uploading":
            return status
        with client._response(
            "PUT",
            f"/v2/submissions/{submission_id}/bundle",
            token=token,
            data=cast(BinaryIO, _UploadReader(source, cancel_event)),
            content_length=report.size_bytes,
            cancel_event=cancel_event,
        ) as response:
            raw = json.loads(
                b"".join(
                    client._chunks(
                        response,
                        65536,
                        time.monotonic() + METADATA_TOTAL_SECONDS,
                        cancel_event,
                    )
                )
            )
        status = _receipt(raw)
        if str(status.submission_id) != submission_id or status.sha256 != report.sha256:
            raise LibraryError("OpenFPVS returned a receipt for a different submission.")
        return status
