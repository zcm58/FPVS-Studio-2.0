"""Native report-write locking across threads and separate runtime processes."""

from __future__ import annotations

import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from multiprocessing.connection import Connection
from pathlib import Path
from threading import Event

import pytest

from fpvs_studio.runtime.reporting_lock import project_reporting_lock


def _hold_reporting_lock_until_terminated(project_root: str, ready: Connection) -> None:
    with project_reporting_lock(Path(project_root)):
        ready.send(True)
        Event().wait(30)


def test_reporting_lock_serializes_threads_with_independent_handles(tmp_path: Path) -> None:
    entered = Event()
    waiting = Event()

    def contender() -> None:
        waiting.set()
        with project_reporting_lock(tmp_path, timeout_seconds=2, poll_interval_seconds=0.01):
            entered.set()

    with ThreadPoolExecutor(max_workers=1) as executor:
        with project_reporting_lock(tmp_path):
            future = executor.submit(contender)
            assert waiting.wait(1)
            assert not entered.wait(0.1)
        future.result(timeout=2)

    assert entered.is_set()
    assert (tmp_path / "logs" / ".reporting.lock").is_file()


def test_reporting_lock_timeout_preserves_current_owner(tmp_path: Path) -> None:
    with project_reporting_lock(tmp_path):
        with pytest.raises(TimeoutError, match="reporting lock wait timed out"):
            with project_reporting_lock(tmp_path, timeout_seconds=0):
                pytest.fail("A second lock handle entered while the first still owns the lock.")
        with pytest.raises(TimeoutError):
            with project_reporting_lock(tmp_path, timeout_seconds=0.02):
                pytest.fail("A timed-out contender released another handle's lock.")

    with project_reporting_lock(tmp_path, timeout_seconds=0):
        pass


def test_reporting_lock_releases_after_exception_without_deleting_file(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="export failed"):
        with project_reporting_lock(tmp_path):
            raise RuntimeError("export failed")

    lock_path = tmp_path / "logs" / ".reporting.lock"
    existing_identity = lock_path.stat().st_ino
    with project_reporting_lock(tmp_path, timeout_seconds=0):
        assert lock_path.stat().st_ino == existing_identity


def test_reporting_lock_is_released_when_runtime_process_exits(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_hold_reporting_lock_until_terminated,
        args=(str(tmp_path), sender),
    )
    process.start()
    sender.close()
    try:
        assert receiver.poll(10), "Child runtime did not acquire its reporting lock."
        assert receiver.recv() is True
        with pytest.raises(TimeoutError):
            with project_reporting_lock(tmp_path, timeout_seconds=0):
                pytest.fail("A different process entered the owned reporting lock.")
    finally:
        process.terminate()
        process.join(timeout=5)
        receiver.close()

    assert not process.is_alive()
    with project_reporting_lock(tmp_path, timeout_seconds=0):
        pass


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"timeout_seconds": -1.0}, "timeout"),
        ({"timeout_seconds": float("inf")}, "timeout"),
        ({"poll_interval_seconds": 0.0}, "polling interval"),
        ({"poll_interval_seconds": float("nan")}, "polling interval"),
    ],
)
def test_reporting_lock_rejects_unbounded_wait_options(
    tmp_path: Path, options: dict[str, float], message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        with project_reporting_lock(tmp_path, **options):
            pytest.fail("Invalid wait options were accepted.")
    assert not (tmp_path / "logs").exists()


def test_reporting_lock_rejects_link_outside_project(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    outside_root = tmp_path / "outside"
    project_root.mkdir()
    outside_root.mkdir()
    try:
        (project_root / "logs").symlink_to(outside_root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Directory symlinks are unavailable in this environment: {exc}")

    with pytest.raises(ValueError, match="escapes the project root"):
        with project_reporting_lock(project_root):
            pytest.fail("The lock escaped its active project root.")
    assert not (outside_root / ".reporting.lock").exists()
