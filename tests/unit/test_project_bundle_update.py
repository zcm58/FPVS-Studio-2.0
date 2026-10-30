"""In-place Library authoring updates preserve local evidence and recover on failure."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from PIL import Image

from fpvs_studio.core import project_bundle_update as updater
from fpvs_studio.core.enums import DutyCycleMode, TriggerBackendKind
from fpvs_studio.core.library_origin import (
    LibraryProjectOrigin,
    load_library_origin,
    save_library_origin,
)
from fpvs_studio.core.models import ProjectRecordingSettings
from fpvs_studio.core.paths import filesystem_path
from fpvs_studio.core.project_bundle import (
    ProjectBundleCancelled,
    ProjectBundleError,
    export_project_bundle,
    import_project_bundle,
)
from fpvs_studio.core.project_service import discover_project_roots
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.preprocessing.manifest import (
    create_empty_manifest,
    read_stimulus_manifest,
    write_stimulus_manifest,
)


def _bytes(root):
    return {
        p.relative_to(filesystem_path(root)).as_posix(): p.read_bytes()
        for p in filesystem_path(root).rglob("*")
        if p.is_file()
    }


@pytest.fixture
def update_case(tmp_path, sample_project, sample_project_root):
    source = sample_project_root
    original = sample_project
    save_project_file(original, source / "project.json")
    write_stimulus_manifest(source, create_empty_manifest(original.meta.project_id))
    old_bundle = tmp_path / "old.fpvsbundle"
    export_project_bundle(source, old_bundle)
    studio = tmp_path / "Studio Root"
    studio.mkdir()
    # A collision-safe local ID must survive replacing a bundle with its upstream ID.
    (studio / original.meta.project_id).mkdir()
    receipt = LibraryProjectOrigin(
        service_url="https://openfpvs.com",
        item_id="test-study",
        installed_version="1.0.0",
        bundle_sha256=hashlib.sha256(old_bundle.read_bytes()).hexdigest(),
        local_project_id=original.meta.project_id,
        auto_check=False,
    )
    root = studio / "local-study"
    shutil.copytree(source, root)
    local = original.model_copy(deep=True)
    local.meta.project_id = root.name
    write_stimulus_manifest(root, create_empty_manifest(local.meta.project_id))
    save_library_origin(
        root, receipt.model_copy(update={"local_project_id": local.meta.project_id})
    )
    local.meta.name = "My local study"
    local.settings.display.monitor_name = "Lab display"
    local.settings.display.preferred_refresh_hz = 60
    local.settings.display.screen_width_cm = 44
    local.settings.display.background_color = "#112233"
    local.settings.display.stimulus_width_degrees = 9
    local.settings.triggers.backend = TriggerBackendKind.NULL
    local.settings.triggers.enabled = False
    local.settings.triggers.serial_port = "COM77"
    local.settings.triggers.baudrate = 57600
    local.settings.triggers.pulse_width_ms = 7
    local.settings.triggers.reset_delay_ms = 9
    local.settings.recording = ProjectRecordingSettings(recording_backend="unicorn_udp")
    local.settings.condition_profile_id = "lab-profile"
    local.settings.allow_repeated_participant_sessions = True
    local.manual_removed_electrodes = {"001": ["A1", "A2"]}
    save_project_file(local, root / "project.json")
    for relative in (
        "runs/P001/results.csv",
        "logs/session.log",
        "cache/local.dat",
        ".fpvs-data-sharing/private.json",
        "my notes.txt",
        ".fpvs-library/extra.txt",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("local evidence " + relative, encoding="utf-8")
    (root / "stimuli/old-user-sidecar.txt").write_text("keep in backup", encoding="utf-8")
    incoming = original.model_copy(deep=True)
    incoming.conditions[0].name = "New authored condition"
    incoming.settings.display.background_color = "#778899"
    incoming.settings.display.stimulus_width_degrees = 3
    incoming.settings.display.preferred_refresh_hz = 120
    incoming.settings.triggers.oddball_trigger_code = 73
    incoming.settings.triggers.allow_nonstandard_oddball_trigger_code = True
    save_project_file(incoming, source / "project.json")
    first_image = next((source / "stimuli").rglob("*.png"))
    Image.new("RGB", (256, 256), color=(0, 250, 0)).save(first_image)
    bundle = tmp_path / "new.fpvsbundle"
    export_project_bundle(source, bundle)
    new_origin = receipt.model_copy(
        update={
            "installed_version": "1.1.0",
            "bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
            "local_project_id": local.meta.project_id,
            "auto_check": True,
        }
    )
    return SimpleNamespace(
        root=root,
        studio=studio,
        bundle=bundle,
        incoming=incoming,
        origin=new_origin,
        local=local,
        source=source,
    )


def _update(case, **kwargs):
    return updater.update_project_bundle(
        case.bundle,
        case.root,
        case.studio,
        library_origin=case.origin,
        expected_snapshot=updater.capture_project_update_snapshot(case.root),
        **kwargs,
    )


def test_update_replaces_authored_files_and_preserves_local_identity_evidence_and_backup(
    update_case,
):
    case = update_case
    before = _bytes(case.root)
    result = _update(case)
    project = load_project_file(case.root / "project.json")
    assert result.scaffold.project_root == case.root
    assert result.scaffold.project == project
    assert project.meta.project_id == case.local.meta.project_id
    assert project.meta.name == "My local study"
    assert project.conditions[0].name == "New authored condition"
    assert project.settings.display.monitor_name == "Lab display"
    assert project.settings.display.preferred_refresh_hz == 60
    assert project.settings.display.screen_width_cm == 44
    assert project.settings.display.background_color == "#778899"
    assert project.settings.display.stimulus_width_degrees == 3
    assert project.settings.triggers.backend == TriggerBackendKind.NULL
    assert project.settings.triggers.serial_port == "COM77"
    assert project.settings.triggers.enabled is False
    assert project.settings.triggers.baudrate == 57600
    assert project.settings.triggers.pulse_width_ms == 7
    assert project.settings.triggers.reset_delay_ms == 9
    assert project.settings.triggers.oddball_trigger_code == 73
    assert project.settings.triggers.allow_nonstandard_oddball_trigger_code is True
    assert project.settings.recording == case.local.settings.recording
    assert project.settings.condition_profile_id == "lab-profile"
    assert project.settings.allow_repeated_participant_sessions is True
    assert project.manual_removed_electrodes == {"001": ["A1", "A2"]}
    assert read_stimulus_manifest(case.root).project_id == project.meta.project_id
    assert result.manifest == read_stimulus_manifest(case.root)
    receipt = load_library_origin(case.root)
    assert receipt.installed_version == "1.1.0"
    assert receipt.bundle_sha256 == case.origin.bundle_sha256
    assert receipt.local_project_id == project.meta.project_id
    assert receipt.auto_check is False
    after = _bytes(case.root)
    for relative, payload in before.items():
        if not relative.startswith("stimuli/") and relative not in (
            "project.json",
            ".fpvs-library/project-origin.json",
        ):
            assert after[relative] == payload
    backup = _bytes(result.backup_path)
    for relative, payload in before.items():
        if relative.startswith("stimuli/") or relative in (
            "project.json",
            ".fpvs-library/project-origin.json",
        ):
            assert backup[relative] == payload
    assert "stimuli/old-user-sidecar.txt" not in after
    assert json.loads(backup["update.json"])["status"] == "complete"
    assert discover_project_roots(case.studio) == [case.root]


@pytest.mark.parametrize("failure_step", range(1, 7))
def test_each_commit_rename_failure_restores_exact_original(update_case, monkeypatch, failure_step):
    case = update_case
    before = _bytes(case.root)
    real_move = updater._move
    count = 0

    def fail_once(source, target):
        nonlocal count
        count += 1
        if count == failure_step:
            raise PermissionError("synthetic Windows sharing violation")
        return real_move(source, target)

    monkeypatch.setattr(updater, "_move", fail_once)
    with pytest.raises(ProjectBundleError, match="original project was restored"):
        _update(case)
    assert _bytes(case.root) == before


def test_cancel_before_commit_is_noop_and_late_cancel_returns_success(update_case):
    case = update_case
    before = _bytes(case.root)
    cancel = Event()

    def cancel_before(stage):
        if stage == "commit":
            cancel.set()

    with pytest.raises(ProjectBundleCancelled):
        _update(case, cancel_event=cancel, progress_callback=cancel_before)
    assert _bytes(case.root) == before


def test_cancel_during_commit_does_not_undo_completed_update(update_case, monkeypatch):
    cancel = Event()
    real_move = updater._move

    def move_and_cancel(source, target):
        real_move(source, target)
        cancel.set()

    monkeypatch.setattr(updater, "_move", move_and_cancel)
    result = _update(update_case, cancel_event=cancel)
    assert result.scaffold.project.conditions[0].name == "New authored condition"
    assert load_library_origin(update_case.root).installed_version == "1.1.0"


def test_precommit_check_failure_leaves_original_unchanged(update_case, monkeypatch):
    case = update_case
    before = _bytes(case.root)
    checked = []

    def reject_pending_results():
        checked.append(True)
        raise RuntimeError("Pending Results capture must finish first")

    def no_move(*_args):
        raise AssertionError("No authored file may move before the precommit check passes")

    monkeypatch.setattr(updater, "_move", no_move)
    with pytest.raises(RuntimeError, match="Pending Results"):
        _update(case, precommit_check=reject_pending_results)
    assert checked == [True]
    assert _bytes(case.root) == before


def test_cancellation_while_precommit_check_runs_is_still_a_noop(update_case):
    case = update_case
    before = _bytes(case.root)
    cancel = Event()
    with pytest.raises(ProjectBundleCancelled):
        _update(case, cancel_event=cancel, precommit_check=cancel.set)
    assert _bytes(case.root) == before


def test_cancellation_during_local_validation_is_not_reported_as_display_failure(
    update_case,
    monkeypatch,
):
    case = update_case
    before = _bytes(case.root)
    cancel = Event()
    validate = updater._validate_bundle_source
    count = 0

    def cancel_local(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            cancel.set()
        return validate(*args, **kwargs)

    monkeypatch.setattr(updater, "_validate_bundle_source", cancel_local)
    with pytest.raises(ProjectBundleCancelled):
        _update(case, cancel_event=cancel)
    assert _bytes(case.root) == before


@pytest.mark.parametrize("mutate", ["project", "stimulus", "receipt"])
def test_review_snapshot_rejects_saved_changes_before_download(update_case, mutate):
    case = update_case
    snapshot = updater.capture_project_update_snapshot(case.root)
    if mutate == "project":
        project = load_project_file(case.root / "project.json")
        project.meta.name = "Changed after review"
        save_project_file(project, case.root / "project.json")
    elif mutate == "stimulus":
        next((case.root / "stimuli").rglob("*.png")).write_bytes(b"changed image")
    else:
        receipt = load_library_origin(case.root)
        save_library_origin(case.root, receipt.model_copy(update={"auto_check": True}))
    changed = _bytes(case.root)
    with pytest.raises(ProjectBundleError, match="changed after update review"):
        updater.update_project_bundle(
            case.bundle,
            case.root,
            case.studio,
            library_origin=case.origin,
            expected_snapshot=snapshot,
        )
    assert _bytes(case.root) == changed


def test_change_while_download_is_prepared_is_not_overwritten(update_case):
    case = update_case

    def edit_before_commit(stage):
        if stage == "commit":
            project = load_project_file(case.root / "project.json")
            project.meta.name = "External edit while preparing update"
            save_project_file(project, case.root / "project.json")

    with pytest.raises(ProjectBundleError, match="changed during update review"):
        _update(case, progress_callback=edit_before_commit)
    assert load_project_file(case.root / "project.json").meta.name.startswith("External edit")
    assert load_library_origin(case.root).installed_version == "1.0.0"


@pytest.mark.parametrize(
    "changes",
    [
        {"item_id": "other-study"},
        {"service_url": "https://other.example.test"},
        {"installed_version": "1.0.0"},
        {"installed_version": "0.9.0"},
        {"installed_version": None},
        {"bundle_sha256": None},
        {"bundle_sha256": "b" * 64},
    ],
)
def test_wrong_identity_version_or_digest_does_not_modify_original(update_case, changes):
    case = update_case
    before = _bytes(case.root)
    case.origin = case.origin.model_copy(update=changes)
    with pytest.raises(ProjectBundleError):
        _update(case)
    assert _bytes(case.root) == before


def test_managed_origin_alias_is_accepted_and_unknown_version_is_not(update_case):
    case = update_case
    receipt = load_library_origin(case.root)
    save_library_origin(
        case.root,
        receipt.model_copy(
            update={
                "service_url": "https://fpvs.zack-murphy.com",
            }
        ),
    )
    _update(case)
    assert load_library_origin(case.root).service_url == "https://openfpvs.com"
    save_library_origin(case.root, receipt.model_copy(update={"installed_version": None}))
    with pytest.raises(ProjectBundleError, match="Review and link"):
        updater.capture_project_update_snapshot(case.root)


def test_separate_installed_newer_copy_does_not_block_update_of_current_project(update_case):
    case = update_case
    other = import_project_bundle(case.bundle, case.studio, library_origin=case.origin)
    other_before = _bytes(other.project_root)
    _update(case)
    assert _bytes(other.project_root) == other_before
    assert load_library_origin(case.root).installed_version == "1.1.0"


def test_reparse_stimulus_is_rejected_without_following_it(update_case, monkeypatch):
    case = update_case
    target = filesystem_path(case.root / "stimuli")
    original = Path.lstat

    def lstat(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == target:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400, st_nlink=1)
        return info

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(ProjectBundleError, match="links or reparse"):
        updater.capture_project_update_snapshot(case.root)


def test_backup_ancestor_reparse_is_rejected_before_writing_outside(update_case, monkeypatch):
    case = update_case
    before = _bytes(case.root)
    target = filesystem_path(case.studio / ".fpvs-studio")
    target.mkdir()
    original = Path.lstat

    def lstat(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == target:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400, st_nlink=1)
        return info

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(ProjectBundleError, match="links or reparse"):
        _update(case)
    assert _bytes(case.root) == before
    assert list(target.iterdir()) == []


def test_snapshot_rejects_hard_linked_authored_files(update_case, tmp_path):
    case = update_case
    source = next((case.root / "stimuli").rglob("*.png"))
    os.link(source, tmp_path / "external-hardlink.png")
    with pytest.raises(ProjectBundleError, match="hard links"):
        updater.capture_project_update_snapshot(case.root)


def test_case_colliding_stimulus_names_are_rejected_before_traversal(update_case, monkeypatch):
    target = filesystem_path(update_case.root / "stimuli")
    original = Path.iterdir

    def iterdir(path):
        children = list(original(path))
        if path == target:
            children.append(children[0].with_name(children[0].name.swapcase()))
        return iter(children)

    monkeypatch.setattr(Path, "iterdir", iterdir)
    with pytest.raises(ProjectBundleError, match="differing only by case"):
        updater.capture_project_update_snapshot(update_case.root)


def test_local_display_incompatibility_leaves_current_project_unchanged(update_case):
    case = update_case
    before = _bytes(case.root)
    case.incoming.settings.protocol.base_hz = 4
    case.incoming.conditions[0].duty_cycle_mode = DutyCycleMode.BLANK_50
    save_project_file(case.incoming, case.source / "project.json")
    case.bundle = case.bundle.with_name("requires-even-120hz-cycle.fpvsbundle")
    export_project_bundle(case.source, case.bundle, refresh_hz=120)
    case.origin = case.origin.model_copy(
        update={
            "bundle_sha256": hashlib.sha256(case.bundle.read_bytes()).hexdigest(),
        }
    )
    with pytest.raises(ProjectBundleError, match="local display setup"):
        _update(case)
    assert _bytes(case.root) == before


def test_project_outside_configured_root_cannot_be_updated(update_case, tmp_path):
    studio = tmp_path / "Other Studio Root"
    studio.mkdir()
    snapshot = updater.capture_project_update_snapshot(update_case.root)
    with pytest.raises(ProjectBundleError, match="configured Studio Root"):
        updater.update_project_bundle(
            update_case.bundle,
            update_case.root,
            studio,
            library_origin=update_case.origin,
            expected_snapshot=snapshot,
        )


def test_studio_root_itself_is_not_an_update_target(update_case):
    case = update_case
    with pytest.raises(ProjectBundleError, match="not the Studio root or a backup"):
        updater.update_project_bundle(
            case.bundle,
            case.root,
            case.root,
            library_origin=case.origin,
            expected_snapshot=updater.capture_project_update_snapshot(case.root),
        )


def test_rollback_failure_retains_backup_and_staging_for_manual_recovery(update_case, monkeypatch):
    real_move = updater._move
    count = 0

    def fail_commit_and_rollback(source, target):
        nonlocal count
        count += 1
        if count in (3, 4):
            raise PermissionError("synthetic permanently locked file")
        return real_move(source, target)

    monkeypatch.setattr(updater, "_move", fail_commit_and_rollback)
    with pytest.raises(updater.ProjectBundleRecoveryError, match="restore its backup") as failure:
        _update(update_case)
    backups = list((update_case.studio / ".fpvs-studio/project-backups").glob("*/*"))
    assert len(backups) == 1
    assert failure.value.backup_path == backups[0]
    assert (backups[0] / "project.json").is_file()
    assert (backups[0] / "stimuli/manifest.json").is_file()
    assert list((update_case.studio / ".fpvs-studio/project-update-staging").iterdir())
