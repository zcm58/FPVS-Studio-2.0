"""Project `.fpvsconfig` import/export tests."""

from __future__ import annotations

import json

import pytest

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.enums import StimulusModality, StimulusVariant
from fpvs_studio.core.models import ImageResolution
from fpvs_studio.core.project_config import (
    ProjectConfigError,
    create_project_from_config,
    export_project_config,
    project_config_filename,
    read_project_config,
    write_project_config,
)
from fpvs_studio.core.serialization import load_project_file, write_json_file
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
    assert config.display.stimulus_width_cm > 0
    assert config.display.stimulus_width_px > 0
    assert config.completed_session is None


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
    sample_project.settings.session.session_seed = 123
    config = export_project_config(sample_project, tmp_path / "source-project")

    scaffold = create_project_from_config(tmp_path, config)
    loaded = load_project_file(scaffold.project_root / "project.json")

    assert loaded.meta.name == sample_project.meta.name
    assert loaded.settings.display.viewing_distance_cm == 90.0
    assert loaded.settings.session.session_seed == 123
    assert loaded.settings.session.show_condition_title_on_screen is False
    assert loaded.settings.triggers.oddball_trigger_code == 55
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
