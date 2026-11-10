"""Durable, local dispatch bookkeeping; this helper never contacts GitHub or starts workers."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

REPOSITORIES = ("zcm58/FPVS-Studio-Feedback", "zcm58/FPVS-Studio-2.0")
MODEL = "gpt-6.1-sol"
DELIVERY = "pull-request"
OUTCOMES = ("implemented", "needs-info", "not-bug", "duplicate", "failed", "cancelled")
_REPOSITORY_PATTERN = "(?:" + "|".join(re.escape(repo) for repo in REPOSITORIES) + ")"
_ISSUE_PATTERN = re.compile(r"https://github\.com/" + _REPOSITORY_PATTERN + r"/issues/[1-9][0-9]*")
_RESULT_PATTERN = re.compile(
    r"https://github\.com/" + _REPOSITORY_PATTERN
    + r"/(?:issues/[1-9][0-9]*|pull/[1-9][0-9]*|commit/[0-9a-f]{7,40})"
)
_SCHEMA = (
    "CREATE TABLE config (id INTEGER PRIMARY KEY CHECK (id = 1), "
    "started_at TEXT NOT NULL, model TEXT NOT NULL, delivery TEXT NOT NULL)",
    "CREATE TABLE issues (url TEXT PRIMARY KEY, created_at TEXT NOT NULL, "
    "status TEXT NOT NULL CHECK (status IN ('queued', 'dispatching', 'running', "
    "'implemented', 'needs-info', 'not-bug', 'duplicate', 'failed', 'cancelled')), "
    "token TEXT UNIQUE, thread_id TEXT, host_id TEXT, claimed_at TEXT, "
    "finished_at TEXT, result_link TEXT)",
    "CREATE UNIQUE INDEX one_active_worker ON issues ((1)) "
    "WHERE status IN ('dispatching', 'running')",
)


class QueueError(ValueError):
    """The requested transition cannot safely proceed."""


def _timestamp(value: str | None = None) -> str:
    if value is None:
        parsed = datetime.now(timezone.utc)
    else:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise QueueError("Use an ISO 8601 timestamp with a UTC offset.") from exc
        if parsed.tzinfo is None:
            raise QueueError("The timestamp must include a UTC offset.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _identity(value: str) -> str:
    if not value or len(value) > 200 or any(character.isspace() for character in value):
        raise QueueError("Thread and host identifiers must be nonempty, without whitespace.")
    return value


class IssueQueue:
    def __init__(self, state_dir: Path):
        self.path = state_dir / "queue.sqlite3"

    @contextmanager
    def _transaction(self, *, initialize: bool = False):
        if initialize:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.path.resolve().as_uri() + ("?mode=rwc" if initialize else "?mode=rw"),
            uri=True, timeout=10, isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise QueueError("Queue integrity check failed; reconcile it before dispatching.")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if initialize and version == 0:
                if connection.execute("SELECT name FROM sqlite_master").fetchone() is not None:
                    raise QueueError("Unrecognized queue database; existing data was preserved.")
                for statement in _SCHEMA:
                    connection.execute(statement)
                connection.execute("PRAGMA user_version = 1")
            elif version != 1:
                raise QueueError("Unrecognized queue version; existing data was preserved.")
            index = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name = 'one_active_worker'"
            ).fetchone()
            if index is None or index[0] != _SCHEMA[2]:
                raise QueueError("The active-worker guard is missing or changed; stop dispatching.")
            config = connection.execute("SELECT * FROM config WHERE id = 1").fetchone()
            if config is None and not (initialize and version == 0):
                raise QueueError("Queue configuration is missing; reconcile the existing database.")
            if config is not None and (config["model"] != MODEL or config["delivery"] != DELIVERY):
                raise QueueError("Queue configuration does not match the approved workflow.")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def init(self, started_at: str | None = None) -> dict:
        timestamp = _timestamp(started_at)
        with self._transaction(initialize=True) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO config VALUES (1, ?, ?, ?)",
                (timestamp, MODEL, DELIVERY),
            )
            return dict(connection.execute("SELECT * FROM config WHERE id = 1").fetchone())

    def status(self) -> dict:
        with self._transaction() as connection:
            return {
                "config": dict(connection.execute("SELECT * FROM config WHERE id = 1").fetchone()),
                "issues": [dict(row) for row in connection.execute(
                    "SELECT * FROM issues ORDER BY created_at, url"
                )],
            }

    def enqueue(self, url: str, created_at: str) -> dict:
        if _ISSUE_PATTERN.fullmatch(url) is None:
            raise QueueError("Use a canonical issue URL in one of the two approved repositories.")
        timestamp = _timestamp(created_at)
        with self._transaction() as connection:
            activation = connection.execute("SELECT started_at FROM config WHERE id = 1").fetchone()
            if timestamp < activation[0]:
                raise QueueError("This issue predates watcher activation; it was not queued.")
            existing = connection.execute("SELECT * FROM issues WHERE url = ?", (url,)).fetchone()
            if existing is not None:
                if existing["created_at"] != timestamp:
                    raise QueueError(
                        "This issue is already recorded with a different creation time."
                    )
                return {"enqueued": False, "issue": dict(existing)}
            connection.execute(
                "INSERT INTO issues (url, created_at, status) VALUES (?, ?, 'queued')",
                (url, timestamp),
            )
            return {"enqueued": True, "issue": dict(connection.execute(
                "SELECT * FROM issues WHERE url = ?", (url,)
            ).fetchone())}

    def claim(self) -> dict:
        with self._transaction() as connection:
            active = connection.execute(
                "SELECT * FROM issues WHERE status IN ('dispatching', 'running')"
            ).fetchone()
            if active is not None:
                return {"state": "busy", "issue": dict(active)}
            pending = connection.execute(
                "SELECT url FROM issues WHERE status = 'queued' ORDER BY created_at, url LIMIT 1"
            ).fetchone()
            if pending is None:
                return {"state": "empty", "issue": None}
            token = str(uuid.uuid4())
            connection.execute(
                "UPDATE issues SET status = 'dispatching', token = ?, claimed_at = ? WHERE url = ?",
                (token, _timestamp(), pending[0]),
            )
            return {"state": "claimed", "issue": self._find_token(connection, token)}

    def retry(self, url: str, *, worker_stopped: bool = False) -> dict:
        if not worker_stopped:
            raise QueueError("Confirm the previous worker has stopped before retrying this issue.")
        if _ISSUE_PATTERN.fullmatch(url) is None:
            raise QueueError("Use a canonical issue URL in one of the two approved repositories.")
        with self._transaction() as connection:
            issue = connection.execute("SELECT * FROM issues WHERE url = ?", (url,)).fetchone()
            if issue is None:
                raise QueueError("This issue has not been queued.")
            if issue["status"] not in OUTCOMES:
                raise QueueError("Only a finished issue can be queued for another attempt.")
            connection.execute(
                "UPDATE issues SET status = 'queued', token = NULL, thread_id = NULL, "
                "host_id = NULL, claimed_at = NULL, finished_at = NULL, result_link = NULL "
                "WHERE url = ?", (url,),
            )
            return dict(connection.execute("SELECT * FROM issues WHERE url = ?", (url,)).fetchone())

    @staticmethod
    def _find_token(connection: sqlite3.Connection, token: str) -> dict:
        row = connection.execute("SELECT * FROM issues WHERE token = ?", (token,)).fetchone()
        if row is None:
            raise QueueError("Unknown claim token; no queue entry was changed.")
        return dict(row)

    def attach(self, token: str, thread_id: str, host_id: str) -> dict:
        thread_id, host_id = _identity(thread_id), _identity(host_id)
        with self._transaction() as connection:
            issue = self._find_token(connection, token)
            if issue["status"] == "running":
                if (issue["thread_id"], issue["host_id"]) == (thread_id, host_id):
                    return issue
                raise QueueError("This claim already belongs to a different worker.")
            if issue["status"] != "dispatching":
                raise QueueError("Only a pending dispatch can be attached to a worker.")
            connection.execute(
                "UPDATE issues SET status = 'running', thread_id = ?, host_id = ? WHERE token = ?",
                (thread_id, host_id, token),
            )
            return self._find_token(connection, token)

    def finish(
        self, token: str, outcome: str, result_link: str, *,
        worker_stopped: bool = False, no_worker_created: bool = False,
    ) -> dict:
        if not worker_stopped:
            raise QueueError("Confirm the worker has stopped before releasing its claim.")
        if outcome not in OUTCOMES:
            raise QueueError("Unknown terminal outcome.")
        if _RESULT_PATTERN.fullmatch(result_link) is None:
            raise QueueError(
                "Use an approved repository's GitHub issue, pull request or commit link."
            )
        with self._transaction() as connection:
            issue = self._find_token(connection, token)
            if issue["status"] in OUTCOMES:
                if (issue["status"], issue["result_link"]) == (outcome, result_link):
                    return issue
                raise QueueError("This claim already has a different terminal result.")
            if issue["status"] == "dispatching" and (
                outcome not in ("failed", "cancelled") or not no_worker_created
            ):
                raise QueueError(
                    "Reconcile this dispatch first: attach its worker, or confirm no worker "
                    "was created and finish as failed or cancelled."
                )
            connection.execute(
                "UPDATE issues SET status = ?, finished_at = ?, result_link = ? WHERE token = ?",
                (outcome, _timestamp(), result_link, token),
            )
            return self._find_token(connection, token)


def queue_for_repo(repo: Path) -> IssueQueue:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True, text=True, check=True,
    )
    return IssueQueue(Path(result.stdout.strip()) / "fpvs-issue-queue")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("init")
    initialize.add_argument("--started-at")
    commands.add_parser("status")
    enqueue = commands.add_parser("enqueue")
    enqueue.add_argument("url")
    enqueue.add_argument("--created-at", required=True)
    commands.add_parser("claim")
    retry = commands.add_parser("retry")
    retry.add_argument("url")
    retry.add_argument("--worker-stopped", action="store_true")
    attach = commands.add_parser("attach")
    attach.add_argument("token")
    attach.add_argument("--thread-id", required=True)
    attach.add_argument("--host-id", required=True)
    finish = commands.add_parser("finish")
    finish.add_argument("token")
    finish.add_argument("--outcome", choices=OUTCOMES, required=True)
    finish.add_argument("--result-link", required=True)
    finish.add_argument("--worker-stopped", action="store_true")
    finish.add_argument("--no-worker-created", action="store_true")
    args = parser.parse_args(argv)
    try:
        queue = queue_for_repo(args.repo)
        if args.command == "init":
            result = queue.init(args.started_at)
        elif args.command == "status":
            result = queue.status()
        elif args.command == "enqueue":
            result = queue.enqueue(args.url, args.created_at)
        elif args.command == "claim":
            result = queue.claim()
        elif args.command == "retry":
            result = queue.retry(args.url, worker_stopped=args.worker_stopped)
        elif args.command == "attach":
            result = queue.attach(args.token, args.thread_id, args.host_id)
        else:
            result = queue.finish(
                args.token, args.outcome, args.result_link,
                worker_stopped=args.worker_stopped, no_worker_created=args.no_worker_created,
            )
    except (QueueError, sqlite3.Error, OSError, subprocess.CalledProcessError) as exc:
        sys.stderr.write(json.dumps({
            "error": str(exc), "action": "Stop and reconcile queue state.",
        }) + "\n")
        return 1
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
