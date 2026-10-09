"""Measure synthetic summary payloads and SQLite growth using OpenFPVS's D1 schema.

Run with the Studio environment and --backend pointing at the sibling OpenFPVS
checkout. All databases are temporary; this script makes no network requests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from fpvs_studio.core.data_sharing import FixationOccurrence, SessionReport


def measure(backend: Path, occurrences: int) -> dict[str, object]:
    start = datetime(2026, 10, 8, tzinfo=timezone.utc)
    base = SessionReport(
        report_id=str(uuid5(NAMESPACE_URL, "synthetic/report/0")),
        experiment_id="synthetic-study", experiment_version="1.0",
        protocol_sha256="a" * 64, completed_at=start, studio_version="2.4.0",
        occurrences=tuple(FixationOccurrence(
            condition_id=f"condition-{index % 6 + 1}", occurrence_index=index + 1,
            total_targets=20, hit_count=18, miss_count=2, false_alarm_count=1,
            accuracy_percent=90, mean_rt_ms=350, rt_count=18,
            scoring_source="timestamps", refresh_hz=60, response_window_ms=1000,
        ) for index in range(occurrences)),
    )
    growth: dict[int, int] = {}
    with tempfile.TemporaryDirectory(prefix="fpvs-report-budget-") as directory:
        with closing(sqlite3.connect(Path(directory) / "synthetic.sqlite")) as database:
            for migration in sorted((backend / "migrations").glob("*.sql")):
                database.executescript(migration.read_text())
            database.commit()
            baseline = database.execute("PRAGMA page_count").fetchone()[0]
            page_size = database.execute("PRAGMA page_size").fetchone()[0]
            for index in range(1500):
                report = base.model_copy(update={
                    "report_id": str(uuid5(NAMESPACE_URL, f"synthetic/report/{index}")),
                    "completed_at": start + timedelta(seconds=index),
                })
                payload = report.model_dump_json()
                database.execute(
                    "INSERT INTO results_reports(project_id, report_id, device_id, sha256, "
                    "received_at, payload, payload_bytes, occurrence_count) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    ("00000000-0000-4000-8000-000000000001", report.report_id,
                     "00000000-0000-4000-8000-000000000002",
                     hashlib.sha256(payload.encode()).hexdigest(),
                     report.completed_at.isoformat(), payload, len(payload.encode()), occurrences),
                )
                if index + 1 in (100, 500, 1500):
                    database.commit()
                    pages = database.execute("PRAGMA page_count").fetchone()[0]
                    growth[index + 1] = (pages - baseline) * page_size
    payload_bytes = len(base.model_dump_json().encode())
    return {
        "occurrences": occurrences, "payload_bytes": payload_bytes,
        "sqlite_growth_bytes": growth, "stored_bytes_per_session_at_1500": growth[1500] / 1500,
        "project_budget_sessions": min(2000, 8388608 // payload_bytes, 100000 // occurrences),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger(__name__).info(
        "%s", json.dumps([measure(args.backend, count) for count in (1, 12, 120)], indent=2),
    )


if __name__ == "__main__":
    main()
