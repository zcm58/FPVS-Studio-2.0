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
    ElectrodeExclusions,
    FixationOccurrence,
    ParticipantSummary,
    SessionReport,
    SharingSettings,
    SharingStudyChoice,
    SharingStudyChoices,
    protocol_fingerprint,
)


def test_study_discovery_contract_bounds_and_unique_identity():
    choice = SharingStudyChoice(
        project_id=str(uuid4()), title="Named study", experiment_id="study",
        experiment_version="1.0", protocol_sha256="a" * 64,
    )
    assert SharingStudyChoices.model_validate_json(
        SharingStudyChoices(projects=(choice,)).model_dump_json()
    ).projects == (choice,)
    for invalid in (
        {"projects": (choice, choice)},
        {"projects": tuple(choice.model_copy(update={"project_id": str(uuid4())})
                           for _ in range(257))},
        {"projects": (), "device_token": "private"},
    ):
        with pytest.raises(ValidationError):
            SharingStudyChoices.model_validate(invalid)
    for update in (
        {"project_id": "not-a-uuid"}, {"title": "x" * 161},
        {"protocol_sha256": "wrong"}, {"device_token": "private"},
    ):
        with pytest.raises(ValidationError):
            SharingStudyChoice.model_validate({**choice.model_dump(), **update})


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


@pytest.mark.parametrize("removed", [None, (), ("A1", "CUSTOM-REF", "OZ")])
def test_electrode_reports_preserve_unknown_empty_and_known_labels(removed):
    exclusions = ElectrodeExclusions(
        execution_id="1" * 32, visit_id=2, removed_electrodes=removed,
    )
    data = {**report_fixture().model_dump(), "schema_version": "1.1",
            "electrode_exclusions": exclusions, "occurrences": ()}
    report = SessionReport.model_validate(data)
    assert SessionReport.model_validate_json(report.model_dump_json()) == report
    assert report.electrode_exclusions.removed_electrodes == removed


@pytest.mark.parametrize("changes", [
    {"execution_id": "X" * 32}, {"execution_id": "1" * 31},
    {"visit_id": True}, {"visit_id": 0}, {"visit_id": 1_000_000_000},
    {"removed_electrodes": ("ft7",)}, {"removed_electrodes": ("A1", "A1")},
    {"removed_electrodes": ("participant notes",)},
    {"removed_electrodes": ("A" * 81,)},
    {"removed_electrodes": tuple(f"A{index}" for index in range(257))},
    {"removed_electrodes": ({"name": "private"},)},
    {"participant_number": "0007"},
])
def test_electrode_report_rejects_invalid_or_private_fields(changes):
    with pytest.raises(ValidationError):
        ElectrodeExclusions.model_validate({
            "execution_id": "1" * 32, "visit_id": 1, "removed_electrodes": (), **changes,
        })


def test_report_versions_require_their_exact_electrode_contract():
    legacy = report_fixture().model_dump()
    with pytest.raises(ValidationError):
        SessionReport.model_validate({**legacy, "electrode_exclusions": None})
    with pytest.raises(ValidationError):
        SessionReport.model_validate({**legacy, "schema_version": "1.1"})
    with pytest.raises(ValidationError):
        SessionReport.model_validate({**legacy, "occurrences": ()})


@pytest.mark.parametrize("changes", [
    {"age": True}, {"age": 0}, {"age": 121}, {"age": 23.5},
    {"sex": "Other"}, {"handedness": "Left"}, {"colorblind": 1},
    {"subject_id": "0007"}, {"participant_number": "0007"}, {"notes": "private"},
])
def test_participant_summary_is_a_strict_private_allowlist(changes):
    with pytest.raises(ValidationError):
        ParticipantSummary.model_validate({
            "subject_id": str(uuid4()), "age": None, "sex": None,
            "handedness": None, "colorblind": None, **changes,
        })


def test_participant_summary_is_required_only_for_version_1_2():
    exclusions = ElectrodeExclusions(execution_id="1" * 32, visit_id=1, removed_electrodes=())
    summary = ParticipantSummary(subject_id=str(uuid4()), age=None, sex=None,
                                 handedness=None, colorblind=None)
    base = {**report_fixture().model_dump(), "electrode_exclusions": exclusions}
    with pytest.raises(ValidationError):
        SessionReport.model_validate({**base, "schema_version": "1.2"})
    with pytest.raises(ValidationError):
        SessionReport.model_validate({**base, "schema_version": "1.1",
                                      "participant_summary": summary})
    report = SessionReport.model_validate({**base, "schema_version": "1.2",
                                          "participant_summary": summary})
    assert SessionReport.model_validate_json(report.model_dump_json()) == report


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
