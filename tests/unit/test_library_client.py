"""Library trust boundaries and retry/cancellation behavior with no network or OS secrets."""

from __future__ import annotations

import hashlib
import io
import json
from contextlib import contextmanager
from email.message import Message
from threading import Event
from urllib.error import HTTPError, URLError

import pytest
from pydantic import ValidationError

from fpvs_studio.library import cache as cache_module
from fpvs_studio.library import client as client_module
from fpvs_studio.library.cache import DownloadCache
from fpvs_studio.library.client import LibraryClient
from fpvs_studio.library.errors import LibraryAuthorizationError, LibraryCancelled, LibraryError
from fpvs_studio.library.models import (
    MAX_DOWNLOAD_BYTES,
    DeviceCredential,
    LibraryCatalog,
    LibraryConnection,
    LibraryItem,
)

ORIGIN = "https://library.example.test"
PAYLOAD = b"synthetic-bundle-bytes"


class MemoryStore:
    def __init__(self, *, connected=True):
        self.value = (
            DeviceCredential(
                token="t" * 43,
                device_name="Test machine",
                connection=LibraryConnection(
                    device_id="device-1", library_name="Test library", device_name="Test machine"
                ),
            )
            if connected
            else None
        )
        self.saved = []
        self.fail_save = False

    def load(self):
        return self.value

    def save(self, value):
        if self.fail_save:
            raise LibraryError("Credential storage unavailable")
        self.saved.append(value)
        self.value = value

    def delete(self):
        self.value = None


class Response(io.BytesIO):
    def __init__(self, value, url, *, content_type="application/json", headers=None, status=200):
        super().__init__(value if isinstance(value, bytes) else json.dumps(value).encode())
        self.url = url
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        for name, value in (headers or {}).items():
            self.headers[name] = value

    def geturl(self):
        return self.url


def item(**changes):
    values = dict(
        item_id="synthetic",
        kind="experiment",
        version="1.0.0",
        title="Synthetic project",
        description="Test bytes only",
        experiment_category="fpvs_oddball",
        filename="synthetic.fpvsbundle",
        size_bytes=len(PAYLOAD),
        uncompressed_size_bytes=100,
        file_count=2,
        sha256=hashlib.sha256(PAYLOAD).hexdigest(),
        min_studio_version="1.8.0",
    )
    values.update(changes)
    return LibraryItem(**values)


def catalog(*items):
    return dict(
        schema_version="1.0", library_name="Test library", items=[i.model_dump() for i in items]
    )


@pytest.fixture
def environment(tmp_path, monkeypatch):
    # Network cases exercise file I/O/locking with synthetic workspace bytes. Native
    # cache ACL acceptance is separate, since the local sandbox denies WRITE_DAC.
    monkeypatch.setattr(cache_module, "_private_directory", lambda path: None)
    store = MemoryStore()
    requests = []
    replies = []

    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            assert timeout == 10
            assert replies, "unexpected HTTP request"
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            if callable(reply):
                return reply(request)
            return Response(reply, request.full_url)

    monkeypatch.setattr(client_module, "build_opener", lambda *handlers: Opener())
    client = LibraryClient(ORIGIN, credential_store=store, cache_root=tmp_path / "cache")
    yield client, store, requests, replies
    client.release_download()


def payload_reply(payload=PAYLOAD, **kwargs):
    return lambda request: Response(
        payload, request.full_url, content_type="application/octet-stream", **kwargs
    )


def test_enrollment_persists_token_before_http_and_reuses_lost_response(environment):
    client, store, requests, replies = environment
    store.value = None

    def fail_after_registration(request):
        submitted = json.loads(request.data)
        assert store.value.token == submitted["device_token"]
        assert store.value.connection is None
        raise URLError("lost response containing secret")

    replies.append(fail_after_registration)
    with pytest.raises(LibraryError, match="connection"):
        client.enroll("INVITE", "Lab machine")
    pending_token = store.value.token
    assert len(pending_token) >= 43
    replies.append(dict(schema_version="1.0", device_id="device-1", library_name="Test library"))
    connection = client.enroll("INVITE", "Changed device name")
    assert connection.device_name == "Lab machine"
    assert json.loads(requests[1].data)["device_token"] == pending_token
    assert client.connection_info() == connection


def test_secure_store_failure_prevents_enrollment_request(environment):
    client, store, requests, _ = environment
    store.value = None
    store.fail_save = True
    with pytest.raises(LibraryError, match="storage"):
        client.enroll("INVITE", "Machine")
    assert requests == []


def test_catalog_uses_bearer_token_and_experiment_filter(environment):
    client, store, requests, replies = environment
    replies.append(catalog(item()))
    result = client.catalog()
    assert result.items[0].title == "Synthetic project"
    assert requests[0].full_url == ORIGIN + "/v1/catalog?kind=experiment"
    assert requests[0].get_header("Authorization") == f"Bearer {store.value.token}"


