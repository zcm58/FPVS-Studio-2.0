"""Cancelable fixed-origin private Library transport and enrollment orchestration."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.client import HTTPException
from pathlib import Path
from threading import Event
from typing import Any, BinaryIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import ValidationError

from fpvs_studio import __version__
from fpvs_studio.core.library_origin import (
    MANAGED_LIBRARY_SERVICE_URL,
    canonical_library_service_url,
)
from fpvs_studio.library.cache import CHUNK_BYTES, DownloadCache, check_cancel, default_cache_root
from fpvs_studio.library.credentials import CredentialStore, credential_store
from fpvs_studio.library.errors import LibraryAuthorizationError, LibraryCancelled, LibraryError
from fpvs_studio.library.models import (
    MAX_CATALOG_BYTES,
    DeviceCredential,
    EnrollmentResponse,
    LibraryCatalog,
    LibraryConnection,
    LibraryItem,
)
from fpvs_studio.library.provenance import (
    require_pinned_origin,
    verify_proof,
    verify_proof_header,
)

DEFAULT_LIBRARY_SERVICE_URL = MANAGED_LIBRARY_SERVICE_URL
NETWORK_TIMEOUT_SECONDS = 10
METADATA_TOTAL_SECONDS = 30
DOWNLOAD_TOTAL_SECONDS = 30 * 60
_VIEW_ONLY_MESSAGE = "Your lab has view-only Library access. Downloads are not permitted."
ProgressCallback = Callable[[int, int], None]


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> None:
        return None


def _origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        raise LibraryError("The Library service URL is invalid.") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or any(ord(char) <= 32 for char in value)
    ):
        raise LibraryError("The Library service must use one HTTPS origin without credentials.")
    return value.rstrip("/")


def _status_error(status: int) -> LibraryError:
    if status in (401, 403):
        return LibraryAuthorizationError(
            "Library access was rejected. Check the lab code or reconnect this device."
        )
    if status in (404, 410):
        return LibraryError("This Library item is no longer available. Refresh the catalog.")
    if status == 429:
        return LibraryError("Too many Library requests. Wait a minute and try again.")
    if status == 426:
        return LibraryError(
            "Update FPVS Studio, then reconnect with your lab code to use the Experiment Library."
        )
    if 300 <= status < 400:
        return LibraryError("The Library service attempted an unsupported redirect.")
    return LibraryError(f"The Library service could not complete the request ({status}).")


class LibraryClient:
    """One GUI-independent client; callers keep long operations off the UI thread."""

    def __init__(
        self,
        service_url: str = DEFAULT_LIBRARY_SERVICE_URL,
        credential_store: CredentialStore | None = None,
        cache_root: Path | None = None,
    ) -> None:
        self.service_url = canonical_library_service_url(_origin(service_url))
        self._store = credential_store
        self._cache = DownloadCache(cache_root or default_cache_root(self.service_url))
        self._download_held = False

    @property
    def enabled(self) -> bool:
        return True

    @property
    def store(self) -> CredentialStore:
        if self._store is None:
            self._store = credential_store(self.service_url)
        return self._store

    @contextmanager
    def _operation(self, cancel_event: Event | None) -> Iterator[None]:
        check_cancel(cancel_event)
        self._cache.acquire()
        try:
            yield
        except OSError:
            raise LibraryError(
                "Library storage is unavailable or full. Free space and try again."
            ) from None
        finally:
            self._cache.release()

    @contextmanager
    def _response(
        self, method: str, path: str, *, token: str = "", data: bytes | BinaryIO | None = None,
        cancel_event: Event | None = None, content_length: int | None = None,
    ) -> Iterator[Any]:
        url = self.service_url + path
        headers = {
            "Accept": "application/octet-stream"
            if path.endswith("/download")
            else "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": f"FPVS-Studio/{__version__}",
        }
        if path.split("?", 1)[0] in ("/v2/enroll", "/v2/catalog"):
            headers["X-FPVS-Library-Metadata"] = "1"
        if data is not None:
            headers["Content-Type"] = "application/json"
        if content_length is not None:
            headers["Content-Type"] = "application/octet-stream"
            headers["Content-Length"] = str(content_length)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            response = build_opener(_NoRedirect()).open(request, timeout=NETWORK_TIMEOUT_SECONDS)
        except HTTPError as error:
            status = error.code
            try:
                view_only = (
                    bool(token) and status == 403 and path.endswith("/download")
                    and self._download_not_permitted(error, cancel_event)
                )
            finally:
                error.close()
            if view_only:
                raise LibraryError(_VIEW_ONLY_MESSAGE) from None
            if token and status in (401, 403):
                # A revoked token cannot enroll again. Keep failed invitation tokens
                # pending, but remove rejected device access so reconnect starts fresh.
                self.store.delete()
            raise _status_error(status) from None
        except (URLError, TimeoutError, OSError):
            raise LibraryError(
                "Could not reach the Experiment Library. Check your connection and retry."
            ) from None
        with response:
            if response.geturl() != url:
                raise LibraryError("The Library service returned an unexpected location.")
            if not 200 <= response.status < 300:
                raise _status_error(response.status)
            if response.headers.get("Content-Encoding", "identity") != "identity":
                raise LibraryError("The Library service returned unsupported compressed transport.")
            yield response

    @classmethod
    def _download_not_permitted(cls, error: HTTPError, cancel_event: Event | None) -> bool:
        """Recognize only the bounded service permission code, never remote prose."""
        if error.fp is None:
            return False
        try:
            raw = b"".join(cls._chunks(
                error, 8192, time.monotonic() + METADATA_TOTAL_SECONDS, cancel_event,
            ))
            metadata = json.loads(raw)
        except LibraryCancelled:
            raise
        except (LibraryError, ValueError, UnicodeError, RecursionError):
            return False
        return isinstance(metadata, dict) and metadata.get("error") == "download_not_permitted"

    @staticmethod
    def _chunks(
        response: Any, limit: int, deadline: float, cancel_event: Event | None
    ) -> Iterator[bytes]:
        received = 0
        while True:
            check_cancel(cancel_event)
            if time.monotonic() >= deadline:
                raise LibraryError("The Library request timed out. Try again.")
            # read1 makes one bounded socket read, so a trickle cannot hide the total deadline.
            try:
                chunk = response.read1(min(CHUNK_BYTES, limit - received + 1))
            except (OSError, HTTPException):
                raise LibraryError("The Library connection was interrupted. Try again.") from None
            if not chunk:
                break
            received += len(chunk)
            if received > limit:
                raise LibraryError("The Library response exceeded its declared size limit.")
            yield bytes(chunk)
        check_cancel(cancel_event)
        if time.monotonic() >= deadline:
            raise LibraryError("The Library request timed out. Try again.")

    def _json_request(
        self,
        method: str,
        path: str,
        *,
        token: str = "",
        payload: dict[str, Any] | None = None,
        cancel_event: Event | None = None,
        limit: int = MAX_CATALOG_BYTES,
    ) -> object:
        check_cancel(cancel_event)
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        deadline = time.monotonic() + METADATA_TOTAL_SECONDS
        with self._response(
            method, path, token=token, data=data, cancel_event=cancel_event,
        ) as response:
            if response.headers.get_content_type() != "application/json":
                raise LibraryError("The Library service returned an unexpected response type.")
            raw = b"".join(self._chunks(response, limit, deadline, cancel_event))
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            raise LibraryError("The Library service returned invalid metadata.") from None

    def connection_info(self) -> LibraryConnection | None:
        with self._operation(None):
            credential = self._load_current_credential()
            return credential.connection if credential is not None else None

    def _load_current_credential(self) -> DeviceCredential | None:
        """Read under the cache lock; old protocol access must reconnect with a new token."""
        credential = self.store.load()
        if credential is not None and credential.library_api_version != 2:
            self.store.delete()
            return None
        return credential

    def enroll(
        self, code: str, device_name: str, *, cancel_event: Event | None = None
    ) -> LibraryConnection:
        code, device_name = code.strip(), device_name.strip()
        if not code or len(code) > 128 or not device_name or len(device_name) > 100:
            raise LibraryError(
                "Enter a lab code and a computer name of up to 100 characters."
            )
        with self._operation(cancel_event):
            existing = self._load_current_credential()
            if existing is not None and existing.connection is not None:
                return existing.connection
            pending = existing or DeviceCredential(
                token=secrets.token_urlsafe(32), device_name=device_name, library_api_version=2,
            )
            # Save BEFORE the request: lost responses retry the same server-side enrollment.
            self.store.save(pending)
            raw = self._json_request(
                "POST",
                "/v2/enroll",
                payload={
                    "schema_version": "1.0",
                    "code": code,
                    "device_token": pending.token,
                    "device_name": pending.device_name,
                },
                cancel_event=cancel_event,
                limit=8192,
            )
            try:
                enrolled = EnrollmentResponse.model_validate(raw)
            except ValidationError:
                raise LibraryError(
                    "The Library service returned invalid enrollment metadata."
                ) from None
            connection = LibraryConnection(
                device_id=enrolled.device_id,
                library_name=enrolled.library_name,
                device_name=pending.device_name,
                access_level=enrolled.access_level,
                lab_name=enrolled.lab_name,
            )
            self.store.save(pending.model_copy(update={"connection": connection}))
            return connection

    def _credential(self) -> DeviceCredential:
        credential = self._load_current_credential()
        if credential is None or credential.connection is None:
            raise LibraryAuthorizationError(
                "Connect to the Experiment Library with your PI's lab code."
            )
        return credential

    def catalog(self, *, cancel_event: Event | None = None) -> LibraryCatalog:
        with self._operation(cancel_event):
            return self._read_catalog(self._credential(), cancel_event)

    def _read_catalog(
        self, credential: DeviceCredential, cancel_event: Event | None,
    ) -> LibraryCatalog:
        raw = self._json_request(
            "GET",
            "/v2/catalog?kind=experiment",
            token=credential.token,
            cancel_event=cancel_event,
        )
        try:
            catalog = LibraryCatalog.model_validate(raw)
        except ValidationError:
            raise LibraryError(
                "The Library catalog uses invalid or unsupported metadata."
            ) from None
        assert credential.connection is not None
        connection = credential.connection.model_copy(update={
            "library_name": catalog.library_name,
            "access_level": catalog.access_level,
            "lab_name": catalog.lab_name,
        })
        if connection != credential.connection:
            self.store.save(credential.model_copy(update={"connection": connection}))
        return catalog

    def download(
        self,
        item: LibraryItem,
        *,
        cancel_event: Event | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> Path:
        """Return verified bytes with a held lease. Call release_download after import/review."""
        check_cancel(cancel_event)
        try:
            item = LibraryItem.model_validate(item.model_dump())
        except ValidationError:
            raise LibraryError(
                "This Library item has invalid metadata. Refresh the catalog."
            ) from None
        if not item.compatible:
            raise LibraryError(item.compatibility_message)
        require_pinned_origin(self.service_url)
        self._cache.acquire()
        try:
            credential = self._credential()
            if credential.connection is not None and credential.connection.access_level == "view":
                raise LibraryError(_VIEW_ONLY_MESSAGE)
            retained = self._cache.verified(item, cancel_event)
            if retained is not None:
                # Confirm current authorization/withdrawal before reusing retained content.
                catalog = self._read_catalog(credential, cancel_event)
                if catalog.access_level != "download":
                    raise LibraryError(_VIEW_ONLY_MESSAGE)
                if item not in catalog.items:
                    raise LibraryError(
                        "This Library item changed or was withdrawn. Refresh the catalog."
                    )
                evidence = self._json_request(
                    "GET", f"/v2/items/{item.item_id}/versions/{item.version}/provenance",
                    token=credential.token, cancel_event=cancel_event, limit=8192,
                )
                if not isinstance(evidence, dict) or set(evidence) != {
                    "schema_version", "key_id", "proof",
                } or evidence["schema_version"] != "1.0":
                    raise LibraryError("untrusted_provenance: Invalid bundle safety response.")
                verify_proof(evidence["proof"], evidence["key_id"], item, self.service_url)
                self._cache.clear(keep=retained.name)
                if progress_callback is not None:
                    progress_callback(item.size_bytes, item.size_bytes)
                self._download_held = True
                return retained
            self._cache.clear()
            deadline = time.monotonic() + DOWNLOAD_TOTAL_SECONDS
            path = f"/v2/items/{item.item_id}/versions/{item.version}/download"
            digest, received = hashlib.sha256(), 0
            with self._response(
                "GET", path, token=credential.token, cancel_event=cancel_event,
            ) as response:
                declared = response.headers.get("Content-Length")
                if declared is not None and declared != str(item.size_bytes):
                    raise LibraryError("The Library download size changed. Refresh the catalog.")
                if response.headers.get_content_type() not in (
                    "application/octet-stream",
                    "application/zip",
                ):
                    raise LibraryError("The Library service returned an unexpected download type.")
                verify_proof_header(
                    response.headers.get("X-FPVS-Artifact-Proof"),
                    response.headers.get("X-FPVS-Artifact-Key-Id"), item, self.service_url,
                )
                with self._cache.create_partial() as target:
                    for chunk in self._chunks(response, item.size_bytes, deadline, cancel_event):
                        target.write(chunk)
                        received += len(chunk)
                        digest.update(chunk)
                        if progress_callback is not None:
                            progress_callback(received, item.size_bytes)
                    target.flush()
                    os.fsync(target.fileno())
            if received != item.size_bytes:
                raise LibraryError(
                    f"The Library download ended early: received {received:,} of "
                    f"{item.size_bytes:,} bytes. Try again."
                )
            if digest.hexdigest() != item.sha256:
                raise LibraryError(
                    "The Library download failed its SHA-256 integrity check. "
                    "Refresh the catalog and try again."
                )
            check_cancel(cancel_event)
            result = self._cache.commit(item)
            self._download_held = True
            return result
        except BaseException as error:
            try:
                self._cache.remove("download.part")
            finally:
                self._cache.release()
            if isinstance(error, OSError):
                raise LibraryError(
                    "Library storage is unavailable or full. Free space and retry."
                ) from None
            raise

    def release_download(self) -> None:
        """Release after the importer/review stops reading; the verified payload remains bounded."""
        if self._download_held:
            self._download_held = False
            self._cache.release()

    def disconnect(self, *, cancel_event: Event | None = None) -> None:
        """Revoke remotely before clearing local access; keep retry state on network failure."""
        with self._operation(cancel_event):
            credential = self._load_current_credential()
            if credential is not None:
                try:
                    self._json_request(
                        "DELETE",
                        "/v2/device",
                        token=credential.token,
                        cancel_event=cancel_event,
                        limit=8192,
                    )
                except LibraryAuthorizationError:
                    pass  # Already revoked/never enrolled: local deletion is still valid.
            self.store.delete()
            self._cache.clear()
