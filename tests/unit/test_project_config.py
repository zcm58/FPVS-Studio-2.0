"""Project `.fpvsconfig` import/export tests."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.enums import (
    ImageGeometryMode,
    PresentationUnit,
    StimulusModality,
    StimulusTransform,
    StimulusVariant,
    TextHeightMode,
)
from fpvs_studio.core.execution import (
    AcquisitionEvidence,
    AcquisitionRunEvidence,
    RecordingSnapshot,
)
from fpvs_studio.core.models import (
    ImageGeometrySettings,
    ImageResolution,
    ProjectRecordingSettings,
    StimulusPresentationOverride,
    TextHeightScheduleSettings,
)
from fpvs_studio.core.project_config import (
    ProjectConfigError,
    completed_toolbox_config,
    create_project_from_config,
    export_project_config,
    find_latest_completed_toolbox_config,
    project_config_filename,
    read_project_config,
    write_project_config,
)
from fpvs_studio.core.recording_hardware import (
    acquisition_profile_for_recording,
    recording_hardware_definitions,
)
from fpvs_studio.core.serialization import load_project_file, save_project_file, write_json_file
from fpvs_studio.preprocessing.models import (
    DerivedImageRecord,
    SourceImageRecord,
    StimulusAssetRecord,
    StimulusManifest,
    StimulusSetManifest,
)


def test_setup_config_exports_project_conditions_and_toolbox_event_map(sample_project) -> None:
    sample_project.conditions[0].trigger_code = 7
    sample_project.settings.triggers.oddball_trigger_code = 88
    sample_project.settings.triggers.allow_nonstandard_oddball_trigger_code = True
    sample_project.settings.session.show_condition_title_on_screen = False
    sample_project.settings.display.stimulus_width_degrees = 10.0
    sample_project.settings.protocol.oddball_every_n = 6

    config = export_project_config(sample_project, project_root=None)

    assert config.project.name == "Sample Project"
    assert config.conditions[0].name == "Faces"
    assert config.conditions[0].trigger_code == 7
    assert config.toolbox.event_map == {"Faces": 7}
    assert config.toolbox.oddball_trigger_code == 88
    assert config.triggers.oddball_trigger_code == 88
    assert config.triggers.allow_nonstandard_oddball_trigger_code is True
    assert config.session.show_condition_title_on_screen is False
    assert config.display.stimulus_width_degrees == 10.0
    assert config.protocol.base_hz == 6.0
    assert config.protocol.oddball_every_n == 6
    assert config.display.stimulus_width_cm > 0
    assert config.display.stimulus_width_px > 0
    assert config.completed_session is None


@pytest.mark.parametrize("backend,profile_id,montage", [
    ("serial", "biosemi_active_two_64", "biosemi64"),
    ("unicorn_udp", "unicorn_hybrid_black", "unicorn8"),
])
def test_setup_handoff_declares_selected_hardware_without_changing_schema(
    sample_project, tmp_path, backend, profile_id, montage,
):
    sample_project.settings.recording = ProjectRecordingSettings(recording_backend=backend)
    config = export_project_config(sample_project, project_root=None)
    assert config.schema_version == "1.2.0"
    assert config.toolbox.handoff_schema_version == "1.0"
    profile = config.toolbox.acquisition_profile
    assert profile.id == profile_id and profile.montage_id == montage
    assert profile.version == profile.montage_version == profile.event_decoder_version == "1.0"
    if backend == "unicorn_udp":
        assert list(profile.source_to_canonical.values()) == [
            "Fz", "C3", "Cz", "C4", "Pz", "PO7", "Oz", "PO8",
        ]
        assert profile.label_mapping_evidence.status == "declared"
    path = tmp_path / "selected.fpvsconfig"
    write_project_config(path, config)
    written_profile = json.loads(path.read_text(encoding="utf-8"))["toolbox"]["acquisition_profile"]
    assert ("source_to_canonical" in written_profile) == (backend == "unicorn_udp")
    assert read_project_config(path).toolbox == config.toolbox
    legacy = config.model_dump(mode="json")
    legacy["toolbox"] = {key: legacy["toolbox"][key] for key in (
        "project_title", "event_map", "oddball_trigger_code",
    )}
    path.write_text(json.dumps(legacy), encoding="utf-8")
    assert read_project_config(path).toolbox.acquisition_profile is None


def test_hardware_registry_does_not_allow_mapping_mutation_or_unknown_choices():
    selected = acquisition_profile_for_recording("unicorn_udp")
    selected.source_to_canonical["EEG 1"] = "Incorrect"
    assert acquisition_profile_for_recording("unicorn_udp").source_to_canonical["EEG 1"] == "Fz"
    with pytest.raises(ValueError, match="Unsupported recording hardware"):
        acquisition_profile_for_recording("unknown")


@pytest.mark.parametrize("backend,label", [
    ("biosemi_active_three", "BioSemi ActiveThree"),
    ("brainproducts_triggerbox", "Brain Products / BrainVision (TriggerBox/Plus)"),
    ("brainproducts_parallel", "Brain Products / BrainVision (Parallel port)"),
])
def test_new_hardware_declares_selection_without_inventing_toolbox_profile(backend, label):
    definition = next(
        item for item in recording_hardware_definitions() if item.recording_backend == backend
    )
    assert definition.label == label
    assert definition.acquisition_profile is None
    assert acquisition_profile_for_recording(backend) is None


@pytest.mark.parametrize("backend", [
    "biosemi_active_three", "brainproducts_triggerbox", "brainproducts_parallel",
])
def test_unprofiled_completed_handoff_requires_exact_selected_hardware(
    sample_project, sample_project_root, tmp_path, backend,
):
    sample_project.settings.recording = ProjectRecordingSettings(recording_backend=backend)
    config = export_project_config(sample_project, sample_project_root)
    plan = compile_session_plan(
        sample_project, project_root=sample_project_root, refresh_hz=60.0, random_seed=12,
    )
    snapshot = RecordingSnapshot(
        selected_backend=backend,
        effective_backend="serial" if backend == "biosemi_active_three" else backend,
        selection_source="project_settings", receiver_validation="not_applicable",
    )
    evidence = AcquisitionEvidence(
        studio_version="test", execution_id="synthetic-execution",
        project_id=plan.project_id, participant_number="007", session_id=plan.session_id,
        recording=snapshot, state="completed", created_at_utc=datetime.now(timezone.utc),
        updated_at_utc=datetime.now(timezone.utc),
        runs=[
            AcquisitionRunEvidence(
                run_id=entry.run_id, condition_id=entry.condition_id,
                condition_name=entry.condition_name, planned_event_count=0, state="completed",
            )
            for entry in plan.ordered_entries()
        ],
    )
    completed = completed_toolbox_config(config, sample_project_root, plan, evidence)
    path = tmp_path / "completed.fpvsconfig"
    write_project_config(path, completed)
    loaded = read_project_config(path)
    assert loaded.toolbox.acquisition_profile is None
    assert loaded.completed_session.acquisition_evidence.recording.selected_backend == backend

    evidence.recording.selected_backend = (
        "brainproducts_triggerbox" if backend == "biosemi_active_three" else "biosemi_active_three"
    )
    with pytest.raises(ProjectConfigError, match="hardware does not match"):
        completed_toolbox_config(config, sample_project_root, plan, evidence)


@pytest.fixture
def captured_completed_config(sample_project, sample_project_root):
    save_project_file(sample_project, sample_project_root / "project.json")
    recording_project = sample_project.model_copy(deep=True)
    recording_project.settings.recording = ProjectRecordingSettings(
        recording_backend="unicorn_udp", unicorn_udp_port=4567,
    )
    config = export_project_config(recording_project, sample_project_root)
    plan = compile_session_plan(
        sample_project, project_root=sample_project_root, refresh_hz=60.0, random_seed=12,
    )
    profile = acquisition_profile_for_recording("unicorn_udp")
    snapshot = RecordingSnapshot(
        selected_backend="unicorn_udp", effective_backend="unicorn_udp",
        acquisition_profile=profile, selection_source="local_settings", udp_port=4567,
        receiver_validation="pending",
    )
    now = datetime.now(timezone.utc)
    evidence = AcquisitionEvidence(
        studio_version="test", execution_id="captured-execution",
        project_id=plan.project_id, participant_number="007", session_id=plan.session_id,
        recording=snapshot, acquisition_profile=profile, state="completed",
        created_at_utc=now, updated_at_utc=now,
        runs=[
            AcquisitionRunEvidence(
                run_id=entry.run_id, condition_id=entry.condition_id,
                condition_name=entry.condition_name, planned_event_count=0, state="completed",
            )
            for entry in plan.ordered_entries()
        ],
    )
    return completed_toolbox_config(config, sample_project_root, plan, evidence)


def test_latest_completed_toolbox_config_keeps_captured_hardware_and_source_files(
    captured_completed_config, sample_project, sample_project_root,
):
    path = sample_project_root / "logs/acquisition/captured-execution-completed.fpvsconfig"
    write_project_config(path, captured_completed_config)
    before = path.read_bytes()
    project_before = (sample_project_root / "project.json").read_bytes()

    config = find_latest_completed_toolbox_config(sample_project_root)

    assert config == captured_completed_config
    assert config.recording.recording_backend == "unicorn_udp"
    assert config.recording.unicorn_udp_port == 4567
    assert config.completed_session.acquisition_evidence.recording.selection_source == (
        "local_settings"
    )
    assert sample_project.settings.recording is None
    assert path.read_bytes() == before
    assert (sample_project_root / "project.json").read_bytes() == project_before
    assert export_project_config(sample_project, sample_project_root).recording is None
    assert not (sample_project_root / "runs").exists()


def test_latest_completed_toolbox_config_reads_only_newest_artifact(
    captured_completed_config, sample_project_root,
):
    root = sample_project_root / "logs/acquisition"
    path = root / "a-newest-completed.fpvsconfig"
    write_project_config(path, captured_completed_config)
    older = root / "z-older-completed.fpvsconfig"
    older.write_text("invalid older config", encoding="utf-8")
    (root / "not-a-completed-snapshot.fpvsconfig").write_text("ignore", encoding="utf-8")
    os.utime(older, ns=(1_000_000, 1_000_000))
    os.utime(path, ns=(2_000_000, 2_000_000))

    assert find_latest_completed_toolbox_config(sample_project_root) == captured_completed_config


def test_latest_completed_toolbox_config_breaks_equal_mtime_ties_by_name(
    captured_completed_config, sample_project_root,
):
    root = sample_project_root / "logs/acquisition"
    older = root / "a-completed.fpvsconfig"
    write_project_config(older, captured_completed_config)
    newer = captured_completed_config.model_copy(deep=True)
    newer.project.name = "Selected captured snapshot"
    path = root / "z-completed.fpvsconfig"
    write_project_config(path, newer)
    for candidate in (older, path):
        os.utime(candidate, ns=(2_000_000, 2_000_000))

    assert find_latest_completed_toolbox_config(sample_project_root) == newer


@pytest.mark.parametrize("failure,expected", [
    ("corrupt", "not valid JSON"),
    ("project", "different project"),
    ("setup", "missing captured session evidence"),
    ("session", "session association"),
    ("state", "not successfully completed"),
    ("hardware", "recording identity"),
])
def test_latest_completed_toolbox_config_rejects_invalid_newest_without_fallback(
    captured_completed_config, sample_project_root, failure, expected,
):
    root = sample_project_root / "logs/acquisition"
    older = root / "older-completed.fpvsconfig"
    write_project_config(older, captured_completed_config)
    payload = captured_completed_config.model_dump(mode="json")
    if failure == "project":
        payload["project"]["project_id"] = "different-project"
    elif failure == "setup":
        payload["completed_session"] = None
    elif failure == "session":
        payload["completed_session"]["session_id"] = "different-session"
    elif failure == "state":
        payload["completed_session"]["acquisition_evidence"]["state"] = "aborted"
    elif failure == "hardware":
        payload["toolbox"]["acquisition_profile"] = None
    path = root / "newest-completed.fpvsconfig"
    path.write_text(
        "invalid JSON" if failure == "corrupt" else json.dumps(payload), encoding="utf-8",
    )
    os.utime(older, ns=(1_000_000, 1_000_000))
    os.utime(path, ns=(2_000_000, 2_000_000))

    with pytest.raises(ProjectConfigError, match=expected):
        find_latest_completed_toolbox_config(sample_project_root)


def test_latest_completed_toolbox_config_reports_unreadable_newest(
    captured_completed_config, sample_project_root, monkeypatch,
):
    from pathlib import Path

    path = sample_project_root / "logs/acquisition/captured-completed.fpvsconfig"
    write_project_config(path, captured_completed_config)
    read_text = Path.read_text

    def locked_snapshot(candidate, *args, **kwargs):
        if candidate.name == path.name:
            raise PermissionError("captured snapshot locked")
        return read_text(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", locked_snapshot)
    with pytest.raises(ProjectConfigError, match="Unable to read project config"):
        find_latest_completed_toolbox_config(sample_project_root)


def test_latest_completed_toolbox_config_without_acquisition_artifacts_allows_legacy_export(
    tmp_path,
):
    assert find_latest_completed_toolbox_config(tmp_path) is None


def test_latest_completed_toolbox_config_with_evidence_requires_completed_artifact(tmp_path):
    path = tmp_path / "logs/acquisition/aborted.acquisition-v1.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ProjectConfigError, match="No completed recording handoff"):
        find_latest_completed_toolbox_config(tmp_path)


def test_config_export_rejects_nonstandard_oddball_without_explicit_override(
    sample_project,
) -> None:
    sample_project.settings.triggers.oddball_trigger_code = 88

    with pytest.raises(ProjectConfigError, match="locked to 55"):
        export_project_config(sample_project, project_root=None)


def test_project_config_filename_uses_compact_project_title() -> None:
    assert project_config_filename("Semantic Categories") == "semanticcategories.fpvsconfig"
    assert (
        project_config_filename("Semantic Categories", completed=True)
        == "semanticcategories-completed.fpvsconfig"
    )


def test_completed_config_exports_session_order_run_seeds_and_manifest_provenance(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.session.block_count = 2
    sample_project.conditions.append(sample_project.conditions[0].model_copy(update={
        "condition_id": "faces-control", "name": "Faces control", "order_index": 1,
        "trigger_code": 2,
    }))
    sample_project.settings.triggers.oddball_trigger_code = 55
    manifest = StimulusManifest(
        project_id=sample_project.meta.project_id,
        sets=[
            StimulusSetManifest(
                set_id="base-set",
                source_dir="stimuli/original-images/base-set",
                available_variants=[StimulusVariant.ORIGINAL, StimulusVariant.PHASE_SCRAMBLED],
                assets=[
                    StimulusAssetRecord(
                        source=SourceImageRecord(
                            relative_path="stimuli/original-images/base-set/base-01.png",
                            sha256="a" * 64,
                            source_format="png",
                            resolution=ImageResolution(width_px=256, height_px=256),
                        ),
                        derivatives=[
                            DerivedImageRecord(
                                variant=StimulusVariant.PHASE_SCRAMBLED,
                                relative_path=(
                                    "stimuli/generated-variants/base-set/"
                                    "scrambled-variants/base-01.png"
                                ),
                                resolution=ImageResolution(width_px=256, height_px=256),
                                seed=12345,
                                deterministic_policy="fft-amplitude-preserved-noise-phase-v1",
                            )
                        ],
                    )
                ],
            )
        ],
    )
    session_plan = compile_session_plan(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=77,
    )
    completed_dir = sample_project_root / "runs" / session_plan.session_id
    write_json_file(completed_dir / "session_plan.json", session_plan)

    config = export_project_config(
        sample_project,
        sample_project_root,
        manifest=manifest,
        completed_session_dir=completed_dir,
    )

    assert config.completed_session is not None
    assert config.completed_session.session_seed == 77
    assert config.completed_session.block_orders == [
        block.condition_order for block in session_plan.blocks
    ]
    assert config.completed_session.source_run_dir == f"runs/{session_plan.session_id}"
    assert [run.random_seed for run in config.completed_session.ordered_runs] == [
        entry.run_spec.random_seed for entry in session_plan.ordered_entries()
    ]
    assert config.completed_session.ordered_runs[0].trigger_events[0].label == "condition_start"
    assert config.stimulus_provenance is not None
    derivative = config.stimulus_provenance.sets[0].assets[0].derivatives[0]
    assert derivative.seed == 12345
    assert derivative.deterministic_policy == "fft-amplitude-preserved-noise-phase-v1"


def test_config_import_creates_new_project_shell_without_copying_stimuli(
    tmp_path,
    sample_project,
) -> None:
    sample_project.conditions[0].trigger_code = 9
    sample_project.settings.display.viewing_distance_cm = 90.0
    sample_project.settings.protocol.base_hz = 7.5
    sample_project.settings.protocol.oddball_every_n = 6
    sample_project.settings.session.session_seed = 123
    config = export_project_config(sample_project, tmp_path / "source-project")

    scaffold = create_project_from_config(tmp_path, config)
    loaded = load_project_file(scaffold.project_root / "project.json")

    assert config.schema_version == "1.2.0"
    assert loaded.meta.name == sample_project.meta.name
    assert loaded.settings.display.viewing_distance_cm == 90.0
    assert loaded.settings.protocol.base_hz == 7.5
    assert loaded.settings.protocol.oddball_every_n == 6
    assert loaded.settings.session.session_seed == 123
    assert loaded.settings.session.show_condition_title_on_screen is False
    assert loaded.settings.triggers.oddball_trigger_code == 55
    assert loaded.settings.fixation_task.enabled is True
    assert loaded.settings.fixation_task.accuracy_task_enabled is True
    assert loaded.settings.fixation_task.participant_tutorial_enabled is True
    assert loaded.settings.fixation_task.target_count_min == 8
    assert loaded.settings.fixation_task.target_count_max == 13
    assert loaded.settings.fixation_task.target_duration_ms == 300
    assert loaded.conditions[0].name == "Faces"
    assert loaded.conditions[0].trigger_code == 9
    assert loaded.stimulus_sets[0].image_count == 0
    assert loaded.stimulus_sets[0].resolution is None
    assert (scaffold.project_root / "stimuli" / "manifest.json").is_file()


def test_config_round_trips_word_stimulus_sets(tmp_path, sample_project) -> None:
    sample_project.stimulus_sets[0] = sample_project.stimulus_sets[0].model_copy(
        update={
            "modality": StimulusModality.WORD,
            "source_dir": None,
            "resolution": None,
            "image_count": 0,
            "words": ["cat", "dog"],
        }
    )
    sample_project.stimulus_sets[1] = sample_project.stimulus_sets[1].model_copy(
        update={
            "modality": StimulusModality.WORD,
            "source_dir": None,
            "resolution": None,
            "image_count": 0,
            "words": ["tool"],
        }
    )
    config = export_project_config(sample_project, tmp_path / "source-project")

    scaffold = create_project_from_config(tmp_path, config)
    loaded = load_project_file(scaffold.project_root / "project.json")

    assert loaded.stimulus_sets[0].modality == StimulusModality.WORD
    assert loaded.stimulus_sets[0].source_dir is None
    assert loaded.stimulus_sets[0].words == ["cat", "dog"]
    assert not (scaffold.project_root / "stimuli" / "original-images" / "base-set").exists()


def test_config_import_never_overwrites_existing_project_folder(
    tmp_path,
    sample_project,
) -> None:
    config = export_project_config(sample_project, tmp_path / "source-project")
    (tmp_path / sample_project.meta.project_id).mkdir()

    first = create_project_from_config(tmp_path, config)
    second = create_project_from_config(tmp_path, config)

    assert first.project_root.name == f"{sample_project.meta.project_id}-from-config"
    assert second.project_root.name == f"{sample_project.meta.project_id}-from-config-2"


def test_read_project_config_rejects_unsupported_schema_version(tmp_path, sample_project) -> None:
    path = tmp_path / "project.fpvsconfig"
    config = export_project_config(sample_project, tmp_path)
    write_project_config(path, config)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema_version"] = "9.9.9"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProjectConfigError, match="Unsupported project config schema version"):
        read_project_config(path)


def test_completed_config_export_requires_session_plan(tmp_path, sample_project) -> None:
    with pytest.raises(ProjectConfigError, match="missing session_plan.json"):
        export_project_config(
            sample_project,
            tmp_path,
            completed_session_dir=tmp_path / "runs" / "missing-session",
        )


def test_project_config_round_trips_as_config_json(tmp_path, sample_project) -> None:
    path = tmp_path / "sample.fpvsconfig"
    config = export_project_config(sample_project, tmp_path)

    write_project_config(path, config)
    loaded = read_project_config(path)

    assert loaded == config


@pytest.mark.parametrize("allow_repeated_sessions", [False, True])
def test_project_config_preserves_participant_session_policy(
    tmp_path,
    sample_project,
    allow_repeated_sessions: bool,
) -> None:
    sample_project.settings.allow_repeated_participant_sessions = allow_repeated_sessions
    path = tmp_path / "sample.fpvsconfig"
    config = export_project_config(sample_project, tmp_path / "source")

    write_project_config(path, config)
    loaded_config = read_project_config(path)
    scaffold = create_project_from_config(tmp_path / "imported", loaded_config)
    loaded_project = load_project_file(scaffold.project_root / "project.json")

    assert loaded_config.project.allow_repeated_participant_sessions is allow_repeated_sessions
    assert loaded_project.settings.allow_repeated_participant_sessions is allow_repeated_sessions


@pytest.mark.parametrize("schema_version", ["1.0.0", "1.1.0", "1.2.0", "1.3.0"])
def test_project_config_without_participant_session_policy_defaults_to_single_session(
    tmp_path,
    sample_project,
    schema_version: str,
) -> None:
    path = tmp_path / "legacy.fpvsconfig"
    payload = export_project_config(sample_project, tmp_path / "source").model_dump(mode="json")
    payload["schema_version"] = schema_version
    del payload["project"]["allow_repeated_participant_sessions"]
    original_payload = json.dumps(payload)
    path.write_text(original_payload, encoding="utf-8")

    config = read_project_config(path)
    scaffold = create_project_from_config(tmp_path / "imported", config)
    loaded_project = load_project_file(scaffold.project_root / "project.json")

    assert config.project.allow_repeated_participant_sessions is False
    assert loaded_project.settings.allow_repeated_participant_sessions is False
    assert path.read_text(encoding="utf-8") == original_payload


def test_project_config_round_trips_presentation_defaults_and_condition_overrides(
    tmp_path,
    sample_project,
) -> None:
    sample_project.settings.presentation.pre_stream_fixation_seconds = 2.5
    sample_project.settings.presentation.defaults.image_geometry = ImageGeometrySettings(
        mode=ImageGeometryMode.CONTAIN,
        width_degrees=6.25,
        height_degrees=5.0,
    )
    sample_project.settings.presentation.defaults.text_height = TextHeightScheduleSettings(
        mode=TextHeightMode.BALANCED_RANDOMIZED,
        unit=PresentationUnit.WINDOW_HEIGHT_FRACTION,
        values=[0.03, 0.05, 0.07],
    )
    sample_project.conditions[0].presentation.oddball = StimulusPresentationOverride(
        transform=StimulusTransform.MIRROR_HORIZONTAL,
    )

    config = export_project_config(sample_project, tmp_path / "source")
    scaffold = create_project_from_config(tmp_path, config)
    loaded = load_project_file(scaffold.project_root / "project.json")

    assert loaded.settings.presentation == sample_project.settings.presentation
    assert (
        loaded.conditions[0].presentation.oddball
        == sample_project.conditions[0].presentation.oddball
    )


def test_read_project_config_migrates_v1_presentation_defaults(tmp_path, sample_project) -> None:
    path = tmp_path / "legacy.fpvsconfig"
    payload = export_project_config(sample_project, tmp_path).model_dump(mode="json")
    payload["schema_version"] = "1.0.0"
    payload.pop("presentation")
    payload["display"]["stimulus_width_degrees"] = 6.25
    for condition in payload["conditions"]:
        condition.pop("presentation")
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = read_project_config(path)

    assert loaded.schema_version == "1.2.0"
    assert loaded.presentation.pre_stream_fixation_seconds == 0.0
    assert loaded.presentation.defaults.image_geometry.width_degrees == 6.25


def test_project_config_without_protocol_loads_current_defaults(tmp_path, sample_project) -> None:
    path = tmp_path / "legacy.fpvsconfig"
    config = export_project_config(sample_project, tmp_path)
    payload = config.model_dump(mode="json")
    del payload["protocol"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = read_project_config(path)

    assert loaded.protocol.base_hz == 6.0
    assert loaded.protocol.oddball_every_n == 5


@pytest.mark.parametrize("configuration", [
    {"recording_backend": "unicorn_udp", "unicorn_udp_port": 2345},
    {"recording_backend": "biosemi_active_three"},
    {
        "recording_backend": "brainproducts_triggerbox", "brainproducts_serial_port": "COM18",
        "brainproducts_pulse_width_ms": 20,
        "brainproducts_amplifier": "actichamp", "brainproducts_sampling_rate_hz": 100,
    },
    {
        "recording_backend": "brainproducts_parallel", "brainproducts_parallel_address": 0xD010,
        "brainproducts_pulse_width_ms": 20, "brainproducts_sampling_rate_hz": 100,
    },
])
def test_recording_device_and_port_survive_config_interchange(
    tmp_path, sample_project, sample_project_root, configuration,
):
    from fpvs_studio.core.models import ProjectRecordingSettings

    setting = ProjectRecordingSettings(**configuration)
    sample_project.settings.recording = setting
    config = export_project_config(sample_project, sample_project_root)
    path = tmp_path / "device.fpvsconfig"
    write_project_config(path, config)
    loaded = read_project_config(path)
    result = create_project_from_config(tmp_path / "imported", loaded)
    assert result.project.settings.recording == setting
