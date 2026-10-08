"""Separate results credentials backed by the existing native OS adapters."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from fpvs_studio.data_sharing.errors import DataSharingError
from fpvs_studio.library.credentials import (
    CredentialStore,
    SecretServiceCredentialStore,
    WindowsCredentialStore,
)


def sharing_credential_store(
    origin: str, project_root: Path, protocol_sha256: str
) -> CredentialStore:
    """Copies at another path cannot inherit a machine's enrollment or opt-in."""
    identity = hashlib.sha256(
        f"{origin}\n{project_root.resolve()}\n{protocol_sha256}".encode()
    ).hexdigest()
    target = f"FPVS-Studio/Data-Sharing/{identity}"
    if sys.platform == "win32":
        return WindowsCredentialStore(target)
    if sys.platform.startswith("linux"):
        return SecretServiceCredentialStore(target)
    raise DataSharingError(
        "Data sharing requires Windows Credential Manager or a Linux desktop keyring.",
        code="credential_store",
    )
