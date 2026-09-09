"""Frame, source, validation, and portable-project contracts for target pairs."""

from __future__ import annotations

import json
import zipfile
from collections import Counter

import pytest
from PIL import Image
from pydantic import ValidationError

from fpvs_studio.core.compiler import CompileError, compile_run_spec
from fpvs_studio.core.enums import DutyCycleMode, ExperimentCategory, StimulusModality
from fpvs_studio.core.models import AttentionalBlinkSettings, ImageResolution, StimulusSet
from fpvs_studio.core.project_bundle import export_project_bundle, import_project_bundle
from fpvs_studio.core.project_config import create_project_from_config, export_project_config
from fpvs_studio.core.run_spec import event_presentation
from fpvs_studio.core.serialization import load_project_file, model_to_json, save_project_file
from fpvs_studio.core.validation import (
    condition_stimulus_repeat_guidance,
    validate_attentional_blink_condition,
    validate_project,
)
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest


@pytest.fixture
def ab_project(sample_project, sample_project_root):
    sample_project = sample_project.model_copy(
        update={"experiment_category": ExperimentCategory.ATTENTIONAL_BLINK}, deep=True
    )
    sample_project.settings.protocol.base_hz = 4.0
    sample_project.settings.protocol.oddball_every_n = 4
    sample_project.settings.fixation_task.enabled = False
    condition = sample_project.conditions[0]
    condition.oddball_cycle_repeats_per_sequence = 3
    condition.attentional_blink = AttentionalBlinkSettings()
    condition.isi_stimulus_set_id = condition.base_stimulus_set_id
    condition.t2_stimulus_set_id = "t2-set"
    sample_project.stimulus_sets.append(
        StimulusSet(
            set_id="t2-set",
            name="T2 Set",
            source_dir="stimuli/original-images/t2-set",
            resolution=ImageResolution(width_px=300, height_px=150),
            image_count=3,
        )
    )
    t2_dir = sample_project_root / "stimuli" / "original-images" / "t2-set"
    t2_dir.mkdir()
    for index in range(3):
        Image.new("RGB", (300, 150), (0, 30 * index, 0)).save(t2_dir / f"t2-{index}.png")
    return sample_project


def test_target_pair_has_exact_frame_coverage_and_explicit_markers(ab_project, sample_project_root):
    ab_project.conditions[0].oddball_cycle_repeats_per_sequence = 1
    run = compile_run_spec(ab_project, refresh_hz=60, project_root=sample_project_root)

    assert run.display.frames_per_stimulus == 15
    assert run.display.total_frames == 60
    assert run.condition.base_hz == 4
    assert run.condition.oddball_hz == 1
    assert run.condition.total_stimuli == 6
    assert [
        (event.phase, event.slot_index, event.on_start_frame, event.on_frames)
        for event in run.stimulus_sequence
    ] == [
        ("base", 0, 0, 15),
        ("base", 1, 15, 15),
        ("base", 2, 30, 15),
        ("t1", 3, 45, 3),
        ("separator", 3, 48, 3),
        ("t2", 3, 51, 9),
    ]
    assert all(event.off_frames == 0 for event in run.stimulus_sequence)
    assert [event.sequence_index for event in run.stimulus_sequence] == list(range(6))
    assert [
        frame
        for event in run.stimulus_sequence
        for frame in range(event.on_start_frame, event.on_start_frame + event.on_frames)
    ] == list(range(60))
    assert [(event.label, event.code, event.frame_index) for event in run.trigger_events] == [
        ("condition_start", 1, 0),
        ("t1_onset", 55, 45),
        ("t2_onset", 56, 51),
    ]
    for event in run.stimulus_sequence:
        source = (
            "t2-set"
            if event.phase == "t2"
            else "oddball-set"
            if event.phase == "t1"
            else "base-set"
        )
        assert f"/{source}/" in event.image_path


def test_legacy_isi_reference_is_preserved_but_explicit_missing_source_is_rejected(ab_project):
    from fpvs_studio.core.models import ProjectFile

    payload = ab_project.model_dump(mode="json")
    payload["conditions"][0].pop("isi_stimulus_set_id")
    payload["conditions"][0]["attentional_blink"].pop("isi_mode")
    restored = ProjectFile.model_validate(payload)
    assert restored.conditions[0].isi_stimulus_set_id == "base-set"
    restored.conditions[0].isi_stimulus_set_id = None
    with pytest.raises(CompileError, match="ISI image folder"):
        compile_run_spec(restored, refresh_hz=60)
    restored.conditions[0].attentional_blink.isi_mode = "blank"
    assert not validate_attentional_blink_condition(restored, restored.conditions[0])


