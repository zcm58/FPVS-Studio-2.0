"""Backend update helpers for FPVS Studio."""

from __future__ import annotations

from fpvs_studio.updates.github_releases import check_for_updates
from fpvs_studio.updates.models import (
    DownloadedInstaller,
    InstallerAsset,
    UpdateCheckResult,
    UpdateError,
)

__all__ = [
    "DownloadedInstaller",
    "InstallerAsset",
    "UpdateCheckResult",
    "UpdateError",
    "check_for_updates",
]
