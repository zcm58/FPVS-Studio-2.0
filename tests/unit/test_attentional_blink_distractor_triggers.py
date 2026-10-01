"""All-character marker playback through fake windows and external transports."""

from collections import Counter
from types import SimpleNamespace

import pytest
from tests.unit.test_psychopy_engine import _build_fake_psychopy, _patch_fake_psychopy

from fpvs_studio.core.compiler import compile_run_spec
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.project_service import build_starter_project
from fpvs_studio.engines.psychopy_engine import PsychoPyEngine
from fpvs_studio.runtime.session_export import write_run_artifacts
from fpvs_studio.runtime.triggers import LoggedTriggerBackend, TriggerEmissionError
from fpvs_studio.triggers.serial_backend import SerialBackend
from fpvs_studio.triggers.unicorn_udp_backend import UnicornUDPBackend


def _msms_run(soa_ms, refresh_hz):
    project = build_starter_project(
        "MSMS markers", experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
    )
    project.settings.protocol.oddball_every_n = 90
    for code, condition in enumerate(project.conditions, start=1):
        condition.trigger_code = code
        settings = condition.attentional_blink
        settings.t2_slot_index = 21 + round(settings.soa_ms / 100)
        settings.target_count = 6
        settings.target_interval_slots = 10
        settings.omit_first_t2 = True
        settings.distractor_trigger_code = 57
    condition = next(c for c in project.conditions if c.attentional_blink.soa_ms == soa_ms)
    return compile_run_spec(
        project, condition_id=condition.condition_id, refresh_hz=refresh_hz, random_seed=42,
    )


def _external_backend(transport, submit):
    if transport == "serial":
        adapter = SerialBackend(serial_module=SimpleNamespace(
            EIGHTBITS=8, PARITY_NONE="N", STOPBITS_ONE=1,
            Serial=lambda **_kwargs: SimpleNamespace(write=submit, close=lambda: None),
        ))
    else:
        adapter = UnicornUDPBackend(socket_factory=lambda *_args: SimpleNamespace(
            setblocking=lambda _flag: None, sendto=submit, close=lambda: None,
        ))
    return LoggedTriggerBackend(adapter, backend_name=transport)


@pytest.mark.parametrize("soa_ms,condition_code", [(100, 1), (300, 2), (500, 3)])
@pytest.mark.parametrize("refresh_hz", [60, 120, 240])
@pytest.mark.parametrize("transport,warmup", [("serial", 0), ("unicorn_udp", 3)])
def test_every_character_emits_one_byte_on_its_own_flip(
    monkeypatch, tmp_path, soa_ms, condition_code, refresh_hz, transport, warmup,
):
    run = _msms_run(soa_ms, refresh_hz)
    captures = {}
    fake = _build_fake_psychopy(
        captures, actual_frame_rate=refresh_hz,
        flip_times=[(index + 1) / refresh_hz
                    for index in range(warmup + run.display.total_frames + 2)],
    )
    draws = []
    original_draw = fake.visual.TextStim.draw

    def record_draw(stimulus):
        original_draw(stimulus)
        if any(event[0] == "clearBuffer" for event in captures["events"]):
            draws.append((captures["window"]._flip_index, stimulus.text))

    monkeypatch.setattr(fake.visual.TextStim, "draw", record_draw)
    monkeypatch.setattr("fpvs_studio.engines.psychopy_stimuli.synchronize_gpu", lambda: None)
    submissions = []

    def submit(payload, *_args):
        submissions.append((captures["window"]._flip_index - 1, payload))
        return len(payload)

    backend = _external_backend(transport, submit)
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake)
    backend.connect()
    try:
        result = engine.run_condition(
            run, tmp_path, runtime_options={"timing_warmup_frames": warmup},
            trigger_backend=backend,
        )
    finally:
        backend.close()
        engine.close_session()

    records = backend.records
    assert Counter(record.code for record in records) == {
        condition_code: 1, 55: 6, 56: 5, 57: 79,
    }
    assert all(record.status == "sent" for record in records)
    assert [(r.frame_index, r.code, r.label) for r in records] == [
        (e.frame_index, e.code, e.label) for e in run.trigger_events
    ]
    assert [flip for flip, _ in submissions] == [
        warmup + 1 + event.frame_index for event in run.trigger_events
    ]
    assert len({flip for flip, _ in submissions}) == 91
    expected_codes = [event.code for event in run.trigger_events]
    assert [payload for _, payload in submissions] == [
        bytes([code]) if transport == "serial" else str(code).encode("ascii")
        for code in expected_codes
    ]
    assert [record.time_s for record in records] == pytest.approx([
        (event.frame_index + 2) / refresh_hz for event in run.trigger_events
    ])
    assert not any(flip == warmup for flip, _ in draws)
    assert (warmup + 1, run.stimulus_sequence[0].text) in draws
    assert captures["window"]._flip_index == warmup + 1 + run.display.total_frames + 1
    assert result.completed_frames == run.display.total_frames == 9 * refresh_hz
    assert not result.aborted
    assert len(result.attentional_blink_onsets) == 90
    assert [onset.time_s for onset in result.attentional_blink_onsets] == pytest.approx([
        index / 10 for index in range(90)
    ])
    result.trigger_log = list(records)
    write_run_artifacts(tmp_path, run, result)


