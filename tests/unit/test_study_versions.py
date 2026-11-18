"""Local authoring history and participant-data protection, using synthetic files."""

import json

import pytest

from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.study_lifecycle import get_study, read_study, set_collection_complete
from fpvs_studio.core.study_versions import (
    commit_change,
    create_from_version,
    current_version,
    historical_draft,
    keep_saved_stimuli,
    list_versions,
    name_version,
    prepare_change,
    restore_version,
)
from fpvs_studio.runtime.participant_results import research_visits_by_version


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
    commit_change(root, sample_project, draft, "Changed after pilot feedback")
    revised = current_version(root)
    assert revised.reason == "Changed after pilot feedback"
    assert not prepare_change(root, sample_project).changes
    assert len(list_versions(root)) == 2
    with pytest.raises(ValueError, match="changed during review"):
        commit_change(root, sample_project, draft, "stale review")
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
        root, historical_draft(root, initial.version_id), "Return to original"
    )
    assert restored.settings.protocol.base_hz != 8
    assert image.read_bytes() == first_image
    assert (root / "logs/private.txt").read_text() == "local only"
    assert get_study(root).collection_complete
    assert list_versions(root)[0].label == "Original"
    assert len(list_versions(root)) == 3


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


def test_unreviewed_asset_change_keeps_settings_and_history(sample_project_root, sample_project):
    root = sample_project_root
    save_project_file(sample_project, root / "project.json")
    prepare_change(root, sample_project)
    before = load_project_file(root / "project.json")
    sample_project.conditions[0].name = "Revised"
    draft = prepare_change(root, sample_project)
    next((root / "stimuli").rglob("*.png")).write_bytes(b"changed during review")
    with pytest.raises(ValueError, match="changed after review"):
        commit_change(root, sample_project, draft, "Already reviewed")
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
