"""Bounded per-user downloads, no-follow checks, and cross-process ownership."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import sys
from pathlib import Path
from threading import Event
from typing import BinaryIO

from fpvs_studio.library.errors import LibraryCancelled, LibraryError
from fpvs_studio.library.models import LibraryItem

CHUNK_BYTES = 256 * 1024
_PAYLOAD_NAME = re.compile(r"^[0-9a-f]{64}\.fpvsbundle$")


def check_cancel(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise LibraryCancelled("Library operation canceled.")


def default_cache_root(service_url: str) -> Path:
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        if not local or not Path(local).is_absolute():
            raise LibraryError("The Windows per-user Library cache location is unavailable.")
        base = Path(local) / "FPVS Studio"
    else:
        configured = os.environ.get("XDG_CACHE_HOME")
        base = Path(configured) if configured else Path.home() / ".cache"
        if not base.is_absolute():
            raise LibraryError("The per-user Library cache location must be absolute.")
        base = base / "fpvs-studio"
    identity = hashlib.sha256(service_url.encode("utf-8")).hexdigest()[:24]
    return base / "experiment-library" / identity


def _check_path(path: Path, *, directory: bool) -> None:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise LibraryError("The Library cache contains a link or Windows reparse point.")
    valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not valid_type or (not directory and info.st_nlink != 1):
        raise LibraryError("The Library cache contains an unsafe file or directory.")


def _check_ancestors(path: Path) -> None:
    for ancestor in reversed((path, *path.parents)):
        if ancestor.exists() or ancestor.is_symlink():
            _check_path(ancestor, directory=True)


def _open_regular(path: Path, flags: int) -> BinaryIO:
    if path.exists() or path.is_symlink():
        _check_path(path, directory=False)
    fd = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0), 0o600)
    try:
        _check_path(path, directory=False)
        opened = os.fstat(fd)
        current = path.lstat()
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            raise LibraryError("The Library cache changed during access. Try again.")
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise LibraryError("The Library cache file is not a private regular file.")
        return os.fdopen(fd, "r+b" if flags & os.O_RDWR else "rb")
    except BaseException:
        os.close(fd)
        raise


def _private_directory(path: Path) -> None:
    if sys.platform != "win32":
        if path.stat().st_uid != os.getuid():
            raise LibraryError("The Library cache must belong to the current OS user.")
        path.chmod(0o700)
        return
    import ctypes
    from ctypes import wintypes

    api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    kernel = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
    api.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
    ]
    api.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    api.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
    api.SetFileSecurityW.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    descriptor = ctypes.c_void_p()
    # Protected DACL: SYSTEM and this directory's owner; inherited by new payloads.
    if not api.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;OW)", 1, ctypes.byref(descriptor), None
    ):
        raise LibraryError("Could not create private Library cache permissions.")
    try:
        if not api.SetFileSecurityW(str(path), 0x80000004, descriptor):
            raise LibraryError("Could not protect the per-user Library cache.")
    finally:
        kernel.LocalFree(descriptor)


class DownloadCache:
    """A held lease protects the returned payload until the importer releases it."""

    def __init__(self, root: Path) -> None:
        self.root = Path(os.path.abspath(root))
        self._lock: BinaryIO | None = None

    def acquire(self) -> None:
        if self._lock is not None:
            raise LibraryError("Finish the current Library operation before starting another.")
        try:
            _check_ancestors(self.root)
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            _check_ancestors(self.root)
            _private_directory(self.root)
            stream = _open_regular(self.root / ".library.lock", os.O_RDWR | os.O_CREAT)
            try:
                if sys.platform == "win32":
                    import msvcrt

                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                stream.close()
                raise LibraryError(
                    "Another FPVS Studio process is using the Experiment Library."
                ) from None
            self._lock = stream
        except OSError:
            raise LibraryError("The per-user Library cache is unavailable or read-only.") from None

    def release(self) -> None:
        if self._lock is not None:
            stream, self._lock = self._lock, None
            try:
                stream.seek(0)
                if sys.platform == "win32":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            finally:
                stream.close()

    def _owned(self, name: str) -> Path:
        if self._lock is None:
            raise LibraryError("Library cache access requires an active operation.")
        if name != "download.part" and not _PAYLOAD_NAME.fullmatch(name):
            raise LibraryError("Unrecognized Library cache filename.")
        _check_ancestors(self.root)
        return self.root / name

    def remove(self, name: str) -> None:
        path = self._owned(name)
        if path.exists() or path.is_symlink():
            _check_path(path, directory=False)
            path.unlink()

    def clear(self, *, keep: str | None = None) -> None:
        self._owned("download.part")
        for path in self.root.iterdir():
            if path.name != keep and (
                _PAYLOAD_NAME.fullmatch(path.name) or path.name == "download.part"
            ):
                self.remove(path.name)

    def payload(self, item: LibraryItem) -> Path:
        return self._owned(f"{item.sha256}.fpvsbundle")

    def verified(self, item: LibraryItem, cancel_event: Event | None) -> Path | None:
        path = self.payload(item)
        if not path.exists() and not path.is_symlink():
            return None
        digest = hashlib.sha256()
        total = 0
        with _open_regular(path, os.O_RDONLY) as stream:
            if os.fstat(stream.fileno()).st_size != item.size_bytes:
                return None
            while chunk := stream.read(CHUNK_BYTES):
                check_cancel(cancel_event)
                total += len(chunk)
                if total > item.size_bytes:
                    return None
                digest.update(chunk)
        check_cancel(cancel_event)
        return path if total == item.size_bytes and digest.hexdigest() == item.sha256 else None

    def create_partial(self) -> BinaryIO:
        self.remove("download.part")
        return _open_regular(self._owned("download.part"), os.O_RDWR | os.O_CREAT | os.O_EXCL)

    def commit(self, item: LibraryItem) -> Path:
        partial = self._owned("download.part")
        _check_path(partial, directory=False)
        target = self.payload(item)
        self.remove(target.name)
        partial.replace(target)
        self.clear(keep=target.name)
        return target
