"""One local Toolbox handoff built from the recorded evidence for the study."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

from fpvs_studio import __version__
from fpvs_studio.core.execution import AcquisitionEvidence
from fpvs_studio.core.paths import project_json_path, resolve_project_relative_path
from fpvs_studio.core.project_config import ProjectConfigFile, read_retained_session_config
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.serialization import atomic_text_write, load_project_file, read_json_file
from fpvs_studio.runtime.participant_history import _iter_session_history_summaries
from fpvs_studio.runtime.reporting_lock import project_reporting_lock


def _digest(value: object) -> str:
    data = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _setup(config: ProjectConfigFile) -> dict[str, Any]:
    """Retain the scientific setup consumed by Toolbox, omitting assets and free text."""
    return config.model_dump(
        mode="json",
        exclude_none=True,
        include={
            "format": True,
            "format_version": True,
            "experiment_category": True,
            "project": {"project_id", "name"},
            "producer": {"application", "version"},
            "protocol": True,
            "condition_defaults": True,
            "conditions": {
                "__all__": {
                    "condition_id",
                    "name",
                    "trigger_code",
                    "base_hz",
                    "sequence_count",
                    "oddball_cycle_repeats_per_sequence",
                    "stream_duration_seconds",
                    "presentation_count",
                    "duty_cycle_mode",
                    "attentional_blink",
                    "masking_catch",
                }
            },
            "condition_modifiers": {"__all__": {"masking"}},
            "triggers": {"oddball_trigger_code"},
            "toolbox": {
                "event_map",
                "oddball_trigger_code",
                "experiment_id",
                "experiment_version",
                "protocol_sha256",
                "study_id",
            },
        },
    ) | {"kind": "setup"}


def capture_study_run(
    root: Path,
    evidence: AcquisitionEvidence,
    specs: Sequence[RunSpec],
    config: ProjectConfigFile | None,
    options: Mapping[str, object],
    removed_electrodes: tuple[str, ...] | None,
) -> None:
    """Freeze the effective settings before presentation, including incomplete visits."""
    if not evidence.session_id or evidence.recording.effective_backend == "null":
        return
    from fpvs_studio.core.study_lifecycle import get_study

    study_id = get_study(root).study_id if project_json_path(root).is_file() else None
    if options.get("studio_study_id") not in (None, study_id):
        raise ValueError("Launch study identity does not match the active Studio project.")
    version = options.get("studio_protocol_version_id")
    payload = {
        "format_version": 1,
        "study_id": study_id,
        "execution_id": evidence.execution_id,
        "project_id": evidence.project_id,
        "participant_number": evidence.participant_number,
        "session_id": evidence.session_id,
        "participant_session_number": evidence.participant_session_number,
        "protocol_version_id": str(UUID(str(version))) if version else None,
        "protocol_change_reason": options.get("studio_protocol_change_reason"),
        "manual_removed_electrodes": removed_electrodes,
        "setup": _setup(config) if config else None,
        "display": config.display.model_dump(mode="json") if config else None,
        "compiled_runs": [
            {
                "run_id": spec.run_id,
                "condition_id": spec.condition.condition_id,
                "display": spec.display.model_dump(mode="json"),
                "random_seed": spec.random_seed,
                "randomization": spec.randomization.model_dump(mode="json")
                if spec.randomization
                else None,
                "planned_markers": [[e.frame_index, e.code, e.label] for e in spec.trigger_events],
            }
            for spec in specs
        ],
    }
    path = resolve_project_relative_path(
        root,
        f"logs/acquisition/{evidence.execution_id}.study-run-v1.json",
    )
    if path.exists():
        raise ValueError(f"Study execution settings already exist for {evidence.execution_id}.")
    atomic_text_write(path, json.dumps(payload, allow_nan=False, ensure_ascii=False))


def _local_files(root: Path, directory: str, pattern: str) -> list[Path]:
    folder = resolve_project_relative_path(root, directory)
    return [
        resolve_project_relative_path(root, f"{directory}/{p.name}")
        for p in sorted(folder.glob(pattern))
    ]


def _visit_from_acquisition(evidence: AcquisitionEvidence) -> dict[str, Any]:
    recording = evidence.recording.model_dump(mode="json", exclude={"recording_association"})
    return {
        "visit_id": evidence.execution_id,
        "execution_id": evidence.execution_id,
        "session_id": evidence.session_id,
        "participant_number": evidence.participant_number,
        "participant_session_number": evidence.participant_session_number,
        "state": evidence.state,
        "recording": recording,
        "protocol_version_id": None,
        "protocol_change_reason": None,
        "setup_id": None,
        "display": None,
        "compiled_refresh_hz": None,
        "manual_removed_electrodes": None,
        "issues": [],
        "runs": [
            {
                "run_id": run.run_id,
                "condition_id": run.condition_id,
                "condition_name": run.condition_name,
                "state": run.state,
                "code_map": [entry.model_dump(mode="json") for entry in run.code_map],
                "planned_event_count": run.planned_event_count,
                "completed_frames": run.completed_frames,
                "sent_events": sum(event.status == "sent" for event in run.attempted_events),
                "error_events": sum(event.status == "error" for event in run.attempted_events),
                "attempted_markers": [
                    [e.trigger_index, e.frame_index, e.code, e.label, e.time_s, e.status]
                    for e in run.attempted_events
                ],
            }
            for run in evidence.runs
        ],
    }


def _identity(record: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(
        record.get(key)
        for key in ("participant_number", "participant_session_number", "session_id")
    )


def _add_history(
    visits: dict[str, dict[str, Any]],
    record: Mapping[str, Any],
    source_key: str,
) -> None:
    pid, number, session = _identity(record)
    if not pid or pid in {"0", "00"} or record.get("test_mode") or record.get("pilot_mode"):
        return
    execution_id = record.get("execution_id")
    key = execution_id or "historical-" + _digest(
        [pid, number, session, None if number else source_key]
    )
    if execution_id and key in visits:
        if _identity(visits[key]) != _identity(record):
            raise ValueError(f"Participant results disagree with execution {key}.")
        version = record.get("protocol_version_id")
        if version and visits[key]["protocol_version_id"] not in (None, version):
            raise ValueError(f"Participant and acquisition protocol versions disagree for {key}.")
        if version:
            visits[key]["protocol_version_id"] = str(UUID(version))
            if visits[key]["setup_id"] and "missing_as_run_protocol" in visits[key]["issues"]:
                visits[key]["issues"].remove("missing_as_run_protocol")
        return
    if (
        not execution_id
        and number
        and any(_identity(v) == _identity(record) for v in visits.values())
    ):
        return
    visits[key] = {
        "visit_id": key,
        "execution_id": execution_id,
        "participant_number": pid,
        "participant_session_number": number,
        "session_id": session,
        "state": "aborted" if record.get("session_aborted") else "historical",
        "recording": None,
        "protocol_version_id": record.get("protocol_version_id"),
        "protocol_change_reason": None,
        "setup_id": None,
        "display": None,
        "compiled_refresh_hz": None,
        "runs": [],
        "manual_removed_electrodes": (record.get("participant_metadata") or {}).get(
            "manual_removed_electrodes"
        ),
        "issues": ["missing_acquisition_evidence", "missing_as_run_protocol"],
    }


def build_study_handoff(project_root: Path) -> dict[str, Any]:
    """Read the roster and its reproducible fingerprint without exporting a file."""
    from fpvs_studio.core.study_lifecycle import get_study
    from fpvs_studio.data_sharing.library_scope import verified_handoff_scope

    root = Path(project_root)
    study = get_study(root)
    project = load_project_file(project_json_path(root))
    project_id = project.meta.project_id
    visits: dict[str, dict[str, Any]] = {}
    setups: dict[str, dict[str, Any]] = {}
    tests_and_pilots: set[tuple[Any, ...]] = set()
    directory = "logs/acquisition"
    with project_reporting_lock(root):
        configs = {
            path.name.removesuffix("-completed.fpvsconfig"): path
            for path in _local_files(root, directory, "*-completed.fpvsconfig")
        }
        for path in _local_files(root, directory, "*.study-session-v1.json"):
            key = path.name.removesuffix(".study-session-v1.json")
            if key in configs:
                raise ValueError(f"Conflicting completed session receipts for {key}.")
            configs[key] = path
        acquisitions = {
            path.name.removesuffix(".acquisition-v1.json"): path
            for path in _local_files(root, directory, "*.acquisition-v1.json")
        }
        snapshots = {
            path.name.removesuffix(".study-run-v1.json"): path
            for path in _local_files(root, directory, "*.study-run-v1.json")
        }
        for key in sorted(configs.keys() | acquisitions.keys() | snapshots.keys()):
            config = (
                read_retained_session_config(configs[key], project_id) if key in configs else None
            )
            completed = config.completed_session if config else None
            archived = completed.acquisition_evidence if completed else None
            evidence = (
                read_json_file(acquisitions[key], AcquisitionEvidence)
                if key in acquisitions
                else archived
            )
            if (
                evidence is None
                or evidence.project_id != project_id
                or evidence.execution_id != key
            ):
                raise ValueError(
                    f"Study evidence for {key} has a missing or conflicting execution identity."
                )
            if archived is not None and archived != evidence:
                raise ValueError(
                    f"Completed handoff conflicts with retained acquisition evidence for {key}."
                )
            if evidence.recording.effective_backend == "null" or evidence.participant_number in {
                "0",
                "00",
            }:
                tests_and_pilots.add(
                    (
                        evidence.participant_number,
                        evidence.participant_session_number,
                        evidence.session_id,
                    )
                )
                continue
            if evidence.session_id is None:
                continue  # A single-condition diagnostic has no research visit.
            visit = _visit_from_acquisition(evidence)
            setup = _setup(config) if config else None
            if config and completed:
                visit.update(
                    display=config.display.model_dump(mode="json"),
                    compiled_refresh_hz=completed.refresh_hz,
                    manual_removed_electrodes=completed.manual_removed_electrodes,
                    session_randomization=completed.model_dump(
                        mode="json",
                        include={
                            "session_seed",
                            "randomization_mode",
                            "randomization_modes",
                            "randomization_seeds",
                            "randomization_algorithm_version",
                            "ordering_policy",
                            "block_orders",
                        },
                    ),
                )
                for run, entry in zip(visit["runs"], completed.ordered_runs, strict=True):
                    run.update(
                        random_seed=entry.random_seed,
                        randomization=entry.randomization.model_dump(mode="json")
                        if entry.randomization
                        else None,
                        planned_markers=[
                            [e.frame_index, e.code, e.label] for e in entry.trigger_events
                        ],
                    )
            if key in snapshots:
                snapshot = json.loads(snapshots[key].read_text(encoding="utf-8"))
                if (
                    snapshot["format_version"] != 1
                    or snapshot["project_id"] != project_id
                    or snapshot["execution_id"] != key
                    or _identity(snapshot) != _identity(visit)
                    or snapshot.get("study_id") not in (None, study.study_id)
                    or (setup is not None and setup != snapshot["setup"])
                ):
                    raise ValueError(f"As-run settings conflict with the retained visit {key}.")
                setup = snapshot["setup"]
                compiled = snapshot["compiled_runs"]
                if [(r["run_id"], r["condition_id"]) for r in compiled] != [
                    (r["run_id"], r["condition_id"]) for r in visit["runs"]
                ]:
                    raise ValueError(f"As-run condition order conflicts with execution {key}.")
                for run, entry in zip(visit["runs"], compiled, strict=True):
                    run.update(
                        {
                            field: entry[field]
                            for field in (
                                "display",
                                "random_seed",
                                "randomization",
                                "planned_markers",
                            )
                        }
                    )
                refresh = {r["display"]["refresh_hz"] for r in compiled}
                visit.update(
                    {
                        field: snapshot[field]
                        for field in (
                            "protocol_version_id",
                            "protocol_change_reason",
                            "display",
                            "manual_removed_electrodes",
                        )
                    }
                )
                if len(refresh) == 1:
                    visit["compiled_refresh_hz"] = refresh.pop()
            if setup is not None:
                visit["setup_id"] = _digest(setup)
                setups[visit["setup_id"]] = setup
            if evidence.state != "completed" or evidence.export_error or not completed:
                visit["issues"].append("incomplete_or_unverified_completion")
            if not setup or not visit["protocol_version_id"]:
                visit["issues"].append("missing_as_run_protocol")
            visits[key] = visit
        for path in _local_files(root, "logs/.participant-results", "*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("schema_version") != 1 or record.get("project_id") != project_id:
                raise ValueError(f"Invalid participant results identity or version in {path.name}.")
            if record.get("test_mode") or record.get("pilot_mode"):
                tests_and_pilots.add(_identity(record))
            elif _identity(record) not in tests_and_pilots:
                _add_history(visits, record, path.name)
        for label, summary in _iter_session_history_summaries(root, strict=True):
            if summary.project_id and summary.project_id != project_id:
                raise ValueError("Participant session history belongs to a different project.")
            metadata = summary.runtime_metadata
            if metadata and (metadata.test_mode or metadata.pilot_mode):
                tests_and_pilots.add(
                    (
                        summary.participant_number,
                        summary.participant_session_number,
                        summary.session_id,
                    )
                )
            if (
                summary.participant_number,
                summary.participant_session_number,
                summary.session_id,
            ) in tests_and_pilots:
                continue
            _add_history(
                visits,
                {
                    "participant_number": summary.participant_number,
                    "session_id": summary.session_id,
                    "participant_session_number": summary.participant_session_number,
                    "session_aborted": summary.aborted,
                    "test_mode": metadata and metadata.test_mode,
                    "pilot_mode": metadata and metadata.pilot_mode,
                },
                label + str(summary.started_at),
            )
    roster = [
        visits[key] for key in sorted(visits) if _identity(visits[key]) not in tests_and_pilots
    ]
    used_setups = {visit["setup_id"] for visit in roster}
    setups = {key: value for key, value in setups.items() if key in used_setups}
    captured_scopes = [setups.get(visit["setup_id"], {}).get("toolbox") for visit in roster]
    website = verified_handoff_scope(root, project, captured_scopes)
    return {
        **({"website_study": website} if website else {}),
        "format": "fpvs-study-handoff",
        "format_version": 1,
        "study_id": study.study_id,
        "project_id": project_id,
        "project_title": project.meta.name,
        "producer": {"application": "FPVS Studio", "version": __version__},
        "collection_complete": study.collection_complete,
        "setups": setups,
        "visits": roster,
        "roster_revision": _digest(roster),
    }


def export_study_handoff(project_root: Path, destination: Path) -> Path:
    """Write an atomic, portable cohort document when the operator requests it."""
    from fpvs_studio.core.study_lifecycle import study_transaction

    handoff = build_study_handoff(project_root)
    if not handoff["collection_complete"]:
        raise ValueError("Mark collection complete before exporting the whole study.")
    if not handoff["visits"]:
        raise ValueError("There are no retained research visits to export.")
    destination = Path(destination)
    if destination.suffix.lower() != ".fpvsconfig":
        raise ValueError("Choose a .fpvsconfig file for the completed study.")
    with study_transaction(project_root) as db:
        if not db.execute("SELECT collection_complete FROM study").fetchone()[0]:
            raise ValueError("Collection reopened during export. Review the updated study.")
        db.execute(
            "CREATE TABLE IF NOT EXISTS roster_exports("
            "sequence INTEGER PRIMARY KEY, revision TEXT NOT NULL)"
        )
        previous = db.execute(
            "SELECT sequence, revision FROM roster_exports ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        if previous and previous["revision"] == handoff["roster_revision"]:
            handoff["roster_sequence"] = previous["sequence"]
        else:
            handoff["roster_sequence"] = db.execute(
                "INSERT INTO roster_exports(revision) VALUES(?)",
                (handoff["roster_revision"],),
            ).lastrowid
        atomic_text_write(
            destination, json.dumps(handoff, ensure_ascii=False, indent=2, allow_nan=False)
        )
    return destination
