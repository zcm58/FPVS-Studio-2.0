"""Review contracts and bounded transport for project and legacy condition uploads."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
import zipfile
from threading import Event
from typing import BinaryIO, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fpvs_studio import __version__
from fpvs_studio.developer.library_publisher import PreparedPublication
from fpvs_studio.library.cache import check_cancel
from fpvs_studio.library.client import METADATA_TOTAL_SECONDS, CredentialOwner, LibraryClient
from fpvs_studio.library.credentials import CredentialStore, DeviceCredential, credential_store
from fpvs_studio.library.errors import LibraryAuthorizationError, LibraryError
from fpvs_studio.library.models import MAX_DOWNLOAD_BYTES
from fpvs_studio.support.website_transfer import website_export

MAX_SUBMISSION_BYTES = 64 * 1024 * 1024
_PI_FRAME_BYTES = 1024 * 1024


def _upload_pi_bundle(
    client: LibraryClient, endpoint: str, token: str, pi_token: str, source: BinaryIO,
    cancel: Event | None,
) -> SubmissionStatus:
    from websockets.exceptions import InvalidStatus, WebSocketException
    from websockets.sync.client import connect

    # LibraryClient accepts HTTPS origins only. The sync transport rejects redirects.
    url = "wss://" + client.service_url.removeprefix("https://") + endpoint
    headers = {"Authorization": f"Bearer {token}", "X-FPVS-PI-Device": pi_token}
    # WebSocket debug tracing includes handshake headers.
    logger = logging.Logger("studio.review_upload", level=logging.CRITICAL)
    try:
        with connect(
            url, additional_headers=headers, compression=None, open_timeout=45, close_timeout=2,
            max_size=16 * 1024, max_queue=2, logger=logger,
        ) as socket:
            deadline = time.monotonic() + 56 * 60
            idle = time.monotonic() + 100
            while True:
                check_cancel(cancel)
                if time.monotonic() >= min(deadline, idle):
                    raise LibraryError("The upload timed out. Retry the same prepared bundle.")
                try:
                    reply = socket.recv(timeout=0.5)
                except TimeoutError:
                    continue
                if reply != "ready":
                    if not isinstance(reply, str):
                        raise LibraryError("OpenFPVS returned an invalid upload receipt.")
                    return _receipt(json.loads(reply))
                chunk = source.read(_PI_FRAME_BYTES)
                if not chunk:
                    raise LibraryError("OpenFPVS requested data beyond the prepared bundle.")
                socket.send(chunk)
                idle = time.monotonic() + 100
    except InvalidStatus as error:
        if error.response.status_code in (401, 403):
            raise LibraryAuthorizationError("Reconnect Studio with your lab PI account.") from None
        raise LibraryError("The upload could not start. Retry the prepared bundle.") from None
    except (OSError, WebSocketException, json.JSONDecodeError):
        raise LibraryError("The upload was interrupted. Retry the same prepared bundle.") from None


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


class SubmissionAccountCode(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$", repr=False)
    expires_at: int = Field(gt=0)


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


def _upload_token(client: LibraryClient, store: CredentialStore | None) -> str:
    # Upload identity is independent of Library enrollment and grants no download access.
    store = store if store is not None else credential_store(client.service_url + "/submissions")
    credential = store.load()
    if credential is None:
        credential = DeviceCredential(
            token=secrets.token_urlsafe(32), device_name="Project uploads"
        )
        store.save(credential)
    return credential.token


def list_submissions(
    client: LibraryClient,
    cancel_event: Event | None = None,
    *,
    upload_store: CredentialStore | None = None,
    project_uploads: bool = False,
) -> SubmissionList:
    with client._operation(cancel_event):
        raw = client._json_request(
            "GET",
            "/submissions/v1" if project_uploads else "/v2/submissions",
            token=_upload_token(client, upload_store)
            if project_uploads
            else client._credential().token,
            cancel_event=cancel_event,
            credential_owner="project_upload" if project_uploads else "library",
        )
        try:
            return SubmissionList.model_validate(raw)
        except ValidationError:
            raise LibraryError("OpenFPVS returned invalid submission statuses.") from None


def create_submission_account_code(
    client: LibraryClient, submission_id: UUID, cancel_event: Event | None = None,
    *, upload_store: CredentialStore | None = None,
) -> str:
    with client._operation(cancel_event):
        raw = client._json_request(
            "POST", f"/submissions/v1/{submission_id}/account-code",
            token=_upload_token(client, upload_store), payload={}, cancel_event=cancel_event,
            credential_owner="project_upload", limit=1024,
        )
        try:
            return SubmissionAccountCode.model_validate(raw).code
        except ValidationError:
            raise LibraryError("OpenFPVS returned an invalid linking code.") from None


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
    if (
        prepared.report.condition_count != 1
        or not 0 < prepared.report.size_bytes <= MAX_SUBMISSION_BYTES
    ):
        raise LibraryError("Submit one condition in a bundle no larger than 64 MiB.")
    return _submit(
        client,
        prepared,
        condition_id=condition_id,
        condition_name=condition_name,
        author_name=author_name,
        author_email=author_email,
        cancel_event=cancel_event,
    )


def submit_project(
    client: LibraryClient,
    prepared: PreparedPublication,
    *,
    author_name: str,
    author_email: str,
    cancel_event: Event | None = None,
    upload_store: CredentialStore | None = None,
) -> SubmissionStatus:
    """Upload the entire clean project without requesting Library access."""
    return _submit(
        client,
        prepared,
        condition_id="__project__",
        condition_name="Whole project",
        author_name=author_name,
        author_email=author_email,
        cancel_event=cancel_event,
        project_uploads=True,
        upload_store=upload_store,
    )


def _submit(
    client: LibraryClient,
    prepared: PreparedPublication,
    *,
    condition_id: str,
    condition_name: str,
    author_name: str,
    author_email: str,
    cancel_event: Event | None,
    project_uploads: bool = False,
    upload_store: CredentialStore | None = None,
) -> SubmissionStatus:
    """Retry the same UUID and exact bytes after uncertain network completion."""
    prefix = "submitted-" if project_uploads else "reviewed-"
    submission_id = str(UUID(prepared.request.item_id.removeprefix(prefix)))
    report = prepared.report
    if report.condition_count < 1 or not 0 < report.size_bytes <= (
        MAX_DOWNLOAD_BYTES if project_uploads else MAX_SUBMISSION_BYTES
    ):
        raise LibraryError("The project bundle must be smaller than 2 GiB.")
    pi_token = None
    if report.size_bytes > MAX_SUBMISSION_BYTES:
        try:
            pi_token = client.enrolled_credential(cancel_event=cancel_event).token
        except LibraryAuthorizationError:
            raise LibraryAuthorizationError(
                "Connect Studio to your personal OpenFPVS lab PI account "
                "to submit a project larger than 64 MiB."
            ) from None
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
        token = (
            _upload_token(client, upload_store) if project_uploads else client._credential().token
        )
        endpoint = "/submissions/v1" if project_uploads else "/v2/submissions"
        credential_owner: CredentialOwner = "project_upload" if project_uploads else "library"
        with website_export("project bundle" if project_uploads else "condition bundle"):
            raw = client._json_request(
                "POST",
                endpoint,
                token=token,
                payload=metadata,
                cancel_event=cancel_event,
                credential_owner=credential_owner,
                pi_device_token=pi_token,
            )
            status = _receipt(raw)
            if str(status.submission_id) != submission_id or status.sha256 != report.sha256:
                raise LibraryError("OpenFPVS returned a receipt for a different submission.")
            if status.status != "uploading":
                return status
            if pi_token:
                status = _upload_pi_bundle(
                    client, f"{endpoint}/{submission_id}/bundle", token, pi_token, source,
                    cancel_event,
                )
                if (str(status.submission_id) != submission_id or status.sha256 != report.sha256
                        or status.status != "pending"):
                    raise LibraryError("OpenFPVS did not confirm this bundle for review.")
                return status
            with client._response(
                "PUT",
                f"{endpoint}/{submission_id}/bundle",
                token=token,
                data=cast(BinaryIO, _UploadReader(source, cancel_event)),
                content_length=report.size_bytes,
                cancel_event=cancel_event,
                credential_owner=credential_owner,
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
