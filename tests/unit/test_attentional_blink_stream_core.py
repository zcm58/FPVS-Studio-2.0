"""Exact independent-target timing and persistence for the native character preset."""

from __future__ import annotations

import json
import re
from itertools import islice

import pytest
from pydantic import ValidationError

from fpvs_studio.core.attentional_blink_stream import (
    describe_attentional_blink_stream,
    iter_attentional_blink_stream_cycles,
    preview_attentional_blink_stream,
    retime_attentional_blink_stream,
    validate_attentional_blink_stream_symbols,
)
from fpvs_studio.core.compiler import CompileError, compile_run_spec, compile_session_plan
from fpvs_studio.core.compiler_schedules import build_trigger_events
from fpvs_studio.core.enums import ExperimentCategory, ProjectSchemaVersion, StimulusModality
from fpvs_studio.core.execution import TriggerRecord
from fpvs_studio.core.experiment_categories import require_valid_experiment_category
from fpvs_studio.core.models import (
    AttentionalBlinkSettings,
    AttentionalBlinkStreamSettings,
    Condition,
    FixationTaskSettings,
    ProjectFile,
    ProtocolSettings,
    StimulusSet,
)
from fpvs_studio.core.project_config import (
    ProjectConfigFile,
    ProjectConfigTriggerEvent,
    create_project_from_config,
    export_project_config,
    read_project_config,
    write_project_config,
)
from fpvs_studio.core.run_spec import (
    AttentionalBlinkStreamRunSpec,
    RunSpec,
    TriggerEvent,
    event_presentation,
)
from fpvs_studio.core.serialization import load_project_file, save_project_file, write_json_file
from fpvs_studio.core.validation import condition_stimulus_repeat_guidance, validate_project


@pytest.fixture
def stream_project(sample_project):
    settings = sample_project.settings.model_copy(deep=True)
    settings.protocol.base_hz = 10
    settings.protocol.oddball_every_n = 20
    settings.fixation_task.enabled = False
    return ProjectFile(
        schema_version=ProjectSchemaVersion.V1_5,
        experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
        meta=sample_project.meta.model_copy(deep=True),
        settings=settings,
        stimulus_sets=[
            StimulusSet(set_id=set_id, name=name, modality=StimulusModality.WORD, words=words)
            for set_id, name, words in (
                ("digits", "Digits", list("23456789")),
                ("t1", "T1", list("ABCDEFGH")),
                ("t2", "T2", list("ABCDEFGH")),
            )
        ],
        conditions=[Condition(
            condition_id="soa-300", name="SOA 300 ms", base_stimulus_set_id="digits",
            oddball_stimulus_set_id="t1", t2_stimulus_set_id="t2", sequence_count=1,
            oddball_cycle_repeats_per_sequence=4,
            attentional_blink=AttentionalBlinkStreamSettings(),
        )],
    )


@pytest.mark.parametrize("soa,lag,t1", [(100, 1, 14), (300, 3, 12), (500, 5, 10)])
def test_requested_timeline_preserves_context_and_equal_exposure(soa, lag, t1):
    description = describe_attentional_blink_stream(soa_ms=soa)
    assert (description.lag, description.intervening_digits) == (lag, lag - 1)
    assert description.t1_slot_index == t1
    assert description.t2_slot_index == 15
    assert description.roles[t1] == "t1"
    assert description.roles[15] == "t2"
    assert description.roles[16:] == ("base",) * 4
    assert description.item_ms == 100
    assert description.cycle_ms == 2000
    assert description.pair_hz == 0.5


@pytest.mark.parametrize("soa", [100, 300, 500])
def test_hiding_cross_preserves_ab_symbols_timing_and_triggers(stream_project, soa):
    stream_project.conditions[0].attentional_blink.soa_ms = soa
    shown = compile_run_spec(stream_project, refresh_hz=60, random_seed=47)
    stream_project.settings.fixation_task = FixationTaskSettings.model_validate({
        **stream_project.settings.fixation_task.model_dump(),
        "show_cross": False, "enabled": False, "accuracy_task_enabled": False,
        "participant_tutorial_enabled": False,
    })
    hidden = compile_run_spec(stream_project, refresh_hz=60, random_seed=47)
    assert not hidden.fixation.show_cross
    assert not hidden.fixation_events
    assert not hidden.fixation.response_keys
    assert not hidden.fixation.participant_tutorial_enabled
    assert hidden.stimulus_sequence == shown.stimulus_sequence
    assert hidden.trigger_events == shown.trigger_events
    assert hidden.display == shown.display
    assert hidden.pre_stream_fixation_frames == shown.pre_stream_fixation_frames
    assert not RunSpec.model_validate_json(hidden.model_dump_json()).fixation.show_cross
    old_payload = shown.model_dump(mode="json")
    del old_payload["fixation"]["show_cross"]
    assert RunSpec.model_validate(old_payload).fixation.show_cross


