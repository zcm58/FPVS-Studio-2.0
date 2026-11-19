"""Synthetic crash recovery; no real credentials, research records or network."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest

from fpvs_studio import __version__
from fpvs_studio.support import crash_inventory as inventory
from fpvs_studio.support.client import SERVICE_ORIGIN, ReportClient, ReportServiceError
from fpvs_studio.support.crash_reporting import (
    CrashConsent,
    CrashSession,
    CrashStore,
    HandledIncident,
    process_alive,
    safe_frame,
)
from fpvs_studio.support.diagnostics import DiagnosticLogging, refresh_automatic_capture


@pytest.fixture
def crash_store(tmp_path, monkeypatch):
    monkeypatch.setattr("fpvs_studio.support.crash_reporting.process_alive", lambda pid: False)
    return CrashStore(tmp_path)


def session(store, consent=None, **fields):
    environment = {
        "os_family": "Windows", "generation": consent.workflow_generation,
    } if consent else {}
    value = CrashSession(
        session_id=uuid4(),
        pid=123456,
        os_version="Synthetic OS",
        installation_id=consent.installation_id if consent else None,
        **environment,
        **fields,
    )
    store.save_session(value)
    return value


def enabled(store):
    value = CrashConsent(enabled=True, expanded_disclosed=True)
    store.save_consent(value)
    return value


def test_on_by_default_persists_identity_and_never_backfills_historical_sessions(crash_store):
    old = session(crash_store)
    first = crash_store.consent()
    assert first.enabled and not first.registered
    assert CrashStore(crash_store.root).consent() == first
    assert crash_store.recover() == []
    assert crash_store._session_path(old).exists()


def test_disclosure_blocks_upload_and_legacy_sessions_are_never_backfilled(crash_store):
    consent = crash_store.consent()
    legacy = session(crash_store, consent)
    legacy.generation = None
    legacy.os_family = None
    crash_store.save_session(legacy)
    assert consent.enabled and not consent.expanded_disclosed
    assert crash_store.recover() == []
    consent = crash_store.disclose()
    assert consent.expanded_disclosed and crash_store.recover() == []


def test_disclosure_retries_a_transient_windows_replace_lock(crash_store, monkeypatch):
    before = crash_store.consent()
    replace = os.replace
    injections = []

    def briefly_locked(source, destination):
        if not injections:
            injections.append(destination)
            error = PermissionError("Synthetic Windows replacement lock")
            error.winerror = 5
            raise error
        return replace(source, destination)

    monkeypatch.setattr(os, "replace", briefly_locked)
    assert crash_store.disclose().expanded_disclosed
    assert crash_store.consent().installation_id == before.installation_id
    assert len(injections) == 1


@pytest.mark.parametrize("queued", [False, True])
def test_correlated_fatal_failure_preserves_the_queued_identity_and_payload(
    crash_store, queued,
):
    consent = enabled(crash_store)
    stack = [safe_frame("fpvs_studio/processing.py", "evaluate", 42)]
    incident = HandledIncident(operation="processing", stack=stack)
    affected = session(crash_store, consent, state="clean", handled=[incident])
    if queued:
        original, = crash_store.recover()
        assert original.report.time_basis == "occurrence"
        assert original.report.created_at == incident.created_at
    affected.state = "failed"
    affected.stack = stack
    affected.failed_at = "2026-11-19T12:01:04+00:00"
    crash_store.update_session(affected)
    recovered, = crash_store.recover()
    assert recovered.report.report_id == incident.report_id
    assert recovered.report.operation == "processing"
    if queued:
        assert recovered == original
    else:
        assert recovered.report.crash_type == "python_exception"
        assert recovered.report.created_at == affected.failed_at


def test_existing_opt_out_survives_reloads_and_new_default(crash_store):
    consent = CrashConsent(enabled=False)
    crash_store.save_consent(consent)
    assert not CrashStore(crash_store.root).consent().enabled
    assert crash_store.recover() == []


def test_invalid_preference_never_becomes_default_enabled(crash_store):
    (crash_store.folder() / "consent.json").write_text("invalid")
    with pytest.raises(ValueError):
        crash_store.consent()


@pytest.mark.parametrize("pycharm_hosted", [False, True])
def test_native_recovery_contains_only_source_locations(crash_store, pycharm_hosted):
    consent = enabled(crash_store)
    value = session(crash_store, consent, pycharm_hosted=pycharm_hosted)
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
    assert "pycharm_hosted" not in data
    assert crash_store.recover()[0].receipt_token == event.receipt_token


@pytest.mark.parametrize("operation", ["stat", "open", "read"])
@pytest.mark.parametrize("failure", [PermissionError, FileNotFoundError])
def test_unreadable_native_trace_defers_only_its_session_until_retry(
    crash_store, monkeypatch, caplog, operation, failure,
):
    consent = enabled(crash_store)
    healthy = session(crash_store, consent, created_epoch=time.time() - 10)
    affected = session(crash_store, consent)
    logs = crash_store.root / "logs"
    logs.mkdir()
    native = logs / f"session-{affected.session_id.hex}-native.log"
    native.write_text(
        "Qt fatal: participant=private-value token=private-secret\n"
        '  File "C:/private/src/fpvs_studio/gui/workers.py", line 42 in run\n',
        encoding="utf-8",
    )
    original_session = crash_store._session_path(affected).read_bytes()
    original_trace = native.read_bytes()
    requests = []

    def received(method, url, data, headers):
        requests.append(json.loads(data))
        return json.dumps({
            "report_id": requests[-1]["report"]["report_id"], "state": "received",
        }).encode()

    original_lstat = Path.lstat
    original_open = Path.open

    def fail():
        raise failure("private error text token=private-secret")

    def unreadable_lstat(path, *args, **kwargs):
        if path.name == native.name:
            fail()
        return original_lstat(path, *args, **kwargs)

    @contextmanager
    def unreadable_stream(path, mode, *args, **kwargs):
        with original_open(path, mode, *args, **kwargs) as stream:
            yield SimpleNamespace(
                fileno=stream.fileno, seek=stream.seek, read=lambda _limit: fail(),
            )

    def unreadable_open(path, mode="r", *args, **kwargs):
        if path.name == native.name and mode == "rb":
            if operation == "open":
                fail()
            return unreadable_stream(path, mode, *args, **kwargs)
        return original_open(path, mode, *args, **kwargs)

    with monkeypatch.context() as patch:
        if operation == "stat":
            patch.setattr(Path, "lstat", unreadable_lstat)
        else:
            patch.setattr(Path, "open", unreadable_open)
        events = crash_store.recover()
        assert [event.report.report_id for event in events] == [healthy.session_id]
        assert not (crash_store.folder() / f"crash-{affected.session_id}.json").exists()
        client = ReportClient(SERVICE_ORIGIN, transport=received)
        assert crash_store.deliver(client, Event()) == 1
        assert requests[0]["report"]["report_id"] == str(healthy.session_id)

    assert crash_store._session_path(affected).read_bytes() == original_session
    assert native.read_bytes() == original_trace
    assert failure.__name__ in caplog.text
    assert "private" not in caplog.text and str(native) not in caplog.text
    events = crash_store.recover()
    assert len(events) == 1
    event = events[0]
    assert event.report.report_id == affected.session_id
    assert event.report.crash_type == "native_fault"
    assert event.report.stack == [safe_frame("fpvs_studio/gui/workers.py", "run", 42)]
    assert event.installation_id == consent.installation_id
    assert "private" not in event.model_dump_json()
    assert crash_store.recover()[0] == event  # Retry retains the report and receipt identity.
    assert crash_store.deliver(client, Event()) == 1
    assert requests[-1]["report"]["report_id"] == str(affected.session_id)
    assert crash_store.recover() == []


@pytest.mark.parametrize("change_stage", ["open", "read"])
def test_changing_native_trace_is_retried_without_guessing_a_report_type(
    crash_store, monkeypatch, change_stage,
):
    consent = enabled(crash_store)
    affected = session(crash_store, consent)
    logs = crash_store.root / "logs"
    logs.mkdir()
    native = logs / f"session-{affected.session_id.hex}-native.log"
    native.write_text("Initial native trace\n", encoding="utf-8")
    original_open = Path.open

    def append_trace():
        with original_open(native, "a", encoding="utf-8") as stream:
            stream.write('  File "fpvs_studio/gui/workers.py", line 42 in run\n')

    @contextmanager
    def changing_stream(path, mode, *args, **kwargs):
        with original_open(path, mode, *args, **kwargs) as stream:
            if change_stage == "open":
                append_trace()

            def read(limit):
                result = stream.read(limit)
                if change_stage == "read":
                    append_trace()
                return result

            yield SimpleNamespace(fileno=stream.fileno, seek=stream.seek, read=read)

    def changing_open(path, mode="r", *args, **kwargs):
        if path.name == native.name and mode == "rb":
            return changing_stream(path, mode, *args, **kwargs)
        return original_open(path, mode, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", changing_open)
        assert crash_store.recover() == []
        assert crash_store.pending() == []
    event = crash_store.recover()[0]
    assert event.report.report_id == affected.session_id
    assert event.report.crash_type == "native_fault"
    assert event.report.stack == [safe_frame("fpvs_studio/gui/workers.py", "run", 42)]


@pytest.mark.parametrize(
    ("file_mode", "attributes"),
    [
        (stat.S_IFDIR, 0),
        (stat.S_IFIFO, 0),
        (stat.S_IFCHR, 0),
        (stat.S_IFLNK, 0),
        (stat.S_IFREG, 0x400),
    ],
)
def test_redirected_or_nonregular_native_trace_is_never_opened(
    crash_store, monkeypatch, file_mode, attributes,
):
    consent = enabled(crash_store)
    affected = session(crash_store, consent)
    logs = crash_store.root / "logs"
    logs.mkdir()
    native = logs / f"session-{affected.session_id.hex}-native.log"
    native.write_text("Preserve source evidence", encoding="utf-8")
    original_lstat, original_open = Path.lstat, Path.open

    def special_lstat(path, *args, **kwargs):
        if path.name == native.name:
            return SimpleNamespace(st_mode=file_mode, st_file_attributes=attributes)
        return original_lstat(path, *args, **kwargs)

    def safe_open(path, *args, **kwargs):
        if path.name == native.name:
            pytest.fail("Recovery opened a redirected or nonregular trace")
        return original_open(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", special_lstat)
        patch.setattr(Path, "open", safe_open)
        assert crash_store.recover() == []
        assert crash_store.pending() == []
    assert native.read_text(encoding="utf-8") == "Preserve source evidence"
    assert crash_store._session_path(affected).exists()


def test_empty_native_trace_preserves_python_failure_classification(crash_store):
    consent = enabled(crash_store)
    affected = session(
        crash_store, consent, state="failed",
        stack=[safe_frame("fpvs_studio/app/main.py", "main", 17)],
    )
    logs = crash_store.root / "logs"
    logs.mkdir()
    (logs / f"session-{affected.session_id.hex}-native.log").touch()
    event = crash_store.recover()[0]
    assert event.report.crash_type == "python_exception"
    assert event.report.stack == affected.stack


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


def test_pycharm_abrupt_exit_still_reports_a_separate_handled_failure(crash_store):
    consent = enabled(crash_store)
    incident = HandledIncident(operation="project", stack=[
        safe_frame("fpvs_studio/gui/workers.py", "run", 42),
    ])
    session(crash_store, consent, pycharm_hosted=True, handled=[incident])
    event, = crash_store.recover()
    assert event.report.crash_type == "internal_error"
    assert event.report.report_id == incident.report_id
    assert crash_store.recover() == [event]


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
        if method == "GET":
            assert url.startswith(SERVICE_ORIGIN + "/v1/reports/")
            assert headers["Authorization"] != f"Bearer {consent.token}"
            raise ReportServiceError("No receipt yet", status=401)
        assert url == SERVICE_ORIGIN + "/v1/crash-reports"
        assert headers["X-Installation-ID"] == str(consent.installation_id)
        report = json.loads(data)["report"]
        assert report["schema_version"] == "2" and report["product"] == "studio"
        assert report["os_family"] == "Windows" and report["time_basis"] == "recovery"
        assert "context" not in report
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


def test_delivered_receipt_resolves_ambiguous_upload_without_second_post(crash_store):
    consent = enabled(crash_store)
    session(crash_store, consent)
    accepted, = crash_store.recover()
    requests = []

    def transport(method, url, data, headers):
        requests.append(method)
        if method == "POST":
            raise ReportServiceError("Synthetic lost acknowledgment")
        assert url == f"{SERVICE_ORIGIN}/v1/reports/{accepted.report.report_id}/status"
        assert headers["Authorization"] == f"Bearer {accepted.receipt_token}"
        assert data is None
        return json.dumps({
            "report_id": str(accepted.report.report_id), "state": "submitted",
        }).encode()

    client = ReportClient(SERVICE_ORIGIN, transport=transport)
    with pytest.raises(ReportServiceError):
        crash_store.deliver(client, Event())
    saved, = crash_store.pending()
    saved.next_attempt = 0
    crash_store.save_event(saved)
    assert crash_store.deliver(client, Event()) == 1
    assert requests == ["POST", "GET"] and crash_store.pending() == []


def test_background_inventory_omits_private_or_absent_facts(monkeypatch):
    monkeypatch.setattr(inventory.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(inventory, "_mac_inventory", lambda: {
        "hardware_model": "MacBookPro18,3", "cpu_model": "Apple M1 Pro",
        "os_build": "26A23", "gpus": ["/Users/person/GPU", "64:86:82:10:11:12"],
        "ram": None, "serial": "do not send",
    })
    context = inventory.collect_inventory("macOS", None)
    assert context.hardware_model == "MacBookPro18,3"
    assert context.cpu_model == "Apple M1 Pro" and context.os_build == "26A23"
    assert context.gpus is None and context.ram_gib is None
    assert "serial" not in context.model_dump_json()


def test_live_disclosure_enables_capture_and_preserves_session_facts(crash_store, monkeypatch):
    from fpvs_studio.support.crash_reporting import CrashContext

    monkeypatch.setattr(
        "fpvs_studio.support.diagnostics.os_identity", lambda: ("macOS", "27.0", "26A7"),
    )
    query_ran = Event()

    def inventory_worker(family, build):
        assert family == "macOS" and build == "26A7"
        query_ran.set()
        return CrashContext(os_build=build)

    monkeypatch.setattr("fpvs_studio.support.diagnostics.collect_inventory", inventory_worker)
    logging_session = DiagnosticLogging(crash_store.root, capture_native=True)
    logging_session.start()
    try:
        assert not query_ran.is_set() and not logging_session.capture_enabled.is_set()
        crash_store.disclose()
        refresh_automatic_capture(enabled=True)
        assert query_ran.wait(3)
        try:
            code = compile(
                "raise RuntimeError('private participant information')",
                "fpvs_studio/project.py", "exec",
            )
            exec(code, {})
        except RuntimeError as error:
            logging_session.record_handled(error, "project")
            logging_session.record_handled(error, "application")
    finally:
        logging_session.close()
    event, = crash_store.recover()
    assert event.report.crash_type == "internal_error"
    assert event.report.operation == "project" and event.report.time_basis == "occurrence"
    assert event.report.app_version == __version__ and event.report.os_version == "27.0"
    assert event.report.context.os_build == "26A7"
    assert "private" not in event.report.model_dump_json()


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
    first = enabled(crash_store)
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


@pytest.mark.parametrize(("outcome", "pycharm_hosted", "expected"), [
    ("clean", False, None),
    ("abrupt", False, "unclean_shutdown"),
    ("python", False, "python_exception"),
    ("abrupt", True, None),
    ("python", True, "python_exception"),
])
def test_real_logging_child_session_lifecycle(tmp_path, outcome, pycharm_hosted, expected):
    store = CrashStore(tmp_path)
    # The first launch must capture a crash even before background registration succeeds.
    assert store.consent().enabled
    store.disclose()
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
        [sys.executable, "-c", script, str(tmp_path), outcome], capture_output=True, timeout=15,
        env={**os.environ, "PYCHARM_HOSTED": "1" if pycharm_hosted else "0"},
    )
    assert result.returncode == (17 if outcome == "abrupt" else 0), result.stderr.decode()
    events = store.recover()
    if expected is None:
        assert events == []
        assert store.recover() == []
    else:
        assert len(events) == 1
        assert events[0].report.crash_type == expected
        assert "private" not in events[0].model_dump_json()
    snapshot, = store.folder().glob("session-*.json")
    assert ("pycharm_hosted" in json.loads(snapshot.read_bytes())) == pycharm_hosted


@pytest.mark.parametrize("failure", ["budget", "startup_budget", "io"])
@pytest.mark.parametrize("outcome", ["clean", "abrupt", "python"])
def test_log_sink_failure_preserves_the_actual_application_lifecycle(tmp_path, failure, outcome):
    store = CrashStore(tmp_path)
    store.disclose()
    script = """
