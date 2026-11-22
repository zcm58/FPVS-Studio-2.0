import csv
import json
from pathlib import Path
from uuid import uuid4

import pytest

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.data_sharing import SharingProfile, SharingSettings, protocol_fingerprint
from fpvs_studio.core.project_config import (
    create_project_from_config,
    read_project_config,
    retain_session_snapshot,
    write_project_config,
)
from fpvs_studio.core.serialization import save_project_file, write_json_file
from fpvs_studio.core.study_lifecycle import get_study, set_collection_complete
from fpvs_studio.data_sharing.storage import save_settings
from fpvs_studio.runtime.study_handoff import (
    build_study_handoff,
    capture_study_run,
    export_study_handoff,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "studio_handoff"


def test_cohort_retains_actual_versions_hardware_and_missing_evidence(tmp_path):
    setup = read_project_config(FIXTURES / "v2-setup.fpvsconfig")
    scaffold = create_project_from_config(tmp_path, setup)
    root = scaffold.project_root
    folder = root / "logs" / "acquisition"
    folder.mkdir()
    version_1, version_2 = str(uuid4()), str(uuid4())
    identity = get_study(root).study_id
    history = [("009", 1, "older"), ("009", 2, "older")]
    for name, pid, number, version in [
        ("biosemi", "007", 1, version_1),
        ("unicorn", "007", 2, version_1),
        ("unicorn-60-02", "008", 1, version_2),
    ]:
        config = read_project_config(FIXTURES / f"v2-completed-{name}.fpvsconfig")
        completed = config.completed_session
        evidence = completed.acquisition_evidence
        completed.participant_number = evidence.participant_number = pid
        completed.participant_session_number = evidence.participant_session_number = number
        key = evidence.execution_id
        plan = compile_session_plan(
            scaffold.project,
            project_root=root,
            refresh_hz=completed.refresh_hz,
            session_id=completed.session_id,
        )
        specs = [item.run_spec for item in plan.ordered_entries()]
        for spec, run in zip(specs, evidence.runs, strict=True):
            spec.run_id = run.run_id
        capture_study_run(
            root,
            evidence,
            specs,
            config,
            {
                "studio_study_id": identity,
                "studio_protocol_version_id": version,
                "studio_protocol_change_reason": "Updated length" if version == version_2 else "",
            },
            ("P9", "P10"),
        )
        write_json_file(folder / f"{key}.acquisition-v1.json", evidence)
        retain_session_snapshot(root, config)
        history.append((pid, number, evidence.session_id))

    records = root / "logs" / ".participant-results"
    records.mkdir()
    for pid, mode in [("009", False), ("010", True)]:
        (records / f"{pid}.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "participant_number": pid,
                    "project_id": setup.project.project_id,
                    "participant_session_number": 1,
                    "execution_id": f"saved-{pid}",
                    "session_id": "older",
                    "session_aborted": True,
                    "test_mode": mode,
                    "participant_metadata": {"age": 27},
                    "responses": ["private answer"],
                }
            ),
            encoding="utf-8",
        )
    with (root / "logs/session_condition_history.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(["participant_number", "participant_session_number", "session_id"])
        writer.writerows(history)
    destination = tmp_path / "cohort.fpvsconfig"
    with pytest.raises(ValueError, match="Mark collection complete"):
        export_study_handoff(root, destination)
    set_collection_complete(root, True)
    export_study_handoff(root, destination)
    first = destination.read_bytes()
    payload = json.loads(first)
    assert payload["study_id"] == identity
    visits = payload["visits"]
    assert len(visits) == 5
    assert [
        v["participant_session_number"] for v in visits if v["participant_number"] == "007"
    ] == [1, 2]
    assert (
        len(
            {
                v["recording"]["selected_backend"]
                for v in visits
                if v["protocol_version_id"] == version_1
            }
        )
        == 2
    )
    (updated,) = [v for v in visits if v["protocol_version_id"] == version_2]
    assert updated["compiled_refresh_hz"] == 60.02
    assert updated["protocol_change_reason"] == "Updated length"
    assert not updated["issues"]
    old_visits = [visit for visit in visits if visit["participant_number"] == "009"]
    assert [
        (visit["participant_session_number"], visit["execution_id"]) for visit in old_visits
    ] == [(2, None), (1, "saved-009")]
    assert all(visit["issues"] and visit["setup_id"] is None for visit in old_visits)
    assert b"private answer" not in first and b"task_assets" not in first
    export_study_handoff(root, destination)
    assert destination.read_bytes() == first
    (records / "009.json").unlink()
    assert build_study_handoff(root)["roster_revision"] != payload["roster_revision"]


def test_older_session_is_readable_and_mismatched_local_evidence_blocks_export(tmp_path):
    config = read_project_config(FIXTURES / "v2-completed-biosemi.fpvsconfig")
    root = create_project_from_config(tmp_path, config).project_root
    folder = root / "logs" / "acquisition"
    folder.mkdir()
    evidence = config.completed_session.acquisition_evidence
    key = evidence.execution_id
    write_project_config(folder / f"{key}-completed.fpvsconfig", config)
    (visit,) = build_study_handoff(root)["visits"]
    assert visit["protocol_version_id"] is None and visit["setup_id"]
    assert visit["issues"] == ["missing_as_run_protocol"]
    assert visit["manual_removed_electrodes"] == ["P9", "P10"]
    evidence.participant_number = "unrelated"
    write_json_file(folder / f"{key}.acquisition-v1.json", evidence)
    with pytest.raises(ValueError, match="conflicts"):
        build_study_handoff(root)


def test_website_destination_requires_verified_as_run_and_current_scope(tmp_path):
    config = read_project_config(FIXTURES / "v2-completed-biosemi.fpvsconfig")
    scaffold = create_project_from_config(tmp_path, config)
    root = scaffold.project_root
    fingerprint = protocol_fingerprint(scaffold.project, root)
    site = {
        "project_id": str(uuid4()),
        "experiment_id": "fixture-experiment",
        "experiment_version": "1.0",
        "protocol_sha256": fingerprint,
    }
    profile = SharingProfile(**site, title="Linked experiment", device_id="private-device")
    save_settings(root, SharingSettings(enabled=True, profile=profile))
    config.toolbox.study_id = profile.project_id
    config.toolbox.experiment_id = profile.experiment_id
    config.toolbox.experiment_version = profile.experiment_version
    config.toolbox.protocol_sha256 = fingerprint
    evidence = config.completed_session.acquisition_evidence
    folder = root / "logs/acquisition"
    folder.mkdir(exist_ok=True)
    write_json_file(folder / f"{evidence.execution_id}.acquisition-v1.json", evidence)
    retain_session_snapshot(root, config)
    assert build_study_handoff(root)["website_study"] == site
    assert "private-device" not in json.dumps(build_study_handoff(root))
    scaffold.project.settings.protocol.base_hz = 5
    save_project_file(scaffold.project, root / "project.json")
    assert "website_study" not in build_study_handoff(root)