def test_target_pairs_keep_global_slots_and_independent_balanced_assets(
    ab_project, sample_project_root
):
    first = compile_run_spec(
        ab_project, refresh_hz=60, project_root=sample_project_root, random_seed=17
    )
    again = compile_run_spec(
        ab_project, refresh_hz=60, project_root=sample_project_root, random_seed=17
    )
    changed = compile_run_spec(
        ab_project, refresh_hz=60, project_root=sample_project_root, random_seed=41
    )
    assert first.stimulus_sequence == again.stimulus_sequence
    assert first.stimulus_sequence != changed.stimulus_sequence
    assert [event.slot_index for event in first.stimulus_sequence if event.phase == "t1"] == [
        3,
        7,
        11,
    ]
    for phase in ("t1", "separator", "t2"):
        counts = Counter(
            event.image_path for event in first.stimulus_sequence if event.phase == phase
        )
        assert sorted(counts.values()) == [1, 1, 1]


def test_target_pair_preserves_standard_total_frames_fixation_and_role_bags(
    ab_project, sample_project_root
):
    ab_project.conditions[0].oddball_cycle_repeats_per_sequence = 20
    ab_project.settings.fixation_task.enabled = True
    ab = compile_run_spec(
        ab_project, refresh_hz=60, project_root=sample_project_root, random_seed=27
    )
    ab_project.conditions[0].attentional_blink = None
    ab_project.conditions[0].t2_stimulus_set_id = None
    ab_project.conditions[0].isi_stimulus_set_id = None
    ab_project = ab_project.model_copy(
        update={"experiment_category": ExperimentCategory.FPVS_ODDBALL}
    )
    standard = compile_run_spec(
        ab_project, refresh_hz=60, project_root=sample_project_root, random_seed=27
    )
    assert ab.display == standard.display
    assert ab.fixation_events == standard.fixation_events
    assert [
        (event.role, event.image_path, event.on_start_frame)
        for event in ab.stimulus_sequence
        if event.phase in ("base", "t1")
    ] == [
        (event.role, event.image_path, event.on_start_frame) for event in standard.stimulus_sequence
    ]
    assert "attentional_blink" not in json.loads(model_to_json(standard))
    assert all(
        "phase" not in event and "slot_index" not in event
        for event in json.loads(model_to_json(standard))["stimulus_sequence"]
    )


def test_t2_uses_oddball_geometry_settings_with_own_source_resolution(
    ab_project, sample_project_root
):
    run = compile_run_spec(ab_project, refresh_hz=60, project_root=sample_project_root)
    t1 = next(event for event in run.stimulus_sequence if event.phase == "t1")
    t2 = next(event for event in run.stimulus_sequence if event.phase == "t2")
    first_geometry = event_presentation(run, t1).image_geometry
    second_geometry = event_presentation(run, t2).image_geometry
    assert first_geometry.source_resolution.width_px == 256
    assert second_geometry.source_resolution.width_px == 300
    assert second_geometry.source_resolution.height_px == 150
    assert second_geometry.width_degrees == first_geometry.width_degrees
    assert second_geometry.mode == first_geometry.mode


def test_target_pair_5994_refresh_retains_integer_frame_schedule(ab_project, sample_project_root):
    run = compile_run_spec(ab_project, refresh_hz=59.94, project_root=sample_project_root)
    assert run.display.frames_per_stimulus == 15
    assert run.display.total_frames == 180
    assert run.attentional_blink.t1_frames == 3
    assert run.attentional_blink.isi_frames == 3
    assert run.attentional_blink.t2_frames == 9
    assert run.display.refresh_hz / run.display.frames_per_stimulus == pytest.approx(3.996)


@pytest.mark.parametrize("mode", [DutyCycleMode.BLANK_50, DutyCycleMode.SINUSOIDAL])
def test_target_pairs_reject_noncontinuous_modes(ab_project, mode):
    ab_project.conditions[0].duty_cycle_mode = mode
    with pytest.raises(CompileError, match="Continuous Images"):
        compile_run_spec(ab_project, refresh_hz=60)


@pytest.mark.parametrize("field", ["t1_duration_ms", "isi_ms"])
@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), -float("inf")])
def test_target_pair_settings_reject_invalid_durations(field, value):
    with pytest.raises(ValidationError):
        AttentionalBlinkSettings(**{field: value})


@pytest.mark.parametrize("t1_ms,isi_ms", [(200, 50), (240, 20), (0.1, 50), (50, 0.1)])
def test_target_pairs_reject_overfull_or_subframe_phases(ab_project, t1_ms, isi_ms):
    ab_project.conditions[0].attentional_blink = AttentionalBlinkSettings(
        t1_duration_ms=t1_ms,
        isi_ms=isi_ms,
    )
    with pytest.raises(CompileError):
        compile_run_spec(ab_project, refresh_hz=60)


