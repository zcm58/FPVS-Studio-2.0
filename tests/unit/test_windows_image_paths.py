"""Long Windows image paths survive import, compilation, preflight, and preparation."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image
from tests.unit.test_attentional_blink_stream_runtime import _play
from tests.unit.test_runtime_preflight import _PreflightEngine

from fpvs_studio.core.compiler import compile_run_spec
from fpvs_studio.core.paths import filesystem_path, stimulus_originals_dir
from fpvs_studio.preprocessing.importer import import_stimulus_source_directory
from fpvs_studio.preprocessing.manifest import (
    create_empty_manifest,
    inspection_summary_to_manifest_set,
    upsert_manifest_set,
)
from fpvs_studio.runtime.preflight import preflight_run_spec

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows extended filesystem paths")


@pytest.mark.parametrize("long_directory", [False, True])
@pytest.mark.parametrize("use_manifest", [False, True])
def test_long_imported_image_reaches_timed_preparation(
    monkeypatch, sample_project, sample_project_root, tmp_path, long_directory, use_manifest,
) -> None:
    project, project_root = sample_project, sample_project_root
    project.settings.fixation_task.enabled = False
    project.settings.fixation_task.accuracy_task_enabled = False
    project.settings.presentation.pre_stream_fixation_seconds = 0
    project.conditions[0].oddball_cycle_repeats_per_sequence = 1
    set_id = "target"
    if long_directory:
        prefix = "target-"
        prefix_length = len(str(stimulus_originals_dir(project_root, prefix)))
        set_id = prefix + "t" * max(1, 270 - prefix_length)
    destination_dir = stimulus_originals_dir(project_root, set_id)
    if long_directory:
        filename = "Target 01.PNG"
        assert len(str(destination_dir)) > 260
    else:
        assert len(str(destination_dir)) < 248
        filename_length = 276 - len(str(destination_dir)) - 1
        filename = "Target 01 " + "x" * (filename_length - 14) + ".PNG"
        assert len(str(destination_dir / filename)) == 276

    source_dir = tmp_path / "input"
    source_dir.mkdir()
    original = source_dir / filename
    assert len(str(original)) < 260
    Image.new("RGB", (128, 64), "purple").save(original)
    original_bytes = original.read_bytes()

    summary, stimulus_set = import_stimulus_source_directory(
        source_dir=source_dir, project_root=project_root, set_id=set_id, set_name="Oddball images",
    )
    imported = filesystem_path(destination_dir / filename)
    assert imported.is_file()
    assert imported.read_bytes() == original_bytes
    assert summary.image_count == stimulus_set.image_count == 1
    project.stimulus_sets.append(stimulus_set)
    project.conditions[0].oddball_stimulus_set_id = set_id
    manifest = None
    if use_manifest:
        manifest = upsert_manifest_set(
            create_empty_manifest(project.meta.project_id),
            inspection_summary_to_manifest_set(set_id=set_id, summary=summary),
        )

    run_spec = compile_run_spec(
        project, refresh_hz=60.0, project_root=project_root, manifest=manifest,
    )
    t2 = run_spec.stimulus_sequence[-1]
    expected_relative = f"stimuli/original-images/{set_id}/{filename}"
    assert t2.role == "oddball"
    assert t2.image_path == expected_relative
    assert "\\" not in t2.image_path and not Path(t2.image_path).is_absolute()
    preflight_run_spec(project_root, run_spec, engine=_PreflightEngine(), decode_image_assets=True)
    result, captures, _triggers, _engine = _play(monkeypatch, run_spec, project_root)
    assert result.completed_frames == run_spec.display.total_frames
    prepared_images = [str(stimulus.image) for stimulus in captures["image_stims"]]
    assert str(imported) in prepared_images
    assert original.read_bytes() == original_bytes