def test_failed_pre_stream_marker_aborts_without_starting_the_stream(monkeypatch, tmp_path):
    run = _msms_run(300, 60)
    captures = {}
    fake = _build_fake_psychopy(captures, flip_times=[1 / 60, 2 / 60, 3 / 60])
    monkeypatch.setattr("fpvs_studio.engines.psychopy_stimuli.synchronize_gpu", lambda: None)

    def fail_submit(_payload):
        raise OSError("marker write failed")

    backend = _external_backend("serial", fail_submit)
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake)
    backend.connect()
    try:
        with pytest.raises(TriggerEmissionError, match="marker write failed"):
            engine.run_condition(
                run, tmp_path, runtime_options={"timing_warmup_frames": 2},
                trigger_backend=backend,
            )
    finally:
        backend.close()
        engine.close_session()
    assert captures["window"].closed
    assert captures["window"]._flip_index == 3
    assert [(r.frame_index, r.label, r.status) for r in backend.records] == [
        (-1, "condition_start", "error"),
    ]


@pytest.mark.parametrize("missing_marker_timestamp", [False, True])
def test_pre_stream_marker_boundary_preserves_clock_domains_and_timing_qc(
    monkeypatch, tmp_path, missing_marker_timestamp,
):
    run = _msms_run(300, 60)
    captures = {}
    times = [(index + 1) / 60 for index in range(run.display.total_frames + 4)]
    if not missing_marker_timestamp:
        times[3:] = [time + 1 / 30 for time in times[3:]]
    fake = _build_fake_psychopy(
        captures, flip_times=times,
        flip_return_none_indices={2} if missing_marker_timestamp else None,
    )
    monkeypatch.setattr("fpvs_studio.engines.psychopy_stimuli.synchronize_gpu", lambda: None)
    backend = _external_backend("serial", lambda payload: len(payload))
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake)
    backend.connect()
    try:
        result = engine.run_condition(
            run, tmp_path, runtime_options={"timing_warmup_frames": 2},
            trigger_backend=backend,
        )
    finally:
        backend.close()
        engine.close_session()
    assert result.completed_frames == 540
    assert len(backend.records) == 91
    assert backend.records[0].time_s == pytest.approx(1 / 60)
    assert [event.time_s for event in result.attentional_blink_onsets] == pytest.approx([
        index / 10 for index in range(90)
    ])
    assert result.runtime_metadata.timing_qc_first_bad_phase == (
        None if missing_marker_timestamp else "stream_onset"
    )
