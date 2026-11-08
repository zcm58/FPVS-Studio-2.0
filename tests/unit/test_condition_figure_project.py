"""Read-only condition selection and output protection for the figure tool."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from fpvs_studio.core.enums import (
    DutyCycleMode,
    ExperimentCategory,
    StimulusModality,
    StimulusVariant,
)
from fpvs_studio.preprocessing.importer import materialize_project_assets
from fpvs_studio.preprocessing.manifest import write_stimulus_manifest
from fpvs_studio.tools.condition_figure_project import (
    ConditionFigureSources,
    condition_figure_candidates,
    load_condition_figure_sources,
    validate_condition_figure_destination,
)


@pytest.mark.parametrize("duty_cycle_mode", list(DutyCycleMode))
def test_automatic_uses_unique_configured_examples_and_condition_timing(
    sample_project, sample_project_root, duty_cycle_mode,
):
    condition = sample_project.conditions[0]
    condition.base_hz = 7.5
    condition.duty_cycle_mode = duty_cycle_mode
    sample_project.settings.protocol.oddball_every_n = 6
    sample_project.settings.display.background_color = (128, 128, 128)
    base_set, oddball_set = sample_project.stimulus_sets
    base_dir = sample_project_root / base_set.source_dir
    for index in (5, 4):
        with Image.new("RGB", (12, 10), color=(0, index, 0)) as image:
            image.save(base_dir / f"{base_set.set_id}-{index:02d}.png")
    oddball_dir = sample_project_root / oddball_set.source_dir
    for index in range(1, 4):
        with Image.new("RGB", (12, 10), color=(0, 0, index)) as image:
            image.save(oddball_dir / f"{oddball_set.set_id}-{index:02d}.png")
    before = sample_project.model_dump()

    sources = load_condition_figure_sources(
        sample_project, sample_project_root, condition.condition_id,
    )
    spec = sources.automatic_spec()

    assert spec.condition_name == condition.name
    assert spec.base_hz == 7.5
    assert spec.oddball_every_n == 6
    assert spec.duty_cycle_mode == duty_cycle_mode
    assert spec.background_color == (128, 128, 128)
    assert spec.base_stimuli == tuple(
        base_dir / f"{base_set.set_id}-{index:02d}.png" for index in range(1, 5)
    )
    assert isinstance(spec.oddball_stimulus, Path)
    assert spec.oddball_stimulus.name == "oddball-set-01.png"
    assert spec.sequence_stimuli == (
        *spec.base_stimuli, base_dir / "base-set-05.png", spec.oddball_stimulus,
        None, None, None, None, None, oddball_dir / "oddball-set-03.png", None, None,
    )
    assert sample_project.model_dump() == before


def test_small_word_pool_keeps_unfilled_slots_and_manual_selection_is_role_scoped(
    sample_project, sample_project_root,
):
    base, oddball = sample_project.stimulus_sets
    base.modality = oddball.modality = StimulusModality.WORD
    base.words = ["zebra", "zebra", "apple"]
    oddball.words = ["sand", "sea"]
    condition = sample_project.conditions[0]
    sources = load_condition_figure_sources(
        sample_project, sample_project_root, condition.condition_id,
    )

    automatic = sources.automatic_spec()
    assert automatic.sequence_stimuli == (
        "zebra", "apple", None, None, "sand", None, None, None, None, "sea", None, None,
    )
    assert automatic.base_hz == sample_project.settings.protocol.base_hz
    manual = sources.make_spec(["apple"] * 4, "sea")
    assert manual.base_stimuli == ("apple",) * 4
    assert manual.sequence_stimuli is None
    with pytest.raises(ValueError, match="configured Base"):
        sources.make_spec(["sand"] * 4, "sea")
    with pytest.raises(ValueError, match="configured Oddball"):
        sources.make_spec(["apple"] * 4, "zebra")


def test_automatic_reserves_role_examples_and_detects_copies_across_paths(tmp_path):
    shared_base, shared_oddball, base, base_copy, oddball_a, oddball_b = (
        tmp_path / f"{name}.png" for name in (
            "shared-base", "shared-oddball", "base", "base-copy", "oddball-a", "oddball-b",
        )
    )
    for path, color in ((shared_base, "red"), (base, "black"),
                        (oddball_a, "blue"), (oddball_b, "white")):
        with Image.new("RGB", (12, 10), color=color) as image:
            image.save(path)
    shared_oddball.write_bytes(shared_base.read_bytes())
    base_copy.write_bytes(base.read_bytes())
    sources = ConditionFigureSources(
        "Overlap", 6.0, 5, (shared_base, base, base_copy), (shared_oddball, oddball_a, oddball_b),
    )

    spec = sources.automatic_spec()

    assert spec.sequence_stimuli == (
        base, shared_base, None, None, oddball_b, None, None, None, None, oddball_a, None, None,
    )


def test_automatic_spreads_choices_across_large_pools():
    base = tuple(f"base {index}" for index in range(19))
    oddballs = tuple(f"oddball {index}" for index in range(9))
    sources = ConditionFigureSources("Full pools", 6.0, 5, base, oddballs)

    spec = sources.automatic_spec()

    assert spec.sequence_stimuli == (
        *base[:8:2], oddballs[0], *base[8:16:2], oddballs[-1], *base[16::2],
    )


def test_uses_selected_manifest_variant_and_reports_missing_derivative(
    sample_project, sample_project_root,
):
    materialize_project_assets(
        sample_project, project_root=sample_project_root, variants=[StimulusVariant.GRAYSCALE],
    )
    condition = sample_project.conditions[0]
    condition.stimulus_variant = StimulusVariant.GRAYSCALE
    sources = load_condition_figure_sources(
        sample_project, sample_project_root, condition.condition_id,
    )
    assert all(
        isinstance(path, Path) and "grayscale-variants" in path.parts
        for path in (*sources.base_stimuli, *sources.oddball_stimuli)
    )
    missing_path = sources.oddball_stimuli[0]
    assert isinstance(missing_path, Path)
    missing_path.unlink()

    with pytest.raises(ValueError, match="Could not load Oddball images.*does not exist"):
        load_condition_figure_sources(sample_project, sample_project_root, condition.condition_id)


def test_candidates_use_setup_order_and_omit_specialized_conditions(multi_condition_project):
    project = multi_condition_project
    in_order = tuple(project.conditions)
    project.conditions = list(reversed(in_order))
    in_order[1].masking_catch = True
    assert condition_figure_candidates(project) == (in_order[0], in_order[2], in_order[3])
    cognitive_load = project.model_copy(update={
        "experiment_category": ExperimentCategory.COGNITIVE_LOAD_FPVS,
    })
    assert condition_figure_candidates(cognitive_load) == condition_figure_candidates(project)
    native_ab = project.model_copy(update={
        "experiment_category": ExperimentCategory.ATTENTIONAL_BLINK,
    })
    assert condition_figure_candidates(native_ab) == ()


def test_missing_stimulus_set_points_to_setup(sample_project, sample_project_root):
    condition = sample_project.conditions[0]
    sample_project.stimulus_sets.pop()
    with pytest.raises(ValueError, match="Assign Base and Oddball.*Setup"):
        load_condition_figure_sources(sample_project, sample_project_root, condition.condition_id)


def test_export_destination_keeps_project_stimulus_folders_and_legacy_assets_read_only(
    sample_project, sample_project_root, tmp_path,
):
    root = sample_project_root
    manifest = materialize_project_assets(
        sample_project, project_root=root, variants=[StimulusVariant.GRAYSCALE],
    )
    sample_project.stimulus_sets[0].source_dir = "old-source"
    asset = manifest.sets[0].assets[0]
    asset.derivatives[0].relative_path = "figures/legacy-variant.png"
    write_stimulus_manifest(root, manifest)

    validate_condition_figure_destination(sample_project, root, tmp_path / "outside.png")
    validate_condition_figure_destination(sample_project, root, root / "figures/figure.png")
    for protected in ("stimuli/test.png", "old-source/new.png"):
        with pytest.raises(ValueError, match="outside the project's stimulus folders"):
            validate_condition_figure_destination(sample_project, root, root / protected)
    with pytest.raises(ValueError, match="does not replace a stimulus"):
        validate_condition_figure_destination(
            sample_project, root, root / "figures/legacy-variant.png",
        )


def test_export_destination_checks_both_link_location_and_target(
    sample_project, sample_project_root, tmp_path,
):
    root = sample_project_root
    stimulus = next((root / sample_project.stimulus_sets[0].source_dir).glob("*.png"))
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside")
    outside_link = tmp_path / "to-stimulus.png"
    stimulus_link = root / "stimuli" / "to-outside.png"
    try:
        outside_link.symlink_to(stimulus)
        stimulus_link.symlink_to(outside)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"This host cannot create a file symlink: {error}")

    for destination in (outside_link, stimulus_link):
        with pytest.raises(ValueError, match="outside the project's stimulus folders"):
            validate_condition_figure_destination(sample_project, root, destination)
