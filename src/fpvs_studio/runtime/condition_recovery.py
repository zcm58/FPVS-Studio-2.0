"""Project-local interruption checkpoints and read-only, occurrence-specific recovery."""

from __future__ import annotations

import errno
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Literal, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fpvs_studio.core.execution import AcquisitionEvidence
from fpvs_studio.core.paths import resolve_project_relative_path, to_project_relative_posix
from fpvs_studio.core.serialization import write_json_file
from fpvs_studio.core.session_plan import SessionBlock, SessionEntry, SessionPlan

RecoveryStage = Literal[
    "setup",
    "pre_condition",
    "armed",
    "transition",
    "playback",
    "post_condition",
    "feedback",
    "between_conditions",
    "finalizing",
    "completion_unknown",
]
_DIRECTORY = "logs/.condition-recovery"
_CONTENTION = {errno.EACCES, errno.EAGAIN, errno.EDEADLK}
_Model = TypeVar("_Model", bound=BaseModel)
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class InterruptedCondition:
    execution_id: str
    participant_number: str
    participant_session_number: int | None
    session_id: str | None
    run_id: str
    run_ordinal: int
    total_runs: int
    condition_id: str
    condition_name: str
    completed_run_ids: tuple[str, ...]
    not_started_run_ids: tuple[str, ...]
    completed_run_labels: tuple[str, ...]
    not_started_run_labels: tuple[str, ...]
    stage: RecoveryStage
    playback_completed: bool
    status: Literal["interrupted", "unverified"]
    can_rerun: bool
    evidence_path: str
    updated_at: datetime


@dataclass(frozen=True)
class ConditionRecoveryReport:
    records: tuple[InterruptedCondition, ...] = ()
    warnings: tuple[str, ...] = ()


