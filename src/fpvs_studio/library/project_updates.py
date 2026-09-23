"""Library project-version discovery; never changes an experiment or downloads bytes."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Literal

from packaging.version import Version

from fpvs_studio import __version__
from fpvs_studio.core.library_origin import LibraryProjectOrigin
from fpvs_studio.library.cache import check_cancel
from fpvs_studio.library.client import LibraryClient
from fpvs_studio.library.errors import LibraryAuthorizationError, LibraryCancelled, LibraryError
from fpvs_studio.library.models import LibraryCatalog, LibraryItem

ProjectUpdateStatus = Literal[
    "unlinked", "disabled", "not_connected", "current", "update_available",
    "incompatible", "unavailable", "version_unknown",
]


@dataclass(frozen=True)
class ProjectUpdateResult:
    status: ProjectUpdateStatus
    origin: LibraryProjectOrigin | None = None
    latest_item: LibraryItem | None = None
    message: str = ""

    @property
    def can_install(self) -> bool:
        return self.latest_item is not None and self.status in {
            "update_available", "version_unknown",
        }


def select_project_update(
    origin: LibraryProjectOrigin, catalog: LibraryCatalog, *, studio_version: str = __version__,
) -> ProjectUpdateResult:
    """Compare the saved version with available versions, even if the old one was withdrawn."""
    candidates = [
        item for item in catalog.items
        if item.item_id == origin.item_id and item.kind == origin.kind
    ]
    if not candidates:
        return ProjectUpdateResult(
            "unavailable", origin,
            message="This experiment is not currently available in the Library.",
        )
    latest_version = max(Version(item.version) for item in candidates)
    newest = [item for item in candidates if Version(item.version) == latest_version]
    if len(newest) != 1:
        return ProjectUpdateResult(
            "unavailable", origin,
            message="The Library has ambiguous equivalent versions. Contact your administrator.",
        )
    latest = newest[0]
    if origin.installed_version is not None:
        installed = Version(origin.installed_version)
        if latest_version <= installed:
            if (latest_version == installed and origin.bundle_sha256 is not None
                    and origin.bundle_sha256 != latest.sha256):
                return ProjectUpdateResult(
                    "unavailable", origin, latest,
                    "The Library changed the bytes of this version. Contact your administrator.",
                )
            return ProjectUpdateResult(
                "current", origin, latest, "No newer Library version is available.",
            )
    if Version(studio_version) < Version(latest.min_studio_version):
        return ProjectUpdateResult(
            "incompatible", origin, latest,
            f"Version {latest.version} requires FPVS Studio {latest.min_studio_version} or later.",
        )
    if origin.installed_version is None:
        return ProjectUpdateResult(
            "version_unknown", origin, latest,
            f"The installed version is unknown. Library version {latest.version} is available.",
        )
    return ProjectUpdateResult(
        "update_available", origin, latest, f"Library version {latest.version} is available.",
    )


def check_project_update(
    client: LibraryClient, origin: LibraryProjectOrigin | None, *, automatic: bool = True,
    cancel_event: Event | None = None,
) -> ProjectUpdateResult:
    """Use the configured client only; local receipts cannot redirect credentials or requests."""
    check_cancel(cancel_event)
    if origin is None:
        return ProjectUpdateResult("unlinked", message="Link this project to a Library experiment.")
    if automatic and not origin.auto_check:
        return ProjectUpdateResult("disabled", origin, message="Automatic version checks are off.")
    if origin.service_url != client.service_url:
        return ProjectUpdateResult(
            "unavailable", origin, message="This project belongs to a different Library service.",
        )
    try:
        if client.connection_info() is None:
            return ProjectUpdateResult(
                "not_connected", origin, message="Connect this computer to check Library versions.",
            )
        catalog = client.catalog(cancel_event=cancel_event)
        check_cancel(cancel_event)
        return select_project_update(origin, catalog)
    except LibraryCancelled:
        raise
    except LibraryAuthorizationError as error:
        return ProjectUpdateResult("not_connected", origin, message=str(error))
    except LibraryError as error:
        return ProjectUpdateResult("unavailable", origin, message=str(error))
