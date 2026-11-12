"""Exercise the read-only Unicorn timing report against known event timelines."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fpvs_studio.core.execution import (
    AcquisitionCodeMapEntry,
    AcquisitionEvidence,
    AcquisitionRunEvidence,
    RecordingSnapshot,
    TriggerRecord,
)
from fpvs_studio.tools import unicorn_timing


@pytest.fixture
def recording_paths(tmp_path: Path) -> tuple[Path, Path]:
    bdf_path = tmp_path / "Unicorn bench recording.bdf"
    bdf_path.write_bytes(b"stand-in for the BDF reader")
    evidence_path = tmp_path / "bench.acquisition-v1.json"
    timestamp = datetime(2000, 1, 1, tzinfo=timezone.utc)
    trigger_records = [
        TriggerRecord(
            trigger_index=0,
            frame_index=-1,
            time_s=0.0,
            code=1,
            label="condition_start",
            backend_name="unicorn_udp",
        )
    ]
    trigger_records.extend(
        TriggerRecord(
            trigger_index=index,
            frame_index=50 * index,
            time_s=50 * index / 60,
            code=55,
            label="oddball",
            backend_name="unicorn_udp",
        )
        for index in range(1, 121)
    )
    evidence = AcquisitionEvidence(
        studio_version="3.0.1",
        execution_id="bench",
        project_id="fixture",
        participant_number="1",
        recording=RecordingSnapshot(
            selected_backend="unicorn_udp",
            effective_backend="unicorn_udp",
            selection_source="project_settings",
            receiver_validation="pending",
        ),
        created_at_utc=timestamp,
        updated_at_utc=timestamp,
        state="completed",
        runs=[
            AcquisitionRunEvidence(
                run_id="run-1",
                condition_id="condition-1",
                condition_name="Bench condition",
                code_map=[
                    AcquisitionCodeMapEntry(code=1, label="condition_start"),
                    AcquisitionCodeMapEntry(code=55, label="oddball"),
                ],
                planned_event_count=len(trigger_records),
                attempted_events=trigger_records,
                state="completed",
                completed_frames=6001,
            )
        ],
    )
    evidence_path.write_text(evidence.model_dump_json(), encoding="utf-8")
    return bdf_path, evidence_path


def _mock_bdf(monkeypatch: pytest.MonkeyPatch, condition_start_code: int = 1) -> None:
    oddballs = tuple(
        (540 + round(index * 250.25 * 5 / 6), 55)
        for index in range(1, 121)
    )
    recording = unicorn_timing.UnicornBdf(
        sample_rate_hz=250.0,
        sample_count=30_000,
        markers=((540, condition_start_code), *oddballs),
        counter_discontinuities=(),
        invalid_samples=(),
    )
    monkeypatch.setattr(unicorn_timing, "read_unicorn_bdf", lambda path: recording)


def test_report_quantifies_relative_drift(
    recording_paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_bdf(monkeypatch)
    bdf_path, evidence_path = recording_paths
    report_path = bdf_path.with_name("timing report.md")

    args = [str(bdf_path), str(evidence_path), "--output", str(report_path)]
    assert unicorn_timing.main(args) == 0

    report = report_path.read_text(encoding="utf-8")
    assert report.startswith("# Unicorn timing report")
    assert "Ordered marker codes match: yes" in report
    assert "Endpoint drift (BDF minus Studio): +100.000 ms" in report
    rate = re.search(r"Apparent sample rate relative to Studio: ([\d.]+) samples/s", report)
    assert rate is not None
    assert float(rate[1]) == pytest.approx(250.25, abs=0.001)
    residual = re.search(r"Fit residual RMS: ([\d.]+) ms", report)
    assert residual is not None
    assert 0.0 < float(residual[1]) < 2.0


def test_report_withholds_fit_for_marker_code_mismatch(
    recording_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _mock_bdf(monkeypatch, condition_start_code=2)

    assert unicorn_timing.main([str(path) for path in recording_paths]) == 0

    report = capsys.readouterr().out
    assert "Ordered marker codes match: no" in report
    assert "Drift fit withheld:" in report
    assert "Apparent sample rate relative to Studio:" not in report
    assert "Endpoint drift (BDF minus Studio):" not in report


@pytest.mark.parametrize("colliding_input", [False, True])
def test_report_refuses_to_overwrite_existing_file(
    recording_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    colliding_input: bool,
) -> None:
    _mock_bdf(monkeypatch)
    bdf_path, evidence_path = recording_paths
    report_path = bdf_path if colliding_input else bdf_path.with_name("existing.md")
    if not colliding_input:
        report_path.write_text("Existing report", encoding="utf-8")
    original = report_path.read_bytes()

    with pytest.raises(SystemExit) as error:
        unicorn_timing.main([str(bdf_path), str(evidence_path), "--output", str(report_path)])

    assert error.value.code == 2
    assert report_path.read_bytes() == original


def test_report_rejects_missing_input_without_creating_output(
    recording_paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_bdf(monkeypatch)
    bdf_path, evidence_path = recording_paths
    report_path = bdf_path.with_name("timing.md")
    evidence_path.unlink()

    with pytest.raises(SystemExit) as error:
        unicorn_timing.main([str(bdf_path), str(evidence_path), "--output", str(report_path)])

    assert error.value.code == 2
    assert not report_path.exists()
