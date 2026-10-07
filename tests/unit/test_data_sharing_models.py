"""Privacy allowlist, metric conservation and protocol identity regressions."""

from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from fpvs_studio.core import data_sharing
from fpvs_studio.core.data_sharing import (
    ComparisonCondition,
    ComparisonSnapshot,
    FixationOccurrence,
    SessionReport,
    SharingSettings,
    protocol_fingerprint,
)


def report_fixture(**changes):
    occurrence = FixationOccurrence(
        condition_id="faces",
        occurrence_index=1,
        total_targets=4,
        hit_count=3,
        miss_count=1,
        false_alarm_count=2,
        accuracy_percent=75.0,
        mean_rt_ms=300.0,
        rt_count=3,
        scoring_source="timestamps",
        refresh_hz=60.0,
        response_window_ms=1000.0,
    )
    fields = dict(
        report_id=str(uuid4()),
        experiment_id="study",
        experiment_version="1.0",
        protocol_sha256="a" * 64,
        completed_at=datetime.now(timezone.utc),
        studio_version="3.0.0",
        occurrences=(occurrence,),
    )
    fields.update(changes)
    return SessionReport(**fields)


@pytest.mark.parametrize("field", ["participant_number", "hostname", "raw_answers", "path"])
def test_report_rejects_private_extra_fields(field):
    with pytest.raises(ValidationError):
        SessionReport.model_validate({**report_fixture().model_dump(), field: "private"})


@pytest.mark.parametrize(
    "changes",
    [
        {"hit_count": True},
        {"miss_count": 0},
        {"accuracy_percent": 76.0},
        {"rt_count": 4},
        {"mean_rt_ms": float("nan")},
        {"mean_rt_ms": None},
        {"total_targets": 1_000_001},
        {"refresh_hz": float("inf")},
    ],
)
def test_occurrence_rejects_inconsistent_or_unbounded_metrics(changes):
    data = report_fixture().occurrences[0].model_dump()
    with pytest.raises(ValidationError):
        FixationOccurrence.model_validate({**data, **changes})


def test_disabled_fixation_null_accuracy_and_rt():
    data = report_fixture().occurrences[0].model_dump()
    result = FixationOccurrence.model_validate(
        {
            **data,
            "total_targets": 0,
            "hit_count": 0,
            "miss_count": 0,
            "accuracy_percent": None,
            "mean_rt_ms": None,
            "rt_count": 0,
        }
    )
    assert result.accuracy_percent is None
    assert result.mean_rt_ms is None


def test_duplicate_occurrences_and_oversized_report_rejected():
    occurrence = report_fixture().occurrences[0]
    with pytest.raises(ValidationError, match="unique"):
        report_fixture(occurrences=(occurrence, occurrence))
    occurrences = tuple(
        occurrence.model_copy(update={"occurrence_index": i}) for i in range(1, 1000)
    )
    with pytest.raises(ValidationError, match="128 KiB"):
        report_fixture(occurrences=occurrences)


def test_reporting_default_is_off():
    assert not SharingSettings().enabled
    with pytest.raises(ValidationError):
        SharingSettings(enabled=True)


def test_comparison_suppression_and_thresholds():
    condition = ComparisonCondition(
        condition_id="faces",
        session_count=9,
        device_count=3,
        eligible=False,
        total_targets=None,
        hit_count=None,
        accuracy_percent=None,
        mean_rt_ms=None,
        rt_count=None,
        scoring_source=None,
        response_window_ms=None,
    )
    with pytest.raises(ValidationError):
        ComparisonCondition.model_validate({**condition.model_dump(), "hit_count": 1})
    condition = condition.model_copy(
        update={
            "eligible": True,
            "total_targets": 0,
            "hit_count": 0,
            "rt_count": 0,
            "scoring_source": "timestamps",
            "response_window_ms": 1000.0,
        }
    )
    with pytest.raises(ValidationError, match="ten sessions"):
        ComparisonSnapshot(
            experiment_id="study",
            experiment_version="1.0",
            protocol_sha256="a" * 64,
            conditions=(condition,),
            generated_at=datetime.now(timezone.utc),
        )


def test_protocol_excludes_identity_seeds_and_machine_settings(sample_project, sample_project_root):
    before = protocol_fingerprint(sample_project, sample_project_root)
    project = sample_project.model_copy(deep=True)
    project.meta.name = "Renamed experiment"
    project.settings.session.session_seed += 1
    project.settings.triggers.serial_port = "COM19"
    project.settings.display.monitor_name = "Another display"
    project.manual_removed_electrodes = {"0009": ["A1"]}
    assert protocol_fingerprint(project, sample_project_root) == before
    project.settings.fixation_task.response_window_seconds += 0.1
    assert protocol_fingerprint(project, sample_project_root) != before


def test_protocol_detects_actual_asset_edits_and_ignores_unrelated_files(
    sample_project, sample_project_root
):
    before = protocol_fingerprint(sample_project, sample_project_root)
    (sample_project_root / "stimuli" / "unrelated.txt").write_text("ignored")
    assert protocol_fingerprint(sample_project, sample_project_root) == before
    source = next((sample_project_root / sample_project.stimulus_sets[0].source_dir).glob("*.png"))
    source.write_bytes(source.read_bytes() + b"changed")
    assert protocol_fingerprint(sample_project, sample_project_root) != before


def test_protocol_immediate_cancellation_does_not_traverse_hash_or_write(
    sample_project,
    sample_project_root,
    monkeypatch,
):
    files = {path: path.read_bytes() for path in sample_project_root.rglob("*") if path.is_file()}
    original_project = sample_project.model_dump_json()
    hash_spy = Mock(side_effect=AssertionError("Hashing should not start."))
    manifest_spy = Mock(side_effect=AssertionError("Traversal should not start."))
    monkeypatch.setattr(data_sharing.hashlib, "sha256", hash_spy)
    monkeypatch.setattr(data_sharing, "load_manifest", manifest_spy)
    with pytest.raises(InterruptedError, match="Protocol verification cancelled"):
        protocol_fingerprint(sample_project, sample_project_root, cancelled=lambda: True)
    hash_spy.assert_not_called()
    manifest_spy.assert_not_called()
    assert sample_project.model_dump_json() == original_project
    assert {
        path: path.read_bytes() for path in sample_project_root.rglob("*") if path.is_file()
    } == files


def test_protocol_mid_hash_cancellation_stops_before_next_chunk_or_file(
    sample_project,
    sample_project_root,
    monkeypatch,
):
    source = sorted(
        (sample_project_root / sample_project.stimulus_sets[0].source_dir).glob("*.png")
    )[0]
    source.write_bytes(b"synthetic asset bytes" * 150_000)
    cancel = Event()
    original_open = Path.open
    reads = []
    streams = []

    class CancelAfterFirstRead:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def read(self, size):
            chunk = self.stream.read(size)
            reads.append(len(chunk))
            cancel.set()
            return chunk

    def monitored_open(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        if args == ("rb",) and path.suffix == ".png":
            streams.append(stream)
            return CancelAfterFirstRead(stream)
        return stream

    monkeypatch.setattr(Path, "open", monitored_open)
    with pytest.raises(InterruptedError, match="Protocol verification cancelled"):
        protocol_fingerprint(sample_project, sample_project_root, cancelled=cancel.is_set)
    assert reads == [1024 * 1024]
    assert len(streams) == 1
    assert streams[0].closed