import os, sys, time
from pathlib import Path
import fpvs_studio.support.diagnostics as diagnostics
from fpvs_studio.support.crash_reporting import CrashSession
root = Path(sys.argv[1])
failure, outcome = sys.argv[2:]
logs = root / "logs"
logs.mkdir()
synthetic = logs / ("session-" + "a" * 32 + ".log")
if failure == "startup_budget":
    synthetic.write_bytes(b"x" * (10 * 1024 * 1024))
session = diagnostics.DiagnosticLogging(root, capture_native=True)
session.start()
assert session.ready.wait(5)
if failure == "budget":
    synthetic.write_bytes(b"x" * (10 * 1024 * 1024))
elif failure == "io":
    def unavailable(*args):
        raise OSError("Synthetic log sink failure")
    diagnostics._LogFile.handle = unavailable
session.logger.warning("Synthetic diagnostic record")
deadline = time.monotonic() + 5
while not diagnostics._logging_notice:
    assert time.monotonic() < deadline
    time.sleep(0.01)
snapshot = root / "automatic-crashes" / f"session-{session.session_id}.json"
assert CrashSession.model_validate_json(snapshot.read_bytes()).state == "active"
assert session.thread.is_alive()
if outcome == "abrupt":
    os._exit(17)
if outcome == "python":
    try:
        raise RuntimeError("private participant message")
    except Exception as error:
        session.record_failure(error)
session.close()
assert not session.thread.is_alive()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), failure, outcome],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == (17 if outcome == "abrupt" else 0), result.stderr.decode()
    events = CrashStore(tmp_path).recover()
    if outcome == "clean":
        assert events == []
    else:
        assert len(events) == 1
        assert events[0].report.crash_type == (
            "python_exception" if outcome == "python" else "unclean_shutdown"
        )
        assert "private" not in events[0].model_dump_json()
