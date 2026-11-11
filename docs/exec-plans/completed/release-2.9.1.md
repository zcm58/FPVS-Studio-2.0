# Studio 2.9.1 release

Status: Completed

Publish the pulled source as a Windows maintenance release. User-facing changes
include Windows scaling and fullscreen task layout fixes, plus access to recording
settings from the Home screen's recording device.

Use the isolated release checkout and the pinned environment from 2.9.0. Build the
full installer and updater manifest. Verify packaged Studio and updater smoke checks
in the approved visible desktop, audit DLL origins, and compare GitHub draft asset
sizes and digests to local files before publishing. Verify the published tag,
release attestation and asset integrity. Record results after publication.

## Build and verification

The Windows x64 installer was built from `456e7c0904d126b87831eb0360077735c09c6bdf`.
Packaging focused verification passed 212 tests. Thirteen targeted checks and
the exact-source Windows GitHub Actions job passed. The frozen task renderer
and runtime matched the release source, and both packaged Studio and updater
passed the approved visible smoke checks.

The installer extraction verified all 7,987 owned files and its embedded
inventory. The 491 bundled third-party native files and 69 native files embedded
in the updater matched the authenticated 2.9.0 baseline. The pre-upload DLL
origin receipt matched the four release assets.

## Publication

[FPVS Studio 2.9.1](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.9.1)
was published as the latest stable immutable release on November 11, 2026 at
2:27 p.m. CST, GitHub release ID `442172286`. Fresh anonymous downloads
matched the full installer, update manifest, and both checksum sidecars.
GitHub release and asset attestation verification passed, and the release tag
resolved to the exact build commit.

The 301,217,632-byte Windows installer has SHA-256
`f12844ba3abf54cac2808b4f94bd2f0dae76c9fecc4958b3c88b9086031e9f1a`.
Evidence is retained under the isolated checkout's ignored
`build/release-2.9.1-evidence/` and `build/release-2.9.1/installer-inventory/`.
The [125% Creatine laptop check](../active/task-screen-fit.md) remains pending.
