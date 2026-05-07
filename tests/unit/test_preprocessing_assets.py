"""Derived-asset materialization tests."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from fpvs_studio.core.enums import StimulusVariant
from fpvs_studio.preprocessing.importer import materialize_project_assets
from fpvs_studio.preprocessing.manifest import find_manifest_set


def test_materialize_grayscale_outputs_png_and_updates_manifest(
    sample_project,
    sample_project_root,
) -> None:
    manifest = materialize_project_assets(
        sample_project,
        project_root=sample_project_root,
        variants=[StimulusVariant.GRAYSCALE],
    )

    manifest_set = find_manifest_set(manifest, set_id="base-set")
    assert manifest_set is not None
    derivative = manifest_set.assets[0].derivatives[0]

    assert derivative.variant == StimulusVariant.GRAYSCALE
    assert derivative.relative_path.startswith(
        "stimuli/generated-variants/base-set/grayscale-variants/"
    )
    with Image.open(sample_project_root / Path(derivative.relative_path)) as image:
        assert image.size == (256, 256)


def test_materialize_rot180_outputs_png_and_updates_manifest(
    sample_project,
    sample_project_root,
) -> None:
    manifest = materialize_project_assets(
        sample_project,
        project_root=sample_project_root,
        variants=[StimulusVariant.ROT180],
    )

    manifest_set = find_manifest_set(manifest, set_id="oddball-set")
    assert manifest_set is not None
    derivative = manifest_set.assets[0].derivatives[0]

    assert derivative.variant == StimulusVariant.ROT180
    assert derivative.relative_path.startswith(
        "stimuli/generated-variants/oddball-set/rotated-180-variants/"
    )
    with Image.open(sample_project_root / Path(derivative.relative_path)) as image:
        assert image.size == (256, 256)


def test_materialize_phase_scrambled_is_deterministic_and_updates_manifest(
    sample_project,
    sample_project_root,
) -> None:
    first_manifest = materialize_project_assets(
        sample_project,
        project_root=sample_project_root,
        variants=[StimulusVariant.PHASE_SCRAMBLED],
    )
    second_manifest = materialize_project_assets(
        sample_project,
        project_root=sample_project_root,
        variants=[StimulusVariant.PHASE_SCRAMBLED],
    )

    first_set = find_manifest_set(first_manifest, set_id="base-set")
    second_set = find_manifest_set(second_manifest, set_id="base-set")
    assert first_set is not None
    assert second_set is not None

    first_derivative = first_set.assets[0].derivatives[0]
    second_derivative = second_set.assets[0].derivatives[0]

    assert first_derivative.variant == StimulusVariant.PHASE_SCRAMBLED
    assert first_derivative.relative_path.startswith(
        "stimuli/generated-variants/base-set/scrambled-variants/"
    )
    assert first_derivative.sha256 == second_derivative.sha256
    assert first_derivative.seed == second_derivative.seed
    assert first_derivative.deterministic_policy is not None
    with Image.open(sample_project_root / Path(first_derivative.relative_path)) as image:
        assert image.size == (256, 256)
