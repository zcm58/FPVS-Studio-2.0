"""Worker-side installation checks before any Library payload transfer."""

from __future__ import annotations

from pathlib import Path
from threading import Event

from fpvs_studio.core.library_installations import (
    LibraryInstallStatus,
    library_install_status,
    scan_library_projects,
)
from fpvs_studio.library.cache import check_cancel
from fpvs_studio.library.client import LibraryClient, ProgressCallback
from fpvs_studio.library.errors import LibraryCancelled, LibraryError
from fpvs_studio.library.models import LibraryItem


def check_library_install(
    root: Path, service_url: str, item: LibraryItem, *, cancel_event: Event | None = None,
) -> LibraryInstallStatus:
    try:
        projects = scan_library_projects(root, cancel_event=cancel_event)
    except InterruptedError as error:
        raise LibraryCancelled(str(error)) from error
    return library_install_status(
        projects, service_url=service_url, item_id=item.item_id,
        version=item.version, title=item.title,
    )


def download_library_install(
    client: LibraryClient, item: LibraryItem, root: Path, *, update: bool = False,
    cancel_event: Event | None = None, progress_callback: ProgressCallback | None = None,
) -> Path | LibraryInstallStatus:
    """An explicit update may add a newer copy, but never the same/newer installed release."""
    status = check_library_install(root, client.service_url, item, cancel_event=cancel_event)
    check_cancel(cancel_event)
    if status.state == "installed" or (status.state != "new" and not update):
        return status
    path = client.download(item, cancel_event=cancel_event, progress_callback=progress_callback)
    try:
        # Another operation may have installed it while the transfer was in progress.
        status = check_library_install(root, client.service_url, item, cancel_event=cancel_event)
        check_cancel(cancel_event)
        if status.state == "installed" or (status.state != "new" and not update):
            raise LibraryError(status.message)
    except Exception:
        client.release_download()
        raise
    return path
