"""Last website-confirmed collection state for one enrolled local project."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Literal

from fpvs_studio.core.data_sharing import SharingModel, SharingProfile
from fpvs_studio.data_sharing.client import DataSharingClient
from fpvs_studio.data_sharing.errors import DataSharingError
from fpvs_studio.data_sharing.library_scope import validate_library_scope
from fpvs_studio.data_sharing.storage import _private_path, _write, read_bounded_model

_RECEIPT = ".fpvs-data-sharing/collection-status.json"


class CollectionReceipt(SharingModel):
    schema_version: Literal["1.0"]
    project_id: str
    collection_status: Literal["in_progress", "complete"]


def last_collection_status(root: Path, profile: SharingProfile) -> str | None:
    path = _private_path(root, _RECEIPT)
    if not path.exists():
        return None
    receipt = read_bounded_model(path, CollectionReceipt, 2048)
    return receipt.collection_status if receipt.project_id == profile.project_id else None


def refresh_collection_status(
    root: Path, profile: SharingProfile, cancel: Event, *, client: DataSharingClient | None = None,
) -> str:
    validate_library_scope(root, profile)
    client = client or DataSharingClient.configured()
    credential = client._load_credential(root, profile)
    raw = client._request("GET", "/results/v1/device/collection", None, cancel, credential.token)
    receipt = client._parse(raw, CollectionReceipt)
    if not profile.project_id or receipt.project_id != profile.project_id:
        raise DataSharingError("Collection status belongs to a different study.", code="protocol")
    _write(root, _RECEIPT, receipt, 2048)
    return receipt.collection_status
