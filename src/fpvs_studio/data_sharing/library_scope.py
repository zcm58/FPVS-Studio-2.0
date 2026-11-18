"""Match a linked Library release without changing local experiment contracts."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

from fpvs_studio.core.data_sharing import SharingProfile, protocol_fingerprint
from fpvs_studio.core.library_origin import (
    LibraryOriginError,
    canonical_library_service_url,
    load_library_origin,
)
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.data_sharing.errors import DataSharingError
from fpvs_studio.data_sharing.storage import SharingStorageError, load_settings


def library_enrollment_scope(root: Path, *, service_url: str | None = None) -> dict[str, str]:
    """Unlinked studies use their protocol; linked studies require the installed release."""
    try:
        origin = load_library_origin(root)
    except LibraryOriginError:
        raise DataSharingError(
            "This project's Library link needs review before results can be shared.",
            code="protocol",
        ) from None
    if origin is None:
        return {}
    if (
        service_url is not None
        and canonical_library_service_url(origin.service_url) != service_url
    ):
        raise DataSharingError(
            "This project's Library link belongs to a different service.", code="configuration",
        )
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


def verified_handoff_scope(
    root: Path, project: ProjectFile, captured_scopes: Sequence[Mapping[str, object] | None]
) -> dict[str, str] | None:
    """Expose the enrolled destination only when every recorded visit belongs to it."""
    try:
        settings = load_settings(root)
        profile = settings.profile
        if not settings.enabled or profile is None or not profile.project_id or not captured_scopes:
            return None
        validate_library_scope(root, profile)
        scope = {
            "project_id": profile.project_id,
            "experiment_id": profile.experiment_id,
            "experiment_version": profile.experiment_version,
            "protocol_sha256": profile.protocol_sha256,
        }
        for captured in captured_scopes:
            if not captured or any(
                captured.get("study_id" if k == "project_id" else k) != v for k, v in scope.items()
            ):
                return None
        return scope if profile.protocol_sha256 == protocol_fingerprint(project, root) else None
    except (DataSharingError, SharingStorageError, OSError, ValueError):
        logging.getLogger(__name__).warning(
            "Cannot verify the website destination for this local export."
        )
        return None
