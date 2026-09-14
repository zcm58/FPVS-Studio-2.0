"""Bounded app-local drafts; explicit UTF-8 exports never touch project storage."""

from __future__ import annotations

import os
import re
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from fpvs_studio.core.paths import filesystem_path
from fpvs_studio.support.models import Draft, ReportKind, utc_now

MAX_DRAFT_BYTES = 256 * 1024
_DRAFT_NAME = re.compile(r"draft-[0-9a-f-]{36}\.json\Z")


def support_directory() -> Path:
    """Resolve OS-local storage explicitly, without falling back to cwd or temp."""
    if sys.platform == "win32":
        value = os.environ.get("LOCALAPPDATA")
        if not value or not Path(value).is_absolute():
            raise OSError("Windows local application-data storage is unavailable.")
        return Path(value) / "FPVS Studio" / "support"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "FPVS Studio" / "support"
    value = os.environ.get("XDG_STATE_HOME")
    if value and not Path(value).is_absolute():
        raise OSError("XDG_STATE_HOME must be an absolute directory.")
    return (Path(value) if value else Path.home() / ".local" / "state") / "fpvs-studio/support"


def atomic_text(path: Path, text: str) -> None:
    """Use an exclusive sibling temporary file and replace only the selected destination."""
    path = filesystem_path(path)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    created = False
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            if os.name != "nt":
                temporary.chmod(0o600)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if created:
            temporary.unlink(missing_ok=True)


def owned_folder(root: Path, name: str) -> Path:
    """Reject redirected support directories before collecting or deleting owned files."""
    base = filesystem_path(root)
    for folder in (base, base / name):
        if folder.exists() and (
            folder.is_symlink()
            or getattr(folder.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise OSError("The support directory cannot be a link or junction.")
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    return base / name


class DraftStore:
    def __init__(self, root: Path, *, kind: ReportKind = "bug") -> None:
        self.root = root
        self.kind = kind
        self._lock = RLock()

    def _folder(self) -> Path:
        return owned_folder(self.root, "drafts" if self.kind == "bug" else "feature-drafts")

    def _files(self) -> list[Path]:
        return sorted(
            (
                p
                for p in self._folder().iterdir()
                if _DRAFT_NAME.fullmatch(p.name) and not p.is_symlink() and p.is_file()
            ),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    def _prune(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).timestamp()
        for index, path in enumerate(self._files()):
            if index >= 5 or path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)

    def load_latest(self) -> Draft | None:
        with self._lock:
            self._prune()
            files = self._files()
            if not files:
                return None
            with files[0].open("rb") as stream:
                data = stream.read(MAX_DRAFT_BYTES + 1)
            if len(data) > MAX_DRAFT_BYTES:
                raise ValueError("The saved report draft exceeds its storage limit.")
            draft = Draft.model_validate_json(data)
            if draft.report.kind != self.kind:
                raise ValueError("The saved draft has the wrong report type.")
            return draft

    def save(self, draft: Draft) -> None:
        if draft.report.kind != self.kind:
            raise ValueError("The draft does not belong in this report store.")
        with self._lock:
            saved = draft.model_copy(update={"updated_at": utc_now()})
            text = saved.model_dump_json()
            if len(text.encode("utf-8")) > MAX_DRAFT_BYTES:
                raise ValueError(
                    "Draft is too large to save. Shorten its description or error logs."
                )
            path = self._folder() / f"draft-{draft.report.report_id}.json"
            if path.is_symlink():
                raise OSError("A report draft cannot be a symbolic link.")
            atomic_text(path, text)
            self._prune()

    def discard(self, draft: Draft) -> None:
        with self._lock:
            path = self._folder() / f"draft-{draft.report.report_id}.json"
            if path.is_symlink():
                raise OSError("A report draft cannot be a symbolic link.")
            path.unlink(missing_ok=True)


def export_report(path: Path, draft: Draft) -> None:
    atomic_text(path, draft.report.as_text(include_logs=draft.include_logs))
