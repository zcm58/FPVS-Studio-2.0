"""Synthetic crash recovery; no real credentials, research records or network."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from threading import Event
from uuid import uuid4

import pytest

from fpvs_studio.support.client import SERVICE_ORIGIN, ReportClient, ReportServiceError
from fpvs_studio.support.crash_reporting import (
    CrashConsent,
    CrashSession,
    CrashStore,
    process_alive,
    safe_frame,
)


@pytest.fixture
def crash_store(tmp_path, monkeypatch):
    monkeypatch.setattr("fpvs_studio.support.crash_reporting.process_alive", lambda pid: False)
    return CrashStore(tmp_path)


def session(store, consent=None, **fields):
    value = CrashSession(
        session_id=uuid4(),
        pid=123456,
        os_version="Synthetic OS",
        installation_id=consent.installation_id if consent else None,
        **fields,
    )
    store.save_session(value)
    return value


def enabled(store):
    value = CrashConsent(enabled=True)
    store.save_consent(value)
    return value


def test_on_by_default_persists_identity_and_never_backfills_historical_sessions(crash_store):
    old = session(crash_store)
    first = crash_store.consent()
    assert first.enabled and not first.registered
    assert CrashStore(crash_store.root).consent() == first
    assert crash_store.recover() == []
    assert crash_store._session_path(old).exists()


def test_existing_opt_out_survives_reloads_and_new_default(crash_store):
    consent = CrashConsent(enabled=False)
    crash_store.save_consent(consent)
    assert not CrashStore(crash_store.root).consent().enabled
    assert crash_store.recover() == []


def test_invalid_preference_never_becomes_default_enabled(crash_store):
    (crash_store.folder() / "consent.json").write_text("invalid")
    with pytest.raises(ValueError):
        crash_store.consent()


def test_native_recovery_contains_only_source_locations(crash_store):
    consent = enabled(crash_store)
    value = session(crash_store, consent)
    logs = crash_store.root / "logs"
    logs.mkdir()
    (logs / f"session-{value.session_id.hex}-native.log").write_text(
        "Qt fatal: participant=private-value token=private-secret\n"
        '  File "C:/Users/private/src/fpvs_studio/gui/workers.py", line 42 in run\n'
        '  File "C:/private/participant.py", line 7 in private_function\n',
        encoding="utf-8",
    )
    events = crash_store.recover()
    assert len(events) == 1
    event = events[0]
    assert event.report.crash_type == "native_fault"
    assert event.report.stack[0].module == "fpvs_studio/gui/workers.py"
    assert event.report.stack[1].module == "<external>"
    assert event.report.stack[1].function == "<external>"
    data = event.model_dump_json()
    assert "private" not in data and "secret" not in data and "participant" not in data
    assert crash_store.recover()[0].receipt_token == event.receipt_token


def test_live_and_clean_sessions_are_never_crashes(crash_store, monkeypatch):
    consent = enabled(crash_store)
    session(crash_store, consent, state="clean")
    active = session(crash_store, consent)
    monkeypatch.setattr(
        "fpvs_studio.support.crash_reporting.process_alive", lambda pid: pid == active.pid
    )
    assert crash_store.recover() == []


def test_unknown_unclean_exit_is_not_labeled_native_crash(crash_store):
    consent = enabled(crash_store)
    session(crash_store, consent)
    assert crash_store.recover()[0].report.crash_type == "unclean_shutdown"


def test_python_failure_uses_safe_frames_and_preserves_original_version(crash_store):
    consent = enabled(crash_store)
    session(
        crash_store,
        consent,
        state="failed",
        app_version="crashing-version",
        stack=[safe_frame("/app/fpvs_studio/app/main.py", "main", 42)],
    )
    event = crash_store.recover()[0]
    assert event.report.app_version == "crashing-version"
    assert event.report.crash_type == "python_exception"
    assert event.report.stack[0].module == "fpvs_studio/app/main.py"


def test_ambiguous_delivery_retries_same_identity_and_then_stops(crash_store):
    consent = enabled(crash_store)
    session(crash_store, consent)
    sent = []

    def transport(method, url, data, headers):
        assert url == SERVICE_ORIGIN + "/v1/crash-reports"
        sent.append(data)
        if len(sent) == 1:
            raise ReportServiceError("Synthetic lost response")
        report_id = json.loads(data)["report"]["report_id"]
        return json.dumps({"report_id": report_id, "state": "received"}).encode()

    client = ReportClient(SERVICE_ORIGIN, transport=transport)
    with pytest.raises(ReportServiceError):
        crash_store.deliver(client, Event())
    event = crash_store.pending()[0]
    assert event.attempts == 1 and event.next_attempt > time.time()
    event.next_attempt = 0
    crash_store.save_event(event)
    assert crash_store.deliver(client, Event()) == 1
    assert sent[0] == sent[1]
    assert crash_store.deliver(client, Event()) == 0
    assert crash_store.pending() == []


def test_disable_cancels_activation_discards_backlog_and_precedes_network(crash_store):
    consent = enabled(crash_store)
    session(crash_store, consent)
    crash_store.recover()
    disabled = crash_store.disable()
    assert not disabled.enabled and disabled.revoke_pending
    assert crash_store.pending() == []
    with pytest.raises(ValueError):
        crash_store.mark_registered(consent.installation_id, Event())
    client = ReportClient(SERVICE_ORIGIN, transport=lambda *args: pytest.fail("HTTP after opt-out"))
    assert crash_store.deliver(client, Event()) == 0


def test_cancel_or_replaced_generation_cannot_register(crash_store):
    cancel = Event()
    first = crash_store.consent()
    cancel.set()
    with pytest.raises(ValueError):
        crash_store.mark_registered(first.installation_id, cancel)
    crash_store.disable()
    disabled = crash_store.consent()
    second = crash_store.finish_revocation(disabled.installation_id, Event())
    assert not second.enabled
    second = crash_store.enable()
    with pytest.raises(ValueError):
        crash_store.mark_registered(first.installation_id, Event())
    assert crash_store.mark_registered(second.installation_id, Event()).registered


def test_reenable_revokes_old_generation_without_backfilling_opted_out_sessions(crash_store):
    first = crash_store.consent()
    session(crash_store, first)
    crash_store.disable()
    session(crash_store)
    consent = crash_store.enable()
    assert consent.enabled and consent.revoke_pending
    assert crash_store.recover() == []
    consent = crash_store.finish_revocation(consent.installation_id, Event())
    assert consent.enabled and consent.installation_id != first.installation_id
    assert crash_store.recover() == []
    session(crash_store, consent)
    assert len(crash_store.recover()) == 1


def test_registration_validates_response_and_keeps_same_capability_after_lost_response(crash_store):
    consent = crash_store.consent()
    requests = []

    def transport(method, url, data, headers):
        requests.append((url, data, headers))
        if len(requests) == 1:
            raise ReportServiceError("Synthetic lost response")
        return json.dumps(
            {"installation_id": str(consent.installation_id), "state": "registered"}
        ).encode()

    client = ReportClient(SERVICE_ORIGIN, transport=transport)
    with pytest.raises(ReportServiceError):
        client.register_crashes(consent, Event())
    client.register_crashes(crash_store.consent(), Event())
    assert requests[0] == requests[1]
    assert requests[0][0].endswith("/v1/crash-installations")
    assert set(json.loads(requests[0][1])) == {"schema_version", "installation_id"}
    bad = ReportClient(SERVICE_ORIGIN, transport=lambda *args: b'{"state":"registered"}')
    with pytest.raises(ReportServiceError):
        bad.register_crashes(consent, Event())


def test_queue_and_metadata_retention_bounds(crash_store):
    consent = enabled(crash_store)
    for _ in range(14):
        session(crash_store, consent)
    assert len(crash_store.recover()) == 10
    assert len(crash_store.pending()) == 10
    event = crash_store.pending()[0]
    event.created_epoch = time.time() - 8 * 86400
    crash_store.save_event(event)
    assert len(crash_store.pending()) == 9
    old = session(crash_store, consent, created_epoch=time.time() - 8 * 86400)
    foreign = crash_store.folder() / "user-notes.txt"
    foreign.write_text("retain")
    crash_store.prune_sessions()
    assert not crash_store._session_path(old).exists()
    assert foreign.read_text() == "retain"


def test_malformed_local_event_is_retained_but_never_sent(crash_store):
    enabled(crash_store)
    invalid = crash_store.folder() / f"crash-{uuid4()}.json"
    invalid.write_text('{"private": "do not send"}')
    assert crash_store.pending() == []
    assert invalid.exists()


def test_windows_liveness_never_uses_kill(monkeypatch):
    if sys.platform != "win32":
        pytest.skip("Windows process query contract")
    monkeypatch.setattr(os, "kill", lambda *args: pytest.fail("unsafe Windows kill query"))
    assert process_alive(os.getpid())


def test_expired_unknown_grant_does_not_block_re_enrollment():
    def missing(*args):
        raise ReportServiceError("Synthetic unknown grant", status=401)

    client = ReportClient(SERVICE_ORIGIN, transport=missing)
    client.revoke_crashes(CrashConsent(), Event())


def test_retry_backoff_does_not_starve_other_reports(crash_store):
    consent = enabled(crash_store)
    for _ in range(4):
        session(crash_store, consent)
    events = crash_store.recover()
    for event in events[:3]:
        event.next_attempt = time.time() + 3600
        crash_store.save_event(event)

    def received(method, url, data, headers):
        report_id = json.loads(data)["report"]["report_id"]
        return json.dumps({"report_id": report_id, "state": "received"}).encode()

    assert crash_store.deliver(ReportClient(SERVICE_ORIGIN, transport=received), Event()) == 1
    assert len(crash_store.pending()) == 3


@pytest.mark.parametrize("outcome", ["clean", "abrupt", "python"])
def test_real_logging_child_session_lifecycle(tmp_path, outcome):
    store = CrashStore(tmp_path)
    # The first launch must capture a crash even before background registration succeeds.
    assert store.consent().enabled
    script = """
import os, sys
from pathlib import Path
from fpvs_studio.support.diagnostics import DiagnosticLogging
session = DiagnosticLogging(Path(sys.argv[1]), capture_native=True)
session.start()
assert session.ready.wait(5)
if sys.argv[2] == "abrupt": os._exit(17)
if sys.argv[2] == "python":
    try: raise RuntimeError("private participant message")
    except Exception as error: session.record_failure(error)
session.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), outcome], capture_output=True, timeout=15
    )
    assert result.returncode == (17 if outcome == "abrupt" else 0), result.stderr.decode()
    events = store.recover()
    if outcome == "clean":
        assert events == []
    else:
        assert len(events) == 1
        assert events[0].report.crash_type == (
            "python_exception" if outcome == "python" else "unclean_shutdown"
        )
        assert "private" not in events[0].model_dump_json()
