"""Retired image-pair projects stay identifiable but cannot become runnable studies."""

import json

import pytest

from fpvs_studio.core.compiler import CompileError, compile_run_spec, compile_session_plan
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.models import AttentionalBlinkSettings
from fpvs_studio.core.project_bundle import ProjectBundleError, export_project_bundle
from fpvs_studio.core.project_config import ProjectConfigError, export_project_config
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest


@pytest.fixture
def retired_project(sample_project):
    project = sample_project.model_copy(
        update={"experiment_category": ExperimentCategory.ATTENTIONAL_BLINK}, deep=True,
    )
    project.conditions[0].attentional_blink = AttentionalBlinkSettings(isi_ms=75)
    project.conditions[0].t2_stimulus_set_id = project.conditions[0].oddball_stimulus_set_id
    return project


@pytest.mark.parametrize("session", [False, True])
def test_image_pairs_cannot_compile_even_with_a_selected_condition(retired_project, session):
    with pytest.raises(CompileError, match="Image-pair.*no longer supported"):
        if session:
            compile_session_plan(retired_project, refresh_hz=60)
        else:
            compile_run_spec(
                retired_project, refresh_hz=60,
                condition_id=retired_project.conditions[0].condition_id,
            )


def test_old_file_load_is_nondestructive_and_save_export_are_blocked(
    retired_project, sample_project_root, tmp_path,
):
    path = sample_project_root / "project.json"
    original = json.dumps(retired_project.model_dump(mode="json")).encode()
    path.write_bytes(original)
    write_stimulus_manifest(
        sample_project_root, create_empty_manifest(retired_project.meta.project_id),
    )
    original_images = {
        p.relative_to(sample_project_root): p.read_bytes()
        for p in (sample_project_root / "stimuli").rglob("*.png")
    }
    loaded = load_project_file(path)
    assert loaded.conditions[0].attentional_blink.isi_ms == 75
    assert (
        loaded.conditions[0].t2_stimulus_set_id
        == retired_project.conditions[0].t2_stimulus_set_id
    )
    with pytest.raises(ValueError, match="Image-pair.*no longer supported"):
        save_project_file(loaded, path)
    with pytest.raises(ProjectConfigError, match="Image-pair.*no longer supported"):
        export_project_config(loaded, None)
    bundle = tmp_path / "retired.fpvsbundle"
    with pytest.raises(ProjectBundleError, match="Image-pair.*no longer supported"):
        export_project_bundle(sample_project_root, bundle)
    assert not bundle.exists()
    assert path.read_bytes() == original
    assert {
        p.relative_to(sample_project_root): p.read_bytes()
        for p in (sample_project_root / "stimuli").rglob("*.png")
    } == original_images
