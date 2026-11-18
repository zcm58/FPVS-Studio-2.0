"""Digest evidence for media verified at research launch."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import cast

from .compiler_support import SUPPORTED_SOURCE_SUFFIXES
from .paths import resolve_project_relative_path
from .study_lifecycle import database_path, study_transaction


def _observation(
    root: Path, version_id: str,
) -> tuple[dict[str, str] | None, dict[str, str | None]]:
    path = database_path(root)
    if not path.is_file():
        return None, {}
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA query_only=ON")
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='run_stimuli'"
        ).fetchone():
            return None, {}
        row = db.execute(
            "SELECT verified, changes FROM run_stimuli WHERE version_id=?", (version_id,)
        ).fetchone()
    if row is None:
        return None, {}
    return (json.loads(row[0]) if row[0] is not None else None), json.loads(row[1])


def observed_run_stimuli(root: Path, version_id: str) -> dict[str, str]:
    """Digests verified for a prior launch under this exact accepted setup."""
    return _observation(root, version_id)[0] or {}


def pending_run_stimulus_changes(root: Path, version_id: str) -> dict[str, str | None]:
    """External changes detected at launch and still awaiting setup review."""
    return _observation(root, version_id)[1]


def _create_table(db: sqlite3.Connection) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS run_stimuli (
        version_id TEXT PRIMARY KEY, verified TEXT, changes TEXT NOT NULL)""")


def record_pending_stimulus_changes(
    db: sqlite3.Connection, version_id: str, changes: dict[str, str | None]
) -> None:
    """Retain newly observed differences without replacing the as-run file identities."""
    _create_table(db)
    db.execute(
        "INSERT INTO run_stimuli(version_id,verified,changes) VALUES(?,NULL,?) "
        "ON CONFLICT(version_id) DO UPDATE SET changes=excluded.changes",
        (version_id, json.dumps(changes, sort_keys=True)),
    )


def verify_run_stimuli(root: Path, version_id: str, digests: dict[str, str]) -> None:
    """Check the media used by a research setup and retain its hashes for subsequent visits."""
    from .study_versions import accepted_stimulus_digests, current_version

    accepted = accepted_stimulus_digests(root)
    with study_transaction(root) as db:
        active = current_version(root)
        if active is None or active.version_id != version_id:
            raise ValueError("The study changed during launch. Review and launch again.")
        _create_table(db)
        row = db.execute(
            "SELECT verified, changes FROM run_stimuli WHERE version_id=?", (version_id,)
        ).fetchone()
        verified = cast(dict[str, str] | None, json.loads(row[0]) if row and row[0] else None)
        changes: dict[str, str | None]
        if verified is None:
            # Check known media on first use. A legacy study may have no declared hashes.
            checkpoint = db.execute(
                "SELECT 1 FROM versions WHERE version_id=?", (version_id,)
            ).fetchone() is not None
            changes = {p: digest for p, digest in digests.items()
                       if (checkpoint or p in accepted) and digest != accepted.get(p)}
            if checkpoint:
                # The compiler discovers legacy image pools by folder. Check any archived
                # sibling absent from this launch against disk; unrelated pools stay untouched.
                folders = {Path(p).parent for p in digests}
                for relative in accepted.keys() - digests.keys():
                    prior = Path(relative)
                    if (
                        prior.parent in folders
                        and prior.suffix.lower() in SUPPORTED_SOURCE_SUFFIXES
                        and not resolve_project_relative_path(root, relative).is_file()
                    ):
                        changes[relative] = None
        else:
            # Compilers can resolve legacy pools directly from a folder. Adding or
            # removing a file there also changes what subsequent participants can see.
            changes = {p: digests.get(p) for p in verified.keys() | digests.keys()
                       if verified.get(p) != digests.get(p)}
        if row is None or json.loads(row[1]) != changes or (verified is None and not changes):
            checked = verified if changes else digests
            db.execute(
                "INSERT OR REPLACE INTO run_stimuli VALUES (?,?,?)",
                (version_id, json.dumps(checked, sort_keys=True) if checked is not None else None,
                 json.dumps(changes, sort_keys=True)),
            )
    if changes:
        raise ValueError(
            "The stimulus files changed. Review and save the experiment before collecting data."
        )
