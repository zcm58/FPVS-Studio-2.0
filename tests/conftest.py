"""Shared pytest fixtures for FPVS Studio tests."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from PIL import Image

from fpvs_studio.core.enums import DutyCycleMode, StimulusModality
from fpvs_studio.core.models import (
    Condition,
    FixationTaskSettings,
    ImageResolution,
    ProjectFile,
    ProjectMeta,
    ProjectSettings,
    StimulusSet,
)
from tests.qt_test_registry import (
    QT_TESTS_ENV_VAR,
    load_qt_test_registry,
    qt_tests_requested,
    registry_mismatches,
    repo_relative_path,
    requested_registered_qt_files,
)

ROOT = Path(__file__).resolve().parents[1]
TEST_ENV_ROOT = (
    ROOT / "build" / "test_env" / f"pytest-{os.getpid()}-{uuid.uuid4().hex[:10]}"
)

if qt_tests_requested(cli_opt_in="--allow-qt-tests" in sys.argv, environ=os.environ):
    # pytest-qt is blocked from entry-point autoload in pyproject.toml so an
    # ordinary unit run never imports PySide6. Load it only after explicit opt-in.
    pytest_plugins = ("pytestqt.plugin",)


def _apply_workspace_test_env() -> Path:
    root = TEST_ENV_ROOT.resolve()
    directories = {
        "tmp": root / "tmp",
        "appdata": root / "appdata",
        "localappdata": root / "localappdata",
        "home": root / "home",
        "userprofile": root / "userprofile",
    }
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)

    os.environ["TMPDIR"] = str(directories["tmp"])
    os.environ["TMP"] = str(directories["tmp"])
    os.environ["TEMP"] = str(directories["tmp"])
    os.environ["APPDATA"] = str(directories["appdata"])
    os.environ["LOCALAPPDATA"] = str(directories["localappdata"])
    os.environ["HOME"] = str(directories["home"])
    os.environ["USERPROFILE"] = str(directories["userprofile"])
    tempfile.tempdir = str(directories["tmp"])
    return root


_apply_workspace_test_env()


def pytest_addoption(parser) -> None:
    group = parser.getgroup("fpvs-studio")
    group.addoption(
        "--allow-qt-tests",
        action="store_true",
        default=False,
        help=(
            "Collect registered Qt tests. These tests require an explicitly "
            "approved visible or CI Qt environment."
        ),
    )


def _qt_tests_allowed(config: pytest.Config) -> bool:
    return qt_tests_requested(
        cli_opt_in=bool(config.getoption("--allow-qt-tests")),
        environ=os.environ,
    )


def pytest_configure(config: pytest.Config) -> None:
    try:
        registry = load_qt_test_registry(ROOT)
    except (OSError, ValueError) as exc:
        raise pytest.UsageError(str(exc)) from exc

    missing, stale = registry_mismatches(ROOT, registry)
    if missing or stale:
        details: list[str] = []
        if missing:
            details.append("Qt tests missing from tests/qt_test_files.txt:")
            details.extend(f"  - {path}" for path in sorted(missing))
        if stale:
            details.append("Stale entries in tests/qt_test_files.txt:")
            details.extend(f"  - {path}" for path in sorted(stale))
        raise pytest.UsageError("\n".join(details))

    config._fpvs_studio_qt_test_registry = registry
    if _qt_tests_allowed(config):
        return

    explicitly_requested = requested_registered_qt_files(
        config.invocation_params.args,
        repo_root=ROOT,
        registry=registry,
    )
    if explicitly_requested:
        formatted = "\n".join(f"  - {path}" for path in sorted(explicitly_requested))
        raise pytest.UsageError(
            "Registered Qt tests require an explicit opt-in before collection:\n"
            f"{formatted}\nSet {QT_TESTS_ENV_VAR}=1 or pass --allow-qt-tests."
        )


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """Keep Qt test modules and their nested conftest from importing by default."""

    if _qt_tests_allowed(config):
        return None
    relative_path = repo_relative_path(Path(collection_path), ROOT)
    registry = config._fpvs_studio_qt_test_registry
    if relative_path == "tests/gui" or relative_path in registry:
        return True
    return None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    registry = config._fpvs_studio_qt_test_registry
    for item in items:
        relative_path = repo_relative_path(Path(item.path), ROOT)
        if relative_path in registry:
            item.add_marker(pytest.mark.qt)


def pytest_report_header(config: pytest.Config) -> str:
    registry = config._fpvs_studio_qt_test_registry
    if _qt_tests_allowed(config):
        return f"FPVS Studio Qt guard: explicit opt-in enabled ({len(registry)} files)"
    return (
        f"FPVS Studio Qt guard: {len(registry)} files excluded before import; "
        f"set {QT_TESTS_ENV_VAR}=1 or pass --allow-qt-tests to opt in"
    )


def pytest_unconfigure(config: pytest.Config) -> None:  # noqa: ARG001
    """Remove this process's namespaced workspace test environment."""

    shutil.rmtree(TEST_ENV_ROOT, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def _workspace_env() -> Path:
    """Keep temp/profile writes inside the workspace for deterministic test runs."""

    return _apply_workspace_test_env()


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
                source_dir="stimuli/original-images/base-set",
                resolution=ImageResolution(width_px=256, height_px=256),
                image_count=3,
            ),
            StimulusSet(
                set_id="oddball-set",
                name="Oddball Set",
                source_dir="stimuli/original-images/oddball-set",
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
        if stimulus_set.modality != StimulusModality.IMAGE:
            continue
        assert stimulus_set.source_dir is not None
        source_dir = project_root / Path(stimulus_set.source_dir)
        source_dir.mkdir(parents=True, exist_ok=True)
        for index in range(1, 4):
            Image.new("RGB", (256, 256), color=(index * 20, 0, 0)).save(
                source_dir / f"{stimulus_set.set_id}-{index:02d}.png"
            )
