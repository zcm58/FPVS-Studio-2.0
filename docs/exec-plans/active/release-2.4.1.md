# FPVS Studio 2.4.1 experiment transfer security release

Status: Active

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
- [ ] Commit and push the exact versioned candidate before packaging.
- [x] Authenticate the public baseline installer and extracted ownership inventory:
  installer SHA-256 `59323a0a8ac02fc75f1fc74733d31ded796530f015ea5a2a87cd8476060a0e35`;
  manifest SHA-256 `2589ff393edbf1283050d945e622fffa4568acb40bc54e0afa5c95281ed4bfea`.
- [ ] Build complete installer, direct patch, update JSON and checksum sidecars.
- [ ] Verify complete extraction, exact patch reconstruction, native dependency
  custody, embedded source and Ed25519 signature verification from the frozen build.
- [ ] Run the required explicitly approved native packaged startup check.
- [ ] Upload a draft and verify all assets before immutable publication.
- [ ] Verify public release body/tag/asset digests and updater selections, then
  record final refs and complete this plan.

## Verification boundaries

The previously committed security implementation passed 2,844 safe non-Qt tests,
20 subtests and 11 Windows symlink-privilege skips. The signature-order vector and
native cache/download paths passed focused checks. Final candidate version checks
and frozen artifact checks are required rather than assuming the installed binary
matches source. No real experiment, report upload, researcher account or credential
will be used in testing. Fresh installation, installed lifecycle, physical-display
and EEG/trigger checks remain separate operational acceptance boundaries.
