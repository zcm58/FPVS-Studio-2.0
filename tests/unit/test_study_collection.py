"""Linked collection receipts keep the exact website study scope."""

import json
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest

from fpvs_studio.core.data_sharing import SharingProfile
from fpvs_studio.data_sharing.client import DataSharingClient
from fpvs_studio.data_sharing.collection import (
    last_collection_status,
    refresh_collection_status,
)
from fpvs_studio.data_sharing.errors import DataSharingError


def test_collection_receipt_is_project_scoped_and_survives_offline(tmp_path, monkeypatch):
    origin = "https://openfpvs.invalid"
    shared = SharingProfile(
        experiment_id="study", experiment_version="1.0", protocol_sha256="0" * 64,
        title="Study", device_id="device-1", project_id=str(uuid4()),
    )
    response = {
        "schema_version": "1.0", "project_id": shared.project_id, "collection_status": "complete",
    }
    calls = []

    def transport(method, url, body, headers, cancel):
        calls.append((method, url, body))
        return json.dumps(response).encode()

    client = DataSharingClient(origin, transport=transport)
    monkeypatch.setattr(client, "_load_credential", lambda *_: SimpleNamespace(token="test"))
    assert last_collection_status(tmp_path, shared) is None
    assert refresh_collection_status(tmp_path, shared, Event(), client=client) == "complete"
    assert calls == [("GET", origin + "/results/v1/device/collection", None)]
    response["project_id"] = str(uuid4())
    with pytest.raises(DataSharingError, match="different study"):
        refresh_collection_status(tmp_path, shared, Event(), client=client)
    assert last_collection_status(tmp_path, shared) == "complete"
    assert last_collection_status(tmp_path, shared.model_copy(update=response)) is None
