"""Local authoring history and participant-data protection, using synthetic files."""

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from fpvs_studio.core import study_versions
from fpvs_studio.core.paths import filesystem_path
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.study_lifecycle import (
    database_path,
    get_study,
    read_study,
    set_collection_complete,
)
from fpvs_studio.core.study_versions import (
    ProtocolReviewRequired,
    accepted_stimulus_digests,
    commit_change,
    commit_setup_change,
    create_from_version,
    current_version,
    ensure_working_setup,
    has_pending_setup_save,
    historical_draft,
    keep_saved_stimuli,
    list_versions,
    list_working_revisions,
    name_version,
    prepare_change,
    prepare_setup_change,
    read_study_and_saved_version_count,
    read_version_protocol,
    restore_version,
    saved_version_count,
)
from fpvs_studio.runtime.participant_results import research_visits_by_version


@pytest.mark.parametrize(
    "schema", ["missing", "versions", "study", "both", "corrupt", "directory"],
)
def test_project_discovery_study_metadata_matches_separate_reads(tmp_path, monkeypatch, schema):
    path = database_path(tmp_path)
    if schema != "missing":
        path.parent.mkdir()
    if schema in {"corrupt", "directory"}:
        if schema == "corrupt":
            path.write_bytes(b"invalid study database" * 64)
        else:
            path.mkdir()
        with pytest.raises(sqlite3.DatabaseError) as previous:
            read_study(tmp_path), saved_version_count(tmp_path)
        with pytest.raises(type(previous.value)) as current:
            read_study_and_saved_version_count(tmp_path)
        assert str(current.value) == str(previous.value)
        return
    if schema != "missing":
        with closing(sqlite3.connect(path)) as db, db:
            if schema in {"study", "both"}:
                db.execute("CREATE TABLE study(study_id,collection_complete,archived,created_from)")
                db.execute("INSERT INTO study VALUES ('original',1,0,NULL)")
            if schema in {"versions", "both"}:
                db.execute("CREATE TABLE versions(version_id)")
                db.execute("INSERT INTO versions VALUES ('v1'), ('v2')")
    expected = read_study(tmp_path), saved_version_count(tmp_path)
    opens = []
    connect = sqlite3.connect

    def counted_connect(db_path, *args, **kwargs):
        opens.append(db_path)
        return connect(db_path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", counted_connect)
    assert read_study_and_saved_version_count(tmp_path) == expected
    if schema == "missing":
        assert not opens and not path.parent.exists()
    elif path.stat().st_ino:
        assert opens == [path]


def test_project_discovery_reads_versions_committed_after_study_state(tmp_path, monkeypatch):
    path = database_path(tmp_path)
    path.parent.mkdir()
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE study(study_id,collection_complete,archived,created_from)")
        db.execute("INSERT INTO study VALUES ('original',1,0,NULL)")
    read = study_versions._read_optional_study

    def read_then_commit(db):
        state = read(db)
        with closing(sqlite3.connect(path)) as writer, writer:
            writer.execute("CREATE TABLE versions(version_id)")
            writer.execute("INSERT INTO versions VALUES ('v1')")
        return state

    monkeypatch.setattr(study_versions, "_read_optional_study", read_then_commit)
    assert read_study_and_saved_version_count(tmp_path) == (read_study(tmp_path), 1)


def test_project_discovery_reopens_a_retargeted_study_database(tmp_path, monkeypatch):
    link = tmp_path / ".fpvs-study"
    old, new = tmp_path / "original-db", tmp_path / "replacement-db"
    for parent, count in ((old, 1), (new, 2)):
        parent.mkdir()
        path = parent / "study.sqlite3"
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("CREATE TABLE study(study_id,collection_complete,archived,created_from)")
            db.execute("INSERT INTO study VALUES (?,0,0,NULL)", (parent.name,))
            db.execute("CREATE TABLE versions(version_id)")
            db.executemany("INSERT INTO versions VALUES (?)", [(str(i),) for i in range(count)])
    if os.name == "nt":
        from _winapi import CreateJunction

        def link_to(directory):
            CreateJunction(str(directory), str(link))

        unlink = link.rmdir
    else:
        def link_to(directory):
            link.symlink_to(directory, target_is_directory=True)

        unlink = link.unlink
    try:
        link_to(old)
    except OSError as exc:
        pytest.skip(f"Directory links are unavailable: {exc}")
    prior_state = read_study(tmp_path)
    read = study_versions._read_optional_study

    def read_then_redirect(db):
        state = read(db)
        unlink()
        link_to(new)
        return state

    monkeypatch.setattr(study_versions, "_read_optional_study", read_then_redirect)
    assert read_study_and_saved_version_count(tmp_path) == (prior_state, 2)


def test_save_restore_and_fork_exact_image_and_protocol(
    sample_project_root, sample_project, tmp_path
):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    assert read_study(root) is None
    assert not prepare_change(root, sample_project).changes
    initial = current_version(root)
    name_version(root, initial.version_id, "Original")
    image = next((root / "stimuli").rglob("*.png"))
    first_image = image.read_bytes()
    image.write_bytes(b"replacement image")
    sample_project.settings.protocol.base_hz = 8
    draft = prepare_change(root, sample_project)
    assert any("Hz" in line and "8" in line for line in draft.changes)
    assert any(image.name in line for line in draft.changes)
    commit_change(
        root, sample_project, draft, "Changed after pilot feedback", research_visits_by_version
    )
    revised = current_version(root)
    assert revised.reason == "Changed after pilot feedback"
    assert not prepare_change(root, sample_project).changes
    assert len(list_versions(root)) == 2
    with pytest.raises(ValueError, match="changed during review"):
        commit_change(root, sample_project, draft, "stale review", research_visits_by_version)
    branch = historical_draft(root, revised.version_id)
    (root / "logs").mkdir(exist_ok=True)
    (root / "logs/private.txt").write_text("local only")
    set_collection_complete(root, True)
    clone = create_from_version(
        root, tmp_path, "Separate study", branch, source_version_id=revised.version_id
    )
    assert get_study(root).study_id in get_study(clone).created_from
    assert revised.version_id in get_study(clone).created_from
    assert get_study(clone).study_id != get_study(root).study_id
    assert not get_study(clone).collection_complete and not list((clone / "logs").iterdir())
    assert (clone / image.relative_to(root)).read_bytes() == b"replacement image"
    restored = restore_version(
        root,
        historical_draft(root, initial.version_id),
        "Return to original",
        research_visits_by_version,
    )
    assert restored.settings.protocol.base_hz != 8
    assert image.read_bytes() == first_image
    assert (root / "logs/private.txt").read_text() == "local only"
    assert get_study(root).collection_complete
    assert list_versions(root)[0].label == "Original"
    assert len(list_versions(root)) == 3


def test_first_setup_save_captures_final_candidate_once(
    sample_project_root, sample_project, monkeypatch
):
    from fpvs_studio.core import study_versions
    from fpvs_studio.core.task_assets import copy_task_asset

    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    image = next((root / "stimuli").rglob("*.png"))
    scans = []
    original_scan = study_versions._assets

    def count_scans(*args, **kwargs):
        scans.append(args[0])
        return original_scan(*args, **kwargs)

    monkeypatch.setattr(study_versions, "_assets", count_scans)
    target = copy_task_asset(root, "memory", image)
    assert saved_version_count(root) == 0
    sample_project.conditions[0].name = "Edited during setup"
    draft = prepare_setup_change(root, sample_project)
    assert not scans
    commit_setup_change(
        root, sample_project, draft, "", research_visits_by_version, save_version=False
    )
    assert scans == [root]
    (only,) = list_versions(root)
    assert (
        read_version_protocol(root, only.version_id)["conditions"][0]["name"]
        == "Edited during setup"
    )
    assert accepted_stimulus_digests(root)[target] == hashlib.sha256(image.read_bytes()).hexdigest()


def test_skip_save_and_unchanged_save_do_not_read_stimuli(
    sample_project_root, sample_project, monkeypatch
):
    from fpvs_studio.core import study_versions

    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    commit_setup_change(
        root,
        sample_project,
        prepare_setup_change(root, sample_project),
        "",
        research_visits_by_version,
        save_version=False,
    )
    first = current_version(root)
    with monkeypatch.context() as guard:
        guard.setattr(study_versions, "_assets", lambda *_: pytest.fail("unexpected stimulus scan"))
        sample_project.settings.protocol.base_hz = 8
        draft = prepare_setup_change(root, sample_project)
        commit_setup_change(
            root,
            sample_project,
            draft,
            "Changed after collection",
            research_visits_by_version,
            save_version=False,
        )
        working = current_version(root)
        assert working.version_id != first.version_id
        assert working in list_working_revisions(root)
        assert working.reason == "Changed after collection"
        unchanged = prepare_setup_change(root, sample_project)
        assert not unchanged.changes
        commit_setup_change(
            root, sample_project, unchanged, "", research_visits_by_version, save_version=True
        )
        assert current_version(root) == working
        assert list_versions(root) == [first]
        with pytest.raises(ValueError, match="changed during review"):
            commit_setup_change(
                root, sample_project, draft, "", research_visits_by_version, save_version=False
            )

    rollback = historical_draft(root, first.version_id)
    assert rollback.changes
    restored = restore_version(root, rollback, "", research_visits_by_version)
    assert restored.settings.protocol.base_hz != 8
    assert len(list_versions(root)) == 2


@pytest.mark.parametrize("save_version", [True, False])
def test_inline_review_then_final_save_preserves_decision(
    sample_project_root, sample_project, save_version
):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    commit_setup_change(
        root,
        sample_project,
        prepare_setup_change(root, sample_project),
        "",
        research_visits_by_version,
        save_version=True,
    )
    sample_project.settings.protocol.base_hz = 10
    draft = prepare_setup_change(root, sample_project)

    def visits(_root):
        return {"first": {"P001"}}

    with pytest.raises(ProtocolReviewRequired):
        commit_setup_change(
            root, sample_project, draft, "", visits, save_version=False, completed_setup=False
        )
    reason = "Reviewed after an early visit"
    commit_setup_change(
        root, sample_project, draft, reason, visits, save_version=False, completed_setup=False
    )
    assert has_pending_setup_save(root)
    assert saved_version_count(root) == 1
    final = prepare_setup_change(root, sample_project)
    assert not final.changes
    commit_setup_change(root, sample_project, final, "", visits, save_version=save_version)
    assert not has_pending_setup_save(root)
    assert saved_version_count(root) == 1 + save_version
    assert current_version(root).reason == reason


def test_working_setup_before_first_save_creates_no_snapshot(sample_project_root, sample_project):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    assert saved_version_count(root) == 0 and list_versions(root) == []
    assert not (root / ".fpvs-study").exists()
    ensure_working_setup(root)
    initial = current_version(root)
    assert initial is not None and saved_version_count(root) == 0
    assert not (root / ".fpvs-study/objects").exists()
    sample_project.conditions[0].name = "Inline edit"
    draft = prepare_setup_change(root, sample_project)
    commit_setup_change(
        root,
        sample_project,
        draft,
        "Reviewed",
        research_visits_by_version,
        save_version=False,
        completed_setup=False,
    )
    assert not (root / ".fpvs-study/objects").exists()
    assert has_pending_setup_save(root) and saved_version_count(root) == 0
    commit_setup_change(
        root,
        sample_project,
        prepare_setup_change(root, sample_project),
        "",
        research_visits_by_version,
        save_version=False,
    )
    assert saved_version_count(root) == 1
    assert not has_pending_setup_save(root)


def test_first_review_detects_external_changes_since_legacy_inspection(
    sample_project_root,
    sample_project,
):
    from fpvs_studio.preprocessing.inspection import inspect_source_directory
    from fpvs_studio.preprocessing.manifest import (
        create_empty_manifest,
        inspection_summary_to_manifest_set,
        upsert_manifest_set,
        write_stimulus_manifest,
    )

    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    pool = sample_project.stimulus_sets[0]
    inspected = inspect_source_directory(root / pool.source_dir, relative_prefix=pool.source_dir)
    manifest = upsert_manifest_set(
        create_empty_manifest(sample_project.meta.project_id),
        inspection_summary_to_manifest_set(set_id=pool.set_id, summary=inspected),
    )
    write_stimulus_manifest(root, manifest)
    original, missing = inspected.files[:2]
    (root / original.relative_path).write_bytes(b"externally replaced")
    (root / missing.relative_path).unlink()
    draft = prepare_change(root, sample_project)
    assert set(draft.changes) == {
        f"Stimulus replaced: {original.relative_path.removeprefix('stimuli/')}",
        f"Stimulus removed: {missing.relative_path.removeprefix('stimuli/')}",
    }


def test_review_is_read_only_and_restore_does_not_archive_skipped_media(
    sample_project_root, sample_project, tmp_path
):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    first = prepare_setup_change(root, sample_project)
    assert not (root / ".fpvs-study").exists()
    commit_setup_change(
        root, sample_project, first, "", research_visits_by_version, save_version=True
    )
    checkpoint = current_version(root)
    image = next((root / "stimuli").rglob("*.png"))
    before = image.read_bytes()
    changed_bytes = b"unique uncheckpointed working bytes"
    image.write_bytes(changed_bytes)
    sample_project.conditions[0].name = "Working edits"
    draft = prepare_setup_change(root, sample_project, stimuli_changed=True)
    commit_setup_change(
        root, sample_project, draft, "", research_visits_by_version, save_version=False
    )
    skipped_digest = hashlib.sha256(changed_bytes).hexdigest()
    skipped_object = root / ".fpvs-study/objects" / skipped_digest
    assert not skipped_object.exists()
    history = historical_draft(root, checkpoint.version_id)
    branch = create_from_version(
        root, tmp_path, "Copied checkpoint", history, source_version_id=checkpoint.version_id
    )
    assert (branch / image.relative_to(root)).read_bytes() == before
    assert image.read_bytes() == changed_bytes
    restore_version(root, history, "", research_visits_by_version)
    assert image.read_bytes() == before and not skipped_object.exists()


def test_inline_edits_back_to_completed_working_setup_need_no_checkpoint(
    sample_project_root, sample_project
):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")

    def accept(rate, *, final):
        sample_project.settings.protocol.base_hz = rate
        commit_setup_change(
            root,
            sample_project,
            prepare_setup_change(root, sample_project),
            "",
            research_visits_by_version,
            save_version=False,
            completed_setup=final,
        )

    accept(6, final=True)
    accept(7, final=True)
    accept(8, final=False)
    assert has_pending_setup_save(root)
    accept(7, final=False)
    assert not has_pending_setup_save(root)
    accept(6, final=False)
    assert has_pending_setup_save(root)


def test_setup_capture_rejects_second_external_edit_after_launch_review(
    sample_project_root, sample_project
):
    from fpvs_studio.core.run_stimulus_identity import verify_run_stimuli

    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    commit_setup_change(
        root,
        sample_project,
        prepare_setup_change(root, sample_project),
        "",
        research_visits_by_version,
        save_version=True,
    )
    version = current_version(root).version_id
    path = next((root / "stimuli").rglob("*.png"))
    relative = path.relative_to(root).as_posix()
    verify_run_stimuli(root, version, {relative: hashlib.sha256(path.read_bytes()).hexdigest()})
    path.write_bytes(b"change seen at launch")
    with pytest.raises(ValueError):
        verify_run_stimuli(root, version, {relative: hashlib.sha256(path.read_bytes()).hexdigest()})
    draft = prepare_setup_change(root, sample_project)
    assert any(relative in change for change in draft.changes)
    path.write_bytes(b"changed again during review")
    with pytest.raises(ValueError, match="changed after review"):
        commit_setup_change(
            root, sample_project, draft, "", research_visits_by_version, save_version=True
        )
    assert saved_version_count(root) == 1 and current_version(root).version_id == version


def test_fork_changed_draft_keeps_original_bytes(sample_project_root, sample_project, tmp_path):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    prepare_change(root, sample_project)
    original = current_version(root)
    image = next((root / "stimuli").rglob("*.png"))
    before = image.read_bytes()
    image.write_bytes(b"candidate")
    draft = prepare_change(root, sample_project)
    fork = create_from_version(root, tmp_path, "New cohort", draft, restore_source_assets=True)
    assert image.read_bytes() == before
    assert (fork / image.relative_to(root)).read_bytes() == b"candidate"
    assert current_version(root) == original


def test_collecting_checkpoint_discovers_external_changes_for_next_save(
    sample_project_root, sample_project
):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    commit_setup_change(root, sample_project, prepare_setup_change(root, sample_project), "",
                        research_visits_by_version, save_version=True)
    sample_project.conditions[0].name = "New condition name"
    image = next((root / "stimuli").rglob("*.png"))
    image.write_bytes(b"new after collection")
    key = hashlib.sha256(image.read_bytes()).hexdigest()
    draft = prepare_setup_change(root, sample_project)
    assert not any(image.name in change for change in draft.changes)

    def visits(_root):
        return {"first": {"P001"}}

    with pytest.raises(ProtocolReviewRequired, match="Save again"):
        commit_setup_change(root, sample_project, draft, "Reviewed name", visits, save_version=True)
    assert saved_version_count(root) == 1
    assert not (root / ".fpvs-study/objects" / key).exists()
    review = prepare_setup_change(root, sample_project)
    assert dict(review.observed_changes) == {image.relative_to(root).as_posix(): key}
    commit_setup_change(
        root, sample_project, review, "Reviewed name and image", visits, save_version=False
    )
    assert saved_version_count(root) == 1 and not (root / ".fpvs-study/objects" / key).exists()
    assert accepted_stimulus_digests(root)[image.relative_to(root).as_posix()] == key


def test_unreviewed_asset_change_keeps_settings_and_history(sample_project_root, sample_project):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    prepare_change(root, sample_project)
    before = load_project_file(root / "project.json")
    sample_project.conditions[0].name = "Revised"
    draft = prepare_change(root, sample_project)
    next((root / "stimuli").rglob("*.png")).write_bytes(b"changed during review")
    with pytest.raises(ValueError, match="changed after review"):
        commit_change(root, sample_project, draft, "Already reviewed", research_visits_by_version)
    assert load_project_file(root / "project.json") == before
    assert len(list_versions(root)) == 1


def test_cancel_after_external_replacement_preserves_both_files(
    sample_project_root, sample_project
):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    prepare_change(root, sample_project)
    image = next((root / "stimuli").rglob("*.png"))
    original = image.read_bytes()
    image.write_bytes(b"outside edit")
    draft = prepare_change(root, sample_project)
    recovered = keep_saved_stimuli(root, draft)
    assert (recovered / image.relative_to(root / "stimuli")).read_bytes() == b"outside edit"
    assert image.read_bytes() == original
    assert len(list_versions(root)) == 1


def test_study_state_survives_long_project_path(tmp_path, sample_project):
    root = tmp_path / ("first" * 20) / ("second" * 20)
    save_project_file(sample_project, root / "project.json")
    state = get_study(root)
    assert read_study(root) == state


def test_manifest_refresh_is_not_a_protocol_edit(sample_project_root, sample_project):
    from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest

    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    write_stimulus_manifest(root, create_empty_manifest(sample_project.meta.project_id))
    prepare_change(root, sample_project)
    write_stimulus_manifest(root, create_empty_manifest(sample_project.meta.project_id))
    assert not prepare_change(root, sample_project).changes


def test_same_size_image_replacement_with_original_timestamp_is_detected(
    sample_project_root, sample_project
):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    image = next((root / "stimuli").rglob("*.png"))
    image.write_bytes(b"AAAA")
    stamp = image.stat()
    prepare_change(root, sample_project)
    image.write_bytes(b"BBBB")
    os.utime(image, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert any(image.name in line for line in prepare_change(root, sample_project).changes)


def _on_stimulus_read(monkeypatch, image, change, *, repeat=False):
    original_open = Path.open
    changed = False

    def open_file(path, mode="r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        if mode == "rb" and path in (image, filesystem_path(image)):
            read = stream.read

            def read_then_change(*args):
                nonlocal changed
                block = read(*args)
                if block and (repeat or not changed):
                    changed = True
                    change()
                return block

            stream.read = read_then_change
        return stream

    monkeypatch.setattr(Path, "open", open_file)


@pytest.mark.parametrize(
    ("relative", "retime_access_only"),
    [
        ("original-images/base/item.jpg", True),
        ("derived/base/gray/item.png", False),
    ],
)
def test_first_baseline_accepts_timestamp_change_when_stimulus_bytes_match(
    sample_project_root, sample_project, monkeypatch, relative, retime_access_only
):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    image = root / "stimuli" / relative
    image.parent.mkdir(parents=True, exist_ok=True)
    contents = b"same stimulus before and after the timestamp update"
    image.write_bytes(contents)
    stamp = image.stat()
    modified = stamp.st_mtime_ns if retime_access_only else stamp.st_mtime_ns - 60_000_000_000
    retimed = False

    def update_timestamps():
        nonlocal retimed
        os.utime(image, ns=(stamp.st_atime_ns + 60_000_000_000, modified))
        retimed = True

    _on_stimulus_read(monkeypatch, image, update_timestamps)

    draft = prepare_change(root, sample_project)

    assert retimed and image.stat().st_mtime_ns == modified
    assert not draft.changes
    assert len(list_versions(root)) == 1
    digest = hashlib.sha256(contents).hexdigest()
    assert draft.assets[relative] == digest
    assert (root / ".fpvs-study" / "objects" / digest).read_bytes() == contents


def test_constant_metadata_activity_does_not_leave_a_reusable_digest(
    sample_project_root, sample_project, monkeypatch
):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    image = next((root / "stimuli").rglob("*.png"))
    stamp = image.stat()
    reads = 0

    def retime():
        nonlocal reads
        reads += 1
        os.utime(image, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + reads * 60_000_000_000))

    _on_stimulus_read(monkeypatch, image, retime, repeat=True)
    assert not prepare_change(root, sample_project).changes
    before = reads
    assert not prepare_change(root, sample_project).changes
    assert reads > before > 0
    assert len(list_versions(root)) == 1


@pytest.mark.parametrize("stamp_available", [True, False])
def test_first_baseline_rejects_mixed_stimulus_then_retries_cleanly(
    sample_project_root, sample_project, monkeypatch, stamp_available
):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    image = next((root / "stimuli").rglob("*.png"))
    block = 1024 * 1024
    image.write_bytes(b"A" * (2 * block))
    stamp = image.stat()
    replacement = b"B" * (2 * block)

    def replace_contents():
        image.write_bytes(replacement)
        os.utime(image, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))

    if not stamp_available:
        monkeypatch.setattr("fpvs_studio.core.study_versions._asset_stamp", lambda *_: None)
    _on_stimulus_read(monkeypatch, image, replace_contents)
    with pytest.raises(ValueError, match="Stimulus changed during review"):
        prepare_change(root, sample_project)
    assert current_version(root) is None
    objects = root / ".fpvs-study" / "objects"
    assert not (objects / hashlib.sha256(b"A" * block + b"B" * block).hexdigest()).exists()
    assert not list(objects.glob("*.tmp"))

    draft = prepare_change(root, sample_project)
    digest = draft.assets[image.relative_to(root / "stimuli").as_posix()]
    assert (objects / digest).read_bytes() == replacement


def test_data_arriving_after_review_requires_a_reason(sample_project_root, sample_project):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    sample_project.settings.protocol.base_hz = 8
    draft = prepare_change(root, sample_project)
    directory = root / "logs/.participant-results"
    directory.mkdir(parents=True)
    (directory / "partial.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "participant_number": "P001",
                "runs": [{"completed_frames": 3}],
            }
        )
    )
    with pytest.raises(ProtocolReviewRequired):
        commit_change(root, sample_project, draft, "", research_visits_by_version)
    assert len(list_versions(root)) == 1


