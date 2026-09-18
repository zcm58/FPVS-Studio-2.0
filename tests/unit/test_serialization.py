"""Failure preservation for the shared project/manifest JSON writer."""

from contextlib import contextmanager
from pathlib import Path

import pytest

import fpvs_studio.core.serialization as serialization
from fpvs_studio.core.serialization import atomic_text_write, load_project_file, save_project_file


def test_project_save_preserves_previous_file_on_partial_write(
    tmp_path, sample_project, monkeypatch,
) -> None:
    destination = tmp_path / "project.json"
    save_project_file(sample_project, destination)
    previous = destination.read_bytes()
    original_open = Path.open

    class PartialWriter:
        def __init__(self, handle):
            self.handle = handle

        def write(self, payload):
            self.handle.write(payload[:21])
            self.handle.flush()
            raise OSError("simulated disk full")

    @contextmanager
    def failing_open(path, mode="r", *args, **kwargs):
        with original_open(path, mode, *args, **kwargs) as handle:
            yield PartialWriter(handle) if mode in {"w", "x"} else handle

    monkeypatch.setattr(Path, "open", failing_open)
    with pytest.raises(OSError, match="simulated disk full"):
        save_project_file(sample_project, destination)

    assert destination.read_bytes() == previous
    assert sorted(p.name for p in tmp_path.iterdir()) == ["project.json"]


def test_project_save_preserves_previous_file_when_replace_fails(
    tmp_path, sample_project, monkeypatch,
) -> None:
    import os

    destination = tmp_path / "project.json"
    save_project_file(sample_project, destination)
    previous = destination.read_bytes()
    sample_project.meta.name = "Changed title"

    def fail_replace(source, target):
        raise PermissionError("destination is locked")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(PermissionError, match="destination is locked"):
        save_project_file(sample_project, destination)

    assert destination.read_bytes() == previous
    assert sorted(p.name for p in tmp_path.iterdir()) == ["project.json"]


def test_project_save_creates_and_replaces_valid_utf8_json(tmp_path, sample_project) -> None:
    destination = tmp_path / "new project" / "project.json"
    save_project_file(sample_project, destination)
    sample_project.meta.name = "Mémoire study"
    save_project_file(sample_project, destination)

    assert load_project_file(destination).meta.name == "Mémoire study"
    assert sorted(p.name for p in destination.parent.iterdir()) == ["project.json"]


def test_atomic_text_preserves_explicit_csv_line_endings(tmp_path) -> None:
    destination = tmp_path / "rows.csv"
    atomic_text_write(destination, "name,value\r\nexample,1\r\n", newline="")
    assert destination.read_bytes() == b"name,value\r\nexample,1\r\n"


@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_project_save_retries_brief_windows_locks_without_overwriting_old_data(
    tmp_path, sample_project, monkeypatch, winerror,
) -> None:
    destination = tmp_path / "project.json"
    save_project_file(sample_project, destination)
    previous = destination.read_bytes()
    real_replace = serialization.os.replace
    attempts = []

    def briefly_locked(source, target):
        attempts.append((source, target))
        if len(attempts) < 3:
            assert destination.read_bytes() == previous
            error = PermissionError("brief Windows file lock")
            error.winerror = winerror
            raise error
        return real_replace(source, target)

    monkeypatch.setattr(serialization.os, "replace", briefly_locked)
    monkeypatch.setattr(serialization.time, "sleep", lambda _: None)
    sample_project.meta.name = "Updated safely"
    save_project_file(sample_project, destination)

    assert load_project_file(destination).meta.name == "Updated safely"
    assert len(attempts) == 3
    assert len(set(attempts)) == 1
    assert not list(tmp_path.glob(".*.tmp"))


def test_project_save_still_raises_persistent_windows_denial(
    tmp_path, sample_project, monkeypatch,
) -> None:
    destination = tmp_path / "project.json"
    save_project_file(sample_project, destination)
    previous = destination.read_bytes()
    attempts = []

    def locked(source, target):
        attempts.append((source, target))
        error = PermissionError("persistent Windows denial")
        error.winerror = 5
        raise error

    monkeypatch.setattr(serialization.os, "replace", locked)
    delays = []
    monkeypatch.setattr(serialization.time, "sleep", delays.append)
    with pytest.raises(PermissionError, match="persistent Windows denial"):
        save_project_file(sample_project, destination)

    assert 1 < len(attempts) <= 5
    assert sum(delays) <= 0.15 + 1e-9
    assert destination.read_bytes() == previous
    assert not list(tmp_path.glob(".*.tmp"))
