"""Synthetic dispatch bookkeeping checks; no network, real issues or worker launches."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / ".agents/scripts/issue_queue.py"
SPEC = importlib.util.spec_from_file_location("studio_issue_queue", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
queue_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(queue_module)
START = "2026-11-09T12:00:00Z"
EARLY = "2026-11-09T12:01:00Z"
LATE = "2026-11-09T12:02:00Z"
ISSUE = "https://github.com/zcm58/FPVS-Studio-Feedback/issues/1"
OTHER = "https://github.com/zcm58/FPVS-Studio-2.0/issues/2"
RESULT = "https://github.com/zcm58/FPVS-Studio-2.0/pull/3"


@pytest.fixture
def queue(tmp_path):
    instance = queue_module.IssueQueue(tmp_path / "queue")
    instance.init(START)
    return instance


def _claim(queue):
    queue.enqueue(ISSUE, EARLY)
    return queue.claim()["issue"]["token"]


def test_init_is_idempotent_and_preserves_activation_and_active_claim(queue):
    token = _claim(queue)
    config = queue.init(LATE)
    assert config == {
        "id": 1, "started_at": "2026-11-09T12:00:00.000000Z",
        "model": "gpt-6.1-sol", "delivery": "pull-request",
    }
    assert queue.claim()["issue"]["token"] == token


def test_duplicate_does_not_reset_running_or_completed_issue(queue):
    token = _claim(queue)
    queue.attach(token, "thread-one", "host-one")
    assert queue.enqueue(ISSUE, EARLY)["enqueued"] is False
    assert queue.status()["issues"][0]["status"] == "running"
    queue.finish(token, "implemented", RESULT, worker_stopped=True)
    assert queue.enqueue(ISSUE, EARLY)["issue"]["status"] == "implemented"
    assert queue.claim() == {"state": "empty", "issue": None}
    with pytest.raises(queue_module.QueueError, match="different creation time"):
        queue.enqueue(ISSUE, LATE)


def test_oldest_issue_first_across_both_repositories(queue):
    queue.enqueue(OTHER, LATE)
    queue.enqueue(ISSUE, EARLY)
    claim = queue.claim()
    assert claim["issue"]["url"] == ISSUE
    queue.attach(claim["issue"]["token"], "thread", "host")
    queue.finish(claim["issue"]["token"], "needs-info", ISSUE, worker_stopped=True)
    assert queue.claim()["issue"]["url"] == OTHER


def test_activation_boundary_and_timezone_normalization(queue):
    with pytest.raises(queue_module.QueueError, match="predates"):
        queue.enqueue(ISSUE, "2026-11-09T11:59:59.999999Z")
    assert queue.enqueue(ISSUE, "2026-11-09T06:00:00-06:00")["enqueued"] is True


@pytest.mark.parametrize("timestamp", ["2026-11-09", "2026-11-09T12:00:00", "tomorrow"])
def test_invalid_timestamp_does_not_queue(queue, timestamp):
    with pytest.raises(queue_module.QueueError, match="timestamp"):
        queue.enqueue(ISSUE, timestamp)
    assert queue.status()["issues"] == []


@pytest.mark.parametrize("url", [
    "http://github.com/zcm58/FPVS-Studio-Feedback/issues/1",
    "https://github.com/other/FPVS-Studio-Feedback/issues/1",
    "https://github.com/zcm58/FPVS-Studio-Feedback/pull/1",
    "https://github.com/zcm58/FPVS-Studio-Feedback/issues/0",
    ISSUE + "?token=secret", ISSUE + "#comment", ISSUE + "/", ISSUE + "\n",
    "https://github.com@example.com/zcm58/FPVS-Studio-Feedback/issues/1",
])
def test_noncanonical_or_outside_urls_are_rejected(queue, url):
    with pytest.raises(queue_module.QueueError, match="canonical"):
        queue.enqueue(url, EARLY)
    assert queue.status()["issues"] == []


def test_simultaneous_connections_claim_only_one_worker(queue):
    queue.enqueue(ISSUE, EARLY)
    queue.enqueue(OTHER, LATE)
    barrier = Barrier(2)

    def claim_from_independent_connection():
        independent = queue_module.IssueQueue(queue.path.parent)
        barrier.wait(timeout=5)
        return independent.claim()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim_from_independent_connection(), range(2)))
    assert sorted(result["state"] for result in results) == ["busy", "claimed"]
    assert results[0]["issue"]["token"] == results[1]["issue"]["token"]
    assert [issue["status"] for issue in queue.status()["issues"]] == ["dispatching", "queued"]


def test_database_guard_blocks_a_second_active_row(queue):
    _claim(queue)
    queue.enqueue(OTHER, LATE)
    with sqlite3.connect(queue.path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE issues SET status = 'running' WHERE url = ?", (OTHER,))


def test_restart_in_new_process_keeps_unknown_dispatch_active(queue):
    token = _claim(queue)
    command = (
        "import importlib.util,json,pathlib,sys; "
        "spec=importlib.util.spec_from_file_location('queue_helper',sys.argv[1]); "
        "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
        "print(json.dumps(module.IssueQueue(pathlib.Path(sys.argv[2])).claim()))"
    )
    result = subprocess.run(
        [sys.executable, "-c", command, str(SCRIPT), str(queue.path.parent)],
        capture_output=True, text=True, timeout=10, check=True,
    )
    assert json.loads(result.stdout)["state"] == "busy"
    assert json.loads(result.stdout)["issue"]["token"] == token


def test_attach_retries_are_idempotent_but_cannot_change_worker(queue):
    token = _claim(queue)
    attached = queue.attach(token, "thread", "host")
    assert queue.attach(token, "thread", "host") == attached
    with pytest.raises(queue_module.QueueError, match="different worker"):
        queue.attach(token, "other-thread", "host")
    with pytest.raises(queue_module.QueueError, match="Unknown claim token"):
        queue.attach("wrong-token", "thread", "host")
    assert queue.claim()["issue"] == attached


def test_finish_requires_stopped_worker_and_correct_token(queue):
    token = _claim(queue)
    queue.attach(token, "thread", "host")
    with pytest.raises(queue_module.QueueError, match="stopped"):
        queue.finish(token, "implemented", RESULT)
    with pytest.raises(queue_module.QueueError, match="Unknown claim token"):
        queue.finish("wrong-token", "implemented", RESULT, worker_stopped=True)
    assert queue.claim()["state"] == "busy"


@pytest.mark.parametrize("outcome", queue_module.OUTCOMES)
def test_finish_outcomes_and_retries(queue, outcome):
    token = _claim(queue)
    queue.attach(token, "thread", "host")
    finished = queue.finish(token, outcome, ISSUE, worker_stopped=True)
    assert finished["status"] == outcome
    assert queue.finish(token, outcome, ISSUE, worker_stopped=True) == finished
    with pytest.raises(queue_module.QueueError, match="different terminal result"):
        queue.finish(token, outcome, RESULT, worker_stopped=True)
    with pytest.raises(queue_module.QueueError, match="pending dispatch"):
        queue.attach(token, "thread", "host")


def test_unknown_dispatch_cannot_be_silently_finished(queue):
    token = _claim(queue)
    for outcome in queue_module.OUTCOMES:
        with pytest.raises(queue_module.QueueError, match="Reconcile this dispatch"):
            queue.finish(token, outcome, ISSUE, worker_stopped=True)
    with pytest.raises(queue_module.QueueError, match="Reconcile this dispatch"):
        queue.finish(token, "implemented", RESULT, worker_stopped=True, no_worker_created=True)
    assert queue.claim()["state"] == "busy"
    assert queue.finish(
        token, "cancelled", ISSUE, worker_stopped=True, no_worker_created=True,
    )["status"] == "cancelled"


@pytest.mark.parametrize("outcome", queue_module.OUTCOMES)
def test_retry_finished_issue_invalidates_previous_assignment(queue, outcome):
    old_token = _claim(queue)
    queue.attach(old_token, "old-thread", "old-host")
    queue.finish(old_token, outcome, ISSUE, worker_stopped=True)
    retried = queue.retry(ISSUE, worker_stopped=True)
    assert retried["status"] == "queued"
    assert retried["url"] == ISSUE
    assert retried["created_at"] == "2026-11-09T12:01:00.000000Z"
    for field in ["token", "thread_id", "host_id", "claimed_at", "finished_at", "result_link"]:
        assert retried[field] is None
    new_token = queue.claim()["issue"]["token"]
    assert new_token != old_token
    with pytest.raises(queue_module.QueueError, match="Unknown claim token"):
        queue.attach(old_token, "old-thread", "old-host")
    with pytest.raises(queue_module.QueueError, match="Unknown claim token"):
        queue.finish(old_token, outcome, ISSUE, worker_stopped=True)
    assert queue.claim()["issue"]["token"] == new_token


@pytest.mark.parametrize("running", [False, True])
def test_retry_cannot_release_an_active_worker(queue, running):
    token = _claim(queue)
    if running:
        queue.attach(token, "thread", "host")
    before = queue.status()
    with pytest.raises(queue_module.QueueError, match="Only a finished issue"):
        queue.retry(ISSUE, worker_stopped=True)
    assert queue.status() == before


def test_retry_requires_attestation_and_repeated_retry_is_rejected(queue):
    token = _claim(queue)
    queue.attach(token, "thread", "host")
    queue.finish(token, "needs-info", ISSUE, worker_stopped=True)
    before = queue.status()
    with pytest.raises(queue_module.QueueError, match="previous worker has stopped"):
        queue.retry(ISSUE)
    assert queue.status() == before
    queue.retry(ISSUE, worker_stopped=True)
    queued = queue.status()
    with pytest.raises(queue_module.QueueError, match="Only a finished issue"):
        queue.retry(ISSUE, worker_stopped=True)
    assert queue.status() == queued


def test_retry_unknown_or_outside_issue_is_rejected(queue):
    with pytest.raises(queue_module.QueueError, match="has not been queued"):
        queue.retry(ISSUE, worker_stopped=True)
    with pytest.raises(queue_module.QueueError, match="canonical"):
        queue.retry("https://example.com/issue/1", worker_stopped=True)
    assert queue.status()["issues"] == []


def test_result_link_rejects_raw_text_and_outside_destinations(queue):
    token = _claim(queue)
    queue.attach(token, "thread", "host")
    for result in ["private raw log", "https://example.com/log", RESULT + "?secret=1"]:
        with pytest.raises(queue_module.QueueError, match="GitHub"):
            queue.finish(token, "implemented", result, worker_stopped=True)
    assert queue.claim()["state"] == "busy"


def test_corrupt_database_is_preserved_and_fails_closed(tmp_path):
    queue = queue_module.IssueQueue(tmp_path)
    damaged = b"not a SQLite database; retain this evidence"
    queue.path.write_bytes(damaged)
    for operation in [queue.init, queue.status, queue.claim]:
        with pytest.raises(sqlite3.DatabaseError):
            operation()
        assert queue.path.read_bytes() == damaged


def test_removed_active_guard_fails_closed(queue):
    _claim(queue)
    with sqlite3.connect(queue.path) as connection:
        connection.execute("DROP INDEX one_active_worker")
    with pytest.raises(queue_module.QueueError, match="guard"):
        queue.claim()


def test_missing_configuration_cannot_reset_activation(queue):
    token = _claim(queue)
    with sqlite3.connect(queue.path) as connection:
        connection.execute("DELETE FROM config")
    with pytest.raises(queue_module.QueueError, match="configuration is missing"):
        queue.init(LATE)
    with sqlite3.connect(queue.path) as connection:
        assert connection.execute("SELECT * FROM config").fetchall() == []
        assert connection.execute("SELECT token FROM issues").fetchone()[0] == token


def test_unknown_database_version_is_preserved(queue):
    with sqlite3.connect(queue.path) as connection:
        connection.execute("PRAGMA user_version = 99")
    with pytest.raises(queue_module.QueueError, match="version"):
        queue.init()
    with sqlite3.connect(queue.path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 99


def test_worktree_and_main_checkout_share_the_active_slot(tmp_path):
    checkout = tmp_path / "source"
    worktree = tmp_path / "worktree"
    subprocess.run(["git", "init", str(checkout)], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(checkout), "-c", "user.name=Queue Test", "-c",
         "user.email=queue-test@example.invalid", "commit", "--allow-empty", "-m", "Fixture"],
        capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "-C", str(checkout), "worktree", "add", "--detach", str(worktree)],
        capture_output=True, check=True,
    )
    primary = queue_module.queue_for_repo(checkout)
    secondary = queue_module.queue_for_repo(worktree)
    assert primary.path == secondary.path
    primary.init(START)
    token = _claim(primary)
    assert secondary.claim()["issue"]["token"] == token


def test_cli_uses_git_common_dir_and_reports_errors_without_initializing(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=True)
    args = [sys.executable, str(SCRIPT), "--repo", str(tmp_path)]
    before = subprocess.run([*args, "status"], capture_output=True, text=True, check=False)
    assert before.returncode == 1
    assert "Stop and reconcile" in json.loads(before.stderr)["action"]
    initialized = subprocess.run(
        [*args, "init", "--started-at", START], capture_output=True, text=True, check=True,
    )
    assert json.loads(initialized.stdout)["model"] == "gpt-6.1-sol"
    assert (tmp_path / ".git/fpvs-issue-queue/queue.sqlite3").is_file()
    invalid = subprocess.run(
        [*args, "enqueue", "https://example.com/issue/1", "--created-at", EARLY],
        capture_output=True, text=True, check=False,
    )
    assert invalid.returncode == 1
    assert "canonical" in json.loads(invalid.stderr)["error"]
