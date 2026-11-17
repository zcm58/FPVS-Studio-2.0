"""Automatic workflow contracts, opt-out and durable delivery without real HTTP."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

from fpvs_studio.support import workflow_reporting as workflow
from fpvs_studio.support.crash_reporting import CrashStore


def report(**changes):
    fields = {
        "workflow": "macos_repair", "outcome": "success", "app_version": "3.0.1",
        "os_version": "27.0", "details": {
            "cpu": "arm64", "python_cpu": "arm64", "rosetta": "native",
            "python_version": "3.10.22", "initial_scipy_version": "1.15.3",
            "final_scipy_version": "1.14.1", "engine_import": "passed",
            "initial_failure_code": "scipy_macho", "failure_code": "none",
            "check_only": False, "elapsed_seconds": 70.6, "macos_build": "26A123",
        },
    }
    fields.update(changes)
    return workflow.build_report(**fields)


class Service:
    def __init__(self):
        self.calls = []
        self.uploads = {}

    def __call__(self, method, url, data, headers):
        body = json.loads(data)
        self.calls.append((method, url, data, headers))
        if url.endswith("/revoke"):
            assert body == {}
            return json.dumps({
                "installation_id": headers["X-Installation-ID"], "state": "revoked",
            }).encode()
        if url.endswith("/workflow-installations"):
            return json.dumps({
                "installation_id": body["installation_id"], "state": "registered",
                "expires_at": time.time() + 86400,
            }).encode()
        assert url.endswith("/workflow-reports")
        identity = body["report"]["report_id"]
        if identity in self.uploads:
            assert self.uploads[identity] == data
        self.uploads[identity] = data
        return json.dumps({"report_id": identity, "state": "received"}).encode()


def consent_path(root):
    return root / "automatic-crashes" / "consent.json"


def change_consent(root, **changes):
    path = consent_path(root)
    path.parent.mkdir(exist_ok=True)
    value = (json.loads(path.read_text()) if path.exists() else {
        "enabled": True, "installation_id": str(uuid4()), "revoke_pending": False,
    })
    value.update(changes)
    path.write_text(json.dumps(value), encoding="utf-8")


def record_path(root, value):
    return root / "automatic-workflows" / f"workflow-{value['report_id']}.json"


def test_module_loads_by_filename_without_site_packages(tmp_path):
    script = (
        "import importlib.util, sys; "
        "spec=importlib.util.spec_from_file_location('workflow', sys.argv[1]); "
        "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
        "assert 'pydantic' not in sys.modules; assert 'PySide6' not in sys.modules; "
        "r=module.build_report(workflow='macos_repair',outcome='failure',"
        "app_version='3.0.1',os_version='27.0',details={'failure_code':'scipy_macho'}); "
        "assert 'Mac setup: Incomplete' in module.render_report(r)"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", script, str(Path(workflow.__file__).resolve())],
        cwd=tmp_path, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("details", [
    {"log": "participant and secret"}, {"python_version": "/Users/private/python"},
    {"failure_code": "token=private"}, {"cpu": "hostname"}, {"rosetta": "other"},
    {"elapsed_seconds": float("nan")}, {"elapsed_seconds": True},
    {"elapsed_seconds": 86401}, {"check_only": "false"},
    {"macos_build": "27.0/private"}, {"engine_import": "private error message"},
    {"initial_engine_import": "private error"}, {"initial_dependency_check": True},
    {"initial_compatibility_check": "different"}, {"compatibility_check": "different"},
    {"package_updates": "reinstalled everything"}, {"change_kind": "private error"},
])
def test_report_rejects_unstructured_or_invalid_details(details):
    with pytest.raises(ValueError):
        report(details=details)


@pytest.mark.parametrize("changes", [
    {"outcome": "unknown"}, {"workflow": "../../private"},
    {"app_version": "secret@example.test"}, {"os_version": "Darwin /Users/private"},
    {"report_id": "../../private"}, {"created_at": "2026-11-16"},
])
def test_report_rejects_invalid_top_level_fields(changes):
    with pytest.raises(ValueError):
        report(**changes)


def test_extra_top_level_data_and_changed_summary_are_rejected():
    value = report()
    value["logs"] = "private"
    with pytest.raises(ValueError):
        workflow.validate_report(value)
    value.pop("logs")
    value["summary"] = "private"
    with pytest.raises(ValueError):
        workflow.render_report(value)


def test_renderer_is_compact_and_explains_versions_and_repair_results():
    value = report(outcome="action_required")
    value["details"].update({
        "initial_studio_version": "2.8.1", "final_studio_version": "3.0.1",
        "psychopy_version": "2026.2.5", "numpy_version": "2.2.6",
        "pyside6_version": "6.11.3", "dependency_check": "passed",
        "environment_rebuild": "skipped", "pycharm_configuration": "action_required",
        "helper_version": "2.1", "change_kind": "repair",
        "initial_engine_import": "failed", "initial_dependency_check": "passed",
        "initial_compatibility_check": "failed", "compatibility_check": "passed",
        "package_updates": "passed", "failure_code": "ide_configuration_failed",
    })
    rendered = workflow.render_report(value)
    assert "Studio package metadata: 2.8.1 → 3.0.1" in rendered
    assert "SciPy: 1.15.3 → 1.14.1" in rendered
    assert "Mac processor: Apple Silicon" in rendered
    assert "PyCharm configuration: action required" in rendered
    assert "Original problem: macOS could not load SciPy's compiled library." in rendered
    assert "Remaining problem: PyCharm configuration did not complete." in rendered
    assert "initial_failure_code" not in rendered
    assert len(rendered.splitlines()) <= 20


def test_dependency_version_mismatch_has_a_specific_explanation():
    value = report(outcome="failure", details={"failure_code": "dependency_mismatch"})
    assert "Installed package versions do not match this Studio source." in (
        workflow.render_report(value)
    )


@pytest.mark.parametrize(("kind", "expected"), [
    ("compatibility_update", "Compatibility updates completed"),
    ("repair", "Repair completed"),
    ("none", "Checks passed; no package updates needed"),
    ("unknown", "Completed"),
])
def test_completion_heading_uses_recorded_change_kind(kind, expected):
    rendered = workflow.render_report(report(details={"change_kind": kind}))
    assert rendered.splitlines()[0] == f"FPVS Studio Mac setup: {expected}"


def test_healthy_engine_with_version_drift_is_reported_as_an_update():
    value = report()
    value["details"].update({
        "change_kind": "compatibility_update", "initial_engine_import": "passed",
        "initial_dependency_check": "passed", "initial_compatibility_check": "failed",
        "dependency_check": "passed", "compatibility_check": "passed",
        "package_updates": "passed", "environment_rebuild": "skipped",
        "initial_failure_code": "dependency_mismatch", "pycharm_configuration": "passed",
        "initial_studio_version": "2.8.0", "final_studio_version": "3.0.1",
        "psychopy_version": "2026.2.5", "numpy_version": "2.2.6",
        "pyside6_version": "6.11.3", "helper_version": "2.1",
    })
    rendered = workflow.render_report(value)
    assert "Compatibility updates completed" in rendered
    assert "Before changes: engine passed; dependencies passed" in rendered
    assert "Final checks: engine passed; dependencies passed" in rendered
    assert "Source requirements: updates available → matched" in rendered
    assert "Package updates: passed; Environment rebuild: skipped" in rendered
    assert "Original problem" not in rendered
    assert "Repair completed" not in rendered
    assert len(rendered.splitlines()) <= 20


def test_failed_compatibility_update_preserves_healthy_baseline_and_failed_final_check():
    rendered = workflow.render_report(report(outcome="failure", details={
        "change_kind": "compatibility_update", "initial_engine_import": "passed",
        "engine_import": "failed", "package_updates": "failed",
        "failure_code": "engine_import_failed",
    }))
    assert "Compatibility update incomplete" in rendered
    assert "Before changes: engine passed" in rendered
    assert "Final checks: engine failed" in rendered
    assert "Remaining problem: The presentation engine could not load its dependencies." in rendered
    assert "completed" not in rendered.lower()


@pytest.mark.parametrize("outcome", ["success", "failure", "action_required"])
def test_check_only_reports_do_not_claim_changes(outcome):
    rendered = workflow.render_report(report(outcome=outcome, details={
        "check_only": True, "change_kind": "repair",
        "initial_engine_import": "passed", "engine_import": "passed",
        "initial_dependency_check": "passed", "dependency_check": "passed",
        "initial_compatibility_check": "failed", "compatibility_check": "failed",
        "failure_code": "dependency_mismatch", "package_updates": "skipped",
        "environment_rebuild": "skipped",
    }))
    assert "Check only; no changes made" in rendered
    assert "Repair completed" not in rendered
    assert "Compatibility updates completed" not in rendered
    assert "Checks: engine passed; dependencies passed" in rendered
    assert "Source requirements: updates available\n" in rendered
    assert "Before changes" not in rendered
    assert "→" not in rendered
    assert "Package updates:" not in rendered
    assert "Remaining problem" not in rendered


@pytest.mark.parametrize(("kind", "expected"), [
    ("compatibility_update", "Compatibility updates need user action"),
    ("repair", "Repair needs user action"),
])
def test_action_required_identifies_the_attempted_work(kind, expected):
    rendered = workflow.render_report(report(
        outcome="action_required", details={"change_kind": kind},
    ))
    assert rendered.splitlines()[0] == f"FPVS Studio Mac setup: {expected}"


def test_legacy_success_does_not_infer_that_a_repair_was_necessary():
    rendered = workflow.render_report(report())
    assert rendered.splitlines()[0] == "FPVS Studio Mac setup: Completed"
    assert "Repair completed" not in rendered


def test_receipt_precedes_http_and_same_identity_is_not_sent_twice(tmp_path):
    service = Service()
    reporter = workflow.WorkflowReporter(tmp_path, transport=service)
    value = report()
    assert reporter.queue(value)
    saved = json.loads(record_path(tmp_path, value).read_text())
    receipt = saved["receipt_token"]
    assert reporter.status(value["report_id"]) == "queued"
    assert reporter.deliver() == 1
    assert reporter.status(value["report_id"]) == "submitted"
    assert reporter.queue(value)
    assert reporter.deliver() == 0
    assert len(service.calls) == 2
    payload = json.loads(service.calls[-1][2])
    assert payload == {
        "report": value, "receipt_token_sha256": hashlib.sha256(receipt.encode()).hexdigest(),
    }
    installation = json.loads((tmp_path / "automatic-workflows/installation.json").read_text())
    capability = installation["current"]
    assert service.calls[-1][3]["X-Installation-ID"] == capability["installation_id"]
    assert service.calls[-1][3]["Authorization"] == f"Bearer {capability['token']}"
    assert receipt not in service.calls[-1][2].decode()
    assert not consent_path(tmp_path).exists()  # Workflow code never creates the GUI preference.


def test_report_identity_cannot_be_reused_for_different_payload(tmp_path):
    reporter = workflow.WorkflowReporter(tmp_path)
    value = report()
    reporter.queue(value)
    with pytest.raises(ValueError, match="different contents"):
        reporter.queue(report(report_id=value["report_id"], outcome="failure"))


def test_ambiguous_upload_preserves_identical_payload_and_backoff(tmp_path, monkeypatch):
    service = Service()
    value = report()

    def ambiguous(method, url, data, headers):
        response = service(method, url, data, headers)
        if url.endswith("/workflow-reports"):
            raise workflow.WorkflowReportError("The request timed out.")
        return response

    reporter = workflow.WorkflowReporter(tmp_path, transport=ambiguous)
    reporter.queue(value)
    with pytest.raises(workflow.WorkflowReportError):
        reporter.deliver()
    assert reporter.status(value["report_id"]) == "queued"
    first = json.loads(record_path(tmp_path, value).read_text())
    assert first["attempts"] == 1
    assert first["next_attempt"] > time.time()
    reporter.transport = service
    assert reporter.deliver() == 0
    monkeypatch.setattr(workflow.time, "time", lambda: first["next_attempt"] + 1)
    assert reporter.deliver() == 1
    second = json.loads(record_path(tmp_path, value).read_text())
    assert second["receipt_token"] == first["receipt_token"]
    assert second["report"] == first["report"]
    assert second["attempts"] == 2


def test_optout_discards_pending_capture_and_revokes_without_upload(tmp_path):
    service = Service()
    reporter = workflow.WorkflowReporter(tmp_path, transport=service)
    value = report()
    reporter.queue(value)
    change_consent(tmp_path, enabled=False)
    assert not reporter.queue(report())
    assert reporter.status(value["report_id"]) == "disabled"
    assert reporter.deliver() == 0
    assert len(service.calls) == 1 and service.calls[0][1].endswith("/revoke")
    assert not record_path(tmp_path, value).exists()


def test_optout_during_registration_prevents_upload_without_overwriting_preference(tmp_path):
    service = Service()

    def optout(method, url, data, headers):
        result = service(method, url, data, headers)
        change_consent(tmp_path, enabled=False)
        return result

    reporter = workflow.WorkflowReporter(tmp_path, transport=optout)
    reporter.queue(report())
    assert reporter.deliver() == 0
    assert len(service.calls) == 1
    assert not json.loads(consent_path(tmp_path).read_text())["enabled"]


def test_old_preference_generation_is_never_uploaded(tmp_path):
    service = Service()
    reporter = workflow.WorkflowReporter(tmp_path, transport=service)
    value = report()
    reporter.queue(value)
    change_consent(tmp_path, installation_id=str(uuid4()))
    assert reporter.deliver() == 0
    assert reporter.status(value["report_id"]) == "missing"
    assert len(service.calls) == 1 and service.calls[0][1].endswith("/revoke")


def test_crash_revocation_does_not_block_reenabled_workflow_reporting(tmp_path):
    change_consent(tmp_path, enabled=True, revoke_pending=True)
    original = consent_path(tmp_path).read_bytes()
    service = Service()
    reporter = workflow.WorkflowReporter(tmp_path, transport=service)
    value = report()
    assert reporter.queue(value)
    assert reporter.deliver() == 1
    assert reporter.status(value["report_id"]) == "submitted"
    assert consent_path(tmp_path).read_bytes() == original


def test_reenable_rotates_workflow_capability_and_does_not_backfill(tmp_path):
    service = Service()
    reporter = workflow.WorkflowReporter(tmp_path, transport=service)
    change_consent(tmp_path, enabled=True)
    first = report()
    reporter.queue(first)
    old_state = json.loads((tmp_path / "automatic-workflows/installation.json").read_text())
    change_consent(tmp_path, enabled=False)
    assert not reporter.queue(report())
    change_consent(tmp_path, enabled=True, revoke_pending=True)
    second = report()
    assert reporter.queue(second)
    assert reporter.deliver() == 1
    new_state = json.loads((tmp_path / "automatic-workflows/installation.json").read_text())
    assert new_state["current"]["installation_id"] != old_state["current"]["installation_id"]
    assert first["report_id"] not in service.uploads
    assert second["report_id"] in service.uploads
    assert new_state["retired"] == []


def test_actual_gui_optout_and_reenable_invalidates_unobserved_workflow_generation(tmp_path):
    crash_store = CrashStore(tmp_path)
    original = crash_store.consent()
    service = Service()
    reporter = workflow.WorkflowReporter(tmp_path, transport=service)
    first = report()
    reporter.queue(first)
    crash_store.disable()
    enabled = crash_store.enable()
    assert enabled.installation_id == original.installation_id
    assert enabled.revoke_pending
    assert enabled.workflow_generation != original.workflow_generation
    assert reporter.deliver() == 0
    assert first["report_id"] not in service.uploads
    assert not record_path(tmp_path, first).exists()
    second = report()
    reporter.queue(second)
    assert reporter.deliver() == 1
    assert second["report_id"] in service.uploads


def test_disabled_origin_and_unapproved_origins_never_make_requests(tmp_path, monkeypatch):
    service = Service()
    monkeypatch.setenv("FPVS_REPORT_SERVICE_URL", "")
    reporter = workflow.WorkflowReporter(tmp_path, transport=service)
    value = report()
    reporter.queue(value)
    assert reporter.deliver() == 0
    assert reporter.status(value["report_id"]) == "disabled"
    assert not service.calls
    for origin in (
        "http://reports.zack-murphy.com", "https://evil.test", workflow.SERVICE_ORIGIN + "/",
    ):
        with pytest.raises(ValueError):
            workflow.WorkflowReporter(tmp_path, origin=origin, transport=service)


@pytest.mark.parametrize("content", ["invalid", "{}", '{"enabled": false}'])
def test_invalid_saved_preference_never_resets_to_enabled(tmp_path, content):
    folder = tmp_path / "automatic-crashes"
    folder.mkdir()
    consent_path(tmp_path).write_text(content)
    service = Service()
    reporter = workflow.WorkflowReporter(tmp_path, transport=service)
    with pytest.raises(ValueError):
        reporter.queue(report())
    with pytest.raises(ValueError):
        reporter.deliver()
    assert not service.calls
    assert consent_path(tmp_path).read_text() == content


@pytest.mark.parametrize("status,expected", [(400, "rejected"), (409, "rejected"),
                                           (429, "queued"), (503, "queued"), (401, "queued")])
def test_rejected_and_retryable_delivery_status(tmp_path, status, expected):
    service = Service()

    def rejected(method, url, data, headers):
        if url.endswith("/workflow-reports"):
            raise workflow.WorkflowReportError("Request not accepted.", status=status)
        return service(method, url, data, headers)

    reporter = workflow.WorkflowReporter(tmp_path, transport=rejected)
    value = report()
    reporter.queue(value)
    with pytest.raises(workflow.WorkflowReportError):
        reporter.deliver()
    assert reporter.status(value["report_id"]) == expected


def test_queue_is_bounded_expires_and_only_attempts_three_per_pass(tmp_path, monkeypatch):
    now = time.time()
    service = Service()
    reporter = workflow.WorkflowReporter(tmp_path, transport=service)
    monkeypatch.setattr(workflow.time, "time", lambda: now)
    old = report()
    reporter.queue(old)
    now += workflow.MAX_AGE_SECONDS + 1
    values = []
    for _ in range(12):
        now += 1
        value = report()
        values.append(value)
        reporter.queue(value)
    paths = list((tmp_path / "automatic-workflows").glob("workflow-*.json"))
    assert len(paths) == 10
    assert not record_path(tmp_path, old).exists()
    assert not record_path(tmp_path, values[0]).exists()
    assert reporter.deliver() == 3
    assert len(service.uploads) == 3


def test_storage_rejects_redirected_file_without_reading_it(tmp_path):
    reporter = workflow.WorkflowReporter(tmp_path)
    value = report()
    reporter.queue(value)
    external = tmp_path / "external.txt"
    external.write_text("private-secret")
    path = record_path(tmp_path, value)
    path.unlink()
    try:
        path.symlink_to(external)
    except OSError:
        pytest.skip("Symlink creation is unavailable on this Windows account.")
    with pytest.raises(OSError, match="links or special files"):
        reporter.deliver()
    assert external.read_text() == "private-secret"


def test_posix_capabilities_are_private(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX mode assertion.")
    reporter = workflow.WorkflowReporter(tmp_path)
    value = report()
    reporter.queue(value)
    assert (tmp_path / "automatic-workflows/installation.json").stat().st_mode & 0o777 == 0o600
    assert record_path(tmp_path, value).stat().st_mode & 0o777 == 0o600
