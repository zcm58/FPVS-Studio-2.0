"""Local protocol revisions, immutable stimulus contents and standalone study creation."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import sys
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast
from uuid import uuid4

from .models import ProjectFile
from .paths import (
    filesystem_path,
    resolve_project_relative_path,
    slugify_project_name,
    validate_project_id,
)
from .serialization import load_project_file, save_project_file
from .study_lifecycle import database_path, get_study, study_transaction

if sys.platform == "win32":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _FileBasicInfo(ctypes.Structure):
        _fields_ = [
            ("creation", ctypes.c_int64),
            ("access", ctypes.c_int64),
            ("write", ctypes.c_int64),
            ("change", ctypes.c_int64),
            ("attributes", wintypes.DWORD),
        ]

    _basic_info = ctypes.windll.kernel32.GetFileInformationByHandleEx
    _basic_info.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.POINTER(_FileBasicInfo),
        wintypes.DWORD,
    ]
    _basic_info.restype = wintypes.BOOL


@dataclass(frozen=True)
class StudyVersion:
    version_id: str
    saved_at: str
    label: str
    reason: str
    changes: tuple[str, ...]


@dataclass(frozen=True)
class ProtocolDraft:
    previous: str | None
    protocol: dict
    assets: dict[str, str]
    changes: tuple[str, ...]
    working_assets: dict[str, str] | None = None


class ProtocolReviewRequired(ValueError):
    """A changed protocol needs the author's recorded decision."""


def _require_reason(root: Path, draft: ProtocolDraft, reason: str) -> None:
    if draft.changes and not reason.strip():
        from fpvs_studio.runtime.participant_results import research_visits_by_version

        if research_visits_by_version(root):
            raise ProtocolReviewRequired(
                "Review this protocol change and record a reason in Studio."
            )