@pytest.mark.parametrize("refresh,frames", [(60, 6), (120, 12), (240, 24)])
@pytest.mark.parametrize("soa", [100, 300, 500])
def test_exact_refresh_schedule(refresh, frames, soa):
    preview = preview_attentional_blink_stream(refresh_hz=refresh, soa_ms=soa)
    assert preview.frames_per_item == frames
    assert preview.achieved_soa_ms == soa
    assert preview.achieved_base_hz == 10
    assert preview.total_frames == 20 * frames


@pytest.mark.parametrize("refresh", [59.94, 144])
def test_unsupported_exact_refresh_rejected(refresh):
    with pytest.raises(ValueError, match="cannot display exact"):
        preview_attentional_blink_stream(refresh_hz=refresh)


@pytest.mark.parametrize("rate", [0, -1, float("nan"), float("inf"), -float("inf")])
def test_protocol_and_stream_reject_nonpositive_or_nonfinite_rate(rate):
    with pytest.raises(ValidationError):
        ProtocolSettings(base_hz=rate)
    with pytest.raises(ValueError, match="finite and greater than zero"):
        describe_attentional_blink_stream(base_hz=rate)


@pytest.mark.parametrize("rate,soa,refresh,frames,lag", [
    (0.5, 6000, 60, 120, 3),
    (7.5, 400, 60, 8, 3),
    (12, 250, 144, 12, 3),
    (20, 300, 60, 3, 6),
    (60, 50, 60, 1, 3),
])
def test_custom_stream_rate_compiles_exact_frames_and_soa(
    stream_project, rate, soa, refresh, frames, lag,
):
    stream_project.settings.protocol.base_hz = rate
    stream_project.conditions[0].attentional_blink.soa_ms = soa
    assert validate_project(stream_project, refresh_hz=refresh).is_valid
    run = compile_run_spec(stream_project, refresh_hz=refresh, random_seed=47)
    assert run.condition.base_hz == rate
    assert run.condition.oddball_hz == rate / 20
    assert run.display.frames_per_stimulus == frames
    assert run.display.total_frames == 80 * frames
    timing = run.attentional_blink
    assert isinstance(timing, AttentionalBlinkStreamRunSpec)
    assert timing.frames_per_item == frames
    assert timing.requested_soa_ms == timing.achieved_soa_ms == soa
    assert timing.lag == lag
    assert timing.t1_slot_index == 15 - lag
    assert [event.on_start_frame for event in run.stimulus_sequence] == list(
        range(0, 80 * frames, frames)
    )
    assert {event.on_frames for event in run.stimulus_sequence} == {frames}
    assert {event.off_frames for event in run.stimulus_sequence} == {0}
    for cycle in range(4):
        events = [event for event in run.stimulus_sequence if event.cycle_index == cycle]
        t1 = next(event for event in events if event.phase == "t1")
        t2 = next(event for event in events if event.phase == "t2")
        assert (t2.on_start_frame - t1.on_start_frame) * 1000 / refresh == soa
    restored = RunSpec.model_validate_json(run.model_dump_json())
    assert restored == run


@pytest.mark.parametrize("rate,soa,error", [
    (7.5, 300, "SOA must be a whole multiple"),
    (12, 300, "SOA must be a whole multiple"),
    (7, 1000, "cannot display exact"),
    (80, 25, "faster than|cannot display exact"),
])
def test_custom_stream_rate_rejects_incompatible_soa_or_display_without_rounding(
    stream_project, rate, soa, error,
):
    stream_project.settings.protocol.base_hz = rate
    stream_project.conditions[0].attentional_blink.soa_ms = soa
    assert not validate_project(stream_project, refresh_hz=60).is_valid
    with pytest.raises(CompileError, match=error):
        compile_run_spec(stream_project, refresh_hz=60)
    assert stream_project.settings.protocol.base_hz == rate
    assert stream_project.conditions[0].attentional_blink.soa_ms == soa


