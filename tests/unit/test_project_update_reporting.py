"""In-place protocol changes cannot strand or relabel unsent Results evidence."""

from threading import Event
from unittest.mock import Mock
from uuid import uuid4

import pytest
from tests.unit.test_data_sharing_models import report_fixture
from tests.unit.test_data_sharing_storage import _capture, _excluded_capture, _upload, enable

from fpvs_studio.data_sharing import project_updates as module
from fpvs_studio.data_sharing.errors import DataSharingCancelled, DataSharingError
from fpvs_studio.data_sharing.storage import (
    load_settings,
    queue_report,
    save_settings,
    update_record,
)
from fpvs_studio.runtime.data_sharing import _save_intent


def _bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def test_unconnected_project_check_creates_nothing(tmp_path):
    result = module.inspect_project_update_reporting(tmp_path)
    assert not result.reconnect_required
    assert _bytes(tmp_path) == {}


@pytest.mark.parametrize("enabled", [False, True])
def test_saved_profile_requires_reconnection_without_mutating_choice(tmp_path, enabled):
    settings = enable(tmp_path)
    save_settings(tmp_path, settings.model_copy(update={"enabled": enabled}))
    before = _bytes(tmp_path)
    result = module.inspect_project_update_reporting(tmp_path)
    assert result.reconnect_required
    assert _bytes(tmp_path) == before
    assert load_settings(tmp_path).enabled is enabled


@pytest.mark.parametrize("state", ["pending", "held", "failed"])
def test_all_unaccepted_report_states_block_and_preserve_exact_bytes(tmp_path, state):
    enable(tmp_path)
    record = queue_report(tmp_path, report_fixture())
    if state != "pending":
        update_record(tmp_path, record.model_copy(update={"state": state}))
    before = _bytes(tmp_path)
    with pytest.raises(DataSharingError, match="Download separately") as caught:
        module.inspect_project_update_reporting(tmp_path)
    assert caught.value.code == "pending_results"
    assert _bytes(tmp_path) == before


def test_opted_out_and_previous_scope_reports_still_block(tmp_path):
    settings = enable(tmp_path)
    queue_report(tmp_path, report_fixture(experiment_id="earlier-study"))
    save_settings(tmp_path, settings.model_copy(update={"enabled": False}))
    before = _bytes(tmp_path)
    with pytest.raises(DataSharingError, match="saved Results reports"):
        module.inspect_project_update_reporting(tmp_path)
    assert not load_settings(tmp_path).enabled
    assert _bytes(tmp_path) == before


def test_receipts_and_terminal_exclusions_do_not_block_or_change(tmp_path):
    enable(tmp_path)
    report = report_fixture()
    _upload(tmp_path, report)
    _capture(tmp_path, report)
    _excluded_capture(tmp_path, reason="protocol_mismatch")
    before = _bytes(tmp_path)
    result = module.inspect_project_update_reporting(tmp_path)
    assert result.reconnect_required
    assert _bytes(tmp_path) == before


@pytest.mark.parametrize("state", ["running", "eligible"])
def test_unfinished_or_unqueued_capture_blocks_without_recovering_it(tmp_path, state):
    enable(tmp_path)
    if state == "running":
        intent = _excluded_capture(tmp_path)
        _save_intent(tmp_path, intent.model_copy(update={"state": "running", "reason": None}))
    else:
        _capture(tmp_path, report_fixture(), state="eligible")
    before = _bytes(tmp_path)
    with pytest.raises(DataSharingError, match="Unfinished Results captures"):
        module.inspect_project_update_reporting(tmp_path)
    assert _bytes(tmp_path) == before


@pytest.mark.parametrize("kind", ["settings", "outbox", "intents"])
def test_malformed_reporting_stays_actionable_and_intact(tmp_path, kind):
    enable(tmp_path)
    path = (tmp_path / ".fpvs-data-sharing/settings.json" if kind == "settings" else
            tmp_path / "logs/data-sharing" / kind / (str(uuid4()) + ".json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"{malformed")
    before = _bytes(tmp_path)
    with pytest.raises(DataSharingError, match="needs review"):
        module.inspect_project_update_reporting(tmp_path)
    assert _bytes(tmp_path) == before


def test_cancellation_does_not_read_or_change_storage(tmp_path, monkeypatch):
    cancel = Event()
    cancel.set()
    monkeypatch.setattr(
        module, "load_settings", Mock(side_effect=AssertionError("unexpected read")),
    )
    with pytest.raises(DataSharingCancelled):
        module.inspect_project_update_reporting(tmp_path, cancel_event=cancel)
    assert _bytes(tmp_path) == {}


def test_recheck_detects_new_report_before_commit(tmp_path):
    enable(tmp_path)
    assert module.inspect_project_update_reporting(tmp_path).reconnect_required
    queue_report(tmp_path, report_fixture())
    before = _bytes(tmp_path)
    with pytest.raises(DataSharingError, match="saved Results reports"):
        module.inspect_project_update_reporting(tmp_path)
    assert _bytes(tmp_path) == before
