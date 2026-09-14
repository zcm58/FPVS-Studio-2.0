"""The future service must satisfy this desktop protocol; never contact a live host."""

from __future__ import annotations

import hashlib
import json
from email.message import Message
from io import BytesIO
from threading import Event

import pytest

from fpvs_studio.support.client import (
    SERVICE_ORIGIN,
    ReportCancelled,
    ReportClient,
    ReportServiceError,
    _NoRedirect,
    http_transport,
)
from fpvs_studio.support.models import Draft, Intent, Report


def test_http_transport_identifies_application_without_changing_auth(monkeypatch):
    response = BytesIO(b"{}")
    response.headers = Message()
    response.headers["Content-Type"] = "application/json"

    class Opener:
        def open(self, request, timeout):
            assert request.get_header("User-agent") == "FPVS-Studio/1.0"
            assert request.get_header("Authorization") == "Bearer synthetic"
            assert timeout == 10
            return response

    monkeypatch.setattr("fpvs_studio.support.client.build_opener", lambda *_: Opener())
    headers = {"Authorization": "Bearer synthetic"}
    assert http_transport("GET", SERVICE_ORIGIN, None, headers) == b"{}"


def intent():
    return Intent(intent_id="i" * 20, browser_token="b" * 43, desktop_token="d" * 43)


def test_feature_submission_uses_shared_receipts_and_minimal_payload():
    report = Draft(report=Report(kind="feature", happened="Please add keyboard shortcuts"))
    calls = []

    def transport(method, url, data, headers):
        calls.append(json.loads(data))
        if url.endswith("/v1/intents"):
            return intent().model_dump_json().encode()
        return json.dumps({"report_id": str(report.report.report_id), "state": "received"}).encode()

    client = ReportClient(SERVICE_ORIGIN, transport=transport)
    grant = client.create_intent(report, Event())
    assert calls[0]["payload_sha256"] == report.report.digest()
    report.delivery = "uncertain"
    report.service_url = SERVICE_ORIGIN
    assert client.submit(report, grant, Event()).state == "received"
    assert calls[1]["kind"] == "feature"
    assert calls[1]["description"] == report.report.happened
    assert "diagnostics" not in calls[1]


def draft():
    return Draft(
        report=Report(
            title="Save error", happened="The editor stopped.", diagnostics="private diagnostics"
        )
    )


def test_production_default_explicit_disable_and_rejects_other_origins(monkeypatch):
    monkeypatch.delenv("FPVS_REPORT_SERVICE_URL", raising=False)
    client = ReportClient.configured()
    assert client.enabled
    assert client.origin == SERVICE_ORIGIN
    monkeypatch.setenv("FPVS_REPORT_SERVICE_URL", "")
    client = ReportClient.configured()
    assert not client.enabled
    with pytest.raises(ReportServiceError, match="not connected"):
        client.create_intent(draft(), Event())
    for value in (
        "http://reports.zack-murphy.com",
        "https://evil.example",
        SERVICE_ORIGIN + "/",
        SERVICE_ORIGIN + "@evil.example",
    ):
        with pytest.raises(ValueError):
            ReportClient(value)


def test_intent_sends_hashes_only_and_browser_capability_is_separate():
    calls = []

    def transport(method, url, data, headers):
        calls.append((method, url, json.loads(data), headers))
        return intent().model_dump_json().encode()

    client = ReportClient(SERVICE_ORIGIN, transport=transport)
    report = draft()
    result = client.create_intent(report, Event())
    body = calls[0][2]
    assert body["payload_sha256"] == report.report.digest()
    assert body["receipt_token_sha256"] == hashlib.sha256(report.receipt_token.encode()).hexdigest()
    assert "private diagnostics" not in str(calls)
    assert report.receipt_token not in str(calls)
    url = client.verification_url(result)
    assert result.browser_token in url.split("#")[1]
    assert result.desktop_token not in url
    assert "private" not in url


def test_submit_requires_saved_identity_and_status_uses_separate_receipt_token():
    calls = []
    report = draft()

    def transport(method, url, data, headers):
        calls.append((method, url, data, headers))
        return json.dumps({"report_id": str(report.report.report_id), "state": "received"}).encode()

    client = ReportClient(SERVICE_ORIGIN, transport=transport)
    with pytest.raises(ReportServiceError, match="receipt"):
        client.submit(report, intent(), Event())
    report.delivery, report.service_url = "uncertain", SERVICE_ORIGIN
    report.include_logs = False
    assert client.submit(report, intent(), Event()).state == "received"
    assert json.loads(calls[0][2])["diagnostics"] == ""
    assert calls[0][3]["Authorization"] == "Bearer " + intent().desktop_token
    assert client.check_receipt(report, Event()).state == "received"
    assert calls[1][3]["Authorization"] == "Bearer " + report.receipt_token
    assert calls[1][2] is None


@pytest.mark.parametrize(
    "response", [b"[]", b"broken", b"x" * 20000, b'{"report_id":"wrong","state":"submitted"}']
)
def test_malformed_receipts_never_claim_success(response):
    report = draft()
    report.delivery, report.service_url = "uncertain", SERVICE_ORIGIN
    client = ReportClient(SERVICE_ORIGIN, transport=lambda *args: response)
    with pytest.raises(ReportServiceError):
        client.check_receipt(report, Event())


def test_cancel_before_request_never_calls_transport():
    def transport(*args):
        pytest.fail("No network request should be made")

    client = ReportClient(SERVICE_ORIGIN, transport=transport)
    cancel = Event()
    cancel.set()
    with pytest.raises(ReportCancelled):
        client.create_intent(draft(), cancel)


def test_untrusted_verification_data_and_redirects_are_rejected():
    client = ReportClient(SERVICE_ORIGIN, transport=lambda *args: b'{"url":"https://evil.example"}')
    with pytest.raises(ReportServiceError):
        client.create_intent(draft(), Event())
    assert _NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example") is None


def test_receipt_network_failure_does_not_mutate_identity_or_resubmit():
    report = draft()
    report.delivery, report.service_url = "uncertain", SERVICE_ORIGIN
    before = report.model_dump()
    calls = []

    def transport(method, *args):
        calls.append(method)
        raise ReportServiceError("Unavailable")

    client = ReportClient(SERVICE_ORIGIN, transport=transport)
    with pytest.raises(ReportServiceError):
        client.check_receipt(report, Event())
    assert calls == ["GET"]
    assert report.model_dump() == before
