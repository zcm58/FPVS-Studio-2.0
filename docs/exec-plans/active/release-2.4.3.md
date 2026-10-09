# FPVS Studio 2.4.3 updater GUI release

Status: Active

Date: 2026-10-09

## Authorized outcome

Bump the patch version, commit/push the completed updater percentage changes, and
publish a new stable release. The public release body must be exactly:

Improvements to the updater GUI

## Delivery and verification

Build the committed master candidate using the canonical packaging scripts under
isolated `build/release-2.4.3` and `dist/release-2.4.3`. Retain the full installer and
include a direct patch from the authenticated public 2.4.2 ownership inventory.
Verify native dependency preservation, frozen source/version identity, full payload,
exact patch reconstruction, all asset sizes/digests and live updater selection.
Stage as a draft, verify its uploads, then publish and verify exact master/tag refs.

The source implementation already passes repo precommit: 2,921 tests, 20 subtests,
11 Windows symlink-permission skips, Ruff, compilation, mypy and repo/docs audits.
The shared Inno script compiles with a safe synthetic fixture. Run fresh metadata,
packaging and documentation checks after the version bump. Registered Qt, visible
packaged GUI and installed-update checks are unrun; publication was requested after
these boundaries were reported. Do not run an installer on the working installation.

## Acceptance

- [x] Version and editable metadata agree; focused release checks pass.
- [ ] Exact source candidate committed and pushed to master.
- [x] Authenticated 2.4.2 baseline and matching build dependencies recorded.
- [ ] Full installer, 2.4.2 patch, update JSON and checksum sidecars built.
- [ ] Frozen/native/full-payload and exact patch reconstruction audits pass.
- [ ] Draft assets match local digests; public release/body/tag verified.
- [ ] Live updater selection and final clean master/remote refs verified.

Evidence and logs stay in the isolated ignored release directories. This plan will
move to completed after publication. Earlier releases and drafts remain intact.

Fresh version checks passed: packaging focused (181 tests) and docs focused
(10 tests). Source and installed editable metadata both report 2.4.3. The public
2.4.2 full installer SHA-256 is
`6f42a547bd4139f0a7d0b10b3b5dd38afe11bc0e01f09d7830b456d3efc42b63`;
its authenticated ownership inventory SHA-256 is
`3f3c2863b5acacd0a88fd5de71aa8ce36996bf062550aa8710843d99240f9134`.
All 7,062 baseline payload files match that inventory, and bundled dependency
versions match the local build environment without changes.
