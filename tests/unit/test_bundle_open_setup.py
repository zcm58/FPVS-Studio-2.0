"""Post-download project reads without importing Qt."""

from __future__ import annotations

import ast
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.unit.test_project_bundle import _save_bundle_ready_project

from fpvs_studio.core.condition_template_profiles import (
    load_condition_template_profile_library,
    save_condition_template_profile_library,
)
from fpvs_studio.core.paths import (
    filesystem_path,
    is_reserved_root_entry_name,
    project_json_path,
    stimulus_manifest_path,
)
from fpvs_studio.core.project_bundle import export_project_bundle, import_project_bundle
from fpvs_studio.core.serialization import load_project_file
from fpvs_studio.gui.document_support import resolve_project_location
from fpvs_studio.preprocessing.manifest import read_stimulus_manifest


def _source_functions(relative, names, **namespace):
    # Execute the actual I/O methods with the document/controller's required state.
    # Qt construction and thread ownership remain covered by registered GUI tests.
    repository = Path(__file__).resolve().parents[2]
    parsed = ast.parse((repository / relative).read_text(encoding="utf-8"))
    nodes = []
    for name in names:
        node = next(node for node in ast.walk(parsed)
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name)
        if isinstance(node, ast.FunctionDef):
            node.decorator_list = []
        nodes.append(node)
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *nodes,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), relative, "exec"), namespace)
    return namespace


@pytest.fixture
def imported_long_project(tmp_path, sample_project, sample_project_root):
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle = tmp_path / "post-download.fpvsbundle"
    export_project_bundle(sample_project_root, bundle)
    receiver = tmp_path / ("another-pc-user-" * 5) / ("研究室 root " * 5) / ("setup-folder-" * 5)
    while len(str(receiver)) <= 280:
        receiver /= "root-folder"
    return import_project_bundle(bundle, receiver).project_root


@pytest.fixture
def no_long_path_policy(monkeypatch):
    original_dir, original_file, original_open = Path.is_dir, Path.is_file, Path.open

    def unavailable(path):
        value = str(path)
        return len(value) >= 248 and not value.startswith("\\\\?\\")

    monkeypatch.setattr(Path, "is_dir", lambda path: False if unavailable(path)
                        else original_dir(path))
    monkeypatch.setattr(Path, "is_file", lambda path: False if unavailable(path)
                        else original_file(path))

    def open_file(path, *args, **kwargs):
        if unavailable(path):
            raise OSError(206, "Windows long-path policy is disabled", str(path))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_file)


@pytest.mark.skipif(os.name != "nt", reason="Windows namespace behavior")
@pytest.mark.parametrize("json_file", [False, True])
def test_open_imported_project_without_windows_long_path_policy(
    imported_long_project, no_long_path_policy, json_file,
):
    read = _source_functions(
        "src/fpvs_studio/gui/document.py", ["read_existing"],
        resolve_project_location=resolve_project_location,
        load_project_file=load_project_file, stimulus_manifest_path=stimulus_manifest_path,
        read_stimulus_manifest=read_stimulus_manifest, filesystem_path=filesystem_path,
    )["read_existing"]
    location = imported_long_project / "project.json" if json_file else imported_long_project
    root, project, manifest = read(location)
    assert root == imported_long_project
    assert project.meta.project_id == root.name
    assert manifest is not None and manifest.project_id == project.meta.project_id


@pytest.mark.skipif(os.name != "nt", reason="Windows namespace behavior")
@pytest.mark.parametrize("manifest", [False, True])
def test_read_imported_project_json_without_windows_long_path_policy(
    imported_long_project, no_long_path_policy, manifest,
):
    loaded = (read_stimulus_manifest(imported_long_project) if manifest
              else load_project_file(imported_long_project / "project.json"))
    identity = loaded.project_id if manifest else loaded.meta.project_id
    assert identity == imported_long_project.name


