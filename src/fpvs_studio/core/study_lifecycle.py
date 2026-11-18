"""Offline identity and collection state for one local Studio study."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .paths import filesystem_path, resolve_project_relative_path


@dataclass(frozen=True)
class StudyState:
    study_id: str
    collection_complete: bool
    archived: bool
    created_from: str | None


def database_path(root: Path) -> Path:
    return resolve_project_relative_path(root, ".fpvs-study/study.sqlite3")


@contextmanager
def study_transaction(root: Path) -> Iterator[sqlite3.Connection]:
    if not filesystem_path(root / "project.json").is_file():
        raise ValueError("Open a saved Studio project first.")
    path = database_path(root)
    path.parent.mkdir(exist_ok=True)
    with closing(sqlite3.connect(path, timeout=5)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            """CREATE TABLE IF NOT EXISTS study(
            singleton INTEGER PRIMARY KEY CHECK(singleton=1), study_id TEXT NOT NULL,
            collection_complete INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0,
            created_from TEXT)"""
        )
        db.execute("INSERT OR IGNORE INTO study(singleton,study_id) VALUES(1,?)", (str(uuid4()),))
        yield db


def _read(db: sqlite3.Connection) -> StudyState:
    row = db.execute(
        "SELECT study_id,collection_complete,archived,created_from FROM study"
    ).fetchone()
    return StudyState(row[0], bool(row[1]), bool(row[2]), row[3])


def read_study(root: Path) -> StudyState | None:
    """Legacy projects appear active without writing during discovery."""
    path = database_path(root)
    if not path.exists():
        return None
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA query_only=ON")
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='study'"
        ).fetchone():
            return None
        return _read(db)


def get_study(root: Path) -> StudyState:
    state = read_study(root)
    if state is None:
        with study_transaction(root) as db:
            state = _read(db)
    return state


def set_collection_complete(root: Path, complete: bool) -> StudyState:
    with study_transaction(root) as db:
        db.execute("UPDATE study SET collection_complete=?", (bool(complete),))
        return _read(db)


def set_archived(root: Path, archived: bool) -> StudyState:
    with study_transaction(root) as db:
        db.execute("UPDATE study SET archived=?", (bool(archived),))
        return _read(db)