@pytest.mark.parametrize("soa", [0, 50, 250, 1500, float("nan"), float("inf")])
def test_invalid_grid_or_missing_context_rejected(soa):
    with pytest.raises(ValueError):
        describe_attentional_blink_stream(soa_ms=soa)


@pytest.mark.parametrize("rate", [10, 7.5, 12])
def test_suggested_soa_interval_can_be_entered_as_an_exact_onset_lag(rate):
    with pytest.raises(ValueError, match="whole multiple") as error:
        describe_attentional_blink_stream(base_hz=rate, soa_ms=500 / rate)
    match = re.search(r"whole multiple of ([\d.e+-]+) ms", str(error.value))
    assert match is not None
    suggested_interval = match.group(1)
    if rate == 10:
        assert suggested_interval == "100"
    description = describe_attentional_blink_stream(
        base_hz=rate, soa_ms=float(suggested_interval),
    )
    assert description.lag == 1
    preview = preview_attentional_blink_stream(
        refresh_hz=60, base_hz=rate, soa_ms=float(suggested_interval),
    )
    assert preview.achieved_soa_ms == pytest.approx(float(suggested_interval))


@pytest.mark.parametrize("soa", [100, 300, 500])
def test_compiled_stream_has_fixed_frames_seeded_symbols_and_target_markers(stream_project, soa):
    stream_project.conditions[0].attentional_blink.soa_ms = soa
    run = compile_run_spec(stream_project, refresh_hz=60, random_seed=47)
    again = compile_run_spec(stream_project, refresh_hz=60, random_seed=47)
    different = compile_run_spec(stream_project, refresh_hz=60, random_seed=48)
    assert run.stimulus_sequence == again.stimulus_sequence
    assert run.stimulus_sequence != different.stimulus_sequence
    assert isinstance(run.attentional_blink, AttentionalBlinkStreamRunSpec)
    assert run.schema_version == "1.3.0"
    assert run.display.total_frames == 480
    assert len(run.stimulus_sequence) == 80
    assert {event.on_frames for event in run.stimulus_sequence} == {6}
    assert {event.off_frames for event in run.stimulus_sequence} == {0}
    assert not any(event.is_blank for event in run.stimulus_sequence)
    assert [event.on_start_frame for event in run.stimulus_sequence] == list(range(0, 480, 6))
    for cycle in range(4):
        events = [event for event in run.stimulus_sequence if event.cycle_index == cycle]
        t1 = next(event for event in events if event.phase == "t1")
        t2 = next(event for event in events if event.phase == "t2")
        assert t2.on_start_frame - t1.on_start_frame == soa / 1000 * 60
        assert t1.text != t2.text
        assert event_presentation(run, t1).text.color == "#FF0000"
        assert event_presentation(run, t2).text.color == "#FFFFFF"
        assert t2.slot_index % 20 == 15
    for previous, event in zip(run.stimulus_sequence, run.stimulus_sequence[1:], strict=False):
        if previous.phase == event.phase == "base":
            assert previous.text != event.text
    t1_markers = [event for event in run.trigger_events if event.label == "t1_onset"]
    t2_markers = [event for event in run.trigger_events if event.label == "t2_onset"]
    assert len(t1_markers) == len(t2_markers) == 4
    assert {event.code for event in t1_markers} == {55}
    assert {event.code for event in t2_markers} == {56}


@pytest.mark.parametrize("soa,expected", [
    (100, (
        "85787828946795CA3465", "95494727258367BG7826",
        "75636943948736DC9365", "72658583976247GB7627",
    )),
    (300, (
        "857878289467C96A3465", "954947272583B96G7826",
        "756369439487D46C9365", "726585839762G57B7627",
    )),
    (500, (
        "8578782894C9695A3465", "9549472725B5674G3675",
        "6369439487D4685C5657", "2658583976G2476B7627",
    )),
])
def test_shared_preview_sampling_preserves_existing_compiled_seed(stream_project, soa, expected):
    """Sharing the preview sampler must not change previously seeded experiments."""

    stream_project.conditions[0].attentional_blink.soa_ms = soa
    run = compile_run_spec(stream_project, refresh_hz=60, random_seed=47)
    actual = tuple(
        "".join(event.text for event in run.stimulus_sequence if event.cycle_index == cycle)
        for cycle in range(4)
    )
    assert actual == expected
    cycles = iter_attentional_blink_stream_cycles(
        describe_attentional_blink_stream(soa_ms=soa),
        base_words=list("23456789"), t1_words=list("ABCDEFGH"),
        t2_words=list("ABCDEFGH"), random_seed=47,
    )
    assert tuple("".join(symbols) for symbols in islice(cycles, 4)) == expected