@pytest.mark.parametrize("source_id", [None, "missing-set"])
def test_target_pairs_require_a_t2_source(ab_project, source_id):
    ab_project.conditions[0].t2_stimulus_set_id = source_id
    with pytest.raises(CompileError, match="T2 image folder"):
        compile_run_spec(ab_project, refresh_hz=60)
    assert any("T2 image folder" in issue.message for issue in validate_project(ab_project).issues)


def test_target_pairs_reject_missing_t2_files(ab_project, sample_project_root):
    t2_dir = sample_project_root / "stimuli" / "original-images" / "t2-set"
    t2_dir.rename(t2_dir.with_name("moved-t2"))
    with pytest.raises(CompileError, match="T2 Set.*no resolvable image paths"):
        compile_run_spec(ab_project, refresh_hz=60, project_root=sample_project_root)


def test_draft_validation_allows_pending_normalization_but_still_checks_markers(ab_project):
    ab_project.stimulus_sets[-1].resolution = None
    condition = ab_project.conditions[0]
    assert (
        validate_attentional_blink_condition(
            ab_project,
            condition,
            require_ready_sources=False,
        )
        == []
    )
    assert any(
        "uniform resolution" in error
        for error in validate_attentional_blink_condition(
            ab_project,
            condition,
        )
    )
    condition.attentional_blink.t2_trigger_code = 55
    assert any(
        "T2 marker" in error
        for error in validate_attentional_blink_condition(
            ab_project,
            condition,
            require_ready_sources=False,
        )
    )


def test_ready_condition_can_be_edited_alongside_empty_ab_draft_pools(ab_project):
    draft = ab_project.conditions[0].model_copy(
        update={
            "condition_id": "draft",
            "name": "Empty draft",
            "base_stimulus_set_id": "draft-base",
            "oddball_stimulus_set_id": "draft-t1",
            "t2_stimulus_set_id": "draft-t2",
            "trigger_code": 2,
            "order_index": 1,
        },
        deep=True,
    )
    ab_project.conditions.append(draft)
    ab_project.stimulus_sets.extend(
        StimulusSet(
            set_id=f"draft-{role}", name=f"Draft {role}",
            source_dir=f"stimuli/original-images/draft-{role}",
        )
        for role in ("base", "t1", "t2")
    )
    ab_project.conditions[0].attentional_blink.isi_ms = 75
    assert all(
        validate_attentional_blink_condition(
            ab_project, condition, refresh_hz=60, require_ready_sources=False
        ) == []
        for condition in ab_project.conditions
    )
    assert len(validate_attentional_blink_condition(ab_project, draft)) == 3
    with pytest.raises(CompileError):
        compile_run_spec(ab_project, condition_id="draft", refresh_hz=60)
    draft.t2_stimulus_set_id = None
    assert any(
        "T2 image folder" in error
        for error in validate_attentional_blink_condition(
            ab_project, draft, require_ready_sources=False
        )
    )
    draft.t2_stimulus_set_id = "draft-t2"
    draft.attentional_blink.isi_ms = 250
    assert validate_attentional_blink_condition(
        ab_project, draft, require_ready_sources=False
    )


def test_target_pairs_require_a_base_slot_before_the_pair(ab_project):
    ab_project.settings.protocol.oddball_every_n = 1
    with pytest.raises(CompileError, match="at least one Base slot"):
        compile_run_spec(ab_project, refresh_hz=60)


def test_target_pairs_reject_word_t2(ab_project):
    ab_project.stimulus_sets[-1] = StimulusSet(
        set_id="t2-set",
        name="T2 Words",
        modality=StimulusModality.WORD,
        words=["cat"],
    )
    with pytest.raises(CompileError, match="images for T2"):
        compile_run_spec(ab_project, refresh_hz=60)


@pytest.mark.parametrize("code", [1, 55])
def test_target_pairs_reject_t2_marker_collisions(ab_project, code):
    ab_project.conditions[0].attentional_blink.t2_trigger_code = code
    with pytest.raises(CompileError, match="T2 marker must differ"):
        compile_run_spec(ab_project, refresh_hz=60)


def test_target_pairs_reject_another_conditions_start_marker(ab_project):
    ab_project.conditions.append(
        ab_project.conditions[0].model_copy(
            update={
                "condition_id": "other",
                "name": "Other",
                "trigger_code": 56,
                "order_index": 1,
            }
        )
    )
    with pytest.raises(CompileError, match="T2 marker must differ"):
        compile_run_spec(ab_project, condition_id="faces", refresh_hz=60)