@pytest.mark.parametrize(
    "status, error_type",
    [
        (401, LibraryAuthorizationError),
        (403, LibraryAuthorizationError),
        (404, LibraryError),
        (410, LibraryError),
        (429, LibraryError),
        (503, LibraryError),
        (302, LibraryError),
    ],
)
def test_http_errors_do_not_expose_bodies_or_credentials(environment, status, error_type):
    client, _, _, replies = environment
    replies.append(HTTPError(ORIGIN, status, "PRIVATE DETAIL", {}, io.BytesIO(b"SECRET")))
    with pytest.raises(error_type) as error:
        client.catalog()
    assert "PRIVATE" not in str(error.value)
    assert "SECRET" not in str(error.value)


@pytest.mark.parametrize("raw", [b"not json", b"[[]]", b'{"schema_version":"2.0"}', b"{" * 1500])
def test_catalog_rejects_malformed_schema_and_nested_response(environment, raw):
    client, _, _, replies = environment
    replies.append(raw)
    with pytest.raises(LibraryError):
        client.catalog()


def test_catalog_response_is_bounded(environment, monkeypatch):
    client, _, _, replies = environment
    replies.append(b"x" * (1024 * 1024 + 1))
    with pytest.raises(LibraryError, match="size limit"):
        client.catalog()


@pytest.mark.parametrize(
    "changes",
    [
        dict(item_id="../escape"),
        dict(filename="C:\\escape.fpvsbundle"),
        dict(filename="CON.fpvsbundle"),
        dict(filename="test.py"),
        dict(kind="condition"),
        dict(version="../1.0"),
        dict(min_studio_version="invalid"),
        dict(sha256="0" * 63),
        dict(size_bytes=MAX_DOWNLOAD_BYTES + 1),
        dict(size_bytes=True),
        dict(file_count=50001),
        dict(uncompressed_size_bytes=20 * 1024**3 + 1),
        dict(experiment_category="future"),
    ],
)
def test_catalog_contract_rejects_untrusted_metadata(changes):
    with pytest.raises(ValidationError):
        item(**changes)


def test_catalog_rejects_duplicate_versions_and_missing_schema():
    with pytest.raises(ValidationError):
        LibraryCatalog.model_validate(catalog(item(), item()))
    raw = catalog(item())
    del raw["schema_version"]
    with pytest.raises(ValidationError):
        LibraryCatalog.model_validate(raw)


def test_download_verifies_hash_size_and_retains_exclusive_lease(environment):
    client, _, requests, replies = environment
    replies.append(payload_reply(headers={"Content-Length": str(len(PAYLOAD))}))
    progress = []
    path = client.download(
        item(), progress_callback=lambda received, total: progress.append((received, total))
    )
    assert path.read_bytes() == PAYLOAD
    assert progress[-1] == (len(PAYLOAD), len(PAYLOAD))
    assert requests[0].full_url.endswith("/v1/items/synthetic/versions/1.0.0/download")
    second = DownloadCache(path.parent)
    with pytest.raises(LibraryError, match="Another"):
        second.acquire()
    client.release_download()
    second.acquire()
    second.release()


@pytest.mark.parametrize("payload", [PAYLOAD[:-1], b"x" * len(PAYLOAD), PAYLOAD + b"x"])
def test_failed_download_removes_partial_and_releases_lock(environment, payload):
    client, _, _, replies = environment
    replies.append(payload_reply(payload))
    with pytest.raises(LibraryError, match="size|integrity"):
        client.download(item())
    assert list(client._cache.root.glob("*.part")) == []
    assert list(client._cache.root.glob("*.fpvsbundle")) == []
    lock = DownloadCache(client._cache.root)
    lock.acquire()
    lock.release()


def test_download_cancellation_cleans_partial(environment):
    client, _, _, replies = environment
    replies.append(payload_reply())
    cancel = Event()
    with pytest.raises(LibraryCancelled):
        client.download(item(), cancel_event=cancel, progress_callback=lambda *_: cancel.set())
    assert list(client._cache.root.glob("*.part")) == []
    assert list(client._cache.root.glob("*.fpvsbundle")) == []


def test_pre_cancellation_does_not_touch_store_cache_or_network(environment):
    client, _, requests, _ = environment
    cancel = Event()
    cancel.set()
    with pytest.raises(LibraryCancelled):
        client.catalog(cancel_event=cancel)
    assert not client._cache.root.exists()
    assert requests == []


def test_cached_payload_rehashed_and_still_requires_authorization(environment):
    client, _, requests, replies = environment
    replies.append(payload_reply())
    path = client.download(item())
    client.release_download()
    replies.append(catalog(item()))
    assert client.download(item()) == path
    assert requests[-1].full_url.endswith("catalog?kind=experiment")
    client.release_download()
    path.write_bytes(b"x" * len(PAYLOAD))
    replies.append(payload_reply())
    assert client.download(item()).read_bytes() == PAYLOAD
    assert requests[-1].full_url.endswith("download")


def test_cached_withdrawn_item_is_not_importable(environment):
    client, _, _, replies = environment
    replies.append(payload_reply())
    client.download(item())
    client.release_download()
    replies.append(catalog())
    with pytest.raises(LibraryError, match="withdrawn"):
        client.download(item())