@pytest.mark.parametrize("soa", [100, 300, 500])
@pytest.mark.parametrize("base_words", [list("97532"), list("82")])
def test_sampled_cycles_randomize_custom_pools_and_preserve_boundary_rules(soa, base_words):
    description = describe_attentional_blink_stream(soa_ms=soa)

    def sample(seed):
        return list(islice(iter_attentional_blink_stream_cycles(
            description, base_words=base_words, t1_words=list("CAB"),
            t2_words=list("BCA"), random_seed=seed,
        ), 12))

    cycles = sample(23)
    assert cycles == sample(23)
    assert cycles != sample(24)
    assert len(set(cycles)) > 1
    previous_digit = None
    for symbols in cycles:
        assert len(symbols) == description.cycle_slots
        assert symbols[description.t1_slot_index] != symbols[description.t2_slot_index]
        for phase, symbol in zip(description.roles, symbols, strict=True):
            if phase == "base":
                assert symbol in base_words
                assert symbol != previous_digit
                previous_digit = symbol
            else:
                assert symbol in "ABC"
                previous_digit = None
    if len(base_words) > 2:
        leading_digits = cycles[0][:description.t1_slot_index]
        assert leading_digits != tuple(
            base_words[index % len(base_words)] for index in range(len(leading_digits))
        )


@pytest.mark.parametrize("refresh", [59.94, 144])
def test_compiler_rejects_rounded_stream_timing(stream_project, refresh):
    with pytest.raises(CompileError, match="cannot display exact"):
        compile_run_spec(stream_project, refresh_hz=refresh)


@pytest.mark.parametrize("base,t1,t2", [
    (["2"], ["A"], ["B"]), (["12", "3"], ["A"], ["B"]),
    (["2", "3"], ["a"], ["B"]), (["2", "3"], ["A"], ["A"]),
    (["2", "2", "3"], ["A"], ["B"]), (["2", "3"], ["A"], []),
])
def test_invalid_symbol_pools_rejected(base, t1, t2):
    with pytest.raises(ValueError):
        validate_attentional_blink_stream_symbols(base, t1, t2)


@pytest.mark.parametrize("rate,soa", [(10, 300), (7.5, 400), (20, 300)])
def test_stream_project_and_config_roundtrip_preserve_schema_and_no_isi_source(
    stream_project, tmp_path, rate, soa,
):
    stream_project.settings.protocol.base_hz = rate
    stream_project.conditions[0].attentional_blink.soa_ms = soa
    path = tmp_path / "project.json"
    save_project_file(stream_project, path)
    loaded = load_project_file(path)
    assert loaded == stream_project
    assert loaded.conditions[0].isi_stimulus_set_id is None
    config = export_project_config(loaded, None)
    assert config.schema_version == "1.3.0"
    config_path = tmp_path / "study.fpvsconfig"
    write_project_config(config_path, config)
    restored = read_project_config(config_path)
    imported = create_project_from_config(tmp_path / "imported", restored).project
    assert imported.schema_version == ProjectSchemaVersion.V1_5
    assert imported.settings.protocol.base_hz == rate
    assert imported.conditions[0].attentional_blink == (
        stream_project.conditions[0].attentional_blink
    )
    assert imported.conditions[0].isi_stimulus_set_id is None
    assert compile_run_spec(imported, refresh_hz=60).stimulus_sequence == (
        compile_run_spec(stream_project, refresh_hz=60).stimulus_sequence
    )
    assert validate_project(imported, refresh_hz=60).is_valid


def test_old_schema_cannot_claim_to_support_letter_stream(stream_project):
    project_data = json.loads(stream_project.model_dump_json())
    project_data["schema_version"] = "1.4.0"
    with pytest.raises(ValidationError, match="schema 1.5.0"):
        ProjectFile.model_validate(project_data)
    config_data = export_project_config(stream_project, None).model_dump()
    config_data["schema_version"] = "1.2.0"
    with pytest.raises(ValidationError, match="schema 1.3.0"):
        ProjectConfigFile.model_validate(config_data)
    run_data = compile_run_spec(stream_project, refresh_hz=60).model_dump()
    run_data["schema_version"] = "1.1.0"
    with pytest.raises(ValidationError, match="schema 1.3.0"):
        RunSpec.model_validate(run_data)


