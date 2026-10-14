"""Synthetic fixtures are shared with the Worker's real SQLite intake tests."""

import json
from pathlib import Path

import pytest

from fpvs_studio.core.data_sharing import ComparisonSnapshot, SessionReport, SharingProfile

FIXTURES = Path(__file__).resolve().parents[2] / "services" / "results" / "fixtures"


@pytest.mark.parametrize(
    "name, model",
    [
        ("report-v1.json", SessionReport),
        ("profile-v1.json", SharingProfile),
        ("comparison-v1.json", ComparisonSnapshot),
    ],
)
def test_worker_wire_fixture_is_accepted_by_desktop(name, model):
    wire = (FIXTURES / name).read_bytes()
    parsed = model.model_validate_json(wire)
    assert parsed.experiment_id == "test-faces"
    assert parsed.experiment_version == "1.0.0"
    assert parsed.protocol_sha256 == "a" * 64
    assert model.model_validate_json(parsed.model_dump_json()) == parsed


def test_legacy_report_serialization_retains_exact_previous_payload_bytes():
    wire = (FIXTURES / "report-v1.json").read_bytes()
    expected = json.loads(wire)
    expected["completed_at"] = "2026-10-05T14:00:00Z"
    parsed = SessionReport.model_validate_json(wire)
    assert parsed.model_dump_json() == json.dumps(expected, separators=(",", ":"))
    assert "electrode_exclusions" not in parsed.model_dump()


def test_electrode_only_version_1_1_does_not_acquire_participant_fields():
    data = json.loads((FIXTURES / "report-v1.json").read_bytes())
    data.update(schema_version="1.1", electrode_exclusions={
        "schema_version": "1.0", "execution_id": "1" * 32,
        "visit_id": 1, "removed_electrodes": [],
    })
    parsed = SessionReport.model_validate_json(json.dumps(data))
    expected = {**data, "completed_at": "2026-10-05T14:00:00Z"}
    assert parsed.model_dump_json() == json.dumps(expected, separators=(",", ":"))
    assert "participant_summary" not in parsed.model_dump()