def test_new_payload_replaces_only_recognized_cache_files(environment):
    client, _, _, replies = environment
    replies.append(payload_reply())
    first = client.download(item())
    client.release_download()
    preserved = first.parent / "user-notes.txt"
    preserved.write_text("user-owned")
    new_bytes = b"different example"
    new_item = item(
        item_id="other", size_bytes=len(new_bytes), sha256=hashlib.sha256(new_bytes).hexdigest()
    )
    replies.append(payload_reply(new_bytes))
    second = client.download(new_item)
    assert second.read_bytes() == new_bytes
    assert not first.exists()
    assert preserved.read_text() == "user-owned"
    assert len(list(first.parent.glob("*.fpvsbundle"))) == 1


def test_incompatible_item_does_not_request_download(environment):
    client, _, requests, _ = environment
    incompatible = item(min_studio_version="999.0.0")
    assert not incompatible.compatible
    with pytest.raises(LibraryError, match="Requires"):
        client.download(incompatible)
    assert requests == []


def test_disconnect_requires_remote_revocation_before_local_deletion(environment):
    client, store, requests, replies = environment
    replies.append(URLError("offline"))
    with pytest.raises(LibraryError):
        client.disconnect()
    assert store.value is not None
    replies.append(dict(schema_version="1.0", revoked=True))
    client.disconnect()
    assert store.value is None
    assert requests[-1].method == "DELETE"


def test_disconnect_clears_already_revoked_credentials(environment):
    client, store, _, replies = environment
    replies.append(HTTPError(ORIGIN, 401, "revoked", {}, None))
    client.disconnect()
    assert store.value is None


@pytest.mark.parametrize(
    "origin",
    [
        "http://library.test",
        "https://user:secret@library.test",
        "https://library.test/path",
        "https://library.test?query=yes",
        "https://library.test:bad",
        "https://library.test/#fragment",
    ],
)
def test_service_origin_cannot_contain_redirect_credentials_or_path(tmp_path, origin):
    with pytest.raises(LibraryError):
        LibraryClient(origin, credential_store=MemoryStore(), cache_root=tmp_path)


def test_unexpected_final_url_or_content_encoding_is_rejected(environment):
    client, _, _, replies = environment
    replies.append(lambda _: Response(catalog(), "https://elsewhere.test"))
    with pytest.raises(LibraryError, match="location"):
        client.catalog()
    replies.append(
        lambda request: Response(catalog(), request.full_url, headers={"Content-Encoding": "gzip"})
    )
    with pytest.raises(LibraryError, match="compressed"):
        client.catalog()


def test_declared_download_size_change_is_rejected(environment):
    client, _, _, replies = environment
    replies.append(payload_reply(headers={"Content-Length": "999"}))
    with pytest.raises(LibraryError, match="size changed"):
        client.download(item())


def test_hardlinked_payload_is_rejected_without_deleting_the_original(environment, tmp_path):
    client, _, _, replies = environment
    replies.append(payload_reply())
    target = client.download(item())
    client.release_download()
    outside = tmp_path / "original.bin"
    target.replace(outside)
    target.hardlink_to(outside)
    with pytest.raises(LibraryError, match="unsafe"):
        client.download(item())
    assert outside.read_bytes() == PAYLOAD


def test_linked_cache_root_is_rejected(environment, tmp_path):
    client, _, _, _ = environment
    actual = tmp_path / "actual"
    actual.mkdir()
    try:
        client._cache.root.symlink_to(actual, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires Windows developer mode or elevated privilege")
    with pytest.raises(LibraryError, match="link"):
        client.catalog()
    assert list(actual.iterdir()) == []


def test_total_deadline_is_checked_between_reads(environment, monkeypatch):
    client, _, _, replies = environment
    replies.append(catalog(item()))
    ticks = iter([0.0, 31.0])
    monkeypatch.setattr(client_module.time, "monotonic", lambda: next(ticks))
    with pytest.raises(LibraryError, match="timed out"):
        client.catalog()


def test_disk_full_is_reported_and_partial_removed(environment, monkeypatch):
    client, _, _, replies = environment
    replies.append(payload_reply())
    original = client._cache.create_partial

    class FullDisk:
        def write(self, chunk):
            raise OSError(28, "synthetic full disk")

    @contextmanager
    def full_disk():
        with original():
            yield FullDisk()

    monkeypatch.setattr(client._cache, "create_partial", full_disk)
    with pytest.raises(LibraryError, match="storage.*full"):
        client.download(item())
    assert list(client._cache.root.glob("*.part")) == []


def test_interrupted_read_does_not_expose_transport_error(environment):
    client, _, _, replies = environment

    class Interrupted(Response):
        def read1(self, count):
            raise TimeoutError("secret network diagnostic")

    replies.append(lambda request: Interrupted({}, request.full_url))
    with pytest.raises(LibraryError, match="interrupted") as error:
        client.catalog()
    assert "secret" not in str(error.value)


def test_mutated_item_cannot_bypass_validated_download_route(environment):
    client, _, requests, _ = environment
    altered = item().model_copy(update={"item_id": "../elsewhere"})
    with pytest.raises(LibraryError, match="invalid metadata"):
        client.download(altered)
    assert requests == []
