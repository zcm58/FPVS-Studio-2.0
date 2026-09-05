"""Explicit installer launch, verified while the cache and executable are guarded."""

from __future__ import annotations

import subprocess
from threading import Event

from fpvs_studio.updates.cache import verified_installer
from fpvs_studio.updates.cache_io import check_cancel, locked_cache, validate_cache_path
from fpvs_studio.updates.models import DownloadedInstaller, UpdateError
from fpvs_studio.updates.validation import validate_asset_identity


def launch_installer(
    downloaded: DownloadedInstaller,
    *,
    relaunch_after_install: bool = True,
    cancel_event: Event | None = None,
) -> subprocess.Popen[bytes]:
    """Final worker stage after explicit confirmation/save, never a GUI-thread hash.

    Windows read guards deny writes and deletion through Popen. Cancellation is
    honored until process creation; a successful launch is never reported canceled.
    Callers must await the launch worker's actual completion before quitting.
    """

    check_cancel(cancel_event)
    validate_asset_identity(downloaded.asset)
    path = downloaded.path
    if not path.is_absolute() or path.name != downloaded.asset.name:
        raise UpdateError("The installer path does not match the selected update asset.")
    if (
        downloaded.sha256 != downloaded.asset.sha256
        or downloaded.size_bytes != downloaded.asset.size_bytes
    ):
        raise UpdateError("The downloaded installer identity does not match the selected update.")
    cache_path = validate_cache_path(path.parent)
    with locked_cache(cache_path, create=False, cancel_event=cancel_event) as cache:
        if cache.regular_info(path.name) is None:
            raise UpdateError(f"Installer file does not exist: {path}")
        with verified_installer(cache, downloaded.asset, cancel_event=cancel_event):
            check_cancel(cancel_event)
            command = [str(path)]
            if relaunch_after_install:
                command.append("/RELAUNCH=1")
            try:
                return subprocess.Popen(command, close_fds=True)
            except OSError as error:
                raise UpdateError(f"Could not launch the update installer: {error}") from error
