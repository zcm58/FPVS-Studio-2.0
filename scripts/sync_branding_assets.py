"""Regenerate derived FPVS Studio branding assets from the canonical source PNG."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from PIL import Image, ImageOps

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "packaging" / "assets" / "fpvs-studio-icon-1024.png"
RUNTIME_ICON = REPO_ROOT / "src" / "fpvs_studio" / "assets" / "fpvs-studio.ico"
DOCS_SITE_ICON = REPO_ROOT / "docs-site" / "assets" / "fpvs-studio-icon.png"
ICO_SIZES = ((16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256))
DOCS_SITE_ICON_SIZE = (512, 512)
LOGGER = logging.getLogger(__name__)


def _resolve_repo_path(path: Path) -> Path:
    resolved = path.resolve()
    repo_root = REPO_ROOT.resolve()
    if resolved != repo_root and repo_root not in resolved.parents:
        raise ValueError(f"Refusing to write outside repository: {resolved}")
    return resolved


def sync_branding_assets(source: Path) -> None:
    source = _resolve_repo_path(source)
    runtime_icon = _resolve_repo_path(RUNTIME_ICON)
    docs_site_icon = _resolve_repo_path(DOCS_SITE_ICON)

    if not source.is_file():
        raise FileNotFoundError(f"Branding source PNG was not found: {source}")

    with Image.open(source) as image:
        icon_source = image.convert("RGBA")
        runtime_icon.parent.mkdir(parents=True, exist_ok=True)
        icon_source.save(runtime_icon, format="ICO", sizes=ICO_SIZES)

        docs_site_icon.parent.mkdir(parents=True, exist_ok=True)
        site_icon = ImageOps.contain(icon_source, DOCS_SITE_ICON_SIZE)
        site_icon.save(docs_site_icon, format="PNG")

    LOGGER.info("Updated %s", runtime_icon.relative_to(REPO_ROOT))
    LOGGER.info("Updated %s", docs_site_icon.relative_to(REPO_ROOT))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Canonical high-resolution branding PNG.",
    )
    args = parser.parse_args()
    sync_branding_assets(args.source)


if __name__ == "__main__":
    main()