def test_target_pairs_preserve_explicit_t1_marker_override(ab_project):
    ab_project.settings.triggers.oddball_trigger_code = 88
    ab_project.settings.triggers.allow_nonstandard_oddball_trigger_code = True
    run = compile_run_spec(ab_project, refresh_hz=60)
    assert {event.code for event in run.trigger_events if event.label == "t1_onset"} == {88}
    assert {event.code for event in run.trigger_events if event.label == "t2_onset"} == {56}


def test_target_pair_repeat_guidance_counts_visible_separator_and_t2(ab_project):
    ab_project.conditions[0].oddball_cycle_repeats_per_sequence = 4
    rows = {row.role: row for row in condition_stimulus_repeat_guidance(ab_project)}
    assert rows["base"].presentation_count == 12
    assert (rows["base"].min_repeats_per_image, rows["base"].max_repeats_per_image) == (4, 4)
    assert rows["oddball"].presentation_count == 4
    assert rows["t2"].presentation_count == 4
    assert rows["isi"].presentation_count == 4


@pytest.mark.parametrize("isi_mode", ["image", "blank"])
def test_config_roundtrip_keeps_independent_t2_source_and_optional_timing(
    ab_project, tmp_path, isi_mode
):
    ab_project.conditions[0].attentional_blink.isi_mode = isi_mode
    ab_project.conditions[0].isi_stimulus_set_id = "isi-set"
    ab_project.stimulus_sets.append(ab_project.stimulus_sets[-1].model_copy(
        update={"set_id": "isi-set", "name": "ISI"},
    ))
    config = export_project_config(ab_project, project_root=None)
    scaffold = create_project_from_config(tmp_path / "config-import", config)
    loaded = load_project_file(scaffold.project_root / "project.json")
    assert loaded.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
    assert loaded.conditions[0].attentional_blink == ab_project.conditions[0].attentional_blink
    assert loaded.conditions[0].t2_stimulus_set_id == "t2-set"
    assert loaded.conditions[0].isi_stimulus_set_id == "isi-set"
    assert next(item for item in loaded.stimulus_sets if item.set_id == "t2-set").image_count == 0
    assert loaded.settings.protocol.base_hz == 4
    assert loaded.settings.protocol.oddball_every_n == 4


def test_config_without_set_inventory_still_creates_t2_placeholder(ab_project, tmp_path):
    config = export_project_config(ab_project, project_root=None)
    config.stimulus_sets = []
    scaffold = create_project_from_config(tmp_path / "config-import", config)
    assert {item.set_id for item in scaffold.project.stimulus_sets} == {
        "base-set",
        "oddball-set",
        "t2-set",
    }


def test_standard_project_and_config_do_not_emit_new_optional_fields(sample_project):
    project_data = json.loads(model_to_json(sample_project))
    config_data = json.loads(model_to_json(export_project_config(sample_project, None)))
    for data in (project_data, config_data):
        assert "attentional_blink" not in data["conditions"][0]
        assert "t2_stimulus_set_id" not in data["conditions"][0]


@pytest.mark.parametrize("isi_mode", ["image", "blank"])
def test_bundle_roundtrip_preserves_target_timing_and_t2_assets(
    ab_project, sample_project_root, tmp_path, isi_mode
):
    import shutil

    isi_dir = "stimuli/original-images/isi-set"
    shutil.copytree(
        sample_project_root / "stimuli/original-images/t2-set", sample_project_root / isi_dir,
    )
    ab_project.stimulus_sets.append(ab_project.stimulus_sets[-1].model_copy(
        update={"set_id": "isi-set", "name": "ISI", "source_dir": isi_dir},
    ))
    ab_project.conditions[0].isi_stimulus_set_id = "isi-set"
    ab_project.conditions[0].attentional_blink.isi_mode = isi_mode
    save_project_file(ab_project, sample_project_root / "project.json")
    write_stimulus_manifest(sample_project_root, create_empty_manifest(ab_project.meta.project_id))
    bundle = tmp_path / "ab.fpvsbundle"
    export_project_bundle(sample_project_root, bundle)
    with zipfile.ZipFile(bundle) as archive:
        assert "stimuli/original-images/t2-set/t2-0.png" in archive.namelist()
        assert "stimuli/original-images/isi-set/t2-0.png" in archive.namelist()
    imported = import_project_bundle(bundle, tmp_path / "portable")
    assert imported.project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
    original = compile_run_spec(
        ab_project, refresh_hz=60, project_root=sample_project_root, random_seed=27
    )
    restored = compile_run_spec(
        imported.project, refresh_hz=60, project_root=imported.project_root, random_seed=27
    )
    assert restored.attentional_blink == original.attentional_blink
    assert restored.stimulus_sequence == original.stimulus_sequence
    assert restored.trigger_events == original.trigger_events
