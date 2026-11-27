"""Local protocol revisions, immutable stimulus contents and standalone study creation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import sys
from collections.abc import Callable, Iterator
from contextlib import ExitStack, closing
from dataclasses import dataclass, replace
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
from .serialization import load_project_file, read_json_file, save_project_file
from .study_lifecycle import (
    StudyState,
    _read_optional_study,
    database_path,
    get_study,
    read_study,
    study_transaction,
)

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
    # Setup review compares saved metadata before the author decides to capture any files.
    setup_metadata: tuple[str, str] | None = None
    observed_changes: tuple[tuple[str, str | None], ...] = ()
    working_protocol: dict | None = None
    candidate_root: Path | None = None
    media_changed: bool = False


class ProtocolReviewRequired(ValueError):
    """A changed protocol needs the author's recorded decision."""


StudyVisitLookup = Callable[[Path], dict[str, set[str]]]


def _require_reason(
    root: Path, draft: ProtocolDraft, reason: str, visits: StudyVisitLookup
) -> None:
    if draft.changes and not reason.strip() and visits(root):
        raise ProtocolReviewRequired("Review this protocol change and record a reason in Studio.")


def _tables(db: sqlite3.Connection) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS versions (
        version_id TEXT PRIMARY KEY, saved_at TEXT NOT NULL, label TEXT NOT NULL,
        reason TEXT NOT NULL, changes TEXT NOT NULL, protocol TEXT NOT NULL,
        assets TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS asset_cache (
        path TEXT PRIMARY KEY, stamp TEXT NOT NULL, digest TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS working_revisions (
        version_id TEXT PRIMARY KEY, saved_at TEXT NOT NULL, reason TEXT NOT NULL,
        changes TEXT NOT NULL, protocol TEXT NOT NULL, manifest TEXT NOT NULL,
        known_media TEXT NOT NULL,
        checkpoint TEXT, pending INTEGER NOT NULL)""")


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


def _has_table(db: sqlite3.Connection, name: str) -> bool:
    return bool(
        db.execute("SELECT 1 FROM sqlite_master WHERE name=? AND type='table'", (name,)).fetchone()
    )


def _active(db: sqlite3.Connection, *, metadata_only: bool = False) -> sqlite3.Row | None:
    # An unsnapshotted setup is active only until another checkpoint is recorded.
    fields = "version_id,saved_at,label,reason,changes"
    if _has_table(db, "working_revisions"):
        row = db.execute(
            "SELECT version_id,saved_at,'' AS label,reason,changes"
            + ("" if metadata_only else ",protocol,manifest,known_media,pending,NULL AS assets")
            + " FROM working_revisions WHERE checkpoint IS "
            "(SELECT version_id FROM versions ORDER BY rowid DESC LIMIT 1) "
            "ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        if row is not None:
            return cast(sqlite3.Row, row)
    if not _has_table(db, "versions"):
        return None
    return cast(
        sqlite3.Row | None,
        db.execute(
            f"SELECT {fields if metadata_only else '*'} FROM versions ORDER BY rowid DESC LIMIT 1"
        ).fetchone(),
    )


def _read_active(root: Path, *, metadata_only: bool = False) -> sqlite3.Row | None:
    path = database_path(root)
    if not path.is_file():
        return None
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA query_only=ON")
        db.row_factory = sqlite3.Row
        return _active(db, metadata_only=metadata_only)


def current_version(root: Path) -> StudyVersion | None:
    """Identity for the current as-run setup, including one saved without a checkpoint."""
    row = _read_active(root, metadata_only=True)
    return _version(row) if row else None


def list_versions(root: Path) -> list[StudyVersion]:
    path = database_path(root)
    if not path.is_file():
        return []
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        if not _has_table(db, "versions"):
            return []
        return [
            _version(row)
            for row in db.execute(
                "SELECT version_id,saved_at,label,reason,changes FROM versions ORDER BY rowid"
            )
        ]


def _saved_version_count(db: sqlite3.Connection) -> int:
    if not _has_table(db, "versions"):
        return 0
    return int(db.execute("SELECT COUNT(*) FROM versions").fetchone()[0])


def _saved_version_count_from_path(path: Path) -> int:
    if not path.is_file():
        return 0
    with closing(sqlite3.connect(path)) as db:
        return _saved_version_count(db)


def saved_version_count(root: Path) -> int:
    return _saved_version_count_from_path(database_path(root))


def read_study_and_saved_version_count(root: Path) -> tuple[StudyState | None, int]:
    """Read the collection state and saved version count for project discovery."""
    path = database_path(root)
    try:
        before = path.stat()
    except FileNotFoundError:
        return None, saved_version_count(root)
    except (OSError, ValueError):
        return read_study(root), saved_version_count(root)

    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA query_only=ON")
        state = _read_optional_study(db)
        # Resolve the path again at the version read boundary. Each SELECT runs
        # independently so commits made between the reads remain visible.
        current = database_path(root)
        if current == path and before.st_ino:
            try:
                after = current.stat()
            except FileNotFoundError:
                return state, 0
            except (OSError, ValueError):
                pass
            else:
                if stat.S_ISREG(after.st_mode) and os.path.samestat(before, after):
                    return state, _saved_version_count(db)
    return state, _saved_version_count_from_path(current)


def has_pending_setup_save(root: Path) -> bool:
    """An inline protected edit was reviewed and still awaits the final checkpoint decision."""
    path = database_path(root)
    if not path.is_file():
        return False
    with closing(sqlite3.connect(path)) as db:
        if not _has_table(db, "working_revisions"):
            return False
        row = db.execute(
            "SELECT pending FROM working_revisions WHERE checkpoint IS "
            "(SELECT version_id FROM versions ORDER BY rowid DESC LIMIT 1) "
            "ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        return bool(row and row[0])


def read_version_protocol(root: Path, version_id: str) -> dict:
    path = database_path(root)
    if path.is_file():
        with closing(sqlite3.connect(path)) as db:
            if _has_table(db, "versions"):
                row = db.execute(
                    "SELECT protocol FROM versions WHERE version_id=?", (version_id,)
                ).fetchone()
                if row is not None:
                    return cast(dict, json.loads(row[0]))
    raise ValueError("This experiment version is unavailable.")


def list_working_revisions(root: Path) -> list[StudyVersion]:
    path = database_path(root)
    if not path.is_file():
        return []
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        if not _has_table(db, "working_revisions"):
            return []
        return [
            _version(row)
            for row in db.execute(
                "SELECT version_id,saved_at,'' AS label,reason,changes FROM working_revisions "
                "ORDER BY rowid"
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


def stage_saved_stimulus(root: Path, relative: str, digest: str, target: Path) -> bool:
    """Stage verified checkpoint bytes at a new caller-owned path if captured locally."""

    blob = _object(root, digest)
    if not blob.is_file():
        return False
    _copy_verified_stimulus(blob, target, relative, digest)
    return True


def _copy_verified_stimulus(source: Path, target: Path, relative: str, digest: str) -> None:
    check = hashlib.sha256()
    with source.open("rb") as handle, target.open("xb") as output:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            check.update(block)
            output.write(block)
    if check.hexdigest() != digest:
        raise ValueError(f"Saved stimulus is damaged: {relative}")


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


def _verify_asset_bytes(path: Path, relative: str, expected: str, size: int) -> os.stat_result:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
        current = _regular(path)
        if (
            digest.hexdigest() != expected
            or current.st_size != size
            or not os.path.samestat(current, os.fstat(source.fileno()))
        ):
            raise ValueError(f"Stimulus changed during review: {relative}")
    return current


def _capture_file(
    root: Path, path: Path, relative: str, db: sqlite3.Connection, rollback: ExitStack | None
) -> str:
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
            size = target.tell()
        key = digest.hexdigest()
        after = _regular(path)
        if not stat.S_ISREG(after.st_mode) or after.st_size != size:
            raise ValueError(f"Stimulus changed during review: {relative}")
        after_stamp = _asset_stamp(path, after)
        if stamp is None or after_stamp != stamp or info.st_ctime_ns != after.st_ctime_ns:
            # Reading a cloud-backed file can advance its Windows change time.
            # Verify the captured bytes before using the new cache stamp.
            verified = _verify_asset_bytes(path, relative, key, size)
            final_stamp = _asset_stamp(path, verified)
            stamp = final_stamp if final_stamp == after_stamp else None
        target_path = _object(root, key)
        if not target_path.exists():
            os.replace(temp, target_path)
            if rollback is not None:
                rollback.callback(target_path.unlink, missing_ok=True)
        db.execute(
            "INSERT OR REPLACE INTO asset_cache VALUES (?,?,?)", (relative, stamp or "", key)
        )
        return key
    finally:
        temp.unlink(missing_ok=True)


def _stimulus_files(root: Path) -> Iterator[tuple[str, Path]]:
    folder = filesystem_path(root / "stimuli")
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
            if not stat.S_ISREG(_regular(path).st_mode):
                raise ValueError(f"Expected a regular stimulus file: {relative}")
            yield relative, path


def _read_assets(root: Path) -> dict[str, str]:
    """Inventory working files for an explicit restore or fork without archiving them."""
    assets = {}
    for relative, path in _stimulus_files(root):
        before = _regular(path)
        stamp = _asset_stamp(path, before)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        key = digest.hexdigest()
        if stamp is None or stamp != _asset_stamp(path, _regular(path)):
            _verify_asset_bytes(path, relative, key, before.st_size)
        assets[relative] = key
    return assets


def _assets(
    root: Path,
    db: sqlite3.Connection,
    source: Path | None = None,
    *,
    rollback: ExitStack | None = None,
) -> dict[str, str]:
    inventory = {
        relative: _capture_file(root, path, relative, db, rollback)
        for relative, path in _stimulus_files(source or root)
    }
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
    return _normalized_manifest(_object(root, digest))


def _normalized_manifest(path: Path) -> dict:
    data = json.loads(path.read_bytes())
    data.pop("generated_at", None)
    for entry in data.get("sets", []):
        for asset in entry.get("assets", []):
            asset["source"].pop("imported_at", None)
            for derivative in asset.get("derivatives", []):
                derivative.pop("created_at", None)
    return cast(dict, data)


def _manifest_json(root: Path) -> str:
    manifest = resolve_project_relative_path(root, "stimuli/manifest.json")
    data = _normalized_manifest(manifest) if manifest.is_file() else None
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _saved_manifest(root: Path, row: sqlite3.Row) -> str:
    if "manifest" in row.keys():
        return str(row["manifest"])
    digest = json.loads(row["assets"]).get("manifest.json")
    data = _manifest_content(root, digest) if digest else None
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _declared_media(manifest: str) -> dict[str, str]:
    data = json.loads(manifest) or {}
    return {
        image["relative_path"]: image["sha256"]
        for pool in data.get("sets", [])
        for asset in pool["assets"]
        for image in (asset["source"], *asset["derivatives"])
        if image.get("sha256")
    }


def _known_media(row: sqlite3.Row) -> dict[str, str]:
    if row["assets"] is None:
        return cast(dict[str, str], json.loads(row["known_media"]))
    return {
        f"stimuli/{path}": digest
        for path, digest in json.loads(row["assets"]).items()
        if path != "manifest.json"
    }


def accepted_stimulus_digests(root: Path) -> dict[str, str]:
    """Return known project-relative media identities without inspecting working media."""
    row = _read_active(root)
    return _known_media(row) if row else {}


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
    row: sqlite3.Row | None,
    protocol: dict[str, Any],
    assets: dict[str, str],
    *,
    previous_assets: dict[str, str] | None = None,
    previous_protocol: dict | None = None,
) -> ProtocolDraft:
    if row is None:
        return ProtocolDraft(None, protocol, assets, ("First saved protocol",))
    old_assets = previous_assets if previous_assets is not None else json.loads(row["assets"])
    previous = previous_protocol if previous_protocol is not None else json.loads(row["protocol"])
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
    changes.extend(_media_changes(old_assets, assets))
    return ProtocolDraft(row["version_id"], protocol, assets, tuple(changes))


def _media_changes(old: dict[str, str], new: dict[str, str]) -> list[str]:
    changes = []
    for path in sorted(old.keys() | new.keys()):
        if old.get(path) != new.get(path):
            action = "added" if path not in old else "removed" if path not in new else "replaced"
            changes.append(f"Stimulus {action}: {path}")
    return changes


def _record_working(
    db: sqlite3.Connection,
    draft: ProtocolDraft,
    manifest: str,
    reason: str,
    known_media: dict[str, str],
    *,
    pending: bool = False,
) -> None:
    db.execute(
        "INSERT INTO working_revisions VALUES (?,?,?,?,?,?,?,"
        "(SELECT version_id FROM versions ORDER BY rowid DESC LIMIT 1),?)",
        (
            str(uuid4()),
            datetime.now(timezone.utc).isoformat(),
            reason.strip(),
            json.dumps(draft.changes),
            json.dumps(draft.protocol),
            manifest,
            json.dumps(known_media),
            pending,
        ),
    )


def ensure_working_setup(root: Path) -> None:
    """Retain the accepted model and manifest before a legacy launch or an editor writes."""
    if not filesystem_path(root / "project.json").is_file() or current_version(root) is not None:
        return
    with study_transaction(root) as db:
        _tables(db)
        if _active(db) is None:
            protocol = _protocol(load_project_file(root / "project.json"))
            manifest = _manifest_json(root)
            _record_working(db, _draft(None, protocol, {}), manifest, "", _declared_media(manifest))


def prepare_setup_change(
    root: Path,
    project: ProjectFile,
    *,
    transient_session_seed: bool = False,
    stimuli_changed: bool = False,
    include_run_observations: bool = True,
) -> ProtocolDraft:
    """Review authored fields and stimulus declarations without enumerating stimulus files."""
    row = _read_active(root)
    saved = _protocol(load_project_file(root / "project.json"))
    candidate = _protocol(project)
    manifest = _manifest_json(root)
    manifest_changed = False
    if row is None:
        changes = _differences(saved, candidate)
        draft = ProtocolDraft(None, candidate, {}, tuple(changes))
    else:
        draft = _draft(row, candidate, {}, previous_assets={})
        changes = list(draft.changes)
        previous_manifest = _saved_manifest(root, row)
        manifest_changed = previous_manifest != manifest
        if manifest_changed:
            old, new = _declared_media(previous_manifest), _declared_media(manifest)
            changes.extend(_media_changes(old, new) or ["Stimulus declarations changed"])
    if row is not None and include_run_observations:
        from .run_stimulus_identity import pending_run_stimulus_changes

        pending = pending_run_stimulus_changes(root, row["version_id"])
        changes.extend(
            f"Stimulus {'removed' if digest is None else 'changed'}: {path}"
            for path, digest in sorted(pending.items())
        )
        draft = replace(draft, observed_changes=tuple(sorted(pending.items())))
    if stimuli_changed:
        changes.append("Stimulus files changed")
    if transient_session_seed:
        changes = [c for c in changes if not c.startswith("settings / session / session_seed:")]
    return replace(
        draft,
        changes=tuple(changes),
        setup_metadata=(json.dumps(saved, sort_keys=True), manifest),
        media_changed=manifest_changed or stimuli_changed or bool(draft.observed_changes),
    )


def _validate_setup_review(root: Path, draft: ProtocolDraft) -> str:
    from .run_stimulus_identity import pending_run_stimulus_changes

    saved = _protocol(load_project_file(root / "project.json"))
    manifest = _manifest_json(root)
    pending = pending_run_stimulus_changes(root, draft.previous) if draft.previous else {}
    if (
        draft.setup_metadata != (json.dumps(saved, sort_keys=True), manifest)
        or dict(draft.observed_changes) != pending
    ):
        raise ValueError("The experiment changed after review. Review its settings again.")
    return manifest


def _proposed_media(
    root: Path, active: sqlite3.Row | None, manifest: str, draft: ProtocolDraft
) -> dict[str, str]:
    from .run_stimulus_identity import observed_run_stimuli

    old = _declared_media(_saved_manifest(root, active)) if active is not None else {}
    new = _declared_media(manifest)
    known = _known_media(active) if active is not None else {}
    if active is not None:
        known.update(observed_run_stimuli(root, active["version_id"]))
    for path in old.keys() | new.keys():
        if old.get(path) != new.get(path):
            if path in new:
                known[path] = new[path]
            else:
                known.pop(path, None)
    for path, digest in draft.observed_changes:
        if digest is None:
            known.pop(path, None)
        else:
            known[path] = digest
    return known


def commit_setup_change(
    root: Path,
    project: ProjectFile,
    draft: ProtocolDraft,
    reason: str,
    visits: StudyVisitLookup,
    *,
    save_version: bool,
    completed_setup: bool = True,
) -> None:
    """Save an accepted setup. Only the first or explicitly requested checkpoint captures bytes."""
    discovered: dict[str, str | None] = {}
    with study_transaction(root) as db, ExitStack() as rollback:
        _tables(db)
        _check_current(db, draft)
        _require_reason(root, draft, reason, visits)
        manifest = _validate_setup_review(root, draft)
        if _protocol(project) != draft.protocol:
            raise ValueError("The experiment changed after review. Review its settings again.")
        active = _active(db)
        pending = active is not None and "pending" in active.keys() and active["pending"]
        if completed_setup and (
            _latest(db) is None or ((draft.changes or pending) and save_version)
        ):
            assets = _assets(root, db, rollback=rollback)
            actual = {f"stimuli/{p}": key for p, key in assets.items() if p != "manifest.json"}
            expected = _proposed_media(root, active, manifest, draft)
            unexplained = {
                path: actual.get(path)
                for path, digest in expected.items()
                if actual.get(path) != digest
            }
            if unexplained and visits(root):
                discovered.update(unexplained)
            for path, reviewed_digest in draft.observed_changes:
                if (
                    path.startswith("stimuli/")
                    and assets.get(path.removeprefix("stimuli/")) != reviewed_digest
                ):
                    discovered[path] = actual.get(path)
            changes = draft.changes or (
                tuple(json.loads(active["changes"]))
                if pending and active
                else ("First saved protocol",)
            )
            if discovered:
                from .run_stimulus_identity import record_pending_stimulus_changes

                if active is None:
                    saved = _protocol(load_project_file(root / "project.json"))
                    _record_working(
                        db, _draft(None, saved, {}), manifest, "", _declared_media(manifest)
                    )
                    active = _active(db)
                    assert active is not None
                record_pending_stimulus_changes(
                    db, active["version_id"], dict(draft.observed_changes) | discovered
                )
            else:
                _record(
                    db,
                    replace(draft, assets=assets, changes=changes),
                    reason or (active["reason"] if pending and active else ""),
                )
        elif draft.changes:
            known = _proposed_media(root, active, manifest, draft)
            needs_decision = not completed_setup
            if needs_decision and pending:
                baseline = db.execute(
                    "SELECT *,NULL AS assets FROM working_revisions "
                    "WHERE pending=0 AND checkpoint IS "
                    "(SELECT version_id FROM versions ORDER BY rowid DESC LIMIT 1) "
                    "ORDER BY rowid DESC LIMIT 1"
                ).fetchone() or _latest(db)
                if baseline is not None:
                    needs_decision = (
                        draft.protocol != json.loads(baseline["protocol"])
                        or manifest != _saved_manifest(root, baseline)
                        or known != _known_media(baseline)
                    )
            _record_working(db, draft, manifest, reason, known, pending=needs_decision)
        elif pending and completed_setup:
            db.execute(
                "UPDATE working_revisions SET pending=0 WHERE version_id=?", (draft.previous,)
            )
        if not discovered:
            save_project_file(project, root / "project.json")
            rollback.pop_all()
    if discovered:
        raise ProtocolReviewRequired(
            "Stimulus files changed after review. Save again to review the changed files."
        )


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


def _record_initial_version(root: Path, db: sqlite3.Connection, assets: dict[str, str]) -> None:
    from fpvs_studio.preprocessing.models import (
        DerivedImageRecord,
        SourceImageRecord,
        StimulusManifest,
    )

    saved = _protocol(load_project_file(root / "project.json"))
    baseline = assets.copy()
    # A legacy manifest can identify an original that was replaced before migration.
    # Preserve that identity so the next review reports the replacement.
    if manifest_digest := assets.get("manifest.json"):
        manifest = read_json_file(_object(root, manifest_digest), StimulusManifest)
        for pool in manifest.sets:
            for asset in pool.assets:
                images: tuple[SourceImageRecord | DerivedImageRecord, ...] = (
                    asset.source,
                    *asset.derivatives,
                )
                for image in images:
                    digest = image.sha256 or ""
                    if image.relative_path.startswith("stimuli/") and re.fullmatch(
                        r"[0-9a-fA-F]{64}", digest
                    ):
                        baseline[image.relative_path.removeprefix("stimuli/")] = digest.lower()
    _record(db, _draft(None, saved, baseline))


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
        row = _active(db)
        if row is None:
            _record_initial_version(root, db, _assets(root, db))
            row = _latest(db)
        before = (
            _assets(root, db)
            if row is not None and row["assets"] is None and candidate_root
            else None
        )
        assets = _assets(root, db, candidate_root)
        protocol = _protocol(project)
        if row is not None and row["assets"] is None and before is None:
            before = {p.removeprefix("stimuli/"): digest for p, digest in _known_media(row).items()}
            if _saved_manifest(root, row) == _manifest_json(root) and "manifest.json" in assets:
                before["manifest.json"] = assets["manifest.json"]
        draft = _draft(row, protocol, assets, previous_assets=before)
        if transient_session_seed:
            # A legacy launch may select a fresh seed without an authored edit.
            changes = tuple(
                c for c in draft.changes if not c.startswith("settings / session / session_seed:")
            )
            return ProtocolDraft(draft.previous, protocol, assets, changes)
        return draft


def _check_current(db: sqlite3.Connection, draft: ProtocolDraft) -> None:
    row = _active(db, metadata_only=True)
    if (row["version_id"] if row else None) != draft.previous:
        raise ValueError(
            "The saved version changed during review. Reopen the project and review again."
        )


def commit_change(
    root: Path, project: ProjectFile, draft: ProtocolDraft, reason: str, visits: StudyVisitLookup
) -> None:
    with study_transaction(root) as db:
        _check_current(db, draft)
        _require_reason(root, draft, reason, visits)
        if _protocol(project) != draft.protocol or _assets(root, db) != draft.assets:
            raise ValueError(
                "The experiment changed after review. Review its settings and stimuli again."
            )
        if draft.changes:
            _record(db, draft, reason)
        save_project_file(project, root / "project.json")


def prepare_library_update(
    root: Path,
    candidate_root: Path,
    project: ProjectFile,
    current_assets: dict[str, str],
    candidate_assets: dict[str, str],
) -> ProtocolDraft:
    """Review a verified staged installation using the Library's file digests."""
    active = _read_active(root)
    protocol = _protocol(project)
    if active is None:
        previous = _protocol(load_project_file(root / "project.json"))
        draft = ProtocolDraft(None, protocol, {}, tuple(_differences(previous, protocol)))
        manifest = _manifest_json(root)
        known = {}
    else:
        draft = _draft(active, protocol, {}, previous_assets={})
        manifest = _saved_manifest(root, active)
        known = _known_media(active)
    before = current_assets.copy()
    before.update(
        {p.removeprefix("stimuli/"): key for p, key in known.items() if p.startswith("stimuli/")}
    )
    after = candidate_assets.copy()
    if manifest == _manifest_json(candidate_root):
        before.pop("manifest.json", None)
        after.pop("manifest.json", None)
    changes = draft.changes + tuple(_media_changes(before, after))
    return replace(draft, assets=candidate_assets, changes=changes, candidate_root=candidate_root)


def record_library_update(
    root: Path,
    draft: ProtocolDraft,
    installed_assets: dict[str, str],
    reason: str,
    visits: StudyVisitLookup,
) -> None:
    """Accept installed bytes as a working revision while the Library backup is available."""
    with study_transaction(root) as db:
        _tables(db)
        _check_current(db, draft)
        _require_reason(root, draft, reason, visits)
        if draft.protocol != _protocol(load_project_file(root / "project.json")) or (
            draft.assets != installed_assets
        ):
            raise ValueError("The installed experiment differs from the reviewed protocol.")
        if draft.changes or draft.previous is None:
            known = {
                f"stimuli/{p}": digest
                for p, digest in installed_assets.items()
                if p != "manifest.json"
            }
            _record_working(
                db, draft, _manifest_json(root), reason, known, pending=bool(draft.changes)
            )


def historical_draft(root: Path, version_id: str) -> ProtocolDraft:
    with study_transaction(root) as db:
        _tables(db)
        row = db.execute("SELECT * FROM versions WHERE version_id=?", (version_id,)).fetchone()
        if row is None:
            raise ValueError("This experiment version is unavailable.")
        head = _active(db)
        assert head is not None
        working = _read_assets(root)
        working_protocol = _protocol(load_project_file(root / "project.json"))
        saved_assets = json.loads(row["assets"])
        compared = working.copy()
        if (
            "manifest.json" in compared
            and "manifest.json" in saved_assets
            and _manifest_json(root) == _saved_manifest(root, row)
        ):
            compared["manifest.json"] = saved_assets["manifest.json"]
        draft = _draft(
            head,
            json.loads(row["protocol"]),
            saved_assets,
            previous_assets=compared,
            previous_protocol=working_protocol,
        )
        if not draft.changes and (
            json.loads(head["protocol"]) != draft.protocol
            or (head["assets"] is None and head["version_id"] != version_id)
        ):
            draft = replace(
                draft, changes=("Restore the selected checkpoint as the current setup",)
            )
        return replace(draft, working_assets=working, working_protocol=working_protocol)


def _materialize(
    source: Path,
    destination: Path,
    assets: dict[str, str],
    *,
    candidate_root: Path | None = None,
    available_assets: dict[str, str] | None = None,
) -> None:
    destination.mkdir()
    for relative, digest in assets.items():
        target = resolve_project_relative_path(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        live = candidate_root
        if available_assets is not None and available_assets.get(relative) == digest:
            live = source
        blob = (
            resolve_project_relative_path(live, f"stimuli/{relative}")
            if live is not None
            else _object(source, digest)
        )
        if not blob.is_file():
            raise ValueError(f"Saved stimulus is missing: {relative}")
        if live is not None:
            _regular(blob)
        _copy_verified_stimulus(blob, target, relative, digest)


def restore_version(
    root: Path, draft: ProtocolDraft, reason: str, visits: StudyVisitLookup
) -> ProjectFile:
    with study_transaction(root) as db:
        _check_current(db, draft)
        _require_reason(root, draft, reason, visits)
        if draft.working_assets is not None and draft.working_assets != _read_assets(root):
            raise ValueError(
                "The working stimuli changed during review. Review this version again."
            )
        saved = load_project_file(root / "project.json")
        if draft.working_protocol is not None and draft.working_protocol != _protocol(saved):
            raise ValueError(
                "The working settings changed during review. Review this version again."
            )
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


def _original_assets(root: Path, row: sqlite3.Row, candidate: dict[str, str]) -> dict[str, str]:
    if row["assets"] is not None:
        return cast(dict[str, str], json.loads(row["assets"]))
    # Earlier working revisions retain identities, not every stimulus byte. Keep other
    # working files, and restore known original content only from verified objects.
    from .run_stimulus_identity import observed_run_stimuli

    original = candidate.copy()
    known = _known_media(row) | observed_run_stimuli(root, row["version_id"])
    for path, digest in known.items():
        if path.startswith("stimuli/"):
            original[path.removeprefix("stimuli/")] = digest
    manifest = row["manifest"]
    if manifest != _manifest_json(root):
        if json.loads(manifest) is None:
            original.pop("manifest.json", None)
        else:
            from fpvs_studio.preprocessing.models import StimulusManifest

            content = StimulusManifest.model_validate_json(manifest).model_dump_json().encode()
            digest = hashlib.sha256(content).hexdigest()
            target = _object(root, digest)
            target.parent.mkdir(exist_ok=True)
            if not target.exists():
                target.write_bytes(content)
            original["manifest.json"] = digest
    return original


def keep_saved_stimuli(root: Path, draft: ProtocolDraft) -> Path | None:
    """Cancel an asset edit without losing either the saved or externally edited bytes."""
    with study_transaction(root) as db:
        _check_current(db, draft)
        row = _active(db)
        if row is None:
            return None
        if draft.setup_metadata is not None:
            _validate_setup_review(root, draft)
            if not draft.media_changed:
                return None
        active_assets = _read_assets(root)
        saved = _original_assets(root, row, active_assets)
        if active_assets == saved:
            return None
        if draft.setup_metadata is None and active_assets != draft.assets:
            raise ValueError("Stimuli changed again during review. Review the current files.")
        private = database_path(root).parent
        recovered = private / f"unapplied-stimuli-{uuid4().hex}"
        with TemporaryDirectory(dir=private) as work:
            stage = Path(work) / "saved"
            _materialize(root, stage, saved, available_assets=active_assets)
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
    if (version.version_id if version else None) != draft.previous:
        raise ValueError("The original study changed. Review it before saving a separate study.")
    slug = slugify_project_name(name)
    validate_project_id(slug)
    destination = parent / slug
    if not name.strip() or destination.exists():
        raise ValueError("Choose an unused name for the new study.")
    if draft.setup_metadata is not None:
        with study_transaction(root) as db:
            _check_current(db, draft)
            _validate_setup_review(root, draft)
            draft = replace(draft, assets=_read_assets(root), candidate_root=root)
    now = datetime.now(timezone.utc)
    metadata = source.meta.model_copy(
        update={"project_id": slug, "name": name.strip(), "created_at": now, "updated_at": now}
    )
    project = ProjectFile.model_validate({**draft.protocol, "meta": metadata})
    with TemporaryDirectory(dir=parent, prefix=".study-copy-") as work:
        stage = Path(work) / "study"
        stage.mkdir()
        _materialize(root, stage / "stimuli", draft.assets, candidate_root=draft.candidate_root)
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
        ensure_working_setup(stage)
        with study_transaction(stage) as db:
            parent_version = source_version_id or (version.version_id if version else None)
            with study_transaction(root) as source_db:
                _tables(source_db)
                ancestor = source_db.execute(
                    "SELECT label,saved_at FROM versions WHERE version_id=? "
                    "UNION ALL SELECT '',saved_at FROM working_revisions WHERE version_id=?",
                    (parent_version, parent_version),
                ).fetchone()
            if ancestor is None and parent_version is not None:
                raise ValueError("The source version is unavailable.")
            origin = f"{source.meta.name}, working setup [{study_id}]"
            if ancestor is not None:
                description = (
                    ancestor["label"] or ancestor["saved_at"][:19].replace("T", " ") + " UTC"
                )
                origin = (
                    f"{source.meta.name}, version {description} [{study_id} / {parent_version}]"
                )
            db.execute("UPDATE study SET created_from=?", (origin,))
        with study_transaction(root) as db:
            _check_current(db, draft)
            row = _active(db)
            if draft.setup_metadata is not None:
                _validate_setup_review(root, draft)
                if not draft.media_changed:
                    restore_source_assets = False
            if draft.working_protocol is not None and draft.working_protocol != _protocol(
                load_project_file(root / "project.json")
            ):
                raise ValueError(
                    "The working settings changed during review. Review this version again."
                )
            original_assets = draft.assets
            if restore_source_assets and row is not None:
                if _read_assets(root) != draft.assets:
                    raise ValueError(
                        "The original stimuli changed during review. Review the study again."
                    )
                original_assets = _original_assets(root, row, draft.assets)
            if restore_source_assets and draft.assets != original_assets:
                # The stimulus editor may have written candidate bytes before Save.
                # Put the original bytes back only after the independent copy is ready.
                with TemporaryDirectory(dir=database_path(root).parent) as swap_path:
                    swap = Path(swap_path)
                    active = root / "stimuli"
                    _materialize(
                        root, swap / "saved", original_assets, available_assets=draft.assets
                    )
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
