"""Fixed-origin credential and receipt contract checks; no live service calls."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from email.message import Message
from io import BytesIO
from threading import Event
from urllib.error import HTTPError
from uuid import uuid4

import pytest

from fpvs_studio.core.data_sharing import (
    FixationOccurrence,
    SessionReport,
    SharingProfile,
    SharingSettings,
    SharingStudyChoice,
    SharingStudyChoices,
)
from fpvs_studio.core.library_origin import LibraryProjectOrigin, save_library_origin
from fpvs_studio.data_sharing.client import (
    DataSharingClient,
    _NoRedirect,
    _status_error,
    http_transport,
)
from fpvs_studio.data_sharing.errors import (
    DataSharingCancelled,
    DataSharingError,
    PendingEnrollmentConflict,
)
from fpvs_studio.data_sharing.storage import save_settings
from fpvs_studio.library.errors import LibraryAuthorizationError, LibraryCancelled, LibraryError
from fpvs_studio.library.models import DeviceCredential, LibraryConnection

ORIGIN = "https://results.example.invalid"
HASH = "a" * 64


def test_pending_results_approval_has_an_actionable_message():
    error = _status_error(403, {
        "schema_version": "1.0", "error": "results_approval_required",
        "message": "Private server text",
    })
    assert error.code == "authorization"
    assert "administrator" in str(error).lower()
    assert "choose Connect again" in str(error)
    assert "Private server text" not in str(error)
    assert not error.retryable


def test_storage_budget_requires_attention_and_throttling_keeps_backoff():
    error = _status_error(429, {
        "schema_version": "1.0", "error": "project_storage_limit", "message": "Private text",
    })
    assert error.code == "storage_limit" and not error.retryable
    assert "administrator" in str(error) and "Private text" not in str(error)
    throttled = _status_error(429, {
        "schema_version": "1.0", "error": "rate_limit", "message": "Private text",
    })
    assert throttled.code == "throttled" and throttled.retryable


@pytest.mark.parametrize("status,body,code", [
    (429, {"schema_version": "1.0", "error": "project_storage_limit", "message": "Private"},
     "storage_limit"),
    (429, {"schema_version": "1.0", "error": "rate_limit", "message": "Private"}, "throttled"),
    (409, {"schema_version": "1.0", "error": "credential_scope_conflict", "message": "Private"},
     "enrollment_scope"),
    (409, {"schema_version": "1.0", "error": "report_conflict", "message": "Private"}, "conflict"),
    (401, {"schema_version": "1.0", "error": "library_authorization", "message": "Private"},
     "library_authorization"),
    (403, {"schema_version": "1.0", "error": "library_lab_code_required", "message": "Private"},
     "library_authorization"),
    (403, {"schema_version": "1.0", "error": "project_not_enabled", "message": "Private"},
     "study_unavailable"),
    (409, {"schema_version": "1.0", "error": "too_many_projects", "message": "Private"},
     "study_limit"),
])
def test_http_budget_and_throttle_errors_are_bounded_and_close_response(
    monkeypatch, status, body, code,
):
    import fpvs_studio.data_sharing.client as module

    headers, stream = Message(), BytesIO(json.dumps(body).encode())
    headers["Content-Type"] = "application/json"

    class Opener:
        def open(self, *args, **kwargs):
            raise HTTPError(ORIGIN, status, "Too many requests", headers, stream)

    monkeypatch.setattr(module, "build_opener", lambda *args: Opener())
    with pytest.raises(DataSharingError) as failure:
        http_transport("POST", ORIGIN + "/results/v1/experiments/study/reports", b"{}", {}, Event())
    assert failure.value.code == code and stream.closed


@pytest.mark.parametrize("payload, expected", [
    (b'{"schema_version":"1.0","error":"results_approval_required","message":"private"}',
     "administrator"),
    (b"x" * 2049, "exceeds its limit"),
    (b"invalid json", "invalid error data"),
    pytest.param(b"[" * 1000 + b"]" * 1000, "invalid error data", id="nested-json"),
])
def test_pending_results_http_error_is_bounded_and_safe(monkeypatch, payload, expected):
    import fpvs_studio.data_sharing.client as module

    headers = Message()
    headers["Content-Type"] = "application/json"
    stream = BytesIO(payload)
    class Opener:
        def open(self, *args, **kwargs):
            raise HTTPError(ORIGIN, 403, "Forbidden", headers, stream)
    monkeypatch.setattr(module, "build_opener", lambda *args: Opener())
    with pytest.raises(DataSharingError, match=expected):
        http_transport("POST", ORIGIN + "/results/v1/enroll", b"{}", {}, Event())
    assert stream.closed


def profile():
    return SharingProfile(
        experiment_id="study",
        experiment_version="1.0",
        protocol_sha256=HASH,
        title="Study",
        device_id="device-1",
    )


def report():
    return SessionReport(
        report_id=str(uuid4()),
        experiment_id="study",
        experiment_version="1.0",
        protocol_sha256=HASH,
        completed_at=datetime.now(timezone.utc),
        studio_version="2.2.4",
        occurrences=(
            FixationOccurrence(
                condition_id="faces",
                occurrence_index=1,
                total_targets=10,
                hit_count=8,
                miss_count=2,
                false_alarm_count=1,
                accuracy_percent=80.0,
                mean_rt_ms=350.0,
                rt_count=8,
                scoring_source="timestamps",
                refresh_hz=60.0,
                response_window_ms=1000.0,
            ),
        ),
    )


class Store:
    def __init__(self, value=None):
        self.value = value

    def load(self):
        return self.value

    def save(self, value):
        self.value = value

    def delete(self):
        self.value = None


class LabAccess:
    service_url = ORIGIN

    def __init__(self, error=None):
        self.value = credential().model_copy(update={"token": "l" * 64, "library_api_version": 2})
        self.error = error
        self.reads = 0

    def enrolled_credential(self, *, cancel_event=None):
        self.reads += 1
        if self.error is not None:
            raise self.error
        return self.value


def study_choice(**changes):
    values = {
        "project_id": "01234567-89ab-cdef-0123-456789abcdef", "title": "Reviewed study",
        "experiment_id": "study", "experiment_version": "1.0", "protocol_sha256": HASH,
    }
    values.update(changes)
    return SharingStudyChoice(**values)


def linked_origin(root, **changes):
    values = {"service_url": ORIGIN, "item_id": "study", "installed_version": "1.0",
              "local_project_id": "local-study"}
    values.update(changes)
    save_library_origin(root, LibraryProjectOrigin(**values))


def credential():
    return DeviceCredential(
        token="a" * 64,
        device_name="FPVS Studio data sharing",
        connection=LibraryConnection(
            device_id="device-1", library_name="Results", device_name="Results"
        ),
    )


def receipt_bytes(payload, **changes):
    body = json.loads(payload)
    response = {
        "schema_version": "1.0",
        "report_id": body["report_id"],
        "experiment_id": "study",
        "experiment_version": "1.0",
        "protocol_sha256": HASH,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "received_at": "2026-10-05T12:00:00Z",
    }
    response.update(changes)
    return json.dumps(response).encode()


def test_openfpvs_default_and_origin_validation(monkeypatch):
    monkeypatch.delenv("FPVS_DATA_SHARING_SERVICE_URL", raising=False)
    assert DataSharingClient.configured().origin == "https://openfpvs.com"
    monkeypatch.setenv("FPVS_DATA_SHARING_SERVICE_URL", "")
    assert not DataSharingClient.configured().enabled
    for origin in (
        "http://results.invalid",
        ORIGIN + "/path",
        ORIGIN + "?x=1",
        "https://user:secret@results.invalid",
        ORIGIN + "#fragment",
    ):
        with pytest.raises(DataSharingError):
            DataSharingClient(origin)
    assert _NoRedirect().redirect_request(None, None, 302, "", {}, ORIGIN) is None


def test_lost_enrollment_response_reuses_secure_token_and_no_hostname(tmp_path):
    store = Store()
    sent = []

    def transport(method, url, body, headers, cancel):
        assert store.value is not None
        sent.append(json.loads(body))
        assert url == ORIGIN + "/results/v1/enroll"
        assert "hostname" not in sent[-1] and "device_name" not in sent[-1]
        if len(sent) == 1:
            raise DataSharingError("Synthetic network loss", retryable=True)
        return profile().model_dump_json().encode()

    client = DataSharingClient(ORIGIN, transport=transport, store_factory=lambda *_: store)
    with pytest.raises(DataSharingError):
        client.enroll(tmp_path, "synthetic-code", HASH, Event())
    client.enroll(tmp_path, "synthetic-code", HASH, Event())
    assert sent[0]["device_token"] == sent[1]["device_token"]
    assert len(sent[0]["device_token"]) == 64
    assert set(sent[0]["device_token"]) <= set("0123456789abcdef")
    assert store.value.connection.device_id == "device-1"


@pytest.mark.parametrize("registered", [False, True])
def test_only_pending_scope_conflicts_offer_explicit_reset(tmp_path, registered):
    saved = credential() if registered else credential().model_copy(update={"connection": None})
    store = Store(saved)

    def transport(*_args):
        raise _status_error(409, {
            "schema_version": "1.0", "error": "credential_scope_conflict", "message": "Private",
        })

    backend = DataSharingClient(ORIGIN, transport=transport, store_factory=lambda *_: store)
    with pytest.raises(DataSharingError) as failure:
        backend.enroll(tmp_path, "new lab code", HASH, Event())
    assert isinstance(failure.value, PendingEnrollmentConflict) is (not registered)
    assert store.value == saved
    assert saved.token not in str(failure.value)
    if not registered:
        assert failure.value.credential_sha256 == hashlib.sha256(saved.token.encode()).hexdigest()


@pytest.mark.parametrize("changed", ["registered", "new-token", "saved-profile", "canceled"])
def test_pending_reset_rechecks_identity_registration_and_cancellation(tmp_path, changed):
    original = credential().model_copy(update={"connection": None})
    store = Store(original)
    cancel = Event()
    if changed == "registered":
        store.value = credential()
    elif changed == "new-token":
        store.value = original.model_copy(update={"token": "b" * 64})
    elif changed == "saved-profile":
        save_settings(tmp_path, SharingSettings(profile=profile()))
    else:
        cancel.set()
    retained = store.value
    calls = []
    backend = DataSharingClient(
        ORIGIN, transport=lambda *args: calls.append(args), store_factory=lambda *_: store,
    )
    with pytest.raises(DataSharingError):
        backend.enroll(
            tmp_path, "new lab code", HASH, cancel,
            reset_pending_credential_sha256=hashlib.sha256(original.token.encode()).hexdigest(),
        )
    assert store.value == retained and not calls


def test_late_enrollment_response_cannot_overwrite_replaced_pending_identity(tmp_path):
    store = Store()
    replacement = credential().model_copy(update={"token": "b" * 64, "connection": None})

    def transport(*_args):
        store.save(replacement)
        return profile().model_dump_json().encode()

    backend = DataSharingClient(ORIGIN, transport=transport, store_factory=lambda *_: store)
    with pytest.raises(DataSharingError, match="connection changed while enrolling"):
        backend.enroll(tmp_path, "lab code", HASH, Event())
    assert store.value == replacement


@pytest.mark.parametrize(
    "changes",
    [
        {"report_id": str(uuid4())},
        {"sha256": "b" * 64},
        {"experiment_id": "other-study"},
        {"protocol_sha256": "b" * 64},
    ],
)
def test_unrelated_receipts_cannot_mark_reports_uploaded(tmp_path, changes):
    payload = report().model_dump_json().encode()
    client = DataSharingClient(
        ORIGIN,
        transport=lambda method, url, body, headers, cancel: receipt_bytes(body, **changes),
        store_factory=lambda *_: Store(credential()),
    )
    with pytest.raises(DataSharingError, match="unrelated receipt"):
        client.submit(tmp_path, profile(), payload, Event())


def test_scope_mismatch_and_last_moment_optout_never_send(tmp_path):
    calls = []
    client = DataSharingClient(
        ORIGIN,
        transport=lambda *args: calls.append(args),
        store_factory=lambda *_: Store(credential()),
    )
    payload = report().model_dump_json().encode()
    with pytest.raises(DataSharingError, match="does not match"):
        client.submit(
            tmp_path, profile().model_copy(update={"experiment_id": "other"}), payload, Event()
        )
    with pytest.raises(DataSharingCancelled):
        client.submit(tmp_path, profile(), payload, Event(), before_send=lambda: False)
    assert not calls


def test_missing_machine_credential_does_not_inherit_copied_project_optin(tmp_path):
    calls = []
    client = DataSharingClient(
        ORIGIN,
        transport=lambda *args: calls.append(args),
        store_factory=lambda *_: Store(),
    )
    with pytest.raises(DataSharingError, match="own results enrollment"):
        client.submit(tmp_path, profile(), report().model_dump_json().encode(), Event())
    assert not calls


def test_openfpvs_project_enrollment_is_bound_to_selected_id(tmp_path):
    project_id = str(uuid4())
    store = Store()
    calls = []

    def transport(method, url, body, headers, cancel):
        calls.append(json.loads(body))
        assert method == "POST" and url.endswith("/results/v1/enroll")
        return profile().model_copy(update={"project_id": project_id}).model_dump_json().encode()

    client = DataSharingClient(ORIGIN, transport=transport, store_factory=lambda *_: store)
    selected = client.enroll(tmp_path, "lab code", HASH, Event(), project_id=project_id)
    assert selected.project_id == project_id
    assert calls[0]["project_id"] == project_id
    assert calls[0]["code"] == "lab code"
    with pytest.raises(DataSharingError, match="valid study"):
        client.enroll(tmp_path, "lab code", HASH, Event(), project_id="../../other")
    assert len(calls) == 1
    wrong = str(uuid4())
    with pytest.raises(DataSharingError, match="different project"):
        client.enroll(tmp_path, "lab code", HASH, Event(), project_id=wrong)


@pytest.mark.parametrize("linked", [False, True])
@pytest.mark.parametrize("count", [0, 1, 2])
def test_lab_discovery_is_read_only_and_sends_only_exact_scope(tmp_path, linked, count):
    if linked:
        linked_origin(tmp_path)
    lab = LabAccess()
    choices = SharingStudyChoices(projects=tuple(
        study_choice(project_id=str(uuid4())) for _ in range(count)
    ))
    calls = []

    def transport(method, url, body, headers, cancel):
        calls.append((method, url, json.loads(body), headers))
        return choices.model_dump_json().encode()

    backend = DataSharingClient(
        ORIGIN, transport=transport, library_client=lab,
        store_factory=lambda *_: pytest.fail("Discovery must not read Results credentials"),
    )
    assert backend.discover_projects(tmp_path, HASH, Event()) == choices
    assert lab.reads == 1 and len(calls) == 1
    method, url, body, headers = calls[0]
    assert (method, url) == ("POST", ORIGIN + "/results/v1/library/projects")
    assert body == {"schema_version": "1.0", "protocol_sha256": HASH, **(
        {"experiment_id": "study", "experiment_version": "1.0"} if linked else {}
    )}
    assert headers["Authorization"] == f"Bearer {lab.value.token}"
    assert not (tmp_path / ".fpvs-data-sharing").exists()
    assert not (tmp_path / "logs").exists()


@pytest.mark.parametrize("problem", ["library-origin", "receipt-origin", "unknown-version"])
def test_lab_discovery_rejects_configuration_before_credential_access(tmp_path, problem):
    lab = LabAccess()
    if problem == "library-origin":
        lab.service_url = "https://other.example.invalid"
    elif problem == "receipt-origin":
        linked_origin(tmp_path, service_url="https://other.example.invalid")
    else:
        linked_origin(tmp_path, installed_version=None)
    backend = DataSharingClient(
        ORIGIN, library_client=lab,
        transport=lambda *_: pytest.fail("Invalid scope must not reach HTTP"),
    )
    with pytest.raises(DataSharingError):
        backend.discover_projects(tmp_path, HASH, Event())
    assert lab.reads == 0


def test_lab_discovery_accepts_canonical_managed_receipt_without_following_it(tmp_path):
    linked_origin(tmp_path, service_url="https://fpvs.zack-murphy.com")
    lab = LabAccess()
    lab.service_url = "https://openfpvs.com"
    urls = []
    backend = DataSharingClient(
        lab.service_url, library_client=lab,
        transport=lambda _method, url, *_: urls.append(url) or b'{"projects":[]}',
    )
    assert not backend.discover_projects(tmp_path, HASH, Event()).projects
    assert urls == ["https://openfpvs.com/results/v1/library/projects"]


@pytest.mark.parametrize("field,value", [
    ("experiment_id", "other-study"), ("experiment_version", "2.0"),
    ("protocol_sha256", "b" * 64),
])
def test_lab_discovery_rejects_unrelated_results(tmp_path, field, value):
    linked_origin(tmp_path)
    choices = SharingStudyChoices(projects=(study_choice(**{field: value}),))
    backend = DataSharingClient(
        ORIGIN, library_client=LabAccess(), transport=lambda *_: choices.model_dump_json().encode(),
    )
    with pytest.raises(DataSharingError, match="different experiment or protocol"):
        backend.discover_projects(tmp_path, HASH, Event())


@pytest.mark.parametrize("error,code", [
    (LibraryAuthorizationError("private details"), "library_authorization"),
    (LibraryCancelled(), "cancelled"), (LibraryError("private details"), "credential_store"),
])
def test_lab_access_failures_are_actionable_without_network(tmp_path, error, code):
    backend = DataSharingClient(
        ORIGIN, library_client=LabAccess(error),
        transport=lambda *_: pytest.fail("Unusable Lab access must not reach HTTP"),
    )
    with pytest.raises(DataSharingError) as failure:
        backend.discover_projects(tmp_path, HASH, Event())
    assert failure.value.code == code and "private details" not in str(failure.value)


def test_lab_enrollment_keeps_distinct_results_token_and_reuses_pending_approval(tmp_path):
    linked_origin(tmp_path)
    lab, store, calls = LabAccess(), Store(), []
    selected = study_choice()

    def transport(method, url, body, headers, _cancel):
        calls.append((url, json.loads(body), headers))
        if len(calls) == 1:
            raise _status_error(403, {"schema_version": "1.0", "message": "Private",
                                      "error": "results_approval_required"})
        if url.endswith("/reports"):
            return receipt_bytes(body)
        return profile().model_copy(
            update={"project_id": selected.project_id},
        ).model_dump_json().encode()

    backend = DataSharingClient(
        ORIGIN, library_client=lab, store_factory=lambda *_: store, transport=transport,
    )
    with pytest.raises(DataSharingError, match="administrator"):
        backend.enroll_from_library(tmp_path, selected.project_id, HASH, Event())
    pending = store.value
    assert pending.connection is None
    connected = backend.enroll_from_library(tmp_path, selected.project_id, HASH, Event())
    assert calls[0][1] == calls[1][1]
    assert calls[0][1] == {
        "schema_version": "1.0", "device_token": pending.token, "protocol_sha256": HASH,
        "project_id": selected.project_id, "experiment_id": "study", "experiment_version": "1.0",
    }
    assert pending.token != lab.value.token
    assert all(item[0] == ORIGIN + "/results/v1/library/enroll" for item in calls)
    assert all(item[2]["Authorization"] == f"Bearer {lab.value.token}" for item in calls)
    backend.submit(tmp_path, connected, report().model_dump_json().encode(), Event())
    assert calls[-1][2]["Authorization"] == f"Bearer {pending.token}"
    assert lab.reads == 2


def test_library_authorization_error_does_not_delete_either_credential(tmp_path):
    lab, store = LabAccess(), Store()

    def transport(*_args):
        raise _status_error(401, {"schema_version": "1.0", "error": "library_authorization",
                                  "message": "Private"})

    backend = DataSharingClient(
        ORIGIN, library_client=lab, store_factory=lambda *_: store, transport=transport,
    )
    original = lab.value
    with pytest.raises(DataSharingError) as failure:
        backend.enroll_from_library(tmp_path, study_choice().project_id, HASH, Event())
    assert failure.value.code == "library_authorization"
    assert lab.value == original and store.value is not None and store.value.connection is None


@pytest.mark.parametrize("changes", [
    {"experiment_id": "other-study"}, {"experiment_version": "2.0"},
    {"protocol_sha256": "b" * 64}, {"project_id": "11234567-89ab-cdef-0123-456789abcdef"},
])
def test_lab_enrollment_cannot_bind_unrelated_response(tmp_path, changes):
    linked_origin(tmp_path)
    selected = study_choice()
    returned = profile().model_copy(update={"project_id": selected.project_id, **changes})
    store = Store()
    backend = DataSharingClient(
        ORIGIN, library_client=LabAccess(), store_factory=lambda *_: store,
        transport=lambda *_: returned.model_dump_json().encode(),
    )
    with pytest.raises(DataSharingError):
        backend.enroll_from_library(tmp_path, selected.project_id, HASH, Event())
    assert store.value is not None and store.value.connection is None