def _tables(db: sqlite3.Connection) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS versions (
        version_id TEXT PRIMARY KEY, saved_at TEXT NOT NULL, label TEXT NOT NULL,
        reason TEXT NOT NULL, changes TEXT NOT NULL, protocol TEXT NOT NULL,
        assets TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS asset_cache (
        path TEXT PRIMARY KEY, stamp TEXT NOT NULL, digest TEXT NOT NULL)""")


def _latest(db: sqlite3.Connection) -> sqlite3.Row | None:
    return cast(
        sqlite3.Row | None,
        db.execute("SELECT * FROM versions ORDER BY rowid DESC LIMIT 1").fetchone(),
    )


def _version(row: sqlite3.Row) -> StudyVersion:
    return StudyVersion(
        row["version_id"],
        row["saved_at"],
        row["label"],
        row["reason"],
        tuple(json.loads(row["changes"])),
    )


def current_version(root: Path) -> StudyVersion | None:
    path = database_path(root)
    if not path.is_file():
        return None
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA query_only=ON")
        db.row_factory = sqlite3.Row
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='versions' AND type='table'"
        ).fetchone():
            return None
        row = _latest(db)
        return _version(row) if row else None


def list_versions(root: Path) -> list[StudyVersion]:
    with study_transaction(root) as db:
        _tables(db)
        return [
            _version(row)
            for row in db.execute(
                "SELECT version_id,saved_at,label,reason,changes FROM versions ORDER BY rowid"
            )
        ]


def name_version(root: Path, version_id: str, label: str) -> None:
    with study_transaction(root) as db:
        if not db.execute(
            "UPDATE versions SET label=? WHERE version_id=?", (label.strip(), version_id)
        ).rowcount:
            raise ValueError("This experiment version is unavailable.")


def _protocol(project: ProjectFile) -> dict:
    return project.model_dump(mode="json", exclude={"meta", "manual_removed_electrodes"})


def _regular(path: Path) -> os.stat_result:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError(f"Linked stimulus paths cannot be versioned: {path.name}")
    return info


def _object(root: Path, digest: str) -> Path:
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Invalid saved stimulus identity.")
    return resolve_project_relative_path(root, f".fpvs-study/objects/{digest}")


def _asset_stamp(path: Path, info: os.stat_result) -> str | None:
    change = info.st_ctime_ns
    if sys.platform == "win32":
        # Python 3.10 st_ctime is Windows creation time. Use the filesystem's
        # change time so a same-size replacement with a restored mtime is caught.
        with path.open("rb") as handle:
            basic = _FileBasicInfo()
            if (
                not _basic_info(
                    msvcrt.get_osfhandle(handle.fileno()),
                    0,
                    ctypes.byref(basic),
                    ctypes.sizeof(basic),
                )
                or not basic.change
            ):
                return None  # This volume cannot verify a cached digest. Read the bytes.
            change = basic.change
    return f"{info.st_dev}:{info.st_ino}:{info.st_size}:{info.st_mtime_ns}:{change}"


def _capture_file(root: Path, path: Path, relative: str, db: sqlite3.Connection) -> str:
    info = _regular(path)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"Expected a regular stimulus file: {relative}")
    stamp = _asset_stamp(path, info)
    cached = db.execute(
        "SELECT digest FROM asset_cache WHERE path=? AND stamp=?", (relative, stamp)
    ).fetchone()
    if cached and _object(root, cached[0]).is_file():
        return str(cached[0])
    directory = resolve_project_relative_path(root, ".fpvs-study/objects")
    directory.mkdir(exist_ok=True)
    temp = directory / (uuid4().hex + ".tmp")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source, temp.open("xb") as target:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
                target.write(block)
        after = _regular(path)
        if _asset_stamp(path, after) != stamp or (
            info.st_size,
            info.st_mtime_ns,
            info.st_ino,
            info.st_ctime_ns,
        ) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ino,
            after.st_ctime_ns,
        ):
            raise ValueError(f"Stimulus changed during review: {relative}")
        key = digest.hexdigest()
        target_path = _object(root, key)
        if not target_path.exists():
            os.replace(temp, target_path)
        db.execute(
            "INSERT OR REPLACE INTO asset_cache VALUES (?,?,?)", (relative, stamp or "", key)
        )
        return key
    finally:
        temp.unlink(missing_ok=True)


def _assets(root: Path, db: sqlite3.Connection, source: Path | None = None) -> dict[str, str]:
    source = source or root
    folder = filesystem_path(source / "stimuli")
    inventory: dict[str, str] = {}
    if folder.exists():
        _regular(folder)

    def fail(error: OSError) -> None:
        raise error

    for parent, dirs, files in os.walk(folder, onerror=fail) if folder.exists() else ():
        for name in dirs:
            _regular(Path(parent) / name)
        for name in files:
            path = Path(parent) / name
            relative = path.relative_to(folder).as_posix()
            inventory[relative] = _capture_file(root, path, relative, db)
    head = _latest(db)
    previous = json.loads(head["assets"]).get("manifest.json") if head else None
    current = inventory.get("manifest.json")
    if previous and current and previous != current:
        if _manifest_content(root, previous) == _manifest_content(root, current):
            inventory["manifest.json"] = previous
            db.execute("UPDATE asset_cache SET digest=? WHERE path='manifest.json'", (previous,))
    return inventory


def _manifest_content(root: Path, digest: str) -> dict:
    """Compare authored stimulus declarations independently of inspection timestamps."""
    data = json.loads(_object(root, digest).read_bytes())
    data.pop("generated_at", None)
    for entry in data.get("sets", []):
        for asset in entry.get("assets", []):
            asset["source"].pop("imported_at", None)
            for derivative in asset.get("derivatives", []):
                derivative.pop("created_at", None)
    return cast(dict, data)


def _show(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _differences(old: object, new: object, key: str = "") -> list[str]:
    if old == new:
        return []
    if isinstance(old, dict) and isinstance(new, dict):
        changes = []
        for field in sorted(old.keys() | new.keys()):
            name = f"{key} / {field}" if key else field
            if field not in old:
                changes.append(f"{name}: added {_show(new[field])}")
            elif field not in new:
                changes.append(f"{name}: removed {_show(old[field])}")
            else:
                changes.extend(_differences(old[field], new[field], name))
        return changes
    if (
        isinstance(old, list)
        and isinstance(new, list)
        and key in {"conditions", "stimulus_sets", "task_modules"}
    ):
        id_key = {
            "conditions": "condition_id",
            "stimulus_sets": "set_id",
            "task_modules": "task_id",
        }[key]
        if all(isinstance(v, dict) and id_key in v for v in old + new):
            changes = _differences({v[id_key]: v for v in old}, {v[id_key]: v for v in new}, key)
            if [v[id_key] for v in old] != [v[id_key] for v in new]:
                changes.append(
                    f"{key} order: {[v[id_key] for v in old]} → {[v[id_key] for v in new]}"
                )
            return changes
    unit = " Hz" if key.endswith("_hz") else ""
    return [f"{key}: {_show(old)}{unit} → {_show(new)}{unit}"]


def _draft(
    row: sqlite3.Row | None, protocol: dict[str, Any], assets: dict[str, str]
) -> ProtocolDraft:
    if row is None:
        return ProtocolDraft(None, protocol, assets, ("First saved protocol",))
    old_assets = json.loads(row["assets"])
    previous = json.loads(row["protocol"])
    changes = _differences(previous, protocol)
    # Make inherited frequencies intelligible when a cadence or override changes.
    old_conditions = {entry["condition_id"]: entry for entry in previous["conditions"]}
    rates = []
    for entry in protocol["conditions"]:
        old = old_conditions.get(entry["condition_id"])
        if old is None:
            continue
        prior_settings = previous["settings"]["protocol"]
        settings = protocol["settings"]["protocol"]
        before = old.get("base_hz") or prior_settings["base_hz"]
        after = entry.get("base_hz") or settings["base_hz"]
        old_oddball = before / prior_settings["oddball_every_n"]
        new_oddball = after / settings["oddball_every_n"]
        if (before, old_oddball) != (after, new_oddball):
            rates.append(
                f"{entry['name']} — base {before:g} Hz → {after:g} Hz, "
                f"oddball {old_oddball:g} Hz → {new_oddball:g} Hz"
            )
    changes = rates + changes
    for path in sorted(old_assets.keys() | assets.keys()):
        if old_assets.get(path) != assets.get(path):
            action = (
                "added"
                if path not in old_assets
                else "removed"
                if path not in assets
                else "replaced"
            )
            changes.append(f"Stimulus {action}: {path}")
    return ProtocolDraft(row["version_id"], protocol, assets, tuple(changes))


def _record(db: sqlite3.Connection, draft: ProtocolDraft, reason: str = "") -> StudyVersion:
    version_id = str(uuid4())
    stamp = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO versions VALUES (?,?,?,?,?,?,?)",
        (
            version_id,
            stamp,
            "",
            reason.strip(),
            json.dumps(draft.changes),
            json.dumps(draft.protocol),
            json.dumps(draft.assets),
        ),
    )
    return StudyVersion(version_id, stamp, "", reason.strip(), draft.changes)


def prepare_change(
    root: Path,
    project: ProjectFile,
    *,
    transient_session_seed: bool = False,
    candidate_root: Path | None = None,
) -> ProtocolDraft:
    """Capture candidate bytes in a worker before asking for a decision."""
    with study_transaction(root) as db:
        _tables(db)
        row = _latest(db)
        if row is None:
            _record(
                db,
                _draft(
                    None, _protocol(load_project_file(root / "project.json")), _assets(root, db)
                ),
            )
            row = _latest(db)
        assets = _assets(root, db, candidate_root)
        protocol = _protocol(project)
        draft = _draft(row, protocol, assets)
        if transient_session_seed:
            # A legacy launch may select a fresh seed without an authored edit.
            changes = tuple(
                c for c in draft.changes if not c.startswith("settings / session / session_seed:")
            )
            return ProtocolDraft(draft.previous, protocol, assets, changes)
        return draft


def _check_current(db: sqlite3.Connection, draft: ProtocolDraft) -> None:
    row = _latest(db)
    if row is None or row["version_id"] != draft.previous:
        raise ValueError(
            "The saved version changed during review. Reopen the project and review again."
        )


def commit_change(root: Path, project: ProjectFile, draft: ProtocolDraft, reason: str) -> None:
    with study_transaction(root) as db:
        _check_current(db, draft)
        _require_reason(root, draft, reason)
        if _protocol(project) != draft.protocol or _assets(root, db) != draft.assets:
            raise ValueError(
                "The experiment changed after review. Review its settings and stimuli again."
            )
        if draft.changes:
            _record(db, draft, reason)
        save_project_file(project, root / "project.json")


def record_library_update(
    root: Path, backup: Path, draft: ProtocolDraft | None, reason: str
) -> None:
    """Record a verified Library installation while its file rollback is still available."""
    with study_transaction(root) as db:
        _tables(db)
        row = _latest(db)
        if row is None:
            _record(
                db,
                _draft(
                    None,
                    _protocol(load_project_file(backup / "project.json")),
                    _assets(root, db, backup),
                ),
            )
            row = _latest(db)
        installed = _draft(
            row, _protocol(load_project_file(root / "project.json")), _assets(root, db)
        )
        if draft is not None and draft != installed:
            raise ValueError("The installed experiment differs from the reviewed protocol.")
        if installed.changes:
            _require_reason(root, installed, reason)
            _record(db, installed, reason)


def historical_draft(root: Path, version_id: str) -> ProtocolDraft:
    with study_transaction(root) as db:
        _tables(db)
        row = db.execute("SELECT * FROM versions WHERE version_id=?", (version_id,)).fetchone()
        if row is None:
            raise ValueError("This experiment version is unavailable.")
        head = _latest(db)
        assert head is not None
        draft = _draft(head, json.loads(row["protocol"]), json.loads(row["assets"]))
        working = _assets(root, db)
        active = json.loads(head["assets"])
        changes = list(draft.changes)
        for path in sorted(working.keys() | draft.assets.keys()):
            if working.get(path) != draft.assets.get(path) and active.get(path) == draft.assets.get(
                path
            ):
                changes.append(f"Restore saved stimulus: {path}")
        return ProtocolDraft(draft.previous, draft.protocol, draft.assets, tuple(changes), working)


def _materialize(source: Path, destination: Path, assets: dict[str, str]) -> None:
    destination.mkdir()
    for relative, digest in assets.items():
        target = resolve_project_relative_path(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        check = hashlib.sha256()
        blob = _object(source, digest)
        if not blob.is_file():
            raise ValueError(f"Saved stimulus is missing: {relative}")
        with blob.open("rb") as handle, target.open("xb") as output:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                check.update(block)
                output.write(block)
        if check.hexdigest() != digest:
            raise ValueError(f"Saved stimulus is damaged: {relative}")


def restore_version(root: Path, draft: ProtocolDraft, reason: str) -> ProjectFile:
    with study_transaction(root) as db:
        _check_current(db, draft)
        _require_reason(root, draft, reason)
        if draft.working_assets is not None and draft.working_assets != _assets(root, db):
            raise ValueError(
                "The working stimuli changed during review. Review this version again."
            )
        saved = load_project_file(root / "project.json")
        restored = ProjectFile.model_validate(
            {
                **draft.protocol,
                "meta": saved.meta,
                "manual_removed_electrodes": saved.manual_removed_electrodes,
            }
        )
        if not draft.changes:
            return saved
        with TemporaryDirectory(dir=database_path(root).parent) as work:
            stage = Path(work)
            _materialize(root, stage / "restored", draft.assets)
            active = resolve_project_relative_path(root, "stimuli")
            if active.exists():
                active.rename(stage / "original")
            try:
                (stage / "restored").rename(active)
                _record(db, draft, reason)
                save_project_file(restored, root / "project.json")
            except BaseException:
                if active.exists():
                    active.rename(stage / "unused")
                if (stage / "original").exists():
                    (stage / "original").rename(active)
                raise
        return restored


def keep_saved_stimuli(root: Path, draft: ProtocolDraft) -> Path | None:
    """Cancel an asset edit without losing either the saved or externally edited bytes."""
    with study_transaction(root) as db:
        _check_current(db, draft)
        row = _latest(db)
        assert row is not None
        saved = json.loads(row["assets"])
        if saved == draft.assets:
            return None
        active_assets = _assets(root, db)
        if active_assets == saved:
            return None
        if active_assets != draft.assets:
            raise ValueError("Stimuli changed again during review. Review the current files.")
        private = database_path(root).parent
        recovered = private / f"unapplied-stimuli-{uuid4().hex}"
        with TemporaryDirectory(dir=private) as work:
            stage = Path(work) / "saved"
            _materialize(root, stage, saved)
            active = root / "stimuli"
            if active.exists():
                active.rename(recovered)
            try:
                stage.rename(active)
            except BaseException:
                if recovered.exists():
                    recovered.rename(active)
                raise
        return recovered if recovered.exists() else None


def create_from_version(
    root: Path,
    parent: Path,
    name: str,
    draft: ProtocolDraft,
    *,
    source_version_id: str | None = None,
    restore_source_assets: bool = False,
) -> Path:
    """Materialize only authored inputs into an independently identified project."""
    source = load_project_file(root / "project.json")
    study_id = get_study(root).study_id
    version = current_version(root)
    if version is None or version.version_id != draft.previous:
        raise ValueError("The original study changed. Review it before saving a separate study.")
    slug = slugify_project_name(name)
    validate_project_id(slug)
    destination = parent / slug
    if not name.strip() or destination.exists():
        raise ValueError("Choose an unused name for the new study.")
    now = datetime.now(timezone.utc)
    metadata = source.meta.model_copy(
        update={"project_id": slug, "name": name.strip(), "created_at": now, "updated_at": now}
    )
    project = ProjectFile.model_validate({**draft.protocol, "meta": metadata})
    with TemporaryDirectory(dir=parent, prefix=".study-copy-") as work:
        stage = Path(work) / "study"
        stage.mkdir()
        _materialize(root, stage / "stimuli", draft.assets)
        manifest = stage / "stimuli" / "manifest.json"
        if manifest.exists():
            from fpvs_studio.preprocessing.manifest import (
                read_stimulus_manifest,
                write_stimulus_manifest,
            )

            original = read_stimulus_manifest(stage)
            write_stimulus_manifest(stage, original.model_copy(update={"project_id": slug}))
        for folder in ("runs", "logs", "cache"):
            (stage / folder).mkdir()
        save_project_file(project, stage / "project.json")
        prepare_change(stage, project)
        with study_transaction(stage) as db:
            parent_version = source_version_id or version.version_id
            with study_transaction(root) as source_db:
                ancestor = source_db.execute(
                    "SELECT label,saved_at FROM versions WHERE version_id=?",
                    (parent_version,),
                ).fetchone()
            if ancestor is None:
                raise ValueError("The source version is unavailable.")
            description = ancestor["label"] or ancestor["saved_at"][:19].replace("T", " ") + " UTC"
            origin = f"{source.meta.name}, version {description} [{study_id} / {parent_version}]"
            db.execute("UPDATE study SET created_from=?", (origin,))
        with study_transaction(root) as db:
            _check_current(db, draft)
            row = _latest(db)
            assert row is not None  # _check_current validated the version inside this transaction.
            original_assets = json.loads(row["assets"])
            if restore_source_assets and draft.assets != original_assets:
                if _assets(root, db) != draft.assets:
                    raise ValueError(
                        "The original stimuli changed during review. Review the study again."
                    )
                # The stimulus editor may have written candidate bytes before Save.
                # Put the original bytes back only after the independent copy is ready.
                with TemporaryDirectory(dir=database_path(root).parent) as swap_path:
                    swap = Path(swap_path)
                    active = root / "stimuli"
                    _materialize(root, swap / "saved", original_assets)
                    if active.exists():
                        active.rename(swap / "edited")
                    try:
                        (swap / "saved").rename(active)
                        stage.rename(destination)
                    except BaseException:
                        if active.exists():
                            active.rename(swap / "unused")
                        if (swap / "edited").exists():
                            (swap / "edited").rename(active)
                        raise
            else:
                stage.rename(destination)
    return destination
