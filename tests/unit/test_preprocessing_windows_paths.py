"""Windows long-path image intake preserves filenames and portable provenance."""

from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image

from fpvs_studio.core.enums import StimulusVariant
from fpvs_studio.preprocessing.controls import (
    generate_phase_scrambled_png,
    generate_rot180_png,
)
from fpvs_studio.preprocessing.grayscale import generate_grayscale_png
from fpvs_studio.preprocessing.importer import (
    import_stimulus_source_directory,
    materialize_project_assets,
)
from fpvs_studio.preprocessing.inspection import compute_file_sha256, inspect_source_directory
from fpvs_studio.preprocessing.normalization import (
    normalize_stimulus_sets,
    scan_stimulus_sets_for_normalization,
)

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows extended filesystem paths")

LONG_FILENAME = (
    "u7659982228_asparagus_on_a_plain_gray_background_hyper_realis_"
    "940736f7-2738-4ce8-a1bc-26a91018375b_0.png"
)


def _fixture_path(path: Path) -> Path:
    """Build fixtures independently of the production helper being tested."""
    return Path("\\\\?\\" + str(path.absolute()))


def _long_project_root(tmp_path: Path, label: str) -> Path:
    component = label + "-" + "p" * max(1, 190 - len(str(tmp_path)) - len(label) - 2)
    project_root = tmp_path / component
    _fixture_path(project_root).mkdir(parents=True)
    return project_root


@pytest.mark.parametrize("label", ["ascii", "画像-é"])
def test_long_import_inspection_variants_and_normalization_preserve_paths(
    tmp_path, sample_project, label
):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / LONG_FILENAME
    Image.new("RGB", (32, 24), (40, 80, 120)).save(_fixture_path(source))
    source_bytes = _fixture_path(source).read_bytes()
    project_root = _long_project_root(tmp_path, label)
    set_id = "condition-1-t2-123456789abc"
    destination = project_root / "stimuli" / "original-images" / set_id / LONG_FILENAME
    assert len(str(destination)) > 260

    summary, stimulus_set = import_stimulus_source_directory(
        source_dir=source_dir,
        project_root=project_root,
        set_id=set_id,
        set_name="T2 images",
    )

    expected_relative = f"stimuli/original-images/{set_id}/{LONG_FILENAME}"
    assert summary.files[0].relative_path == expected_relative
    assert summary.files[0].sha256 == sha256(source_bytes).hexdigest()
    assert _fixture_path(destination).read_bytes() == source_bytes
    inspected = inspect_source_directory(
        project_root / stimulus_set.source_dir, relative_prefix=stimulus_set.source_dir
    )
    assert inspected.files == summary.files
    assert compute_file_sha256(destination) == summary.files[0].sha256

    project = sample_project.model_copy(
        update={"stimulus_sets": [stimulus_set], "conditions": []}, deep=True
    )
    variants = [StimulusVariant.GRAYSCALE, StimulusVariant.ROT180, StimulusVariant.PHASE_SCRAMBLED]
    manifest = materialize_project_assets(project, project_root=project_root, variants=variants)
    repeated = materialize_project_assets(project, project_root=project_root, variants=variants)
    asset = manifest.sets[0].assets[0]
    assert asset.source.relative_path == expected_relative
    assert {record.variant for record in asset.derivatives} == set(variants)
    assert repeated.sets[0].assets[0].derivatives == asset.derivatives
    assert repeated.sets[0].assets[0].source.sha256 == asset.source.sha256
    for derivative in asset.derivatives:
        assert "\\" not in derivative.relative_path
        assert not Path(derivative.relative_path).is_absolute()
        with Image.open(_fixture_path(project_root / derivative.relative_path)) as image:
            assert image.size == (32, 24)
    assert "\\\\?\\" not in _fixture_path(project_root / "stimuli/manifest.json").read_text(
        encoding="utf-8"
    )

    scan = scan_stimulus_sets_for_normalization(
        project_root=project_root, stimulus_sets=[stimulus_set]
    )
    assert scan.can_normalize
    assert scan.image_count == 1
    result = normalize_stimulus_sets(
        project_root=project_root, stimulus_sets=[stimulus_set], target_size=256
    )
    assert result.processed_count == 1
    normalized = result.sets[0]
    assert normalized.source_dir == f"stimuli/normalized-images/{set_id}"
    normalized_dir = _fixture_path(project_root / normalized.source_dir)
    normalized_file = next(normalized_dir.iterdir())
    with Image.open(normalized_file) as image:
        assert image.size == (256, 256)
    assert _fixture_path(destination).read_bytes() == source_bytes
    assert _fixture_path(source).read_bytes() == source_bytes


@pytest.mark.parametrize("kind", ["grayscale", "rot180", "phase_scrambled"])
def test_standalone_derivative_helpers_accept_long_source_and_destination(tmp_path, kind):
    root = _long_project_root(tmp_path, "画像")
    source = root / LONG_FILENAME
    Image.new("RGB", (32, 24), (40, 80, 120)).save(_fixture_path(source))
    destination = root / "derivatives" / LONG_FILENAME
    assert len(str(source)) > 260
    if kind == "grayscale":
        generate_grayscale_png(source, destination)
    elif kind == "rot180":
        generate_rot180_png(source, destination)
    else:
        generate_phase_scrambled_png(source, destination, seed=31)
    with Image.open(_fixture_path(destination)) as image:
        assert image.size == (32, 24)