def test_mixed_ab_layouts_require_separation(stream_project):
    legacy = stream_project.conditions[0].model_copy(update={
        "condition_id": "legacy", "attentional_blink": AttentionalBlinkSettings(),
    })
    stream_project.conditions.append(legacy)
    with pytest.raises(ValueError, match="separate experiments"):
        require_valid_experiment_category(stream_project)


def test_repeat_guidance_counts_two_target_slots(stream_project):
    rows = {row.role: row for row in condition_stimulus_repeat_guidance(stream_project)}
    assert rows["base"].presentation_count == 4 * 18
    assert rows["oddball"].presentation_count == rows["t2"].presentation_count == 4
    assert "isi" not in rows


@pytest.fixture
def repeated_target_project(stream_project):
    stream_project.settings.protocol.oddball_every_n = 90
    stream_project.stimulus_sets[0].words = list("ABCDEFGH")
    stream_project.stimulus_sets[1].words = list("23456789")
    stream_project.stimulus_sets[2].words = list("23456789")
    condition = stream_project.conditions[0]
    condition.oddball_cycle_repeats_per_sequence = 1
    condition.attentional_blink = AttentionalBlinkStreamSettings(
        soa_ms=300, t2_slot_index=24, target_count=6,
        target_interval_slots=10, omit_first_t2=True,
    )
    return stream_project


