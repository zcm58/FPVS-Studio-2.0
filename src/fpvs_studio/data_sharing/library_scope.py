"""Match a linked Library release without changing local experiment contracts."""

from __future__ import annotations

from pathlib import Path

from fpvs_studio.core.data_sharing import SharingProfile
from fpvs_studio.core.library_origin import LibraryOriginError, load_library_origin
from fpvs_studio.data_sharing.errors import DataSharingError


def library_enrollment_scope(root: Path) -> dict[str, str]:
    """Unlinked studies use their invitation; linked studies require the installed release."""
    try:
        origin = load_library_origin(root)
    except LibraryOriginError:
        raise DataSharingError(
            "This project's Library link needs review before results can be shared.",
            code="protocol",
        ) from None
    if origin is None:
        return {}
    if origin.installed_version is None:
        raise DataSharingError(
            "Confirm this project's installed Library version before sharing results.",
            code="protocol",
        )
    return {"experiment_id": origin.item_id, "experiment_version": origin.installed_version}


def validate_library_scope(root: Path, profile: SharingProfile) -> None:
    scope = library_enrollment_scope(root)
    if scope and (
        scope["experiment_id"] != profile.experiment_id
        or scope["experiment_version"] != profile.experiment_version
    ):
        raise DataSharingError(
            "Results access belongs to a different Library experiment or version. "
            "Reconnect with access for this project's installed version.",
            code="protocol",
        )
