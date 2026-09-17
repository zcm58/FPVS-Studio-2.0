"""Cache permission and no-follow decisions without changing OS ACLs in unit tests."""

from __future__ import annotations

import ctypes
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from fpvs_studio.library import cache
from fpvs_studio.library.errors import LibraryError


def test_windows_reparse_paths_are_rejected_even_when_not_symlinks(tmp_path, monkeypatch):
    attributes = SimpleNamespace(st_file_attributes=0x400, st_mode=stat.S_IFDIR)
    monkeypatch.setattr(Path, "lstat", lambda self: attributes)
    with pytest.raises(LibraryError, match="reparse"):
        cache._check_path(tmp_path, directory=True)


def test_permission_failure_does_not_create_or_lock_payloads(tmp_path, monkeypatch):
    def denied(path):
        raise LibraryError("private cache denied")

    monkeypatch.setattr(cache, "_private_directory", denied)
    local = cache.DownloadCache(tmp_path / "cache")
    with pytest.raises(LibraryError, match="denied"):
        local.acquire()
    assert list(local.root.iterdir()) == []
    assert local._lock is None


@pytest.mark.parametrize("success", [True, False])
def test_windows_cache_uses_protected_owner_system_acl(tmp_path, monkeypatch, success):
    calls = []

    class Function:
        def __init__(self, result):
            self.result = result

        def __call__(self, *args):
            calls.append(args)
            return self.result

    api = SimpleNamespace(
        ConvertStringSecurityDescriptorToSecurityDescriptorW=Function(True),
        SetFileSecurityW=Function(success),
        LocalFree=Function(None),
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: api, raising=False)
    monkeypatch.setattr(cache.sys, "platform", "win32")
    if success:
        cache._private_directory(tmp_path)
    else:
        with pytest.raises(LibraryError, match="Could not protect"):
            cache._private_directory(tmp_path)
    assert calls[0][0] == "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;OW)"
    assert calls[1][1] == 0x80000004
    assert len(calls) == 3  # Security descriptor is freed on success and failure.


def test_cache_does_not_remove_unrecognized_user_files(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "_private_directory", lambda path: None)
    local = cache.DownloadCache(tmp_path / "cache")
    local.acquire()
    try:
        note = local.root / "notes.txt"
        note.write_text("keep")
        with pytest.raises(LibraryError, match="Unrecognized"):
            local.remove(note.name)
        local.clear()
        assert note.read_text() == "keep"
    finally:
        local.release()
