"""Durable, project-contained Unicorn evidence outside the presentation frame loop."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fpvs_studio import __version__
from fpvs_studio.core.execution import (
    AcquisitionCodeMapEntry,
    AcquisitionEvidence,
    AcquisitionRunEvidence,
    RunExecutionSummary,
    TriggerRecord,
)
from fpvs_studio.core.paths import resolve_project_relative_path
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.serialization import write_json_file
from fpvs_studio.runtime.recording import recording_snapshot


class AcquisitionEvidenceRecorder:
    """Persist snapshots at safe run boundaries; never write during marker callbacks."""

    def __init__(
        self, project_root: Path, run_specs: Sequence[RunSpec], *,
        project_id: str,
        runtime_options: Mapping[str, object] | None,
        participant_number: str, participant_session_number: int | None = None,
        session_id: str | None = None,
    ) -> None:
        self.path: Path | None = None
        self.evidence: AcquisitionEvidence | None = None
        self._active_run_id: str | None = None
        self._trigger_start_index = 0
        if (runtime_options or {}).get("recording_backend") != "unicorn_udp":
            return
        now = datetime.now(timezone.utc)
        execution_id = uuid4().hex
        self.path = resolve_project_relative_path(
            project_root, f"logs/acquisition/{execution_id}.acquisition-v1.json",
        )
        self.evidence = AcquisitionEvidence(
            studio_version=__version__, execution_id=execution_id,
            project_id=project_id,
            participant_number=participant_number,
            participant_session_number=participant_session_number,
            session_id=session_id, recording=recording_snapshot(runtime_options),
            created_at_utc=now, updated_at_utc=now,
            runs=[
                AcquisitionRunEvidence(
                    run_id=spec.run_id, condition_id=spec.condition.condition_id,
                    condition_name=spec.condition.name,
                    planned_event_count=len(spec.trigger_events),
                    code_map=[
                        AcquisitionCodeMapEntry(code=code, label=label)
                        for code, label in dict.fromkeys(
                            (event.code, event.label) for event in spec.trigger_events
                        )
                    ],
                ) for spec in run_specs
            ],
        )
        self._write()

    def _write(self) -> None:
        if self.evidence is not None and self.path is not None:
            self.evidence.updated_at_utc = datetime.now(timezone.utc)
            write_json_file(self.path, self.evidence)

    def start_run(self, run_id: str, trigger_start_index: int) -> None:
        if self.evidence is None:
            return
        self._active_run_id = run_id
        self._trigger_start_index = trigger_start_index
        self.evidence.state = "running"
        self._run(run_id).state = "started"
        self._write()

    def _run(self, run_id: str) -> AcquisitionRunEvidence:
        assert self.evidence is not None
        return next(run for run in self.evidence.runs if run.run_id == run_id)

    def record_run(self, summary: RunExecutionSummary) -> None:
        if self.evidence is None:
            return
        run = self._run(summary.run_id)
        run.attempted_events = _actual_attempts(summary.trigger_log)
        run.state = "aborted" if summary.aborted else "completed"
        run.completed_frames = summary.completed_frames
        run.abort_reason = summary.abort_reason
        self._write()

    def finish(
        self, *, abort_reason: str | None = None, interrupted: bool = False,
        records: Sequence[TriggerRecord] = (), export_error: str | None = None,
    ) -> None:
        if self.evidence is None:
            return
        self.evidence.state = "interrupted" if interrupted else (
            "aborted" if abort_reason is not None else "completed"
        )
        self.evidence.abort_reason = abort_reason
        self.evidence.export_error = export_error
        if self._active_run_id is not None:
            run = self._run(self._active_run_id)
            run.attempted_events = _actual_attempts(records[self._trigger_start_index:])
            if run.state == "started":
                run.state = "interrupted" if interrupted else "aborted"
                run.abort_reason = abort_reason
        self._write()


def _actual_attempts(records: Sequence[TriggerRecord]) -> list[TriggerRecord]:
    return [record for record in records if record.status in {"sent", "error"}]
