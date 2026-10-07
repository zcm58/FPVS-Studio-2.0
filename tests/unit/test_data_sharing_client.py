"""Fixed-origin credential and receipt contract checks; no live service calls."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from threading import Event
from uuid import uuid4

import pytest

from fpvs_studio.core.data_sharing import FixationOccurrence, SessionReport, SharingProfile
from fpvs_studio.data_sharing.client import DataSharingClient, _NoRedirect
from fpvs_studio.data_sharing.errors import DataSharingCancelled, DataSharingError
from fpvs_studio.library.models import DeviceCredential, LibraryConnection

ORIGIN = "https://results.example.invalid"
HASH = "a" * 64


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
    with pytest.raises(DataSharingError, match="project ID"):
        client.enroll(tmp_path, "lab code", HASH, Event(), project_id="../../other")
    assert len(calls) == 1
    wrong = str(uuid4())
    with pytest.raises(DataSharingError, match="different project"):
        client.enroll(tmp_path, "lab code", HASH, Event(), project_id=wrong)