@pytest.mark.skipif(os.name != "nt", reason="Windows namespace behavior")
def test_imported_project_remains_discoverable_after_restart(
    imported_long_project, no_long_path_policy,
):
    methods = _source_functions(
        "src/fpvs_studio/gui/controller.py",
        ["_normalize_path", "_is_within_configured_root", "_discover_project_roots"],
        Path=Path, filesystem_path=filesystem_path, project_json_path=project_json_path,
        is_reserved_root_entry_name=is_reserved_root_entry_name,
    )
    controller = SimpleNamespace(
        _fpvs_root_dir=imported_long_project.parent, _normalize_path=methods["_normalize_path"],
    )
    controller._is_within_configured_root = lambda path: methods["_is_within_configured_root"](
        controller, path,
    )
    assert methods["_discover_project_roots"](controller) == [imported_long_project]


@pytest.mark.skipif(os.name != "nt", reason="Windows namespace behavior")
def test_setup_image_readiness_detects_changes_under_long_root(
    imported_long_project, no_long_path_policy,
):
    source = filesystem_path(imported_long_project / "stimuli/readiness")
    source.mkdir(parents=True)
    marker = _source_functions(
        "src/fpvs_studio/gui/document_stimuli.py", ["_source_dir_marker"],
        Path=Path, filesystem_path=filesystem_path,
    )["_source_dir_marker"]
    document = SimpleNamespace(_project_root=imported_long_project)
    stimulus = SimpleNamespace(source_dir="stimuli/readiness")
    first = marker(document, stimulus)
    assert first == ("directory", source.stat().st_mtime_ns)
    changed_time = first[1] + 10_000_000_000
    os.utime(source, ns=(changed_time, changed_time))
    assert marker(document, stimulus) == ("directory", source.stat().st_mtime_ns)
    assert marker(document, stimulus) != first


def _settings_controller(root):
    stored = {"root": str(root), "recent": []}
    settings = SimpleNamespace(
        value=lambda key, default, **kwargs: stored.get(key, default),
        setValue=lambda key, value: stored.update({key: value}),
        remove=lambda key: stored.pop(key, None), sync=lambda: None,
    )
    methods = _source_functions(
        "src/fpvs_studio/gui/controller.py",
        ["load_recent_project_roots", "record_recent_project_root",
         "load_fpvs_root_dir", "save_fpvs_root_dir"],
        Path=Path, filesystem_path=filesystem_path,
        _RECENT_PROJECT_ROOTS_KEY="recent", _MAX_RECENT_PROJECTS=10, _FPVS_ROOT_DIR_KEY="root",
    )
    controller = SimpleNamespace(_settings=settings, _normalize_fpvs_root_layout=lambda: True)
    controller.load_recent_project_roots = lambda: methods["load_recent_project_roots"](controller)
    return controller, methods, stored


@pytest.mark.skipif(os.name != "nt", reason="Windows namespace behavior")
def test_opened_bundle_is_retained_in_recent_projects(imported_long_project, no_long_path_policy):
    controller, methods, stored = _settings_controller(imported_long_project.parent)
    methods["record_recent_project_root"](controller, imported_long_project)
    assert stored["recent"] == [str(imported_long_project)]
    assert controller.load_recent_project_roots() == [imported_long_project]


@pytest.mark.skipif(os.name != "nt", reason="Windows namespace behavior")
@pytest.mark.parametrize("save", [False, True])
def test_receiving_root_preference_survives_long_path_policy(
    imported_long_project, no_long_path_policy, save,
):
    root = imported_long_project.parent
    controller, methods, stored = _settings_controller(root)
    if save:
        methods["save_fpvs_root_dir"](controller, root)
    assert methods["load_fpvs_root_dir"](controller) == root
    assert stored["root"] == str(root)
    assert controller._fpvs_root_dir == root


@pytest.mark.skipif(os.name != "nt", reason="Windows namespace behavior")
def test_root_setup_preserves_template_library_on_long_paths(imported_long_project, monkeypatch):
    root = imported_long_project.parent
    library = load_condition_template_profile_library(root)
    custom = library.profiles[0].model_copy(update={
        "profile_id": "local-profile", "display_name": "Local profile to preserve",
        "built_in": False,
    }, deep=True)
    library.profiles.append(custom)
    saved = save_condition_template_profile_library(root, library)
    original_mkdir = Path.mkdir

    def mkdir(path, *args, **kwargs):
        if len(str(path)) >= 248 and not str(path).startswith("\\\\?\\"):
            raise OSError(206, "Windows long-path policy is disabled", str(path))
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    assert load_condition_template_profile_library(root) == saved
