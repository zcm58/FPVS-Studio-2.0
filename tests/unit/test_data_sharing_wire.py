"""Synthetic fixtures are shared with the Worker's real SQLite intake tests."""

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
