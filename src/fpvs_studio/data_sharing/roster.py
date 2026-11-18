"""Explicitly share opaque research-visit membership for the linked lab study."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from threading import Event
from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from fpvs_studio.core.data_sharing import Sha256, SharingModel
from fpvs_studio.data_sharing.client import DataSharingClient, check_cancel
from fpvs_studio.data_sharing.errors import DataSharingError
from fpvs_studio.data_sharing.library_scope import validate_library_scope
from fpvs_studio.data_sharing.storage import (
    _private_path,
    _storage_lock,
    _write,
    load_settings,
    read_bounded_model,
)
from fpvs_studio.runtime.study_handoff import build_study_handoff
from fpvs_studio.support.website_transfer import website_export


class RosterReceipt(SharingModel):
    schema_version: Literal["1.0"]
    source_study_id: str
    roster_revision: Sha256 | None


def share_study_roster(root: Path, cancel: Event) -> str:
    """Publish only after the operator consented to the website roster transfer."""
    with website_export("study roster"):
        return _share(root, cancel, DataSharingClient.configured())


def _share(root: Path, cancel: Event, client: DataSharingClient) -> str:
    check_cancel(cancel)
    settings = load_settings(root)
    profile = settings.profile
    if not settings.enabled or profile is None or not profile.project_id:
        raise DataSharingError(
            "Connect this project to a study and enable sharing.", code="authorization"
        )
    validate_library_scope(root, profile)
    credential = client._load_credential(root, profile)
    try:
        handoff = build_study_handoff(root)
        source = str(UUID(handoff["study_id"]))
        target = RosterReceipt(
            schema_version="1.0", source_study_id=source, roster_revision=handoff["roster_revision"]
        )
        visits = sorted(
            hashlib.sha256(f"openfpvs-visit-v1\n{source}\n{visit['visit_id']}".encode()).hexdigest()
            for visit in handoff["visits"]
        )
    except (KeyError, TypeError, ValueError, OSError) as error:
        raise DataSharingError(
            "Review the local study roster before sharing.", code="protocol"
        ) from error
    if (
        not visits
        or len(visits) > 2000
        or len(set(visits)) != len(visits)
        or not target.roster_revision
    ):
        raise DataSharingError(
            "Choose a study with 1–2,000 distinct research visits.", code="protocol"
        )
    endpoint = f"/results/v1/device/roster/{source}"
    scope = hashlib.sha256(
        f"{client.origin}\n{profile.project_id}\n{profile.device_id}\n{source}".encode()
    ).hexdigest()
    relative = f".fpvs-data-sharing/rosters/{scope}.json"

    def request(method: str, payload: bytes | None = None) -> RosterReceipt:
        if load_settings(root) != settings:
            raise DataSharingError(
                "The study sharing settings changed. Review the connection.", code="authorization"
            )
        validate_library_scope(root, profile)
        raw = client._request(method, endpoint, payload, cancel, credential.token)
        try:
            receipt = RosterReceipt.model_validate_json(raw)
        except ValidationError as error:
            raise DataSharingError(
                "The website sent an invalid roster receipt.", code="protocol"
            ) from error
        if receipt.source_study_id != source:
            raise DataSharingError("The website receipt belongs to another study.", code="protocol")
        return receipt

    def saved_revision() -> str | None:
        path = _private_path(root, relative)
        if not path.exists():
            return None
        saved = read_bounded_model(path, RosterReceipt, 1024)
        if saved.source_study_id != source or saved.roster_revision is None:
            raise DataSharingError(
                "The saved roster receipt does not match the study.", code="protocol"
            )
        return saved.roster_revision

    with _storage_lock(root):
        previous = saved_revision()
    remote = request("GET")
    if remote != target:
        if remote.roster_revision != previous:
            raise DataSharingError(
                "Another roster revision was shared. Review the study on its original computer.",
                code="conflict",
            )
        body = {
            **target.model_dump(exclude={"source_study_id"}),
            "parent_roster_revision": previous,
            "visits": visits,
        }
        if request("POST", json.dumps(body, separators=(",", ":")).encode()) != target:
            raise DataSharingError(
                "The website did not confirm this study revision.", code="protocol"
            )
    with _storage_lock(root):
        if saved_revision() not in (previous, target.roster_revision):
            raise DataSharingError(
                "The locally recorded roster changed. Review the current revision.", code="conflict"
            )
        _write(root, relative, target, 1024)
    return target.roster_revision
