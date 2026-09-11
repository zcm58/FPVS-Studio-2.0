"""Resolve and reserve participant visits without reusing research output identities.

Runtime launchers reserve a numbered visit after preflight. Permanent, exclusive-created
markers protect compact exports and interrupted launches as well as detailed folders.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fpvs_studio.core.paths import logs_dir, runs_dir, to_project_relative_posix
from fpvs_studio.runtime.participant_history import (
    ParticipantSessionNumberSource,
    _iter_session_history_summaries,
    infer_participant_session_numbers,
    participant_session_number_from_output_label,
)

PARTICIPANT_SESSION_RESERVATIONS_DIRNAME = ".participant-sessions"


class ParticipantSessionConflictError(ValueError):
    """The participant visit shown to the researcher is no longer available."""


@dataclass(frozen=True)
class ParticipantSessionReservation:
    participant_session_number: int
    output_label: str


def _validated_participant_number(participant_number: str) -> str:
    if not isinstance(participant_number, str) or not re.fullmatch(r"[0-9]+", participant_number):
        raise ValueError("Participant number must contain digits only.")
    return participant_number


def _reservation_root(project_root: Path, participant_number: str) -> Path:
    path = (
        logs_dir(project_root) / PARTICIPANT_SESSION_RESERVATIONS_DIRNAME / f"P{participant_number}"
    )
    to_project_relative_posix(project_root, path)
    return path


def resolve_next_participant_session_number(project_root: Path, participant_number: str) -> int:
    """Preview the next visit, counting old, aborted, compact and interrupted launches.

    This is read-only. The launcher must reserve the returned number before playback.
    Leading zeros are part of the participant identity and are preserved.
    """

    participant_number = _validated_participant_number(participant_number)
    sources: list[ParticipantSessionNumberSource] = []
    known_output_labels: set[str] = set()
    for output_label, summary in _iter_session_history_summaries(project_root, strict=True):
        if summary.participant_number != participant_number:
            continue
        known_output_labels.add(output_label)
        occurred_at = summary.started_at or summary.finished_at
        sources.append(
            ParticipantSessionNumberSource(
                participant_number,
                output_label,
                occurred_at.isoformat() if occurred_at is not None else "",
                summary.participant_session_number,
            )
        )

    runs_root = runs_dir(project_root)
    if runs_root.is_dir():
        for entry in runs_root.iterdir():
            number = participant_session_number_from_output_label(entry.name, participant_number)
            if number is not None and entry.name not in known_output_labels:
                sources.append(ParticipantSessionNumberSource(participant_number, entry.name))

    numbers = set(infer_participant_session_numbers(sources))

    reservation_root = _reservation_root(project_root, participant_number)
    if reservation_root.is_dir():
        for entry in reservation_root.iterdir():
            match = re.fullmatch(r"session-([0-9]+)\.json", entry.name)
            if match is not None:
                numbers.add(int(match.group(1)))

    return max(numbers, default=0) + 1


def reserve_participant_session(
    project_root: Path,
    participant_number: str,
    *,
    session_id: str,
    participant_session_number: int | None = None,
    create_output_directory: bool,
) -> ParticipantSessionReservation:
    """Claim a visit atomically; keep claims after failures so partial data stays safe."""

    participant_number = _validated_participant_number(participant_number)
    if participant_session_number is not None and (
        isinstance(participant_session_number, bool)
        or not isinstance(participant_session_number, int)
        or participant_session_number < 1
    ):
        raise ValueError("Participant session number must be a positive integer.")

    while True:
        number = resolve_next_participant_session_number(project_root, participant_number)
        if participant_session_number is not None and participant_session_number != number:
            raise ParticipantSessionConflictError(
                f"Participant {participant_number} now requires Session {number}. "
                "Reopen the participant details and review the session number before launching."
            )
        output_label = f"P{participant_number}_session{number:02d}"
        output_dir = runs_dir(project_root) / output_label
        to_project_relative_posix(project_root, output_dir)
        reservation_root = _reservation_root(project_root, participant_number)
        reservation_root.mkdir(parents=True, exist_ok=True)
        marker = reservation_root / f"session-{number}.json"
        try:
            with marker.open("x", encoding="utf-8") as handle:
                json.dump(
                    {
                        "participant_number": participant_number,
                        "participant_session_number": number,
                        "session_id": session_id,
                        "reserved_at_utc": datetime.now(timezone.utc).isoformat(),
                        "output_dir": f"runs/{output_label}" if create_output_directory else None,
                    },
                    handle,
                    indent=2,
                )
                handle.write("\n")
        except FileExistsError:
            # Another launcher won the claim. An explicit preview is rejected on
            # the next pass; direct launches may safely claim the following visit.
            continue
        if create_output_directory:
            try:
                output_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                # The folder may have appeared after preview, independently of our
                # marker. Never write into it, even when it currently looks empty.
                continue
        return ParticipantSessionReservation(number, output_label)