def test_real_partial_records_activate_protection(sample_project_root):
    root = sample_project_root
    directory = root / "logs/.participant-results"
    directory.mkdir(parents=True)
    for index, (frames, test, pilot) in enumerate(
        [(0, False, False), (10, True, False), (3, False, True), (1, "false", False)]
    ):
        record = {
            "schema_version": 1,
            "participant_number": str(index),
            "session_id": f"s{index}",
            "participant_session_number": 1,
            "protocol_version_id": "first",
            "test_mode": test,
            "pilot_mode": pilot,
            "finalized": False,
            "runs": [{"run_id": "r", "aborted": True, "completed_frames": frames}],
        }
        (directory / f"{index}.json").write_text(json.dumps(record))
    assert research_visits_by_version(root) == {"first": {"3 · 1"}}


def test_legacy_admin_ids_do_not_activate_version_protection(tmp_path):
    directory = tmp_path / "logs/.participant-results"
    directory.mkdir(parents=True)
    (directory / "admin.json").write_text(json.dumps({
        "schema_version": 1, "participant_number": "0", "session_id": "admin",
        "test_mode": False, "protocol_version_id": "first",
        "runs": [{"run_id": "run", "completed_frames": 1}],
    }))
    (directory.parent / "session_condition_history.csv").write_text(
        "participant_number,session_id,completed_frames\n00,second,12\n000,research,1\n"
    )
    assert research_visits_by_version(tmp_path) == {"": {"000 · research"}}
