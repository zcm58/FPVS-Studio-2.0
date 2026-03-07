"""Shared pytest fixtures for FPVS Studio tests."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.models import (
    Condition,
    FixationTaskSettings,
    ImageResolution,
    ProjectFile,
    ProjectMeta,
    ProjectSettings,
    StimulusSet,
)


def _build_project(project_id: str, project_name: str, *, condition_count: int) -> ProjectFile:
    conditions = [
        Condition(
            condition_id=f"condition-{index + 1}",
            name=f"Condition {index + 1}",
            instructions=f"Instructions for condition {index + 1}.",
            base_stimulus_set_id="base-set",
            oddball_stimulus_set_id="oddball-set",
            sequence_count=1,
            duty_cycle_mode=DutyCycleMode.CONTINUOUS,
            order_index=index,
        )
        for index in range(condition_count)
    ]
    if condition_count == 1:
        conditions[0] = conditions[0].model_copy(
            update={
                "condition_id": "faces",
                "name": "Faces",
                "instructions": "",
            }
        )

    return ProjectFile(
        meta=ProjectMeta(
            project_id=project_id,
            name=project_name,
            template_id="fpvs_6hz_every5_v1",
        ),
        settings=ProjectSettings(
            fixation_task=FixationTaskSettings(
                enabled=True,
                changes_per_sequence=2,
                target_duration_ms=250,
                min_gap_ms=1000,
                max_gap_ms=2000,
                response_keys=["space"],
            )
        ),
        stimulus_sets=[
            StimulusSet(
                set_id="base-set",
                name="Base Set",
                source_dir="stimuli/source/base-set/originals",
                resolution=ImageResolution(width_px=256, height_px=256),
                image_count=3,
            ),
            StimulusSet(
                set_id="oddball-set",
                name="Oddball Set",
                source_dir="stimuli/source/oddball-set/originals",
                resolution=ImageResolution(width_px=256, height_px=256),
                image_count=3,
            ),
        ],
        conditions=conditions,
    )


@pytest.fixture
def sample_project() -> ProjectFile:
    """Return a minimally valid project with one compile-ready condition."""

    return _build_project("sample-project", "Sample Project", condition_count=1)


@pytest.fixture
def multi_condition_project() -> ProjectFile:
    """Return a compile-ready project with four ordered conditions."""

    project = _build_project(
        "multi-condition-project",
        "Multi Condition Project",
        condition_count=4,
    )
    project.settings.session.block_count = 2
    return project


@pytest.fixture
def sample_project_root(tmp_path, sample_project: ProjectFile) -> Path:
    """Create a project-like directory with deterministic source image files."""

    project_root = tmp_path / sample_project.meta.project_id
    _populate_project_root(project_root, sample_project)
    return project_root


@pytest.fixture
def multi_condition_project_root(tmp_path, multi_condition_project: ProjectFile) -> Path:
    """Create a project-like directory for the multi-condition project."""

    project_root = tmp_path / multi_condition_project.meta.project_id
    _populate_project_root(project_root, multi_condition_project)
    return project_root


def _populate_project_root(project_root: Path, project: ProjectFile) -> None:
    """Create deterministic source image files for a project root."""

    for stimulus_set in project.stimulus_sets:
        source_dir = project_root / Path(stimulus_set.source_dir)
        source_dir.mkdir(parents=True, exist_ok=True)
        for index in range(1, 4):
            Image.new("RGB", (256, 256), color=(index * 20, 0, 0)).save(
                source_dir / f"{stimulus_set.set_id}-{index:02d}.png"
            )
