"""Repair reporting matches Studio's protocol without importing its dependencies at runtime."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from email.message import Message
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from fpvs_studio.support.models import Draft, Report

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "macos_repair_reporting", ROOT / "macos_repair_environment.py",
)
assert SPEC is not None and SPEC.loader is not None
repair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair)
ORIGIN = "https://reports.zack-murphy.com"
INTENT = {"intent_id": "i" * 16, "browser_token": "b" * 32, "desktop_token": "d" * 32}


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Tests must replace every native, browser and network action.")

    monkeypatch.setattr("urllib.request.build_opener", unexpected)
    monkeypatch.setattr("webbrowser.open", unexpected)
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("platform.release", lambda: "25.0")
    monkeypatch.setattr(repair.subprocess, "run", unexpected)
    monkeypatch.setattr(repair, "_native_dialog", unexpected, raising=False)
    monkeypatch.setattr(
        repair, "_redact", lambda text: text.replace("private-secret", "<redacted>"), raising=False,
    )
    monkeypatch.setattr(repair, "_private_json", lambda path, data: path.write_text(
        json.dumps(data), encoding="utf-8"), raising=False)
    monkeypatch.delenv("FPVS_REPORT_SERVICE_URL", raising=False)


@pytest.fixture
def diagnostic(tmp_path):
    path = tmp_path / "repair.log"
    path.write_text("Engine probe failed: private-secret\n", encoding="utf-8")
    return path


def _flow(monkeypatch, diagnostic, *, upload_error=False):
    calls = []

    def request(origin, method, path, *, data=None, token=""):
        assert origin == ORIGIN
        calls.append((method, path, data, token))
        if path == "/v1/intents":
            return INTENT
        if path.startswith("/v1/intents/"):
            return {"state": "verified"}
        saved = repair._report_load(diagnostic.with_suffix(".report.json"))
        assert saved["delivery"] == "uncertain"
        if upload_error:
            raise ValueError("Connection lost; check status.")
        return {"report_id": saved["report"]["report_id"], "state": "submitted"}

    monkeypatch.setattr(repair, "_report_request", request)
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url, new: opened.append(url) or True)
    return calls, opened


def test_report_payload_and_saved_receipt_match_studio_contract(monkeypatch, diagnostic):
    calls, opened = _flow(monkeypatch, diagnostic)
    message = repair._send_repair_report(diagnostic, "Repair failed: private-secret", "2.8.1")
    saved = repair._report_load(diagnostic.with_suffix(".report.json"))
    draft = Draft.model_validate(saved)
    assert not draft.report.problems()
    assert draft.delivery == "submitted"
    assert draft.report.payload() == calls[2][2]
    assert repair._report_bytes(saved["report"]) == draft.report.payload()
    request = json.loads(calls[0][2])
    assert request["payload_sha256"] == draft.report.digest()
    expected_receipt_hash = hashlib.sha256(draft.receipt_token.encode()).hexdigest()
    assert request["receipt_token_sha256"] == expected_receipt_hash
    assert calls[1][3] == calls[2][3] == INTENT["desktop_token"]
    assert "private-secret" not in draft.report.payload().decode()
    assert opened == [ORIGIN + "/verify#intent_id=" + "i" * 16 + "&token=" + "b" * 32]
    assert "submitted" in message
    assert draft.receipt_token not in message


def test_ambiguous_upload_keeps_identity_and_only_checks_status(monkeypatch, diagnostic):
    calls, opened = _flow(monkeypatch, diagnostic, upload_error=True)
    with pytest.raises(ValueError, match="Connection lost"):
        repair._send_repair_report(diagnostic, "Repair failed", "2.8.1")
    saved = repair._report_load(diagnostic.with_suffix(".report.json"))
    assert saved["delivery"] == "uncertain"
    previous_report = saved["report"]

    def check(origin, method, path, *, data=None, token=""):
        assert method == "GET"
        assert path == f"/v1/reports/{previous_report['report_id']}/status"
        assert token == saved["receipt_token"]
        return {"report_id": previous_report["report_id"], "state": "received"}

    monkeypatch.setattr(repair, "_report_request", check)
    repair._send_repair_report(diagnostic, "Changed outcome must not change payload", "9.9")
    assert repair._report_load(diagnostic.with_suffix(".report.json"))["report"] == previous_report
    assert len(opened) == 1
    assert sum(path.startswith("/v1/reports?") for _, path, _, _ in calls) == 1


def test_receipt_must_be_durable_before_upload(monkeypatch, diagnostic):
    calls, _ = _flow(monkeypatch, diagnostic)
    write = repair._private_json

    def fail_uncertain(path, draft):
        if draft["delivery"] == "uncertain":
            raise PermissionError("synthetic permission failure")
        write(path, draft)

    monkeypatch.setattr(repair, "_private_json", fail_uncertain)
    with pytest.raises(ValueError, match="receipt could not be saved"):
        repair._send_repair_report(diagnostic, "Repair failed", "2.8.1")
    assert all(not path.startswith("/v1/reports?") for _, path, _, _ in calls)


@pytest.mark.parametrize("value", ["", "http://reports.zack-murphy.com", "https://example.com"])
def test_disabled_or_unapproved_endpoint_never_connects(monkeypatch, diagnostic, value):
    monkeypatch.setenv("FPVS_REPORT_SERVICE_URL", value)
    with pytest.raises(ValueError):
        repair._send_repair_report(diagnostic, "Repair failed", "2.8.1")
    assert not diagnostic.with_suffix(".report.json").exists()


def test_log_is_redacted_utf8_bounded_and_preserves_failure_tail(diagnostic):
    diagnostic.write_text("Interpreter: ARM64 Python 3.10\n" + "é" * 200_000
                          + "\nFailure: private-secret", encoding="utf-8")
    payload = repair._report_payload(diagnostic, "Failed", "2.8.1")
    assert len(payload["diagnostics"].encode("utf-8")) <= 256 * 1024
    assert payload["diagnostics"].startswith("Interpreter: ARM64 Python 3.10")
    assert "[Middle log text omitted" in payload["diagnostics"]
    assert payload["diagnostics"].endswith("Failure: <redacted>")
    assert not Report.model_validate(payload).problems()


def test_corrupt_receipt_does_not_start_another_report(diagnostic):
    diagnostic.with_suffix(".report.json").write_text('{"receipt_token":"private-secret"}')
    with pytest.raises(ValueError, match="preserved") as error:
        repair._send_repair_report(diagnostic, "Failed", "2.8.1")
    assert "private-secret" not in str(error.value)


@pytest.mark.parametrize("status", ["expired", "unexpected"])
def test_verification_failure_never_uploads(monkeypatch, diagnostic, status):
    calls, _ = _flow(monkeypatch, diagnostic)
    request = repair._report_request

    def verify(origin, method, path, **kwargs):
        if path.startswith("/v1/intents/"):
            return {"state": status}
        return request(origin, method, path, **kwargs)

    monkeypatch.setattr(repair, "_report_request", verify)
    with pytest.raises(ValueError):
        repair._send_repair_report(diagnostic, "Failed", "2.8.1")
    assert repair._report_load(diagnostic.with_suffix(".report.json"))["delivery"] == "editing"
    assert len(calls) == 1


def _response(monkeypatch, body=b"{}", *, content_type="application/json", encoding="identity"):
    response = BytesIO(body)
    response.headers = Message()
    response.headers["Content-Type"] = content_type
    response.headers["Content-Encoding"] = encoding

    def opener(handler):
        assert handler.redirect_request(None, None, 302, "", {}, "https://elsewhere") is None

        def open_request(request, timeout):
            assert request.full_url == ORIGIN + "/v1/intents"
            assert request.get_header("Accept-encoding") == "identity"
            assert timeout == 10
            return response

        return SimpleNamespace(open=open_request)

    monkeypatch.setattr("urllib.request.build_opener", opener)
    return response


def test_transport_is_bounded_json_and_rejects_redirects(monkeypatch):
    _response(monkeypatch)
    assert repair._report_request(ORIGIN, "POST", "/v1/intents", data=b"{}") == {}


@pytest.mark.parametrize("body,kind,encoding", [
    (b"x" * (16 * 1024 + 1), "application/json", "identity"),
    (b"{}", "text/html", "identity"), (b"{}", "application/json", "gzip"),
    (b"[]", "application/json", "identity"), (b"private-secret", "application/json", "identity"),
])
def test_transport_rejects_unsafe_responses_without_echoing_them(monkeypatch, body, kind, encoding):
    _response(monkeypatch, body, content_type=kind, encoding=encoding)
    with pytest.raises(ValueError) as error:
        repair._report_request(ORIGIN, "GET", "/v1/intents")
    assert "private-secret" not in str(error.value)


def test_http_404_is_not_an_authoritative_not_received_receipt(monkeypatch):
    def failed(request, timeout):
        raise HTTPError(request.full_url, 404, "private-secret", {}, BytesIO(b"private-secret"))

    monkeypatch.setattr("urllib.request.build_opener", lambda *_: SimpleNamespace(open=failed))
    with pytest.raises(ValueError, match="check report status") as error:
        repair._report_request(ORIGIN, "GET", "/v1/intents", token="private-secret")
    assert "private-secret" not in str(error.value)


def test_close_does_not_send_or_save_report(monkeypatch, diagnostic):
    monkeypatch.setattr(repair, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(repair, "_native_dialog", lambda *_: "Close")
    repair._offer_report(diagnostic, "Failed", "2.8.1")
    assert not diagnostic.with_suffix(".report.json").exists()


def test_copy_uses_stdin_and_never_submits(monkeypatch, diagnostic):
    monkeypatch.setattr(repair, "sys", SimpleNamespace(platform="darwin"))
    dialogs = iter(["Copy Log", "Close"])
    monkeypatch.setattr(repair, "_native_dialog", lambda *_: next(dialogs))
    copied = []
    monkeypatch.setattr(repair.subprocess, "run", lambda command, **kwargs: copied.append(
        (command, kwargs)))
    repair._offer_report(diagnostic, "Failed", "2.8.1")
    assert copied[0][0] == ["/usr/bin/pbcopy"]
    assert copied[0][1]["input"].rstrip().endswith("<redacted>")
    assert not diagnostic.with_suffix(".report.json").exists()


def test_uncertain_upload_offers_check_status_immediately(monkeypatch, diagnostic):
    monkeypatch.setattr(repair, "sys", SimpleNamespace(platform="darwin"))
    calls, _ = _flow(monkeypatch, diagnostic, upload_error=True)
    dialogs = []

    def dialog(message, buttons, default):
        dialogs.append((message, buttons))
        return "Send Error Report" if len(dialogs) == 1 else "Close"

    monkeypatch.setattr(repair, "_native_dialog", dialog)
    repair._offer_report(diagnostic, "Failed", "2.8.1")
    assert "Check Status" in dialogs[1][1]
    assert "Send Error Report" not in dialogs[1][1]
    assert sum(path.startswith("/v1/reports?") for _, path, _, _ in calls) == 1


def test_corrupt_receipt_still_allows_copying_diagnostics(monkeypatch, diagnostic):
    monkeypatch.setattr(repair, "sys", SimpleNamespace(platform="darwin"))
    diagnostic.with_suffix(".report.json").write_text("invalid receipt")
    dialogs = []

    def dialog(message, buttons, default):
        dialogs.append(buttons)
        return "Close"

    monkeypatch.setattr(repair, "_native_dialog", dialog)
    repair._offer_report(diagnostic, "Failed", "2.8.1")
    assert dialogs == [("Close", "Copy Log")]


def test_verification_retry_keeps_original_frozen_payload(monkeypatch, diagnostic):
    calls, _ = _flow(monkeypatch, diagnostic)
    monkeypatch.setattr("webbrowser.open", lambda *_args, **_kwargs: False)
    with pytest.raises(ValueError, match="could not open"):
        repair._send_repair_report(diagnostic, "First failure", "2.8.1")
    first_hash = json.loads(calls[0][2])["payload_sha256"]
    diagnostic.write_text("New log contents")
    monkeypatch.setattr("webbrowser.open", lambda *_args, **_kwargs: True)
    repair._send_repair_report(diagnostic, "Changed outcome", "9.9")
    assert json.loads(calls[1][2])["payload_sha256"] == first_hash
    assert json.loads(calls[-1][2])["happened"] == "First failure"


def test_pending_verification_times_out_without_upload(monkeypatch, diagnostic):
    now = [0]
    monkeypatch.setattr("time.monotonic", lambda: now[0])
    monkeypatch.setattr("time.sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    monkeypatch.setattr("webbrowser.open", lambda *_args, **_kwargs: True)
    calls = []

    def request(origin, method, path, **kwargs):
        calls.append((method, path))
        return INTENT if path == "/v1/intents" else {"state": "pending"}

    monkeypatch.setattr(repair, "_report_request", request)
    with pytest.raises(ValueError, match="timed out"):
        repair._send_repair_report(diagnostic, "Failed", "2.8.1")
    assert now[0] == 120
    assert not any(path.startswith("/v1/reports?") for _, path in calls)


def test_transport_enforces_total_response_deadline(monkeypatch):
    _response(monkeypatch)
    ticks = iter((0, 1, 31))
    monkeypatch.setattr("time.monotonic", lambda: next(ticks))
    with pytest.raises(ValueError, match="could not complete"):
        repair._report_request(ORIGIN, "GET", "/v1/intents")


def test_json_expansion_cannot_exceed_payload_or_receipt_limit(diagnostic):
    diagnostic.write_bytes(b"\x00" * (256 * 1024))
    with pytest.raises(ValueError, match="too large"):
        repair._send_repair_report(diagnostic, "Failed", "2.8.1")
    assert not diagnostic.with_suffix(".report.json").exists()