@pytest.mark.parametrize("refresh", [60, 120, 240])
@pytest.mark.parametrize("soa", [100, 300, 500])
def test_repeated_targets_have_exact_nine_second_schedule_and_markers(
    repeated_target_project, refresh, soa,
):
    settings = repeated_target_project.conditions[0].attentional_blink
    settings.soa_ms = soa
    settings.t2_slot_index = 21 + soa // 100
    preview = preview_attentional_blink_stream(
        refresh_hz=refresh, cycle_slots=90, soa_ms=soa,
        t2_slot_index=settings.t2_slot_index, target_count=6,
        target_interval_slots=10, omit_first_t2=True,
    )
    run = compile_run_spec(repeated_target_project, refresh_hz=refresh, random_seed=47)
    assert validate_project(repeated_target_project, refresh_hz=refresh).is_valid
    assert run.display.total_frames == preview.total_frames == 9 * refresh
    assert preview.cycle_ms == 9000 and preview.pair_hz == 1
    assert preview.description.pair_hz == 1
    assert preview.description.t1_slot_index == 21
    assert preview.achieved_soa_ms == soa
    assert len(run.stimulus_sequence) == 90
    assert [event.phase for event in run.stimulus_sequence] == list(preview.description.roles)
    assert [event.on_start_frame for event in run.stimulus_sequence] == [
        slot * refresh // 10 for slot in range(90)
    ]
    assert {event.on_frames for event in run.stimulus_sequence} == {refresh // 10}
    assert {event.off_frames for event in run.stimulus_sequence} == {0}
    assert not any(event.is_blank for event in run.stimulus_sequence)
    t1_events = [event for event in run.stimulus_sequence if event.phase == "t1"]
    t2_events = [event for event in run.stimulus_sequence if event.phase == "t2"]
    assert [event.on_start_frame / refresh for event in t1_events] == [
        2.1, 3.1, 4.1, 5.1, 6.1, 7.1,
    ]
    assert [event.cycle_index for event in t1_events] == list(range(6))
    assert [event.cycle_index for event in t2_events] == list(range(1, 6))
    assert len({event.text for event in t1_events}) == len({event.text for event in t2_events}) == 1
    assert t1_events[0].text != t2_events[0].text
    assert t1_events[0].text.isdigit() and t2_events[0].text.isdigit()
    for t1, t2 in zip(t1_events[1:], t2_events, strict=True):
        assert t2.on_start_frame - t1.on_start_frame == soa * refresh // 1000
    omitted = run.stimulus_sequence[settings.t2_slot_index]
    assert omitted.phase == "base" and omitted.text.isalpha()
    assert not any(marker.frame_index == omitted.on_start_frame for marker in run.trigger_events)
    assert [(marker.frame_index, marker.code, marker.label) for marker in run.trigger_events] == [
        (0, repeated_target_project.conditions[0].trigger_code, "condition_start"),
        *[(event.on_start_frame, 55 if event.phase == "t1" else 56, f"{event.phase}_onset")
          for event in run.stimulus_sequence if event.phase in ("t1", "t2")],
    ]


def test_repeated_target_sampling_keeps_one_pair_per_burst_and_seeded_distractors():
    description = describe_attentional_blink_stream(
        cycle_slots=90, soa_ms=300, t2_slot_index=24,
        target_count=6, target_interval_slots=10, omit_first_t2=True,
    )

    def sample(seed):
        return list(islice(iter_attentional_blink_stream_cycles(
            description, base_words=list("ABCDEFGH"), t1_words=list("23456789"),
            t2_words=list("23456789"), random_seed=seed,
        ), 12))

    bursts = sample(47)
    assert bursts == sample(47) and bursts != sample(48)
    pairs = set()
    previous = None
    for symbols in bursts:
        targets = {
            phase: {symbol for role, symbol in zip(description.roles, symbols, strict=True)
                    if role == phase}
            for phase in ("t1", "t2")
        }
        assert len(targets["t1"]) == len(targets["t2"]) == 1
        assert targets["t1"] != targets["t2"]
        pairs.add((next(iter(targets["t1"])), next(iter(targets["t2"]))))
        assert symbols[24].isalpha()
        for role, symbol in zip(description.roles, symbols, strict=True):
            if role == "base":
                assert symbol.isalpha() and symbol != previous
                previous = symbol
            else:
                previous = None
    assert len(pairs) > 1


@pytest.mark.parametrize("rate", [10, 20, 30])
def test_retiming_repeated_targets_preserves_duration_first_onset_and_cadence(rate):
    description = retime_attentional_blink_stream(
        base_hz=10, cycle_slots=90, soa_ms=300, t2_slot_index=24,
        target_count=6, target_interval_slots=10, omit_first_t2=True,
        new_base_hz=rate, new_soa_ms=400,
    )
    assert description.cycle_ms == 9000
    assert description.t1_slot_index / rate == 2.1
    assert description.t2_slot_index / rate == 2.5
    assert description.target_interval_slots / rate == 1
    assert description.roles.count("t1") == 6 and description.roles.count("t2") == 5
    assert description.roles[description.t2_slot_index] == "base"


@pytest.mark.parametrize("rate,soa", [(7.5, 400), (12, 250), (15, 200), (20, 125)])
def test_retiming_repeated_targets_rejects_inexact_grid(rate, soa):
    with pytest.raises(ValueError, match="exactly on character boundaries|whole multiple"):
        retime_attentional_blink_stream(
            base_hz=10, cycle_slots=90, soa_ms=300, t2_slot_index=24,
            target_count=6, target_interval_slots=10, omit_first_t2=True,
            new_base_hz=rate, new_soa_ms=soa,
        )


@pytest.mark.parametrize("changes,error", [
    ({"target_interval_slots": None}, "longer than"),
    ({"target_interval_slots": 3}, "longer than"),
    ({"target_interval_slots": 14}, "after the final T2"),
    ({"target_count": 8}, "after the final T2"),
    ({"target_count": 1, "target_interval_slots": None}, "require repeated targets"),
])
def test_invalid_repeated_targets_rejected_before_compilation_or_playback(
    repeated_target_project, changes, error,
):
    run_payload = compile_run_spec(repeated_target_project, refresh_hz=60).model_dump()
    run_payload["attentional_blink"].update(changes)
    with pytest.raises(ValidationError, match=error):
        RunSpec.model_validate(run_payload)
    condition = repeated_target_project.conditions[0]
    condition.attentional_blink = condition.attentional_blink.model_copy(update=changes)
    assert not validate_project(repeated_target_project, refresh_hz=60).is_valid
    with pytest.raises(CompileError, match=error):
        compile_run_spec(repeated_target_project, refresh_hz=60)


@pytest.mark.parametrize("distractor_code", [None, 57])
def test_repeated_targets_project_config_and_run_spec_roundtrip(
    repeated_target_project, tmp_path, distractor_code,
):
    settings = repeated_target_project.conditions[0].attentional_blink
    settings.distractor_trigger_code = distractor_code
    project_path = tmp_path / "project.json"
    save_project_file(repeated_target_project, project_path)
    restored = load_project_file(project_path)
    assert restored == repeated_target_project
    config_path = tmp_path / "repeated-targets.fpvsconfig"
    write_project_config(config_path, export_project_config(restored, project_root=None))
    imported = create_project_from_config(tmp_path / "imported", read_project_config(config_path))
    assert imported.project.conditions == restored.conditions
    assert imported.project.settings.protocol == restored.settings.protocol
    run = compile_run_spec(imported.project, refresh_hz=60, random_seed=47)
    assert RunSpec.model_validate_json(run.model_dump_json()) == run
    assert run.stimulus_sequence == compile_run_spec(
        repeated_target_project, refresh_hz=60, random_seed=47,
    ).stimulus_sequence
    assert run.attentional_blink.target_count == 6
    assert run.attentional_blink.target_interval_slots == 10
    assert run.attentional_blink.omit_first_t2
    assert run.attentional_blink.distractor_trigger_code == distractor_code
    rows = {row.role: row for row in condition_stimulus_repeat_guidance(imported.project)}
    assert rows["base"].presentation_count == 79
    assert rows["oddball"].presentation_count == 6
    assert rows["t2"].presentation_count == 5


@pytest.mark.parametrize("refresh", [60, 120, 240])
@pytest.mark.parametrize("soa,condition_code", [(100, 1), (300, 2), (500, 3)])
def test_distractor_markers_cover_every_character_without_changing_stream_timing(
    repeated_target_project, refresh, soa, condition_code,
):
    condition = repeated_target_project.conditions[0]
    condition.trigger_code = condition_code
    condition.attentional_blink.soa_ms = soa
    condition.attentional_blink.t2_slot_index = 21 + soa // 100
    without_distractors = compile_run_spec(
        repeated_target_project, refresh_hz=refresh, random_seed=47,
    )
    condition.attentional_blink.distractor_trigger_code = 57
    run = compile_run_spec(repeated_target_project, refresh_hz=refresh, random_seed=47)
    assert run.stimulus_sequence == without_distractors.stimulus_sequence
    assert run.display == without_distractors.display
    assert run.pre_stream_fixation_frames == without_distractors.pre_stream_fixation_frames
    assert run.display.total_frames == 9 * refresh
    assert len(run.trigger_events) == 91
    assert len({marker.frame_index for marker in run.trigger_events}) == 91
    assert run.trigger_events[0] == TriggerEvent(
        frame_index=-1, code=condition_code, label="condition_start",
    )
    expected = {"base": (57, "distractor_onset"), "t1": (55, "t1_onset"),
                "t2": (56, "t2_onset")}
    for event, marker in zip(run.stimulus_sequence, run.trigger_events[1:], strict=True):
        assert marker.frame_index == event.on_start_frame
        assert (marker.code, marker.label) == expected[event.phase]
    assert sum(marker.code == 55 for marker in run.trigger_events) == 6
    assert sum(marker.code == 56 for marker in run.trigger_events) == 5
    assert sum(marker.code == 57 for marker in run.trigger_events) == 79
    assert run.trigger_events[1].frame_index == 0
    assert run.trigger_events[1].code == 57
    omitted_slot = condition.attentional_blink.t2_slot_index
    assert run.trigger_events[omitted_slot + 1].code == 57
    assert RunSpec.model_validate_json(run.model_dump_json()) == run


@pytest.mark.parametrize("code", [0, 256, True, 57.0, "57"])
def test_distractor_code_requires_nonzero_strict_byte_code(stream_project, code):
    with pytest.raises(ValidationError):
        AttentionalBlinkStreamSettings(distractor_trigger_code=code)
    payload = compile_run_spec(stream_project, refresh_hz=60).model_dump()
    payload["attentional_blink"]["distractor_trigger_code"] = code
    with pytest.raises(ValidationError):
        RunSpec.model_validate(payload)


@pytest.mark.parametrize("code", [1, 2, 55, 56, 58])
def test_distractor_code_cannot_alias_any_condition_or_target_marker(stream_project, code):
    condition = stream_project.conditions[0]
    other = condition.model_copy(deep=True)
    other.condition_id = "other"
    other.trigger_code = 2
    other.attentional_blink.t2_trigger_code = 58
    stream_project.conditions.append(other)
    condition.attentional_blink.distractor_trigger_code = code
    report = validate_project(stream_project, refresh_hz=60)
    assert not report.is_valid
    with pytest.raises(CompileError, match="Distractor marker must differ"):
        compile_run_spec(stream_project, condition_id=condition.condition_id, refresh_hz=60)


def test_optional_distractor_markers_preserve_legacy_serialized_shape(stream_project):
    settings = stream_project.conditions[0].attentional_blink
    assert "distractor_trigger_code" not in settings.model_dump()
    assert "distractor_trigger_code" not in settings.model_dump_json()
    run = compile_run_spec(stream_project, refresh_hz=60)
    assert "distractor_trigger_code" not in run.model_dump()["attentional_blink"]
    assert "distractor_trigger_code" not in run.model_dump_json()
    assert run.trigger_events[0].frame_index == 0
    assert {marker.label for marker in run.trigger_events} == {
        "condition_start", "t1_onset", "t2_onset",
    }


@pytest.mark.parametrize("change", [
    "start_frame", "start_code", "remove_start", "remove_distractor", "wrong_distractor",
    "extra_distractor", "remove_t1", "remove_t2", "code_collision", "disabled", "not_ab",
])
def test_run_spec_rejects_invalid_opted_in_distractor_schedule(stream_project, change):
    stream_project.conditions[0].attentional_blink.distractor_trigger_code = 57
    payload = compile_run_spec(stream_project, refresh_hz=60).model_dump()
    markers = payload["trigger_events"]
    if change == "start_frame":
        markers[0]["frame_index"] = 0
    elif change == "start_code":
        markers[0]["code"] = 2
    elif change == "remove_start":
        markers.pop(0)
    elif change == "remove_distractor":
        markers.pop(1)
    elif change == "wrong_distractor":
        markers[1]["code"] = 58
    elif change == "extra_distractor":
        markers.append(markers[1].copy())
    elif change in {"remove_t1", "remove_t2"}:
        markers.remove(next(marker for marker in markers
                            if marker["label"] == f"{change.removeprefix('remove_')}_onset"))
    elif change == "code_collision":
        payload["attentional_blink"]["distractor_trigger_code"] = 55
    elif change == "disabled":
        payload["attentional_blink"].pop("distractor_trigger_code")
    elif change == "not_ab":
        payload["attentional_blink"] = None
    with pytest.raises(ValidationError):
        RunSpec.model_validate(payload)


@pytest.mark.parametrize("label", ["t1_onset", "t2_onset", "distractor_onset", "oddball_onset"])
def test_only_condition_marker_may_use_pre_stream_frame(label):
    with pytest.raises(ValidationError, match="Only condition_start"):
        TriggerEvent(frame_index=-1, code=55, label=label)
    with pytest.raises(ValidationError, match="Only condition_start"):
        TriggerRecord(trigger_index=0, frame_index=-1, time_s=0, code=55,
                      label=label, backend_name="null")
    with pytest.raises(ValidationError, match="Only condition_start"):
        ProjectConfigTriggerEvent(frame_index=-1, code=55, label=label)
    assert TriggerRecord(trigger_index=0, frame_index=-1, time_s=0, code=1,
                         label="condition_start", backend_name="null").frame_index == -1


def test_distractor_trigger_builder_rejects_non_ab_events(stream_project):
    run = compile_run_spec(stream_project, refresh_hz=60)
    sequence = [event for event in run.stimulus_sequence if event.phase == "base"]
    with pytest.raises(CompileError, match="letter stream"):
        build_trigger_events(stimulus_sequence=sequence, condition_trigger_code=1,
                             oddball_trigger_code=55, t2_trigger_code=56,
                             distractor_trigger_code=57)


def test_completed_config_retains_pre_stream_and_all_character_markers(
    repeated_target_project, tmp_path,
):
    repeated_target_project.conditions[0].attentional_blink.distractor_trigger_code = 57
    project_root = tmp_path / "source"
    session = compile_session_plan(repeated_target_project, refresh_hz=60, random_seed=47)
    completed_dir = project_root / "runs" / session.session_id
    write_json_file(completed_dir / "session_plan.json", session)
    config = export_project_config(repeated_target_project, project_root,
                                   completed_session_dir=completed_dir)
    config_path = tmp_path / "completed.fpvsconfig"
    write_project_config(config_path, config)
    loaded = read_project_config(config_path)
    assert loaded == config
    for completed, entry in zip(loaded.completed_session.ordered_runs,
                                session.ordered_entries(), strict=True):
        assert len(completed.trigger_events) == 91
        assert completed.trigger_events[0].frame_index == -1
        assert [marker.model_dump() for marker in completed.trigger_events] == [
            marker.model_dump() for marker in entry.run_spec.trigger_events
        ]
    imported = create_project_from_config(tmp_path / "imported", loaded)
    run = compile_run_spec(imported.project, refresh_hz=60)
    assert run.attentional_blink.distractor_trigger_code == 57
    assert len(run.trigger_events) == 91
