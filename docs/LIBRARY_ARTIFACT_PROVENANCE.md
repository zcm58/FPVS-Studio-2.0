# Library Artifact Provenance

`library/provenance.py` verifies exact bundle safety evidence before a download is
written to the cache or a retained payload is returned for import. It uses the
existing `cryptography` Ed25519 implementation, required by base installations.
The strict native catalog remains schema `1.0` with its existing fields.

## Trust and wire contract

The managed `https://openfpvs.com` service uses locally pinned key ID
`openfpvs-safety-2026-10` and raw public key
`y8mIyJT8Ai-vAzRvBhTxsqq74eHFuogNo1XEXU2WLSg`. Keys returned by an HTTP response
cannot establish trust. Key rotation requires a reviewed Studio source update.
The existing managed origin policy maps earlier service aliases to this origin;
unconfigured custom HTTPS origins fail with `untrusted_provenance` on download.

A successful `/v2/items/{item_id}/versions/{version}/download` includes:

- `X-FPVS-Artifact-Key-Id`: the pinned key ID.
- `X-FPVS-Artifact-Proof`: unpadded base64url UTF-8 JSON, at most 8,192 characters.

The signed proof contains policy, item ID, version, SHA-256, compressed byte size,
filename, file count, uncompressed byte size, condition count, scanner,
scanner version, scan time, expiration time, and a base64url Ed25519 signature.
The signature covers that ordered JSON array using compact UTF-8 encoding;
the signature field itself is excluded. Identity, hash, size, filename and
inventory counts must match the selected catalog item. The policy must be
`openfpvs-bundle-v1`. Reviewed condition bundles require a signed condition count
of one. Missing, malformed, forged or mismatched evidence fails closed before
partial cache creation. SHA-256 and transfer size checks still verify the bytes.

The scan expiration is the server's evidence-ingestion deadline. It does not expire
an approval that was already accepted. Studio rejects future or implausible scan
times but accepts an older approved proof only after current authenticated service
authorization. The service owns approval, withdrawal and live asset checks;
the desktop owns signature verification, bounded transfer and bundle extraction.

For a retained payload, Studio rehashes the file, refreshes the authorized catalog,
then requests the bounded authenticated
`GET /v2/items/{item_id}/versions/{version}/provenance` response:

```json
{"schema_version":"1.0","key_id":"openfpvs-safety-2026-10","proof":{}}
```

The actual `proof` contains all signed fields above. This request rechecks live
catalog identity, safety approval, withdrawal and download permission. A retained
file with an invalid proof, denied permission or withdrawn identity is never
returned for import. No additional bundle bytes are downloaded. Imported projects
remain independent offline copies; withdrawal prevents new Library transfers and
cache reuse without modifying previous imports. Do not log signatures, credentials
or private bundle content.

## Release publication

The canonical `developer/catalog_publisher.py` already stages private Library
releases as drafts, uploads all assets, checks the complete asset inventory and
each GitHub SHA-256/size, then publishes and writes the catalog. An existing
published release is read-only, including GitHub releases marked `immutable`.
Retries verify the retained exact assets; missing or changed assets require a
new tag. Draft starter recovery never modifies an immutable release. Publication
confirmation must identify the exact release ID and tag.

GitHub's repository immutable-release setting is an explicit maintainer operation
and applies to future releases. Enable it before future publication, attach every
installer, patch, update manifest and checksum to the draft, verify exact bytes,
then publish. GitHub automatically creates a signed release attestation binding
the locked tag and assets. Verify the release and downloaded artifact with
`gh release verify` and `gh release verify-asset` against the correct repository.
See [GitHub immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases)
and [release verification](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/verify-release-integrity).

On October 8, 2026, the maintainer enabled this setting on `zcm58/FPVS-Studio-2.0`,
`zcm58/FPVS-Toolbox-Releases` and private `zcm58/OpenFPVS-Website`. Each fixed
repository's setting returned `enabled: true` on the authenticated verification
read. No release, tag, asset or content publication changed during this operation.

Studio and Toolbox packaging scripts build local artifacts; they do not upload
or publish GitHub releases. Their publication process must preserve the same
draft-first sequence. Enabling future release immutability does not retrospectively
lock an older mutable release or Authenticode-sign an existing installer. A public
Toolbox release-only repository attests the published artifact, not its private
source build identity. Keep private sources private and record an exact source
commit/build association when generating future release evidence.

## Verification

`test_library_provenance.py` uses ephemeral signing keys and synthetic metadata to
cover exact signatures, changed digests and fields, invalid policies, key substitution,
bounded headers and approved historical evidence. Client tests prove cache creation
and reuse fail before import when evidence is untrusted. Publisher tests use a fake
GitHub API and cover immutable retries and exact publication confirmation.

Run the Library focused route and safe repo precommit. Tests never contact scanner,
GitHub or service endpoints and never use maintainer private keys. Local source
checks do not establish a new installed Studio build or a published release.
