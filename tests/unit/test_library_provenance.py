"""Exact signed safety contracts use ephemeral keys and synthetic metadata only."""

import base64
import json
import time

import pytest
from tests.unit.library_provenance_fixtures import (
    KEY,
    KEY_ID,
    PUBLIC_KEY,
    proof_headers,
    sign_proof,
)

from fpvs_studio.library import provenance
from fpvs_studio.library.errors import LibraryError
from fpvs_studio.library.models import LibraryItem

ORIGIN = "https://openfpvs.com"
NOW = 1700000000


@pytest.fixture
def bundle(monkeypatch):
    monkeypatch.setattr(provenance, "PINNED_KEYS", {ORIGIN: (KEY_ID, PUBLIC_KEY)})
    monkeypatch.setattr(provenance.time, "time", lambda: NOW)
    return LibraryItem(
        item_id="synthetic", version="1.0.0", title="Synthetic", description="Test only",
        experiment_category="fpvs_oddball", filename="synthetic.fpvsbundle",
        size_bytes=42, uncompressed_size_bytes=100, file_count=2, sha256="a" * 64,
        min_studio_version="1.8.0",
    )


def test_valid_exact_proof_and_header_verify(bundle):
    proof = sign_proof(bundle, scanner_version="synthetic \u00e9 1.0")
    provenance.verify_proof(proof, KEY_ID, bundle, ORIGIN)
    headers = proof_headers(bundle, proof)
    provenance.verify_proof_header(
        headers["X-FPVS-Artifact-Proof"], KEY_ID, bundle, ORIGIN,
    )


def test_worker_ordered_json_signature_contract(bundle):
    # Keep this explicit vector independent from the implementation's field list.
    proof = sign_proof(bundle, scanned_at=1700000000, expires_at=1700003600)
    payload = (
        '["openfpvs-bundle-v1","synthetic","1.0.0","' + "a" * 64
        + '",42,"synthetic.fpvsbundle",2,100,1,"clamav","synthetic 1.0",'
        '1700000000,1700003600]'
    )
    proof["signature"] = base64.urlsafe_b64encode(KEY.sign(payload.encode())).decode().rstrip("=")
    provenance.verify_proof(proof, KEY_ID, bundle, ORIGIN)


@pytest.mark.parametrize("field,value", [
    ("sha256", "b" * 64), ("item_id", "different"), ("version", "2.0.0"),
    ("size_bytes", 43), ("filename", "different.fpvsbundle"), ("file_count", 3),
    ("uncompressed_size_bytes", 101), ("scanner_version", "changed"),
    ("condition_count", 2),
])
def test_changed_signed_fields_are_denied(bundle, field, value):
    proof = sign_proof(bundle)
    proof[field] = value
    with pytest.raises(LibraryError, match="untrusted_provenance"):
        provenance.verify_proof(proof, KEY_ID, bundle, ORIGIN)


def test_catalog_and_proof_mutation_cannot_rebind_the_signature(bundle):
    proof = sign_proof(bundle)
    proof["sha256"] = "b" * 64
    changed = bundle.model_copy(update={"sha256": "b" * 64})
    with pytest.raises(LibraryError, match="untrusted_provenance"):
        provenance.verify_proof(proof, KEY_ID, changed, ORIGIN)


@pytest.mark.parametrize("changes", [
    {"policy": "different-policy"}, {"scanner": "unapproved-scanner"},
    {"condition_count": True}, {"condition_count": 0}, {"condition_count": 257},
    {"scanner_version": ""}, {"scanner_version": "x" * 101},
    {"scanned_at": NOW + 120}, {"scanned_at": 0},
    {"scanned_at": True}, {"expires_at": 0}, {"expires_at": NOW + 100000},
])
def test_even_signed_invalid_policy_shape_or_time_is_denied(bundle, changes):
    proof = sign_proof(bundle, **changes)
    with pytest.raises(LibraryError, match="untrusted_provenance"):
        provenance.verify_proof(proof, KEY_ID, bundle, ORIGIN)


def test_approved_proof_expiry_is_an_ingestion_deadline(bundle):
    now = int(time.time())
    proof = sign_proof(bundle, scanned_at=now - 864000, expires_at=now - 860400)
    provenance.verify_proof(proof, KEY_ID, bundle, ORIGIN)


def test_single_condition_review_has_a_signed_count(bundle):
    reviewed = bundle.model_copy(update={"item_id": "reviewed-synthetic"})
    provenance.verify_proof(sign_proof(reviewed), KEY_ID, reviewed, ORIGIN)
    with pytest.raises(LibraryError, match="untrusted_provenance"):
        provenance.verify_proof(sign_proof(reviewed, condition_count=2), KEY_ID, reviewed, ORIGIN)


def test_response_keys_and_unknown_services_cannot_replace_the_pin(bundle):
    proof = sign_proof(bundle)
    with pytest.raises(LibraryError, match="untrusted_provenance"):
        provenance.verify_proof(proof, "attacker-key", bundle, ORIGIN)
    with pytest.raises(LibraryError, match="No trusted"):
        provenance.verify_proof(proof, KEY_ID, bundle, "https://custom.example.test")
    with pytest.raises(LibraryError, match="untrusted_provenance"):
        provenance.verify_proof({**proof, "public_key": PUBLIC_KEY}, KEY_ID, bundle, ORIGIN)


@pytest.mark.parametrize("value", [None, "", "!", "a" * 8193, "a===", "bnVsbA", "W10"])
def test_missing_malformed_or_oversized_headers_are_denied(bundle, value):
    with pytest.raises(LibraryError, match="untrusted_provenance"):
        provenance.verify_proof_header(value, KEY_ID, bundle, ORIGIN)


def test_corrupt_signature_and_noncanonical_base64_are_denied(bundle):
    proof = sign_proof(bundle)
    proof["signature"] = base64.urlsafe_b64encode(b"x" * 64).decode().rstrip("=")
    with pytest.raises(LibraryError, match="untrusted_provenance"):
        provenance.verify_proof(proof, KEY_ID, bundle, ORIGIN)
    proof = sign_proof(bundle)
    proof["signature"] += "="
    encoded = base64.urlsafe_b64encode(json.dumps(proof).encode()).decode().rstrip("=")
    with pytest.raises(LibraryError, match="untrusted_provenance"):
        provenance.verify_proof_header(encoded, KEY_ID, bundle, ORIGIN)
