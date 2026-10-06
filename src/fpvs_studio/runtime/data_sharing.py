"""Explicit completed-session capture, separate from research exports and transport."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import Field, StrictInt, field_validator, model_validator

from fpvs_studio import __version__
from fpvs_studio.core.data_sharing import (
    FixationOccurrence,
    SessionReport,
    Sha256,
    SharingModel,
    SharingProfile,
    _uuid,
)
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.data_sharing.library_scope import validate_library_scope
from fpvs_studio.data_sharing.storage import (
    MAX_RECORDS,
    SharingStorageError,
    _private_path,
    _write,
    load_settings,
    queue_report,
    read_bounded_model,
)

MAX_INTENT_BYTES = 256 * 1024
MAX_HISTORY_BYTES = 64 * 1024 * 1024


class CaptureIntent(SharingModel):
    """Private local join evidence; this object is never submitted over HTTP."""

    schema_version: Literal["1.0"] = "1.0"
    report_id: str
    profile: SharingProfile
    actual_protocol_sha256: Sha256 | None
    project_id: str = Field(min_length=1, max_length=255)
    session_id: str = Field(min_length=1, max_length=255)
    participant_number: str = Field(min_length=1, max_length=255)
    participant_session_number: StrictInt | None = Field(ge=1)
    run_ids: tuple[str, ...] = Field(max_length=4096)
    experiment_test_mode: bool
    pilot_mode: bool
    state: Literal["running", "eligible", "ineligible", "finalized"] = "running"
    reason: (
        Literal[
            "local_testing",
            "test_participant",
            "protocol_mismatch",
            "incomplete_session",
            "incomplete_or_invalid_metrics",
        ]
        | None
    ) = None
    report: SessionReport | None = None
    research_committed: bool = False
    evidence_sha256: Sha256 | None = None

    _validate_id = field_validator("report_id")(_uuid)

    @model_validator(mode="after")
    def validate_proof(self) -> CaptureIntent:
        if len(set(self.run_ids)) != len(self.run_ids):
            raise ValueError("Capture run IDs must be unique.")
        if self.state in {"eligible", "finalized"}:
            if self.report is None or self.reason is not None:
                raise ValueError("Eligible captures require an explicit report and no exclusion.")
            for field in ("experiment_id", "experiment_version", "protocol_sha256"):
                if getattr(self.profile, field) != getattr(self.report, field):
                    raise ValueError("Capture profile differs from its immutable report.")
            if self.report.report_id != self.report_id:
                raise ValueError("Capture UUID differs from its immutable report.")
            if (
                self.experiment_test_mode
                or self.pilot_mode
                or self.participant_number in {"0", "00"}
            ):
                raise ValueError("Test executions cannot become eligible captures.")
            if self.actual_protocol_sha256 != self.profile.protocol_sha256:
                raise ValueError("Eligible captures require the registered protocol.")
        elif self.report is not None:
            raise ValueError("Unconfirmed captures cannot contain an eligible report.")
        if self.research_committed != (self.evidence_sha256 is not None):
            raise ValueError("Committed captures require their evidence digest.")
        if self.state == "finalized" and not self.research_committed:
            raise ValueError("Finalized captures require committed research proof.")
        return self


def _intent_relative(report_id: str) -> str:
    _uuid(report_id)
    return f"logs/data-sharing/intents/{report_id}.json"


def _save_intent(root: Path, intent: CaptureIntent) -> None:
    _write(root, _intent_relative(intent.report_id), intent, MAX_INTENT_BYTES)


def _history_evidence(root: Path, intent: CaptureIntent) -> str:
    """Verify the exact numbered research occurrence rows owned by this intent."""
    path = _private_path(root, "logs/session_condition_history.csv")
    if not path.exists() or path.stat().st_size > MAX_HISTORY_BYTES:
        raise SharingStorageError(
            "Committed sharing evidence is missing or exceeds its read limit."
        )
    selected: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, strict=True):
            if (
                row.get("project_id") != intent.project_id
                or row.get("session_id") != intent.session_id
                or row.get("participant_number") != intent.participant_number
                or row.get("participant_session_number", "")
                != str(intent.participant_session_number or "")
            ):
                continue
            run_id = row.get("run_id", "")
            if run_id not in intent.run_ids:
                continue
            if run_id in selected or any(
                row.get(field, "").lower() not in {"false", "0"}
                for field in ("session_aborted", "run_aborted")
            ):
                raise SharingStorageError("Committed sharing evidence is duplicated or incomplete.")
            selected[run_id] = row
    if set(selected) != set(intent.run_ids) or intent.report is None:
        raise SharingStorageError(
            "Committed sharing evidence does not cover every planned occurrence."
        )
    for run_id, occurrence in zip(intent.run_ids, intent.report.occurrences, strict=True):
        row = selected[run_id]
        if row.get("condition_id") != occurrence.condition_id:
            raise SharingStorageError(
                "Committed condition identity differs from the capture intent."
            )
        for field in ("total_targets", "hit_count", "miss_count", "false_alarm_count"):
            raw = row.get(field, "")
            if int(raw or "0") != getattr(occurrence, field):
                raise SharingStorageError(
                    "Committed fixation metrics differ from the capture intent."
                )
    payload = json.dumps(
        [selected[key] for key in intent.run_ids],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_session_report(
    plan: SessionPlan,
    summary: SessionExecutionSummary,
    intent: CaptureIntent,
) -> SessionReport:
    entries = plan.ordered_entries()
    if (
        summary.aborted
        or not entries
        or len(summary.run_results) != len(entries)
        or summary.completed_condition_count != len(entries)
        or summary.total_condition_count != len(entries)
    ):
        raise ValueError("Only complete sessions can be shared.")
    occurrences: list[FixationOccurrence] = []
    for index, (entry, result) in enumerate(zip(entries, summary.run_results, strict=True), 1):
        if (
            result.run_id != entry.run_id
            or result.condition_id != entry.condition_id
            or result.aborted
            or result.completed_frames != entry.run_spec.display.total_frames
            or not result.task_flow_completed
            or result.task_flow_aborted
        ):
            raise ValueError("Every planned stream and task must finish before sharing.")
        fixation = result.fixation_task_summary
        if entry.run_spec.fixation.accuracy_task_enabled and fixation is None:
            raise ValueError("Enabled fixation scoring requires a completed summary.")
        rt_count = (
            sum(
                event.outcome == "hit" and (event.rt_s is not None or event.rt_frames is not None)
                for event in result.fixation_responses
            )
            if fixation is not None
            else 0
        )
        source = (
            result.runtime_metadata.fixation_rt_scoring_source if result.runtime_metadata else None
        )
        if source == "mixed":
            raise ValueError("Mixed scoring within one occurrence requires review.")
        scoring_source: Literal["timestamps", "frames"] = (
            "timestamps" if source == "hardware_timestamp" else "frames"
        )
        occurrences.append(
            FixationOccurrence(
                condition_id=entry.condition_id,
                occurrence_index=index,
                total_targets=fixation.total_targets if fixation else 0,
                hit_count=fixation.hit_count if fixation else 0,
                miss_count=fixation.miss_count if fixation else 0,
                false_alarm_count=fixation.false_alarm_count if fixation else 0,
                accuracy_percent=fixation.accuracy_percent
                if fixation and fixation.total_targets
                else None,
                mean_rt_ms=fixation.mean_rt_ms if fixation else None,
                rt_count=rt_count,
                scoring_source=scoring_source,
                refresh_hz=float(entry.run_spec.display.refresh_hz),
                response_window_ms=(
                    entry.run_spec.fixation.response_window_frames
                    / entry.run_spec.display.refresh_hz
                    * 1000.0
                ),
            )
        )
    return SessionReport(
        report_id=intent.report_id,
        experiment_id=intent.profile.experiment_id,
        experiment_version=intent.profile.experiment_version,
        protocol_sha256=intent.profile.protocol_sha256,
        completed_at=datetime.now(timezone.utc),
        studio_version=__version__,
        occurrences=tuple(occurrences),
    )


class SharingCapture:
    """Persist launch intent, terminal proof and post-commit report in that order."""

    def __init__(self, root: Path, plan: SessionPlan, intent: CaptureIntent) -> None:
        self.root = root
        self.plan = plan
        self.intent = intent

    @classmethod
    def begin(
        cls,
        root: Path,
        plan: SessionPlan,
        *,
        participant_number: str,
        participant_session_number: int | None,
        runtime_options: Mapping[str, object] | None,
    ) -> SharingCapture | None:
        settings = load_settings(root)
        if not settings.enabled or settings.profile is None:
            return None
        options = runtime_options or {}
        if (
            options.get("experiment_test_mode", False)
            or options.get("pilot_mode", False)
            or participant_number in {"0", "00"}
        ):
            return None
        validate_library_scope(root, settings.profile)
        directory = _private_path(root, "logs/data-sharing/intents")
        if directory.exists() and len(list(directory.glob("*.json"))) >= MAX_RECORDS:
            raise SharingStorageError("Sharing capture history is full; review prior captures.")
        actual = options.get("sharing_protocol_sha256")
        intent = CaptureIntent(
            report_id=str(uuid4()),
            profile=settings.profile,
            actual_protocol_sha256=actual if isinstance(actual, str) else None,
            project_id=plan.project_id,
            session_id=plan.session_id,
            participant_number=participant_number,
            participant_session_number=participant_session_number,
            run_ids=tuple(entry.run_id for entry in plan.ordered_entries()),
            experiment_test_mode=bool(options.get("experiment_test_mode", False)),
            pilot_mode=bool(options.get("pilot_mode", False)),
        )
        _save_intent(root, intent)
        return cls(root, plan, intent)

    def terminal(self, summary: SessionExecutionSummary) -> None:
        reason = None
        if self.intent.experiment_test_mode or self.intent.pilot_mode:
            reason = "local_testing"
        elif self.intent.participant_number in {"0", "00"}:
            reason = "test_participant"
        elif self.intent.actual_protocol_sha256 != self.intent.profile.protocol_sha256:
            reason = "protocol_mismatch"
        elif summary.aborted:
            reason = "incomplete_session"
        report = None
        if reason is None:
            try:
                report = build_session_report(self.plan, summary, self.intent)
            except ValueError:
                reason = "incomplete_or_invalid_metrics"
        updated = self.intent.model_copy(
            update={
                "state": "eligible" if reason is None else "ineligible",
                "reason": reason,
                "report": report,
            }
        )
        _save_intent(self.root, updated)
        self.intent = updated

    def research_committed(self) -> None:
        if self.intent.state != "eligible":
            return
        digest = _history_evidence(self.root, self.intent)
        updated = self.intent.model_copy(
            update={
                "research_committed": True,
                "evidence_sha256": digest,
            }
        )
        _save_intent(self.root, updated)
        self.intent = updated
        self.finalize()

    def finalize(self) -> None:
        if (
            self.intent.state != "eligible"
            or self.intent.report is None
            or not self.intent.research_committed
            or self.intent.evidence_sha256 is None
        ):
            return
        if _history_evidence(self.root, self.intent) != self.intent.evidence_sha256:
            raise SharingStorageError(
                "Committed research evidence changed; report requires review."
            )
        queue_report(self.root, self.intent.report)
        updated = self.intent.model_copy(update={"state": "finalized"})
        _save_intent(self.root, updated)
        self.intent = updated


def recover_captures(root: Path) -> tuple[str, ...]:
    """Reconcile explicit committed intents only; missing terminal proof remains held."""
    directory = _private_path(root, "logs/data-sharing/intents")
    if not directory.exists():
        return ()
    paths = list(directory.glob("*.json"))
    if len(paths) > MAX_RECORDS:
        raise SharingStorageError("Sharing capture history exceeds its bounded record limit.")
    warnings: list[str] = []
    for path in sorted(paths):
        intent = read_bounded_model(
            _private_path(root, _intent_relative(path.stem)),
            CaptureIntent,
            MAX_INTENT_BYTES,
        )
        if intent.report_id != path.stem:
            raise SharingStorageError("Sharing capture filename does not match its UUID.")
        if intent.state in {"ineligible", "finalized"}:
            continue
        if intent.state == "running" or not intent.research_committed:
            warnings.append(
                f"Capture {intent.report_id} requires review: "
                "completion or commit proof is missing."
            )
            continue
        capture = SharingCapture.__new__(SharingCapture)
        capture.root = root
        capture.intent = intent
        capture.finalize()
    return tuple(warnings)


def capture_errors(root: Path) -> tuple[str, ...]:
    """Safe status summaries, without participant identity or research answers."""
    directory = _private_path(root, "logs/data-sharing/intents")
    if not directory.exists():
        return ()
    paths = list(directory.glob("*.json"))
    if len(paths) > MAX_RECORDS:
        raise SharingStorageError("Sharing capture history exceeds its bounded record limit.")
    warnings = []
    for path in sorted(paths):
        intent = read_bounded_model(
            _private_path(root, _intent_relative(path.stem)),
            CaptureIntent,
            MAX_INTENT_BYTES,
        )
        if intent.report_id != path.stem:
            raise SharingStorageError("Sharing capture filename does not match its UUID.")
        if intent.state in {"running", "eligible"}:
            detail = (
                "local queue completion is pending"
                if intent.research_committed
                else "completion or commit proof requires review"
            )
            warnings.append(f"Capture {intent.report_id}: {detail}.")
        elif intent.reason in {"protocol_mismatch", "incomplete_or_invalid_metrics"}:
            warnings.append(
                f"Capture {intent.report_id}: {intent.reason.replace('_', ' ')}; retained locally."
            )
    return tuple(warnings)
