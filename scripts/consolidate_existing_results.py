"""Archive redundant existing output only after a verified unified workbook is staged.

Dry-run is the default. Use the Studio Python environment with PYTHONPATH=src.
The archive retains byte-for-byte originals; canonical research logs and inputs stay put.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import load_workbook

from fpvs_studio.core.paths import resolve_project_relative_path, to_project_relative_posix
from fpvs_studio.core.serialization import replace_file_atomically
from fpvs_studio.runtime import session_export
from fpvs_studio.runtime.reporting_lock import project_reporting_lock

_WORKBOOK = "logs/participant_summary.xlsx"
LOGGER = logging.getLogger(__name__)
_ARCHIVES = "logs/.output-archives"
_GENERATED_SHEETS = {
    "Participant Summary", "Demographics", "Fixation by Condition", "Fixation Responses",
    "Task Answers", "Results Notes", "Full Text",
}
_REQUIRED_SHEETS = {
    "Participant Summary", "Demographics", "Fixation by Condition", "Fixation Responses",
    "Task Answers", "Results Notes",
}
_DETAILED_CSV_NAMES = {
    "participant_metadata.csv", "conditions.csv", "events.csv", "fixation_events.csv",
    "responses.csv", "frame_intervals.csv", "trigger_log.csv", "task_responses.csv",
    "attentional_blink_events.csv", "attentional_blink_bursts_v1.csv",
    "attentional_blink_stream_events_v1.csv", "masking_trials_v1.csv", "masking_trials_v2.csv",
    "masking_scene_events_v1.csv",
}


@dataclass(frozen=True)
class SourceFile:
    path: str
    size: int
    sha256: str
    rows: int | None = None


@dataclass(frozen=True)
class ProjectInventory:
    project_root: Path
    sources: tuple[SourceFile, ...]
    preserved_other_csvs: int


@dataclass(frozen=True)
class ConsolidationResult:
    project: str
    applied: bool
    archived_files: int
    retired_csvs: int
    archived_bytes: int
    archive: str | None = None
    retired_workbooks: int = 0


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _local(root: Path, relative: str) -> Path:
    path = resolve_project_relative_path(root, relative)
    lexical = root
    for part in Path(relative).parts:
        lexical = lexical / part
        if lexical.is_symlink() or (lexical.exists()
                and getattr(lexical.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("Redirected output cannot be consolidated.")
    return path


def _csv_rows(path: Path) -> int:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        next(reader, None)
        return sum(1 for _ in reader)


def _summary_cell(header: str, value: object) -> str:
    if value is None or value == "":
        return ""
    numeric = {"Age", "Total Targets", "Hits", "False Alarms", "Session Number",
               "Mean Accuracy Across All Conditions (%)",
               "Mean Reaction Time Across All Conditions (ms)"}
    if header in numeric:
        try:
            number = Decimal(str(value))
            if number.is_finite():
                return str(number.normalize())
        except InvalidOperation:
            pass
    return str(value)


def _covered_backup(root: Path, path: Path) -> bool:
    """Require every old column and row to be an exact subset of canonical summary rows."""

    if path.suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            values = list(csv.reader(stream, strict=True))
    else:
        workbook = load_workbook(path, read_only=True, data_only=False)
        try:
            if workbook.sheetnames != ["Participant Summary"]:
                return False
            values = [list(row) for row in
                      workbook["Participant Summary"].iter_rows(values_only=True)]
        finally:
            workbook.close()
    return _summary_values_covered(root, values)


def _summary_values_covered(root: Path, values: list[list[Any]]) -> bool:
    history = _local(root, "logs/session_condition_history.csv")
    rows = session_export._read_csv_dict_rows(history) if history.is_file() else []
    expected = session_export._participant_summary_rows(root, rows)
    header = session_export.PARTICIPANT_SUMMARY_HEADER
    if not values or not values[0] or set(values[0]) - set(header):
        return False
    old_header = values[0]
    if len(old_header) != len(set(old_header)):
        return False
    indices = [header.index(column) for column in old_header]
    available = Counter(tuple(_summary_cell(column, row[index])
                              for column, index in zip(old_header, indices, strict=True))
                        for row in expected)
    required = Counter(tuple(_summary_cell(column, value)
                             for column, value in zip(old_header, row, strict=True))
                       for row in values[1:]
                       if any(value is not None and value != "" for value in row))
    return not (required - available)


def inventory_project(project_root: Path) -> ProjectInventory:
    """Read only file identity and table sizes, never print participant values."""

    root = project_root.resolve(strict=True)
    if not (root / "project.json").is_file():
        raise ValueError("Consolidation requires a project.json in the selected project.")
    candidates = [_WORKBOOK, "logs/participant_summary.csv", "post_condition_responses.csv"]
    backup_candidates = []
    backup_root = _local(root, "backups")
    if backup_root.is_dir():
        backup_candidates.extend(backup_root.glob("*/logs/participant_summary.*"))
    log_root = _local(root, "logs")
    if log_root.is_dir():
        backup_candidates.extend(log_root.glob("backup-*/participant_summary.*"))
    for path in backup_candidates:
        path = _local(root, to_project_relative_posix(root, path))
        if path.suffix in {".xlsx", ".csv"} and _covered_backup(root, path):
            candidates.append(to_project_relative_posix(root, path))
    run_root = _local(root, "runs")
    other_csvs = 0
    if run_root.is_dir():
        for directory, folders, filenames in os.walk(run_root, followlinks=False):
            folders[:] = [name for name in folders if not (Path(directory) / name).is_symlink()]
            for name in filenames:
                if not name.lower().endswith(".csv"):
                    continue
                path = Path(directory) / name
                if name in _DETAILED_CSV_NAMES:
                    candidates.append(to_project_relative_posix(root, path))
                else:
                    other_csvs += 1
    sources = []
    for relative in sorted(set(candidates)):
        path = _local(root, relative)
        if path.is_file():
            sources.append(SourceFile(relative, path.stat().st_size, _digest(path),
                                      _csv_rows(path) if path.suffix == ".csv" else None))
    return ProjectInventory(root, tuple(sources), other_csvs)


def _assert_unchanged(inventory: ProjectInventory) -> None:
    for source in inventory.sources:
        path = _local(inventory.project_root, source.path)
        if (not path.is_file() or path.stat().st_size != source.size
                or _digest(path) != source.sha256):
            raise ValueError("A source output changed during consolidation; no cleanup is safe.")


def _assert_generated_workbook(root: Path, path: Path) -> None:
    if not path.is_file():
        return
    workbook = load_workbook(path, data_only=False)
    try:
        if set(workbook.sheetnames) - _GENERATED_SHEETS:
            raise ValueError("Custom workbook sheets require review; the workbook was preserved.")
        if "Participant Summary" not in workbook:
            raise ValueError("Unknown summary sheet; the workbook was preserved.")
        if "Full Text" in workbook:
            from fpvs_studio.runtime.workbook_layout import _FULL_TEXT_MARKER

            header = [cell.value for cell in workbook["Full Text"][1]]
            if (header != ["Sheet", "Cell", "Part", "Parts", "Text"]
                    or workbook["Full Text"].sheet_properties.codeName != _FULL_TEXT_MARKER):
                raise ValueError("Custom Full Text sheet requires review; workbook preserved.")
        values = [list(row) for row in workbook["Participant Summary"].iter_rows(values_only=True)]
        if not _summary_values_covered(root, values):
            raise ValueError(
                "Unmatched historical summary rows require review; workbook preserved."
            )
        if workbook._external_links:
            raise ValueError("Linked workbook content requires review; the workbook was preserved.")
        for worksheet in workbook:
            if worksheet._charts or worksheet._images:
                raise ValueError("Workbook drawings require review; the workbook was preserved.")
            if any(cell.data_type == "f" for row in worksheet for cell in row):
                raise ValueError("Workbook formulas require review; the workbook was preserved.")
    finally:
        workbook.close()


def _workbook_parity(path: Path) -> dict[str, dict[str, Any]]:
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        if not _REQUIRED_SHEETS.issubset(workbook.sheetnames):
            raise ValueError("The unified workbook is missing required research sheets.")
        result = {}
        for worksheet in workbook:
            digest = hashlib.sha256()
            serialized_rows = []
            ignored: set[int] = set()
            for index, raw in enumerate(worksheet.iter_rows(values_only=True)):
                values = list(raw)
                if index == 0:
                    ignored = {i for i, value in enumerate(values) if value == "Source"}
                payload = [value for i, value in enumerate(values) if i not in ignored]
                serialized = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
                if index == 0:
                    digest.update(serialized)
                else:
                    serialized_rows.append(serialized)
            for row in sorted(serialized_rows):
                digest.update(b"\n")
                digest.update(row)
            result[worksheet.title] = {"rows": len(serialized_rows), "sha256": digest.hexdigest()}
        return result
    finally:
        workbook.close()


def _build_workbook(root: Path, destination: Path) -> None:
    history = _local(root, "logs/session_condition_history.csv")
    rows = session_export._read_csv_dict_rows(history) if history.is_file() else []
    participant_rows = session_export._participant_summary_rows(root, rows)
    session_export._write_participant_summary_xlsx(
        destination, participant_rows, project_root=root, history_rows=rows,
    )


def _materialize_legacy(root: Path) -> None:
    from fpvs_studio.runtime.participant_results import _freeze_legacy_participant_results_unlocked

    _freeze_legacy_participant_results_unlocked(root)


def _research_guards(root: Path) -> tuple[SourceFile, ...]:
    from fpvs_studio.runtime.participant_results import participant_results_source_paths

    paths = participant_results_source_paths(root)
    history = _local(root, "logs/session_condition_history.csv")
    if history.is_file():
        paths.append(history)
    return tuple(SourceFile(to_project_relative_posix(root, path),
                            path.stat().st_size, _digest(path))
                 for path in dict.fromkeys(paths))


def _verify_archive(
    path: Path, sources: tuple[SourceFile, ...], parity: dict[str, dict[str, Any]],
) -> None:
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("The output archive failed its CRC check.")
        expected = {source.path for source in sources} | {"manifest.json"}
        if len(archive.namelist()) != len(expected) or set(archive.namelist()) != expected:
            raise ValueError("The output archive has unexpected or missing entries.")
        manifest = json.loads(archive.read("manifest.json"))
        if (manifest.get("schema_version") != 1
                or manifest.get("sources") != [asdict(source) for source in sources]
                or manifest.get("workbook_sheets") != parity):
            raise ValueError("The output archive manifest did not match verified sources.")
        for source in sources:
            digest = hashlib.sha256()
            size = 0
            with archive.open(source.path) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    size += len(chunk)
                    digest.update(chunk)
            if size != source.size or digest.hexdigest() != source.sha256:
                raise ValueError("Archived output did not match its original bytes.")


def _archive(
    inventory: ProjectInventory, destination: Path, parity: dict[str, dict[str, Any]],
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".zip.tmp")
    try:
        with ZipFile(temporary, "x", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for source in inventory.sources:
                archive.write(_local(inventory.project_root, source.path), arcname=source.path)
            archive.writestr("manifest.json", json.dumps({
                "schema_version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "sources": [asdict(source) for source in inventory.sources],
                "workbook_sheets": parity,
            }, indent=2))
        _verify_archive(temporary, inventory.sources, parity)
        replace_file_atomically(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _restore_file(root: Path, source: SourceFile, archive_path: Path) -> None:
    target = _local(root, source.path)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.restore")
    try:
        with ZipFile(archive_path) as archive, archive.open(source.path) as original:
            with temporary.open("xb") as output:
                for chunk in iter(lambda: original.read(1024 * 1024), b""):
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
        if _digest(temporary) != source.sha256:
            raise ValueError("Archived output could not be restored exactly.")
        replace_file_atomically(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def consolidate_project(project_root: Path, *, apply: bool = False) -> ConsolidationResult:
    """Consolidate one project, retaining verified originals before removing redundant CSVs."""

    inventory = inventory_project(project_root)
    csvs = tuple(source for source in inventory.sources if source.path.endswith(".csv"))
    retired = tuple(source for source in inventory.sources if source.path != _WORKBOOK)
    summary = ConsolidationResult(
        inventory.project_root.name, False, len(inventory.sources), len(csvs),
        sum(source.size for source in inventory.sources),
        retired_workbooks=sum(source.path.endswith(".xlsx") for source in retired),
    )
    if not apply or not inventory.sources:
        return summary
    root = inventory.project_root
    with project_reporting_lock(root):
        from fpvs_studio.runtime.condition_recovery import _inactive

        recovery = _local(root, "logs/.condition-recovery")
        for lock in recovery.glob("*.lock"):
            if not _inactive(root, lock.with_suffix(".json")):
                raise ValueError("An experiment is running; close it before consolidating output.")
        _assert_unchanged(inventory)
        workbook_path = _local(root, _WORKBOOK)
        _assert_generated_workbook(root, workbook_path)
        stage = _local(root, f"logs/.results-{uuid4().hex}.xlsx")
        probe = _local(root, f"logs/.results-{uuid4().hex}.xlsx")
        archive_path = _local(root, f"{_ARCHIVES}/{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
                                    f"-{uuid4().hex}.zip")
        removed: list[SourceFile] = []
        replaced = False
        committed_digest: str | None = None
        try:
            _build_workbook(root, stage)
            parity = _workbook_parity(stage)
            if not retired and workbook_path.is_file():
                try:
                    existing_parity = _workbook_parity(workbook_path)
                except ValueError:
                    existing_parity = None
                if existing_parity == parity:
                    return ConsolidationResult(root.name, False, 0, 0, 0)
            _materialize_legacy(root)
            _build_workbook(root, probe)
            if _workbook_parity(probe) != parity:
                raise ValueError("Materialized research records changed workbook contents.")
            _assert_unchanged(inventory)
            guards = ProjectInventory(root, _research_guards(root), 0)
            _archive(inventory, archive_path, parity)
            _assert_unchanged(inventory)
            _assert_unchanged(guards)
            committed_digest = _digest(stage)
            replace_file_atomically(stage, workbook_path)
            replaced = True
            if _workbook_parity(workbook_path) != parity:
                raise ValueError("Committed workbook did not match verified research contents.")
            for source in retired:
                path = _local(root, source.path)
                if _digest(path) != source.sha256:
                    raise ValueError("An output changed before cleanup; it was preserved.")
                path.unlink()
                removed.append(source)
            _build_workbook(root, probe)
            if _workbook_parity(probe) != parity:
                raise ValueError("Cleanup changed research results; restoring original outputs.")
        except Exception:
            if archive_path.is_file():
                for source in removed:
                    if not _local(root, source.path).exists():
                        _restore_file(root, source, archive_path)
                previous = next((source for source in inventory.sources
                                 if source.path == _WORKBOOK), None)
                if (replaced and previous is not None and workbook_path.is_file()
                        and _digest(workbook_path) == committed_digest):
                    _restore_file(root, previous, archive_path)
            raise
        finally:
            stage.unlink(missing_ok=True)
            probe.unlink(missing_ok=True)
    return ConsolidationResult(root.name, True, len(inventory.sources), len(csvs),
                               sum(source.size for source in inventory.sources), str(archive_path),
                               sum(source.path.endswith(".xlsx") for source in retired))


def discover_projects(root: Path) -> list[Path]:
    """Select only direct project children of the explicitly named Studio root."""
    root = root.resolve(strict=True)
    return [project for project in sorted(root.iterdir())
            if project.is_dir() and not project.is_symlink()
            and (project / "project.json").is_file()]


def consolidate_root(root: Path, *, apply: bool = False) -> list[ConsolidationResult]:
    """Visit only direct project children of the explicitly selected Studio root."""
    return [consolidate_project(project, apply=apply) for project in discover_projects(root)]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for project in discover_projects(args.root):
        result = consolidate_project(project, apply=args.apply)
        LOGGER.info("%s", json.dumps(asdict(result)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
