"""Synthetic hostile transfer responses; never contact remote services."""

from __future__ import annotations

from email.message import Message
from io import BytesIO
from threading import Event
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request

import pytest

from fpvs_studio.data_sharing import client as sharing
from fpvs_studio.developer import catalog_publisher as publisher
from fpvs_studio.support import client as support
from fpvs_studio.updates import patches, validation


@pytest.mark.parametrize("url", [
    "http://github.com/file", "https://evil.example/file", "https://127.0.0.1/file",
    "https://github.com@evil.example/file", "https://github.com:444/file",
    "https://github.com/file\n", "https://github.com/file#fragment",
])
def test_update_redirect_is_rejected_before_following(monkeypatch, url):
    followed = []
    monkeypatch.setattr(
        HTTPRedirectHandler, "redirect_request", lambda *args: followed.append(args),
    )
    with pytest.raises(validation.UpdateError):
        validation.UpdateRedirectHandler().redirect_request(
            Request("https://github.com/source"), None, 302, "", Message(), url,
        )
    assert followed == []


def test_official_signed_cdn_redirect_remains_supported():
    url = "https://release-assets.githubusercontent.com/file?signature=synthetic"
    request = validation.UpdateRedirectHandler().redirect_request(
        Request("https://github.com/source"), None, 302, "", Message(), url,
    )
    assert request.full_url == url


class Response(BytesIO):
    def __init__(self, payload=b"{}"):
        super().__init__(payload)
        self.headers = Message()
        self.headers["Content-Type"] = "application/json"
        self.headers["Content-Encoding"] = "identity"
        self.status = 200

    def read(self, *args):
        pytest.fail("A peer must not hold a filling read open between deadline checks")

    def read1(self, size=-1):
        return BytesIO.read(self, size)


def opener(response):
    class Opener:
        def open(self, *args, **kwargs):
            return response
    return Opener()


def test_results_response_uses_single_socket_reads(monkeypatch):
    response = Response()
    monkeypatch.setattr(sharing, "build_opener", lambda *_: opener(response))
    assert sharing.http_transport("GET", "https://results.invalid", None, {}, Event()) == b"{}"
    assert response.closed


def test_results_cancel_during_read_is_checked_before_success(monkeypatch):
    response = Response(b"")
    cancel = Event()
    def read1(size):
        cancel.set()
        return b""
    response.read1 = read1
    monkeypatch.setattr(sharing, "build_opener", lambda *_: opener(response))
    with pytest.raises(sharing.DataSharingCancelled):
        sharing.http_transport("GET", "https://results.invalid", None, {}, cancel)
    assert response.closed


def test_results_http_error_closes_body(monkeypatch):
    body = BytesIO(b"untrusted error")
    error = HTTPError("https://results.invalid", 403, "", Message(), body)
    class Opener:
        def open(self, *args, **kwargs):
            raise error
    monkeypatch.setattr(sharing, "build_opener", lambda *_: Opener())
    with pytest.raises(sharing.DataSharingError):
        sharing.http_transport("GET", "https://results.invalid", None, {}, Event())
    assert body.closed


def test_support_response_uses_single_socket_reads(monkeypatch):
    response = Response()
    monkeypatch.setattr(support, "build_opener", lambda *_: opener(response))
    assert support.http_transport("GET", support.SERVICE_ORIGIN, None, {}) == b"{}"


def test_support_rejects_deeply_nested_json_as_protocol_error():
    client = support.ReportClient(support.SERVICE_ORIGIN, transport=lambda *_: b"["*2000+b"]"*2000)
    with pytest.raises(support.ReportServiceError):
        client._request("GET", "/v1/intents")


@pytest.mark.parametrize("module,call", [
    (sharing, lambda: sharing.http_transport("GET", "https://results.invalid", None, {}, Event())),
    (support, lambda: support.http_transport("GET", support.SERVICE_ORIGIN, None, {})),
])
def test_trickling_response_expires_even_on_eof(monkeypatch, module, call):
    response = Response()
    now = [0.0]
    def read1(size):
        now[0] = 31.0
        return b""
    response.read1 = read1
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(module, "build_opener", lambda *_: opener(response))
    with pytest.raises((sharing.DataSharingError, support.ReportServiceError), match="timed out"):
        call()
    assert response.closed


def test_publisher_response_uses_single_socket_reads(monkeypatch):
    response = Response()
    api = publisher.GitHubPublisher("synthetic")
    api._opener = opener(response)
    assert api.request("GET", publisher.REPO_PATH) == {}


def test_publisher_cancel_during_response_preserves_uncertain_delivery():
    response = Response()
    cancel = Event()
    def read1(size):
        cancel.set()
        return b""
    response.read1 = read1
    api = publisher.GitHubPublisher("synthetic", cancel)
    api._opener = opener(response)
    with pytest.raises(publisher.CatalogCancelled):
        api.request("GET", publisher.REPO_PATH)
    assert response.closed


def test_patch_metadata_http_error_closes_body(monkeypatch):
    url = "https://github.com/zcm58/FPVS-Studio-2.0/releases/download/v1.5.1/FPVS-Studio-Update-1.5.1.json"
    body = BytesIO(b"untrusted error")
    error = HTTPError(url, 403, "", Message(), body)
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(patches, "urlopen", fail)
    metadata = {
        "name": "FPVS-Studio-Update-1.5.1.json", "browser_download_url": url,
        "id": 1, "size": 2, "digest": "sha256:" + "a" * 64,
    }
    with pytest.raises(validation.UpdateError):
        patches._fetch_manifest(metadata, "1.5.1", None)
    assert body.closed


def test_deep_revocation_json_is_protocol_error_and_preserves_credential(tmp_path, monkeypatch):
    client = sharing.DataSharingClient(
        "https://openfpvs.com", transport=lambda *_: b"[" * 2000 + b"]" * 2000,
    )
    monkeypatch.setattr(client, "_load_credential", lambda *_: SimpleNamespace(token="synthetic"))
    def never_delete(*args):
        pytest.fail("Invalid revocation confirmation must preserve the credential")
    monkeypatch.setattr(client, "_store", never_delete)
    with pytest.raises(sharing.DataSharingError, match="Invalid revocation"):
        client.disconnect(tmp_path, SimpleNamespace(protocol_sha256="a" * 64), Event())
