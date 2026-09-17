"""Prepare and review a clean whole-project bundle without uploading it."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from fpvs_studio import __version__
from fpvs_studio.core.library_publish import prepare_library_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Saved project folder or existing .fpvsbundle")
    parser.add_argument("output", type=Path, help="New versioned .fpvsbundle outside the source")
    parser.add_argument("--minimum-studio-version", default=__version__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Compile and show inventory; write no output bundle"
    )
    parser.add_argument(
        "--metadata", type=Path, help="Optionally save the review inventory as JSON"
    )
    args = parser.parse_args()
    result = prepare_library_bundle(
        args.source,
        args.output,
        minimum_studio_version=args.minimum_studio_version,
        dry_run=args.dry_run,
    )
    payload = json.dumps(result.as_dict(), indent=2)
    if args.metadata:
        args.metadata.parent.mkdir(parents=True, exist_ok=True)
        with args.metadata.open("x", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.info(payload)


if __name__ == "__main__":
    main()
