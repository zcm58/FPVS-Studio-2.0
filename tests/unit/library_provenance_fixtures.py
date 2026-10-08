"""Ephemeral signed synthetic evidence; never use the production signing key."""

import base64
import json
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from fpvs_studio.library import provenance

KEY = Ed25519PrivateKey.generate()
KEY_ID = "synthetic-test-key"
PUBLIC_KEY = base64.urlsafe_b64encode(
    KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw),
).decode().rstrip("=")


def sign_proof(item, **changes):
    now = int(time.time())
    proof = {
        "policy": provenance.SAFETY_POLICY,
        **{field: getattr(item, field) for field in (
            "item_id", "version", "sha256", "size_bytes", "filename", "file_count",
            "uncompressed_size_bytes",
        )},
        "condition_count": 1, "scanner": "clamav", "scanner_version": "synthetic 1.0",
        "scanned_at": now - 1, "expires_at": now + 3599,
        **changes,
    }
    payload = json.dumps(
        [proof[field] for field in provenance._SIGNED_FIELDS],
        ensure_ascii=False, separators=(",", ":"),
    ).encode()
    proof["signature"] = base64.urlsafe_b64encode(KEY.sign(payload)).decode().rstrip("=")
    return proof


def proof_headers(item, proof=None):
    encoded = base64.urlsafe_b64encode(
        json.dumps(sign_proof(item) if proof is None else proof).encode(),
    ).decode().rstrip("=")
    return {"X-FPVS-Artifact-Proof": encoded, "X-FPVS-Artifact-Key-Id": KEY_ID}
