"""Authorized output cleanup requires byte archives, research parity and safe rollback."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from openpyxl import load_workbook

from fpvs_studio.core.task_models import TaskResponseRecord
from fpvs_studio.runtime import session_export

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/consolidate_existing_results.py"
SPEC = importlib.util.spec_from_file_location("studio_results_consolidation", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
consolidation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = consolidation
SPEC.loader.exec_module(consolidation)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "project.json").write_text("{}", encoding="utf-8")
    output = root / "runs/P009_session01"
    output.mkdir(parents=True)
    history = {column: "" for column in session_export.SESSION_CONDITION_HISTORY_HEADER}
    history.update(project_id="project", participant_number="009", participant_age="30",
                   participant_sex="Female", participant_handedness="Right handed",
                   participant_colorblind="No", participant_session_number="1",
                   session_id="session", output_dir="runs/P009_session01",
                   condition_id="condition", condition_name="Condition", run_id="run",
                   run_seed="17", session_seed="31", session_aborted="False",
                   run_aborted="False", global_order_index="0", total_targets="1",
                   hit_count="1", miss_count="0", false_alarm_count="0",
                   accuracy_percent="100", mean_rt_ms="300")
    (root / "logs").mkdir()
    with (root / "logs/session_condition_history.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, session_export.SESSION_CONDITION_HISTORY_HEADER)
        writer.writeheader()
        writer.writerow(history)
    response = TaskResponseRecord(
        response_index=0, task_id="survey", step_id="questions", phase="pre_condition",
        condition_id="condition", run_id="run", block_index=0, global_order_index=0,
        repetition_index=0, question_id="q1", response_kind="option_selection",
        selected_option_ids=["yes"], reaction_time_s=0.35,
    )
    session_export._write_csv(output / "task_responses.csv",
                              ["session_run_id", *session_export.TASK_RESPONSES_HEADER],
                              [("run", *session_export._task_response_row(response))])
    definition = {"run_id": "run", "condition_id": "condition", "condition_name": "Condition",
                  "pre_tasks": [{"task_id": "survey", "name": "Original survey", "steps": [{
                      "step_id": "questions", "questions": [{"question_id": "q1",
                          "prompt": "Original question?", "options": [
                              {"option_id": "yes", "label": "Original answer"}]}]}]}]}
    (output / "session_plan.json").write_text(json.dumps({"blocks": [{"entries": [definition]}]}),
                                              encoding="utf-8")
    (output / "session_summary.json").write_text(json.dumps({
        "project_id": "project", "participant_number": "009", "participant_session_number": 1,
        "session_id": "session", "aborted": False,
        "participant_metadata": {"age": 30, "sex": "Female", "handedness": "Right handed",
                                 "colorblind": False},
        "run_results": [{"run_id": "run", "condition_id": "condition",
                         "condition_name": "Condition", "aborted": False}],
    }), encoding="utf-8")
    (output / "events.csv").write_text("frame,event\n1,base\n", encoding="utf-8")
    (output / "raw.eeg").write_bytes(b"protected EEG bytes")
    (root / "logs/task_responses.csv").write_text(
        ",".join(session_export.COMPACT_TASK_RESPONSES_HEADER) + "\n", encoding="utf-8",
    )
    (root / "custom.xlsx").write_bytes(b"unrecognized user workbook")
    consolidation._build_workbook(root, root / "logs/participant_summary.xlsx")
    rows = session_export._participant_summary_rows(root, [history])
    session_export._write_csv(root / "logs/participant_summary.csv",
                              session_export.PARTICIPANT_SUMMARY_HEADER, rows)
    return root


def _tree_bytes(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def test_default_is_read_only_and_root_discovery_stays_direct(project):
    nested = project / "unrelated/nested"
    nested.mkdir(parents=True)
    (nested / "project.json").write_text("{}", encoding="utf-8")
    before = _tree_bytes(project)
    result, = consolidation.consolidate_root(project.parent)
    assert not result.applied
    assert result.retired_csvs == 3
    assert _tree_bytes(project) == before


def test_cleanup_preserves_research_and_archives_exact_originals(project):
    original = _tree_bytes(project)
    backup = project / "backups/old/logs/participant_summary.xlsx"
    backup.parent.mkdir(parents=True)
    backup.write_bytes(original["logs/participant_summary.xlsx"])
    # Backups must be plain historical summary sheets for automatic coverage proof.
    workbook = load_workbook(backup)
    for sheet in list(workbook):
        if sheet.title != "Participant Summary":
            workbook.remove(sheet)
    workbook.save(backup)
    workbook.close()
    backup_bytes = backup.read_bytes()
    old_parity = consolidation._workbook_parity(project / "logs/participant_summary.xlsx")
    result = consolidation.consolidate_project(project, apply=True)
    assert result.applied
    assert result.retired_csvs == 3
    assert result.retired_workbooks == 1
    assert not backup.exists()
    assert not (project / "logs/participant_summary.csv").exists()
    assert not (project / "runs/P009_session01/events.csv").exists()
    assert not (project / "runs/P009_session01/task_responses.csv").exists()
    assert (project / "logs/session_condition_history.csv").read_bytes() == original[
        "logs/session_condition_history.csv"]
    assert (project / "logs/task_responses.csv").read_bytes() == original["logs/task_responses.csv"]
    assert (project / "runs/P009_session01/raw.eeg").read_bytes() == b"protected EEG bytes"
    assert (project / "custom.xlsx").read_bytes() == b"unrecognized user workbook"
    with ZipFile(result.archive) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        for source in manifest["sources"]:
            data = archive.read(source["path"])
            assert len(data) == source["size"]
            assert hashlib.sha256(data).hexdigest() == source["sha256"]
        assert archive.read("logs/participant_summary.xlsx") == original[
            "logs/participant_summary.xlsx"]
        assert archive.read("backups/old/logs/participant_summary.xlsx") == backup_bytes
        assert manifest["workbook_sheets"] == old_parity
    consolidation._build_workbook(project, project / "logs/rebuilt.xlsx")
    assert consolidation._workbook_parity(project / "logs/rebuilt.xlsx") == old_parity
    workbook = load_workbook(project / "logs/rebuilt.xlsx", read_only=True)
    try:
        rows = list(workbook["Task Answers"].values)
        answer = dict(zip(rows[0], rows[1], strict=True))
        assert (answer["Question"], answer["Answer"], answer["PID"]) == (
            "Original question?", "Original answer", "009",
        )
    finally:
        workbook.close()


def test_source_change_before_commit_preserves_changed_file_and_original_workbook(
    project, monkeypatch,
):
    old = (project / "logs/participant_summary.xlsx").read_bytes()
    archive = consolidation._archive
    events = project / "runs/P009_session01/events.csv"

    def archive_then_change(*args, **kwargs):
        archive(*args, **kwargs)
        events.write_text("new external edit\n", encoding="utf-8")

    monkeypatch.setattr(consolidation, "_archive", archive_then_change)
    with pytest.raises(ValueError, match="changed"):
        consolidation.consolidate_project(project, apply=True)
    assert events.read_text(encoding="utf-8") == "new external edit\n"
    assert (project / "logs/participant_summary.xlsx").read_bytes() == old
    assert (project / "logs/participant_summary.csv").exists()


def test_cleanup_failure_restores_removed_sources_and_original_workbook(project, monkeypatch):
    before = _tree_bytes(project)
    unlink = Path.unlink
    target = project / "runs/P009_session01/events.csv"

    def fail_one_unlink(path, *args, **kwargs):
        if path == target:
            raise PermissionError("Synthetic cleanup lock")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_one_unlink)
    with pytest.raises(PermissionError, match="Synthetic"):
        consolidation.consolidate_project(project, apply=True)
    for relative, data in before.items():
        assert (project / relative).read_bytes() == data


def test_custom_active_workbook_is_preserved(project):
    path = project / "logs/participant_summary.xlsx"
    workbook = load_workbook(path)
    workbook.create_sheet("Researcher notes")["A1"] = "Custom content"
    workbook.save(path)
    workbook.close()
    before = _tree_bytes(project)
    with pytest.raises(ValueError, match="Custom workbook"):
        consolidation.consolidate_project(project, apply=True)
    for relative, data in before.items():
        assert (project / relative).read_bytes() == data


def test_unmatched_backup_and_unknown_run_table_are_not_cleanup_candidates(project):
    backup = project / "logs/backup-custom/participant_summary.xlsx"
    backup.parent.mkdir()
    workbook = load_workbook(project / "logs/participant_summary.xlsx")
    for sheet in list(workbook):
        if sheet.title != "Participant Summary":
            workbook.remove(sheet)
    workbook["Participant Summary"]["A2"] = "999"
    workbook.save(backup)
    workbook.close()
    unknown = project / "runs/P009_session01/custom-analysis.csv"
    unknown.write_text("custom,value\nx,1\n", encoding="utf-8")
    before = backup.read_bytes(), unknown.read_bytes()
    inventory = consolidation.inventory_project(project)
    assert inventory.preserved_other_csvs == 1
    assert "logs/backup-custom/participant_summary.xlsx" not in {
        source.path for source in inventory.sources
    }
    consolidation.consolidate_project(project, apply=True)
    assert (backup.read_bytes(), unknown.read_bytes()) == before


def test_archive_verification_failure_never_replaces_or_removes_outputs(project, monkeypatch):
    before = _tree_bytes(project)

    def reject(*_args, **_kwargs):
        raise ValueError("Synthetic archive verification failure")

    monkeypatch.setattr(consolidation, "_verify_archive", reject)
    with pytest.raises(ValueError, match="Synthetic archive"):
        consolidation.consolidate_project(project, apply=True)
    for relative, data in before.items():
        assert (project / relative).read_bytes() == data
    assert not list((project / "logs/.output-archives").glob("*.zip"))


def test_repeat_apply_leaves_current_workbook_and_archive_unchanged(project):
    consolidation.consolidate_project(project, apply=True)
    before = _tree_bytes(project)
    result = consolidation.consolidate_project(project, apply=True)
    assert not result.applied
    assert result.archived_files == result.retired_csvs == result.archived_bytes == 0
    assert result.archive is None
    assert _tree_bytes(project) == before
