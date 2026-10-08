"""Verify exact bundle safety evidence against the locally pinned maintainer key."""

from __future__ import annotations

import base64
import binascii
import json
import re
import time
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fpvs_studio.library.errors import LibraryError
from fpvs_studio.library.models import LibraryItem

MAX_PROOF_HEADER_BYTES = 8192
SAFETY_POLICY = "openfpvs-bundle-v1"
PINNED_KEYS = {
    "https://openfpvs.com": (
        "openfpvs-safety-2026-10", "y8mIyJT8Ai-vAzRvBhTxsqq74eHFuogNo1XEXU2WLSg",
    ),
}
_SIGNED_FIELDS = (
    "policy", "item_id", "version", "sha256", "size_bytes", "filename", "file_count",
    "uncompressed_size_bytes", "condition_count", "scanner", "scanner_version",
    "scanned_at", "expires_at",
)
_ERROR = "untrusted_provenance: Bundle safety evidence is missing or untrusted."


def _decode(value: Any, length: int | None = None) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise LibraryError(_ERROR)
    try:
        result = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, binascii.Error):
        raise LibraryError(_ERROR) from None
    if (length is not None and len(result) != length) or (
        base64.urlsafe_b64encode(result).decode("ascii").rstrip("=") != value
    ):
        raise LibraryError(_ERROR)
    return result


def require_pinned_origin(service_url: str) -> None:
    if service_url not in PINNED_KEYS:
        raise LibraryError(
            "untrusted_provenance: No trusted bundle-signing key is configured for this service."
        )


def verify_proof(proof: Any, key_id: Any, item: LibraryItem, service_url: str) -> None:
    require_pinned_origin(service_url)
    expected_id, encoded_key = PINNED_KEYS[service_url]
    if key_id != expected_id or not isinstance(proof, dict) or set(proof) != {
        *_SIGNED_FIELDS, "signature",
    }:
        raise LibraryError(_ERROR)
    if proof["policy"] != SAFETY_POLICY or any(
        proof[field] != getattr(item, field) or type(proof[field]) is not type(getattr(item, field))
        for field in (
            "item_id", "version", "sha256", "size_bytes", "filename", "file_count",
            "uncompressed_size_bytes",
        )
    ):
        raise LibraryError(_ERROR)
    scanned, expires = proof["scanned_at"], proof["expires_at"]
    if (
        type(proof["condition_count"]) is not int or not 1 <= proof["condition_count"] <= 256
        or (item.item_id.startswith("reviewed-") and proof["condition_count"] != 1)
        or proof["scanner"] not in ("microsoft-defender", "clamav", "cisco-secure-endpoint")
        or not isinstance(proof["scanner_version"], str)
        or not 1 <= len(proof["scanner_version"]) <= 100
        or type(scanned) is not int or type(expires) is not int
        or not 0 < scanned <= int(time.time()) + 60
        or not scanned <= expires <= scanned + 90000
    ):
        raise LibraryError(_ERROR)
    try:
        # Match the Worker's JSON.stringify array, including non-ASCII scanner text.
        payload = json.dumps(
            [proof[field] for field in _SIGNED_FIELDS], ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")
        Ed25519PublicKey.from_public_bytes(_decode(encoded_key, 32)).verify(
            _decode(proof["signature"], 64), payload,
        )
    except (InvalidSignature, ValueError, UnicodeError, TypeError):
        raise LibraryError(_ERROR) from None


def verify_proof_header(value: Any, key_id: Any, item: LibraryItem, service_url: str) -> None:
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_PROOF_HEADER_BYTES:
        raise LibraryError(_ERROR)
    try:
        proof = json.loads(_decode(value).decode("utf-8"))
    except (ValueError, UnicodeError, RecursionError):
        raise LibraryError(_ERROR) from None
    verify_proof(proof, key_id, item, service_url)
