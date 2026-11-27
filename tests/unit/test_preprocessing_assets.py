"""Derived-asset materialization tests."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image

from fpvs_studio.core.enums import StimulusVariant
from fpvs_studio.preprocessing.importer import materialize_project_assets
from fpvs_studio.preprocessing.manifest import find_manifest_set, write_stimulus_manifest


def test_materialization_reuses_the_imported_derivative_and_its_provenance(
    sample_project, sample_project_root, monkeypatch,
) -> None:
    root = sample_project_root
    variant = StimulusVariant.ROT180
    manifest = materialize_project_assets(sample_project, project_root=root, variants=[variant])
    record = manifest.sets[0].assets[0].derivatives[0]
    generated = root / record.relative_path
    imported = generated.with_name("preserved-rotation.png")
    with Image.open(generated) as img:
        img.save(imported, compress_level=0)
    assert imported.read_bytes() != generated.read_bytes()
    generated.unlink()
    record.relative_path = imported.relative_to(root).as_posix()
    record.sha256 = sha256(imported.read_bytes()).hexdigest()
    write_stimulus_manifest(root, manifest)

    def unexpected_write(*args, **kwargs):
        raise AssertionError("The imported files and their manifest are already complete")

    monkeypatch.setattr("fpvs_studio.preprocessing.importer.generate_rot180_png", unexpected_write)
    monkeypatch.setattr(
        "fpvs_studio.preprocessing.importer.write_stimulus_manifest", unexpected_write
    )
    retained = materialize_project_assets(sample_project, project_root=root, variants=[variant])

    assert retained == manifest
    assert sha256(imported.read_bytes()).hexdigest() == record.sha256
    assert not generated.exists()


def test_missing_imported_location_reuses_matching_canonical_copy(
    sample_project, sample_project_root, monkeypatch,
) -> None:
    root = sample_project_root
    variant = StimulusVariant.ROT180
    manifest = materialize_project_assets(sample_project, project_root=root, variants=[variant])
    record = manifest.sets[0].assets[0].derivatives[0]
    canonical = root / record.relative_path
    record.relative_path = "stimuli/old-layout/rotation.png"
    write_stimulus_manifest(root, manifest)

    def unexpected_generation(*args, **kwargs):
        raise AssertionError("The matching canonical PNG should be reused")

    monkeypatch.setattr(
        "fpvs_studio.preprocessing.importer.generate_rot180_png", unexpected_generation
    )
    retained = materialize_project_assets(sample_project, project_root=root, variants=[variant])
    assert retained == manifest
    repaired = root / record.relative_path
    assert repaired.read_bytes() == canonical.read_bytes()

    repaired.unlink()
    Image.new("RGB", (256, 256), "green").save(canonical)
    with pytest.raises(ValueError, match="checksum differs"):
        materialize_project_assets(sample_project, project_root=root, variants=[variant])
    assert not repaired.exists()


def test_materialization_rejects_a_replaced_canonical_png_and_preserves_the_record(
    sample_project, sample_project_root,
) -> None:
    from fpvs_studio.preprocessing.manifest import read_stimulus_manifest

    root = sample_project_root
    variant = StimulusVariant.ROT180
    manifest = materialize_project_assets(sample_project, project_root=root, variants=[variant])
    asset = manifest.sets[0].assets[0]
    record = asset.derivatives[0]
    path = root / record.relative_path
    Image.new("RGB", record.resolution.as_tuple(), "green").save(path)
    replaced = path.read_bytes()
    with pytest.raises(ValueError, match="checksum differs from the manifest"):
        materialize_project_assets(sample_project, project_root=root, variants=[variant])
    assert path.read_bytes() == replaced
    assert read_stimulus_manifest(root) == manifest


@pytest.mark.parametrize("imported_layout", [False, True])
def test_missing_recorded_derivative_repair_preserves_exact_bytes_and_provenance(
    sample_project, sample_project_root, monkeypatch, imported_layout,
) -> None:
    root = sample_project_root
    variant = StimulusVariant.GRAYSCALE
    manifest = materialize_project_assets(sample_project, project_root=root, variants=[variant])
    record = manifest.sets[0].assets[0].derivatives[0]
    original = root / record.relative_path
    png = original.read_bytes()
    original.unlink()
    if imported_layout:
        record.relative_path = "stimuli/archived-layout/image.png"
        write_stimulus_manifest(root, manifest)
    destination = root / record.relative_path
    files_before = {item: item.read_bytes() for item in root.rglob("*") if item.is_file()}

    def different_encoder(source, target):
        with Image.open(source) as image:
            image.convert("L").save(target, format="PNG", compress_level=0)

    with monkeypatch.context() as changed:
        changed.setattr(
            "fpvs_studio.preprocessing.importer.generate_grayscale_png", different_encoder
        )
        with pytest.raises(ValueError, match="Restore the original PNG"):
            materialize_project_assets(sample_project, project_root=root, variants=[variant])
    assert files_before == {item: item.read_bytes() for item in root.rglob("*") if item.is_file()}

    restored = materialize_project_assets(sample_project, project_root=root, variants=[variant])
    assert restored == manifest
    assert destination.read_bytes() == png


def test_equivalent_source_extensions_keep_distinct_derivatives_without_rewriting_the_first(
    sample_project, sample_project_root,
) -> None:
    root = sample_project_root
    sources = root / sample_project.stimulus_sets[0].source_dir
    Image.new("RGB", (256, 256), "orange").save(sources / "photo.jpg")
    variant = StimulusVariant.ROT180
    original = materialize_project_assets(sample_project, project_root=root, variants=[variant])
    first = next(a for a in original.sets[0].assets if a.source.relative_path.endswith("photo.jpg"))
    first_record = first.derivatives[0]
    first_path = root / first_record.relative_path
    first_bytes = first_path.read_bytes()
    # The newly added filename sorts before the already-materialized JPEG.
    (sources / "photo.jpeg").write_bytes((sources / "photo.jpg").read_bytes())
    updated = materialize_project_assets(sample_project, project_root=root, variants=[variant])
    photos = [
        asset for asset in updated.sets[0].assets
        if Path(asset.source.relative_path).stem == "photo"
    ]
    records = [asset.derivatives[0] for asset in photos]
    assert len({record.relative_path for record in records}) == 2
    assert first_record in records
    assert all((root / record.relative_path).read_bytes() == first_bytes for record in records)
    repeated = materialize_project_assets(sample_project, project_root=root, variants=[variant])
    assert repeated == updated


def test_recorded_repair_preserves_a_file_created_while_encoding(
    sample_project, sample_project_root, monkeypatch,
) -> None:
    from fpvs_studio.preprocessing.grayscale import generate_grayscale_png

    root = sample_project_root
    variant = StimulusVariant.GRAYSCALE
    manifest = materialize_project_assets(sample_project, project_root=root, variants=[variant])
    restored = root / manifest.sets[0].assets[0].derivatives[0].relative_path
    restored.unlink()

    def simultaneous_repair(source, target):
        generate_grayscale_png(source, target)
        Image.new("L", (256, 256), 127).save(restored)

    monkeypatch.setattr(
        "fpvs_studio.preprocessing.importer.generate_grayscale_png", simultaneous_repair
    )
    with pytest.raises(FileExistsError):
        materialize_project_assets(sample_project, project_root=root, variants=[variant])
    with Image.open(restored) as image:
        assert image.getextrema() == (127, 127)


@pytest.mark.parametrize("damaged_checkpoint", [False, True])
def test_missing_variant_prefers_verified_saved_study_bytes(
    sample_project, sample_project_root, monkeypatch, damaged_checkpoint,
) -> None:
    from fpvs_studio.core.serialization import save_project_file
    from fpvs_studio.core.study_versions import commit_setup_change, prepare_setup_change

    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    variant = StimulusVariant.ROT180
    manifest = materialize_project_assets(sample_project, project_root=root, variants=[variant])
    record = manifest.sets[0].assets[0].derivatives[0]
    path = root / record.relative_path
    with Image.open(path) as image:
        preserved = image.copy()
    preserved.save(path, compress_level=0)
    expected = path.read_bytes()
    record.sha256 = sha256(expected).hexdigest().upper()
    write_stimulus_manifest(root, manifest)
    draft = prepare_setup_change(root, sample_project)
    commit_setup_change(root, sample_project, draft, "", lambda _root: {}, save_version=True)
    checkpoint = root / ".fpvs-study" / "objects" / record.sha256.lower()
    assert checkpoint.read_bytes() == expected
    path.unlink()

    def unexpected_encoder(*args, **kwargs):
        raise AssertionError("Use the recorded checkpoint bytes before re-encoding")

    monkeypatch.setattr(
        "fpvs_studio.preprocessing.importer.generate_rot180_png", unexpected_encoder
    )
    if damaged_checkpoint:
        Image.new("RGB", (256, 256), "green").save(checkpoint, format="PNG")
        with pytest.raises(ValueError, match="Saved stimulus is damaged"):
            materialize_project_assets(sample_project, project_root=root, variants=[variant])
        assert not path.exists()
    else:
        restored = materialize_project_assets(sample_project, project_root=root, variants=[variant])
        assert restored == manifest
        assert checkpoint.read_bytes() == path.read_bytes() == expected
        assert materialize_project_assets(
            sample_project, project_root=root, variants=[variant]
        ) == manifest


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
