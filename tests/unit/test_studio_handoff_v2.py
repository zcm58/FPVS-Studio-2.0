"""Shared writer fixtures and strict, app-version-independent interchange."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from tests.unit.studio_handoff_fixtures import build_handoff_fixtures, legacy_config_payload

from fpvs_studio import __version__
from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.project_config import (
    ProjectConfigError,
    ProjectConfigFile,
    create_project_from_config,
    export_project_config,
    read_project_config,
    write_project_config,
)
from fpvs_studio.core.serialization import load_project_file

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "studio_handoff"


def test_real_producer_matches_portable_consumer_fixtures(tmp_path):
    fixtures = build_handoff_fixtures(tmp_path)
    assert set(fixtures) == {path.name for path in FIXTURES.glob("*.fpvsconfig")}
    for name, config in fixtures.items():
        assert config.producer.version == __version__
        path = tmp_path / name
        write_project_config(path, config)
        actual = json.loads(path.read_text(encoding="utf-8"))
        expected = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        # App releases are provenance, not a new interchange generation.
        expected["producer"]["version"] = __version__
        if "completed_session" in expected:
            expected["completed_session"]["acquisition_evidence"]["studio_version"] = __version__
        assert actual == expected
        assert actual["format_version"] == 2
        assert "schema_version" not in actual
        assert read_project_config(path) == config


def test_completed_6002hz_handoff_preserves_requested_protocol_and_frame_schedule(tmp_path):
    config = read_project_config(FIXTURES / "v2-completed-unicorn-60-02.fpvsconfig")
    assert config.display.preferred_refresh_hz == 60.02
    assert (config.protocol.base_hz, config.protocol.oddball_every_n) == (6.0, 5)
    completed = config.completed_session
    assert completed is not None
    assert completed.refresh_hz == 60.02
    completed_run, = completed.ordered_runs
    start, *oddballs = completed_run.trigger_events
    assert (start.frame_index, start.code, start.label) == (0, 1, "condition_start")
    assert [event.frame_index for event in oddballs] == list(range(40, 7200, 50))
    assert {(event.code, event.label) for event in oddballs} == {(55, "oddball_onset")}

    evidence = completed.acquisition_evidence
    assert evidence is not None
    acquisition_run, = evidence.runs
    assert acquisition_run.completed_frames == 7200
    assert acquisition_run.planned_event_count == len(acquisition_run.attempted_events) == 145
    assert [event.time_s for event in acquisition_run.attempted_events[1:]] == pytest.approx(
        [frame / 60.02 for frame in range(40, 7200, 50)], rel=0, abs=1e-12,
    )

    scaffold = create_project_from_config(tmp_path, config)
    restored = load_project_file(scaffold.project_root / "project.json")
    restored_refresh = restored.settings.display.preferred_refresh_hz
    assert restored_refresh == 60.02
    assert restored.settings.protocol.base_hz == 6.0
    assert restored.settings.protocol.oddball_hz == 1.2
    plan = compile_session_plan(
        restored, project_root=scaffold.project_root, refresh_hz=restored_refresh,
    )
    entry, = plan.ordered_entries()
    assert plan.refresh_hz == 60.02
    assert entry.run_spec.display.total_frames == 7200
    assert entry.run_spec.display.frames_per_stimulus == 10
    assert entry.run_spec.condition.oddball_hz == 1.2
    assert [(trigger.frame_index, trigger.code) for trigger in entry.run_spec.trigger_events] == [
        (trigger.frame_index, trigger.code) for trigger in completed_run.trigger_events
    ]


@pytest.mark.parametrize("version", [f"1.{minor}.0" for minor in range(16)])
def test_all_historical_envelopes_normalize_without_rewriting_sources(
    sample_project, tmp_path, version,
):
    config = export_project_config(sample_project, None)
    payload = legacy_config_payload(config, version)
    path = tmp_path / "historical.fpvsconfig"
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = path.read_bytes()
    imported = read_project_config(path)
    assert (imported.format, imported.format_version, imported.kind) == (
        "fpvs-handoff", 2, "setup",
    )
    assert imported.conditions == config.conditions
    assert imported.protocol == config.protocol
    assert imported.producer == config.producer
    assert path.read_bytes() == before
    assert payload["schema_version"] == version
    assert "format_version" not in payload
    new_path = tmp_path / "current.fpvsconfig"
    write_project_config(new_path, imported)
    written = json.loads(new_path.read_text(encoding="utf-8"))
    assert written["format_version"] == 2
    assert "schema_version" not in written


@pytest.mark.parametrize("producer", [None, {}, {"application": "FPVS Studio"}])
def test_missing_legacy_provenance_remains_unknown(sample_project, producer):
    payload = legacy_config_payload(export_project_config(sample_project, None), "1.2.0")
    if producer is None:
        del payload["producer"]
    else:
        payload["producer"] = producer
    config = ProjectConfigFile.model_validate(payload)
    assert config.producer.version == "unknown"
    assert config.producer.exported_at is None


def test_legacy_nested_handoff_revision_is_not_written_again(sample_project, tmp_path):
    payload = legacy_config_payload(export_project_config(sample_project, None), "1.2.0")
    payload["toolbox"]["handoff_schema_version"] = "1.0"
    config = ProjectConfigFile.model_validate(payload)
    path = tmp_path / "current.fpvsconfig"
    write_project_config(path, config)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["format_version"] == 2
    assert "handoff_schema_version" not in written["toolbox"]


@pytest.mark.parametrize("missing", ["format", "format_version", "kind", "protocol", "producer"])
def test_current_handoffs_require_explicit_contract_fields(sample_project, missing):
    payload = export_project_config(sample_project, None).model_dump(mode="json")
    del payload[missing]
    with pytest.raises(ValidationError, match=missing):
        ProjectConfigFile.model_validate(payload)


@pytest.mark.parametrize("revision", [1, 3, True, 2.0, "2", None])
def test_current_handoffs_reject_unsupported_or_coerced_revision(sample_project, revision):
    payload = export_project_config(sample_project, None).model_dump(mode="json")
    payload["format_version"] = revision
    with pytest.raises(ValidationError, match="format revision"):
        ProjectConfigFile.model_validate(payload)


@pytest.mark.parametrize("scope", ["root", "protocol", "condition"])
def test_unknown_scientific_fields_fail_closed(sample_project, scope):
    payload = export_project_config(sample_project, None).model_dump(mode="json")
    target = {"root": payload, "protocol": payload["protocol"],
              "condition": payload["conditions"][0]}[scope]
    target["unknown_timing_policy"] = "future"
    with pytest.raises(ValidationError, match="unknown_timing_policy"):
        ProjectConfigFile.model_validate(payload)


def test_descriptive_metadata_and_future_app_version_roundtrip(sample_project, tmp_path):
    config = export_project_config(sample_project, None)
    config.producer.version = "999.0.0"
    config.metadata = {"lab": {"label": "Example", "notes": ["descriptive", None]}}
    path = tmp_path / "future-app.fpvsconfig"
    write_project_config(path, config)
    assert read_project_config(path) == config


def test_current_and_legacy_envelopes_cannot_be_mixed(sample_project):
    payload = export_project_config(sample_project, None).model_dump(mode="json")
    payload["schema_version"] = "1.2.0"
    with pytest.raises(ValidationError, match="cannot mix"):
        ProjectConfigFile.model_validate(payload)


def test_kind_must_describe_completion_content(sample_project):
    payload = export_project_config(sample_project, None).model_dump(mode="json")
    payload["kind"] = "completed_session"
    with pytest.raises(ValidationError, match="kind must"):
        ProjectConfigFile.model_validate(payload)


def test_unvalidated_model_copy_cannot_write_or_import_future_revision(sample_project, tmp_path):
    config = export_project_config(sample_project, None).model_copy(update={"format_version": 3})
    path = tmp_path / "export" / "future.fpvsconfig"
    project_root = tmp_path / "projects"
    with pytest.raises(ProjectConfigError, match="format revision"):
        write_project_config(path, config)
    with pytest.raises(ProjectConfigError, match="format revision"):
        create_project_from_config(project_root, config)
    assert not path.parent.exists()
    assert not project_root.exists()
