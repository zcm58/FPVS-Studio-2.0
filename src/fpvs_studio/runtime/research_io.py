"""Read recorded CSV rows and replace completed research workbooks on disk."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fpvs_studio.core.serialization import replace_file_atomically


def read_research_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Reject broken row boundaries before using a table as research evidence."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, strict=True)
        try:
            header = next(reader, [])
            if len(set(header)) != len(header):
                raise ValueError(f"{path.name} contains duplicate column names.")
            rows = []
            for row in reader:
                if not row:
                    continue
                if len(row) != len(header):
                    raise ValueError(f"{path.name} contains malformed rows.")
                rows.append(dict(zip(header, row, strict=True)))
        except csv.Error as exc:
            raise ValueError(f"{path.name} contains malformed rows.") from exc
    return header, rows


def save_workbook_atomically(workbook: Any, path: Path) -> None:
    """Keep the previous workbook until its replacement has been completely written."""
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp",
                                delete=False) as handle:
            temporary_path = Path(handle.name)
        workbook.save(temporary_path)
        with temporary_path.open("r+b") as handle:
            os.fsync(handle.fileno())
        replace_file_atomically(temporary_path, path)
    finally:
        workbook.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