class _Run(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(min_length=1)
    condition_id: str = Field(min_length=1)
    condition_name: str = Field(min_length=1)


class _Checkpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1"] = "1"
    execution_id: str
    project_id: str
    participant_number: str
    participant_session_number: int | None = None
    session_id: str
    state: Literal["running", "completed", "cancelled", "interrupted"] = "running"
    stage: RecoveryStage = "setup"
    current_run_id: str | None = None
    completed_run_ids: list[str] = Field(default_factory=list)
    started_run_ids: list[str] = Field(default_factory=list)
    runs: list[_Run]
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_progress(self) -> _Checkpoint:
        run_ids = [run.run_id for run in self.runs]
        planned = set(run_ids)
        started = set(self.started_run_ids)
        completed = set(self.completed_run_ids)
        if len(planned) != len(run_ids):
            raise ValueError("Recovery run identifiers must be unique.")
        if len(started) != len(self.started_run_ids) or len(completed) != len(
            self.completed_run_ids
        ):
            raise ValueError("Recovery progress identifiers must be unique.")
        if not completed <= started <= planned:
            raise ValueError("Recovery progress must refer to started, planned runs.")
        if self.current_run_id is not None and self.current_run_id not in started:
            raise ValueError("The current recovery run must be a started, planned run.")
        if self.current_run_id is None and started:
            raise ValueError("Started recovery progress requires a current run.")
        return self


def _lock(stream: BinaryIO) -> None:
    if sys.platform == "win32":
        import msvcrt

        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(stream: BinaryIO) -> None:
    if sys.platform == "win32":
        import msvcrt

        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class ConditionRecoveryRecorder:
    """Hold an OS lifetime lock; persist only between presentation operations."""

    def __init__(
        self,
        project_root: Path,
        plan: SessionPlan,
        *,
        participant_number: str,
        participant_session_number: int | None,
    ) -> None:
        self.execution_id = uuid4().hex
        self._path = resolve_project_relative_path(
            project_root,
            f"{_DIRECTORY}/{self.execution_id}.json",
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self._path.with_suffix(".lock").open("x+b")
        self._locked = False
        self.checkpoint = _Checkpoint(
            execution_id=self.execution_id,
            project_id=plan.project_id,
            participant_number=participant_number,
            participant_session_number=participant_session_number,
            session_id=plan.session_id,
            runs=[
                _Run(
                    run_id=entry.run_id,
                    condition_id=entry.condition_id,
                    condition_name=entry.condition_name,
                )
                for entry in plan.ordered_entries()
            ],
        )
        try:
            self._stream.write(b"0")
            self._stream.flush()
            _lock(self._stream)
            self._locked = True
            write_json_file(self._path.with_suffix(".plan.json"), plan)
            self._write()
        except BaseException:
            self.close()
            raise

    def _write(self) -> None:
        self.checkpoint.updated_at = datetime.now(timezone.utc)
        write_json_file(self._path, self.checkpoint)

    def start_run(self, run_id: str, *, playback_armed: bool = False) -> None:
        self.checkpoint.current_run_id = run_id
        if run_id not in self.checkpoint.started_run_ids:
            self.checkpoint.started_run_ids.append(run_id)
        self.stage("armed" if playback_armed else "pre_condition")

    def stage(self, stage: RecoveryStage) -> None:
        self.checkpoint.stage = stage
        self._write()

    def playback_finished(self, run_id: str, *, aborted: bool) -> None:
        if not aborted and run_id not in self.checkpoint.completed_run_ids:
            self.checkpoint.completed_run_ids.append(run_id)
        self.stage("post_condition")

    def finish(self, state: Literal["completed", "cancelled", "interrupted"]) -> None:
        self.checkpoint.state = state
        self._write()
        if state in {"completed", "cancelled"}:
            # Keep the small terminal marker to suppress historical acquisition fallback;
            # only interrupted launches need a duplicate, potentially large compiled plan.
            try:
                self._path.with_suffix(".plan.json").unlink(missing_ok=True)
            except OSError:
                _LOGGER.warning("Could not retire a completed condition recovery plan.")

    def close(self) -> None:
        if not self._stream.closed:
            if self._locked:
                _unlock(self._stream)
                self._locked = False
            self._stream.close()


def _inactive(project_root: Path, path: Path) -> bool:
    """Missing or unreadable lifetime evidence is not proof that an owner exited."""
    lock_path = resolve_project_relative_path(
        project_root,
        to_project_relative_posix(project_root, path.with_suffix(".lock")),
    )
    with lock_path.open("rb") as stream:
        try:
            _lock(stream)
        except OSError as error:
            if error.errno in _CONTENTION:
                return False
            raise
        _unlock(stream)
        return True


def _bounded_read(
    path: Path,
    model: type[_Model],
    *,
    limit: int = 32 * 1024 * 1024,
) -> _Model:
    with path.open("rb") as stream:
        payload = stream.read(limit + 1)
    if len(payload) > limit:
        raise ValueError("Recovery record exceeds its size limit.")
    return model.model_validate_json(payload)


def _labels(runs: list[_Run], ids: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        f"Run {index}: {run.condition_name} ({run.run_id})"
        for index, run in enumerate(runs, 1)
        if run.run_id in ids
    )


def _original_plan(
    project_root: Path, source: _Checkpoint | AcquisitionEvidence
) -> SessionPlan | None:
    path = resolve_project_relative_path(
        project_root, f"{_DIRECTORY}/{source.execution_id}.plan.json"
    )
    candidates = [path] if path.exists() else []
    runs = resolve_project_relative_path(project_root, "runs")
    if not candidates and runs.exists():
        candidates.extend(runs.glob("*/session_plan.json"))
    expected = [(run.run_id, run.condition_id, run.condition_name) for run in source.runs]
    if len({run[0] for run in expected}) != len(expected):
        raise ValueError("Recovery run identifiers must be unique.")
    for candidate in candidates:
        relative = to_project_relative_posix(project_root, candidate)
        checked = resolve_project_relative_path(project_root, relative)
        try:
            plan = _bounded_read(checked, SessionPlan, limit=128 * 1024 * 1024)
        except (OSError, ValueError):
            continue
        entries = plan.ordered_entries()
        if (
            plan.project_id == source.project_id
            and plan.session_id == source.session_id
            and [(entry.run_id, entry.condition_id, entry.condition_name) for entry in entries]
            == expected
            and all(entry.run_spec.project_id == source.project_id for entry in entries)
        ):
            return plan
    return None


def query_condition_recovery(project_root: Path) -> ConditionRecoveryReport:
    """Inspect known project records without creating, rewriting or deleting any file."""
    records: list[InterruptedCondition] = []
    warnings: list[str] = []
    known: set[str] = set()
    directory = resolve_project_relative_path(project_root, _DIRECTORY)
    candidates = sorted(directory.glob("*.json")) if directory.exists() else []
    for candidate in candidates:
        if candidate.name.endswith(".plan.json"):
            continue
        try:
            path = resolve_project_relative_path(project_root, f"{_DIRECTORY}/{candidate.name}")
            checkpoint = _bounded_read(path, _Checkpoint, limit=1024 * 1024)
            if checkpoint.execution_id != candidate.stem:
                raise ValueError("Recovery execution identifier does not match its filename.")
            known.add(checkpoint.execution_id)
            if checkpoint.state in {"completed", "cancelled"} or not _inactive(project_root, path):
                continue
            runs = checkpoint.runs
            if not runs:
                continue
            run = (
                runs[0]
                if checkpoint.current_run_id is None
                else next(run for run in runs if run.run_id == checkpoint.current_run_id)
            )
            completed = tuple(checkpoint.completed_run_ids)
            not_started = tuple(
                item.run_id for item in runs if item.run_id not in checkpoint.started_run_ids
            )
            available = _original_plan(project_root, checkpoint) is not None
            records.append(
                InterruptedCondition(
                    execution_id=checkpoint.execution_id,
                    participant_number=checkpoint.participant_number,
                    participant_session_number=checkpoint.participant_session_number,
                    session_id=checkpoint.session_id,
                    run_id=run.run_id,
                    run_ordinal=runs.index(run) + 1,
                    total_runs=len(runs),
                    condition_id=run.condition_id,
                    condition_name=run.condition_name,
                    completed_run_ids=completed,
                    not_started_run_ids=not_started,
                    completed_run_labels=_labels(runs, completed),
                    not_started_run_labels=_labels(runs, not_started),
                    stage=checkpoint.stage,
                    playback_completed=run.run_id in completed,
                    status="interrupted",
                    can_rerun=available,
                    evidence_path=to_project_relative_posix(project_root, path),
                    updated_at=checkpoint.updated_at,
                )
            )
            if not available:
                warnings.append(
                    f"Original compiled plan unavailable for execution {checkpoint.execution_id}."
                )
        except (OSError, ValueError):
            warnings.append(f"Could not inspect recovery record {candidate.name}.")
            known.add(candidate.stem)

    acquisition = resolve_project_relative_path(project_root, "logs/acquisition")
    for candidate in (
        sorted(acquisition.glob("*.acquisition-v1.json")) if acquisition.exists() else []
    ):
        try:
            path = resolve_project_relative_path(project_root, f"logs/acquisition/{candidate.name}")
            evidence = _bounded_read(path, AcquisitionEvidence)
            if candidate.name != f"{evidence.execution_id}.acquisition-v1.json":
                raise ValueError("Acquisition execution identifier does not match its filename.")
            if evidence.execution_id in known or evidence.state not in {"running", "interrupted"}:
                continue
            if not evidence.runs:
                continue
            active = next(
                (run for run in evidence.runs if run.state in {"started", "interrupted"}), None
            )
            if active is None:
                active = next(
                    (run for run in reversed(evidence.runs) if run.state == "completed"), None
                )
            if active is None:
                continue
            runs = [
                _Run(
                    run_id=run.run_id,
                    condition_id=run.condition_id,
                    condition_name=run.condition_name,
                )
                for run in evidence.runs
            ]
            completed = tuple(run.run_id for run in evidence.runs if run.state == "completed")
            not_started = tuple(run.run_id for run in evidence.runs if run.state == "not_started")
            available = _original_plan(project_root, evidence) is not None
            records.append(
                InterruptedCondition(
                    execution_id=evidence.execution_id,
                    participant_number=evidence.participant_number,
                    participant_session_number=evidence.participant_session_number,
                    session_id=evidence.session_id,
                    run_id=active.run_id,
                    run_ordinal=evidence.runs.index(active) + 1,
                    total_runs=len(runs),
                    condition_id=active.condition_id,
                    condition_name=active.condition_name,
                    completed_run_ids=completed,
                    not_started_run_ids=not_started,
                    completed_run_labels=_labels(runs, completed),
                    not_started_run_labels=_labels(runs, not_started),
                    stage="completion_unknown",
                    playback_completed=active.state == "completed",
                    status="unverified",
                    can_rerun=available,
                    evidence_path=to_project_relative_posix(project_root, path),
                    updated_at=evidence.updated_at_utc,
                )
            )
            if not available:
                warnings.append(
                    f"Original compiled plan unavailable for execution {evidence.execution_id}."
                )
        except (OSError, ValueError):
            warnings.append(f"Could not inspect acquisition record {candidate.name}.")
    records.sort(key=lambda record: record.updated_at.timestamp(), reverse=True)
    return ConditionRecoveryReport(tuple(records), tuple(warnings))


def build_recovery_session_plan(
    project_root: Path,
    record: InterruptedCondition,
    *,
    allow_unverified: bool = False,
) -> SessionPlan:
    """Select exactly one saved occurrence into a new session; never recompile it."""
    current = next(
        (
            item
            for item in query_condition_recovery(project_root).records
            if item.execution_id == record.execution_id and item.run_id == record.run_id
        ),
        None,
    )
    if current is None or not current.can_rerun:
        raise ValueError(
            "The original condition is unavailable or this execution is still running."
        )
    if current != record:
        raise ValueError("The recovery evidence changed; refresh it before rerunning.")
    if current.status == "unverified" and not allow_unverified:
        raise ValueError(
            "Confirm that the original session is no longer running before rerunning it."
        )
    path = resolve_project_relative_path(project_root, current.evidence_path)
    source: _Checkpoint | AcquisitionEvidence
    if current.status == "unverified":
        source = _bounded_read(path, AcquisitionEvidence)
    else:
        source = _bounded_read(path, _Checkpoint, limit=1024 * 1024)
    if (
        source.execution_id != current.execution_id
        or source.session_id != current.session_id
        or source.participant_number != current.participant_number
        or source.participant_session_number != current.participant_session_number
        or len(source.runs) != current.total_runs
        or (
            source.runs[current.run_ordinal - 1].run_id,
            source.runs[current.run_ordinal - 1].condition_id,
            source.runs[current.run_ordinal - 1].condition_name,
        )
        != (current.run_id, current.condition_id, current.condition_name)
    ):
        raise ValueError("The recovery evidence changed; refresh it before rerunning.")
    plan = _original_plan(project_root, source)
    if plan is None:
        raise ValueError("The original compiled session plan is unavailable.")
    selected = next(entry for entry in plan.ordered_entries() if entry.run_id == current.run_id)
    return _single_occurrence_plan(plan, selected)


def build_replacement_session_plan(plan: SessionPlan, condition_id: str) -> SessionPlan:
    """Explicit current-setup replacement; callers must disclose its new schedule/seed."""
    selected = next(
        (entry for entry in plan.ordered_entries() if entry.condition_id == condition_id),
        None,
    )
    if selected is None:
        raise ValueError("The condition is no longer present in the newly compiled project.")
    return _single_occurrence_plan(plan, selected)


def _single_occurrence_plan(plan: SessionPlan, selected: SessionEntry) -> SessionPlan:
    entry = selected.model_copy(
        deep=True,
        update={
            "global_order_index": 0,
            "block_index": 0,
            "index_within_block": 0,
        },
    )
    recovered = plan.model_copy(
        deep=True,
        update={
            "session_id": f"recovery-{uuid4().hex}",
            "block_count": 1,
            "total_runs": 1,
            "blocks": [
                SessionBlock(block_index=0, condition_order=[entry.condition_id], entries=[entry])
            ],
        },
    )
    return SessionPlan.model_validate(recovered.model_dump())
