# FPVS Studio 2.4.1 experiment transfer security release

Status: Completed

Date: 2026-10-08

## Scope and authorization

The user explicitly requested a new public Studio release compatible with the
deployed OpenFPVS signature checks, and specified version v2.4.1 and the exact
release note below. Integrate the committed transfer and signature hardening
through `3c089cf` into master without altering experiment/runtime/trigger contracts.
Version is owned by `pyproject.toml`; package, tag, installer and update metadata
must all agree. Preserve existing releases and the independent 2.2.7 draft.

Build a full Windows installer and a direct patch from the authenticated public
2.4.0 installer using the canonical packaging scripts. Keep versioned artifacts
and evidence in ignored `build/release-2.4.1` and `dist/release-2.4.1`.
Use the existing owner-authorized GitHub credentials without expanding scopes.
Upload to a draft, verify exact names/sizes/digests, then publish as latest stable
with GitHub immutable release protection enabled.

## Exact release note

improved security handling around uploading/downloading experiments

## Verification gates

- [x] Confirm version, clean checkout and fast-forward integration with master.
- [x] Pass packaging focused verification and final safe repository precommit:
  181 packaging tests; 2,844 safe tests, 20 subtests and 11 Windows symlink skips;
  mypy on 228 source files and harness/docs audits pass.
- [x] Commit and push the exact versioned candidate before packaging.
- [x] Authenticate the public baseline installer and extracted ownership inventory:
  installer SHA-256 `59323a0a8ac02fc75f1fc74733d31ded796530f015ea5a2a87cd8476060a0e35`;
  manifest SHA-256 `2589ff393edbf1283050d945e622fffa4568acb40bc54e0afa5c95281ed4bfea`.
- [x] Build complete installer, direct patch, update JSON and checksum sidecars.
- [x] Verify complete extraction, exact patch reconstruction, native dependency
  custody, embedded source and Ed25519 signature verification from the frozen build.
- [x] Run the required explicitly approved native packaged startup check.
- [x] Upload a draft and verify all assets before immutable publication.
- [x] Verify public release body/tag/asset digests and updater selections, then
  record final refs and complete this plan.

## Verification boundaries

The previously committed security implementation passed 2,844 safe non-Qt tests,
20 subtests and 11 Windows symlink-privilege skips. The signature-order vector and
native cache/download paths passed focused checks. Final candidate version checks
and frozen artifact checks are required rather than assuming the installed binary
matches source. No real experiment, report upload, researcher account or credential
will be used in testing. Fresh installation, installed lifecycle, physical-display
and EEG/trigger checks remain separate operational acceptance boundaries.

## Delivery record

[FPVS Studio v2.4.1](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.4.1)
is the public latest stable release, ID `407075169`, with `immutable: true`.
Built source and immutable tag both identify
`ddff4158e5f802aa1e0fc482b0e53bbe070b4930`. The public body is exactly the
requested note above. All six assets match locally audited sizes and SHA-256;
the unrelated 2.2.7 draft was untouched.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.4.1.exe` | 300686648 | `3aa9557c89518863b6bc5858fbc84b12ba4e0c5c895565c91e04822238ead551` |
| `FPVS-Studio-Patch-2.4.0-to-2.4.1.exe` | 98477396 | `1b9a076f2246d9d2e6398a4c4c22dca0ca5b0d07e8e7fdde474a0bf173e6d5c5` |
| `FPVS-Studio-Update-2.4.1.json` | 435 | `ea769fdaa08eabbc667996bc5ec046fc6a32c65485ec62518f39c7ccbf7cb191` |

The three checksum sidecars complete the six-asset set. All 7,987 owned payload
files match the full installer. The authenticated 2.4.0 patch changes/adds 86
files, removes 22, and reconstructs the same complete target. All 228 embedded
Studio modules match the committed source, with no extras. All 493 native input
records match reviewed source/hash custody; 53 native updates belong to reviewed
Qt, cryptography and serialization distributions, with no unexpected inputs.

The embedded Library code and bundled cryptography 50.0.2 accepted the exact
real OpenFPVS Masking proof under the independent Ed25519 pin and the RFC 8032
vector, and rejected altered signatures/digests. This diagnostic loaded embedded
PYZ code and bundled extensions in an isolated Python process; it did not run
the normal application, network or installer.

Official ClamAV 1.5.4 with fresh daily generation 28147 passed actual scans:
installer 1/1 files, patch 1/1, extracted payload 7,839/7,839 nonempty files.
All report zero infections/skips/errors, no warnings and exit zero. The complete
7,988-file extracted tree (owned files plus inventory) matches its exact ownership
map before and after scanning. Vendor scanner, definitions and asset byte custody
remain unchanged. The final scans use the supported 2 GiB minus 1 file cap;
the rejected first attempt remains separate evidence.

The user separately approved visible startup checks. The unchanged packaged
Studio passed version, native runtime imports, settings/test-mode controls and
update dialog checks. The existing bundled updater passed visible standalone
repair and synthetic failed-update repair checks, with no network or installer
execution. Both native updater screenshots were reviewed for clipping.

Anonymous public metadata and downloaded JSON/checksum sidecars match the local
files. Nine real updater selections passed: authenticated 2.4.0 selects the
direct patch; missing inventory, forced repair and older versions select the
full installer; 2.4.1 reports no update.

Verified official GitHub CLI 2.102.0 passed actual cryptographic verification
of the release and all six local assets. Signed release/v0.2 statements match
repository `zcm58/FPVS-Studio-2.0`, repository/package ID `1175530401`, owner
`203023940`, release database ID `407075169`, exact tag/source and all asset
digests. GitHub signer identity and verified timestamps passed on all seven
operations. Existing GCM credentials stayed in memory/scoped child environment;
no global authentication settings or credentials were written.

Ignored evidence under `build/release-2.4.1/` includes source/native/artifact audits,
`frozen-provenance-audit.json`, `release-malware-audit.json`,
`packaged-smoke-report.json`, `updater-gui-smoke.json`,
`native-startup-custody.json`, `public-verification.json` and
`attestation-verification.json`.

Installer Authenticode remains `NotSigned`; GitHub release attestations bind
published source/tag/assets through a separate trust mechanism. Maintainer/build
compromise and retained upstream runtime dependency limitations remain documented
boundaries. No certificate purchase, real research upload, fresh installation,
installed update lifecycle, physical-display or EEG/trigger test was performed.
The documentation-only completion follows the built/tagged source without
changing application or packaging inputs.
