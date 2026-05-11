"""Installed-bundle smoke-check entry point for FPVS Studio release packaging."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fpvs_studio.gui.packaged_smoke import collect_packaged_smoke_report


def run_packaged_smoke(argv: Sequence[str]) -> int:
    """Run a bounded installed-app smoke check and write a JSON report."""

    output_path = _parse_output_path(argv)
    try:
        report = collect_packaged_smoke_report()
    except Exception as error:
        report = {
            "ok": False,
            "error": f"{type(error).__name__}: {error}",
        }
    _write_report(output_path, report)
    return 0 if report.get("ok") is True else 1


def _parse_output_path(argv: Sequence[str]) -> Path | None:
    args = list(argv)
    try:
        output_index = args.index("--packaged-smoke-output")
    except ValueError:
        return None
    try:
        return Path(args[output_index + 1])
    except IndexError as error:
        raise ValueError("--packaged-smoke-output requires a path.") from error


def _write_report(output_path: Path | None, report: dict[str, Any]) -> None:
    report_text = json.dumps(report, indent=2, sort_keys=True)
    if output_path is None:
        sys.stdout.write(f"{report_text}\n")
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text + "\n", encoding="utf-8")
