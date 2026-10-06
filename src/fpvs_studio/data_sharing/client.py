"""Bounded, cancelable HTTPS access to one explicit results-service origin."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from collections.abc import Callable, Mapping
from http.client import HTTPException
from pathlib import Path
from threading import Event
from typing import Protocol, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import BaseModel, ValidationError

from fpvs_studio import __version__
from fpvs_studio.core.data_sharing import (
    ComparisonSnapshot,
    DeliveryReceipt,
    SessionReport,
    SharingProfile,
)
from fpvs_studio.data_sharing.credentials import sharing_credential_store
from fpvs_studio.data_sharing.errors import DataSharingCancelled, DataSharingError
from fpvs_studio.data_sharing.library_scope import (
    library_enrollment_scope,
    validate_library_scope,
)
from fpvs_studio.library.credentials import CredentialStore
from fpvs_studio.library.errors import LibraryError
from fpvs_studio.library.models import DeviceCredential, LibraryConnection

MAX_RESPONSE_BYTES = 256 * 1024
SOCKET_TIMEOUT_SECONDS = 10
REQUEST_DEADLINE_SECONDS = 30
ModelT = TypeVar("ModelT", bound=BaseModel)
StoreFactory = Callable[[str, Path, str], CredentialStore]


class Transport(Protocol):
    def __call__(
        self,
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        cancel: Event,
    ) -> bytes: ...


def check_cancel(cancel: Event) -> None:
    if cancel.is_set():
        raise DataSharingCancelled()


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        return None


def _status_error(status: int) -> DataSharingError:
    if status in (401, 403):
        return DataSharingError(
            "Results access was rejected. Reconnect with a valid lab invitation code.",
            code="authorization",
        )
    if status == 409:
        return DataSharingError(
            "The service rejected conflicting report or enrollment details.",
            code="conflict",
        )
    if status in (400, 404, 410, 413, 422):
        return DataSharingError(
            "The registered experiment or report does not match this service. "
            "Check its invitation and protocol version.",
            code="protocol",
        )
    if 300 <= status < 400:
        return DataSharingError("Results-service redirects are not allowed.", code="redirect")
    return DataSharingError(
        "The results service is temporarily unavailable. The local report is retained.",
        code="throttled" if status == 429 else "unavailable",
        retryable=True,
    )


def http_transport(
    method: str,
    url: str,
    body: bytes | None,
    headers: Mapping[str, str],
    cancel: Event,
) -> bytes:
    check_cancel(cancel)
    request = Request(url, data=body, headers=dict(headers), method=method)
    started = time.monotonic()
    try:
        with build_opener(_NoRedirect()).open(request, timeout=SOCKET_TIMEOUT_SECONDS) as response:
            if response.headers.get_content_type() != "application/json":
                raise DataSharingError(
                    "The results service returned invalid data.", code="protocol"
                )
            chunks: list[bytes] = []
            size = 0
            while True:
                check_cancel(cancel)
                if time.monotonic() - started > REQUEST_DEADLINE_SECONDS:
                    raise DataSharingError(
                        "Results request timed out.", code="timeout", retryable=True
                    )
                chunk = response.read(min(16384, MAX_RESPONSE_BYTES + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise DataSharingError("Results response exceeds its limit.", code="protocol")
                chunks.append(chunk)
            return b"".join(chunks)
    except HTTPError as error:
        raise _status_error(error.code) from None
    except (URLError, OSError, HTTPException):
        raise DataSharingError(
            "Unable to reach the results service. Local reports are retained for retry.",
            code="network",
            retryable=True,
        ) from None


def _origin(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        raise DataSharingError("Invalid results-service origin.", code="configuration") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or any(ord(character) <= 32 for character in value)
    ):
        raise DataSharingError(
            "The results service must use one HTTPS origin without paths or credentials.",
            code="configuration",
        )
    return value.rstrip("/")


class DataSharingClient:
    def __init__(
        self,
        service_url: str = "",
        *,
        transport: Transport | None = None,
        store_factory: StoreFactory = sharing_credential_store,
    ) -> None:
        self.origin = _origin(service_url)
        self._transport = transport or http_transport
        self._store_factory = store_factory

    @classmethod
    def configured(cls) -> DataSharingClient:
        return cls(os.environ.get("FPVS_DATA_SHARING_SERVICE_URL", ""))

    @property
    def enabled(self) -> bool:
        return bool(self.origin)

    def _store(self, root: Path, protocol: str) -> CredentialStore:
        return self._store_factory(self.origin, root, protocol)

    def _load_credential(self, root: Path, profile: SharingProfile) -> DeviceCredential:
        try:
            credential = self._store(root, profile.protocol_sha256).load()
        except LibraryError:
            raise DataSharingError(
                "Cannot read results access from the OS secure credential store.",
                code="credential_store",
            ) from None
        if (
            credential is None
            or credential.connection is None
            or credential.connection.device_id != profile.device_id
        ):
            raise DataSharingError(
                "This machine needs its own results enrollment. Reconnect using a lab code.",
                code="authorization",
            )
        return credential

    def _request(
        self,
        method: str,
        path: str,
        body: bytes | None,
        cancel: Event,
        token: str | None = None,
    ) -> bytes:
        check_cancel(cancel)
        if not self.enabled:
            raise DataSharingError(
                "The results service has not been configured for this build.",
                code="configuration",
            )
        headers = {"Accept": "application/json", "User-Agent": f"FPVS-Studio/{__version__}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = self._transport(method, self.origin + path, body, headers, cancel)
        if len(response) > MAX_RESPONSE_BYTES:
            raise DataSharingError("Results response exceeds its limit.", code="protocol")
        return response

    @staticmethod
    def _parse(raw: bytes, model: type[ModelT]) -> ModelT:
        try:
            return model.model_validate_json(raw)
        except (ValidationError, ValueError):
            raise DataSharingError(
                "The results service returned invalid data.", code="protocol"
            ) from None

    def enroll(self, root: Path, code: str, protocol_sha256: str, cancel: Event) -> SharingProfile:
        check_cancel(cancel)
        if not code.strip() or len(code) > 128:
            raise DataSharingError("Enter a valid lab invitation code.", code="invitation")
        if not self.enabled:
            raise DataSharingError("The results service is not configured.", code="configuration")
        scope = library_enrollment_scope(root)
        store = self._store(root, protocol_sha256)
        try:
            credential = store.load()
            if credential is None:
                credential = DeviceCredential(
                    token=secrets.token_hex(32),
                    device_name="FPVS Studio data sharing",
                )
                store.save(credential)
            payload = json.dumps(
                {
                    "schema_version": "1.0",
                    "code": code.strip(),
                    "device_token": credential.token,
                    "protocol_sha256": protocol_sha256,
                    **scope,
                },
                separators=(",", ":"),
            ).encode("utf-8")
            profile = self._parse(
                self._request("POST", "/v1/enroll", payload, cancel), SharingProfile
            )
            if profile.protocol_sha256 != protocol_sha256:
                raise DataSharingError(
                    "The invitation belongs to a different protocol.", code="protocol"
                )
            validate_library_scope(root, profile)
            credential = credential.model_copy(
                update={
                    "connection": LibraryConnection(
                        device_id=profile.device_id,
                        library_name="FPVS Studio data sharing",
                        device_name=credential.device_name,
                    )
                }
            )
            store.save(credential)
            return profile
        except LibraryError:
            raise DataSharingError(
                "Enrollment requires an available OS secure credential store.",
                code="credential_store",
            ) from None

    def submit(
        self,
        root: Path,
        profile: SharingProfile,
        payload: bytes,
        cancel: Event,
        *,
        before_send: Callable[[], bool] | None = None,
    ) -> DeliveryReceipt:
        validate_library_scope(root, profile)
        report = self._parse(payload, SessionReport)
        if (
            report.experiment_id != profile.experiment_id
            or report.experiment_version != profile.experiment_version
            or report.protocol_sha256 != profile.protocol_sha256
        ):
            raise DataSharingError("The report does not match this enrollment.", code="protocol")
        credential = self._load_credential(root, profile)
        if before_send is not None and not before_send():
            raise DataSharingCancelled()
        receipt = self._parse(
            self._request(
                "POST",
                f"/v1/experiments/{profile.experiment_id}/reports",
                payload,
                cancel,
                credential.token,
            ),
            DeliveryReceipt,
        )
        self._validate_receipt(
            receipt, profile, report.report_id, hashlib.sha256(payload).hexdigest()
        )
        return receipt

    @staticmethod
    def _validate_receipt(
        receipt: DeliveryReceipt,
        profile: SharingProfile,
        report_id: str,
        digest: str,
    ) -> None:
        if (
            receipt.report_id != report_id
            or receipt.sha256 != digest
            or receipt.experiment_id != profile.experiment_id
            or receipt.experiment_version != profile.experiment_version
            or receipt.protocol_sha256 != profile.protocol_sha256
        ):
            raise DataSharingError("The service returned an unrelated receipt.", code="protocol")

    def receipt(
        self,
        root: Path,
        profile: SharingProfile,
        report_id: str,
        digest: str,
        cancel: Event,
    ) -> DeliveryReceipt:
        from uuid import UUID

        if str(UUID(report_id)) != report_id:
            raise DataSharingError("Invalid local report identity.", code="protocol")
        credential = self._load_credential(root, profile)
        receipt = self._parse(
            self._request(
                "GET",
                f"/v1/experiments/{profile.experiment_id}/reports/{report_id}/receipt",
                None,
                cancel,
                credential.token,
            ),
            DeliveryReceipt,
        )
        self._validate_receipt(receipt, profile, report_id, digest)
        return receipt

    def comparison(self, root: Path, profile: SharingProfile, cancel: Event) -> ComparisonSnapshot:
        validate_library_scope(root, profile)
        credential = self._load_credential(root, profile)
        snapshot = self._parse(
            self._request(
                "POST",
                f"/v1/experiments/{profile.experiment_id}/comparison",
                b'{"schema_version":"1.0"}',
                cancel,
                credential.token,
            ),
            ComparisonSnapshot,
        )
        if (
            snapshot.experiment_id != profile.experiment_id
            or snapshot.experiment_version != profile.experiment_version
            or snapshot.protocol_sha256 != profile.protocol_sha256
        ):
            raise DataSharingError("The comparison belongs to another protocol.", code="protocol")
        return snapshot

    def disconnect(self, root: Path, profile: SharingProfile, cancel: Event) -> bool:
        confirmed = True
        try:
            credential = self._load_credential(root, profile)
            raw = self._request("DELETE", "/v1/device", None, cancel, credential.token)
        except DataSharingError as error:
            if error.code != "authorization":
                raise
            # Rejected credentials cannot revoke remotely, but must not trap an
            # operator in an enrollment which they can no longer use or replace.
            confirmed = False
            raw = b""
        if confirmed and raw != b'{"schema_version":"1.0","revoked":true}':
            try:
                if json.loads(raw) != {"schema_version": "1.0", "revoked": True}:
                    raise ValueError
            except (ValueError, UnicodeError):
                raise DataSharingError(
                    "Invalid revocation confirmation.", code="protocol"
                ) from None
        try:
            self._store(root, profile.protocol_sha256).delete()
        except LibraryError:
            raise DataSharingError(
                "The OS results credential could not be removed; sharing remains off.",
                code="credential_store",
            ) from None
        return confirmed
