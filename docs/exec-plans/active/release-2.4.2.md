# FPVS Studio 2.4.2 startup crash fixes release

Status: Active

Date: 2026-10-09

## Authorized outcome

The user requested committing/pushing Studio changes and, if the crash fixes were
not released, a version bump and public release with the exact note below. Published
2.4.1 predates crash-fix commit `b3d5328`; release 2.4.2 includes that commit and the
merged reporting/upload updates. Preserve all existing releases and the 2.2.7 draft.

## Exact release note

fixed several backend issues causing crashes after startup

## Delivery route and boundaries

Use the canonical packaging scripts under isolated `build/release-2.4.2` and
`dist/release-2.4.2`, with the checksum/attestation-authenticated published 2.4.1
installer as the direct-patch baseline. Keep source, installed/bundled metadata,
tag and artifact versions aligned. Compare native dependencies against the published
baseline and preserve reviewed versions. Stage all installer, patch, update JSON and
checksum assets as a draft, verify their bytes, then publish an immutable release.

The earlier user approval permits visible synthetic Qt/packaged checks with isolated
settings and fake network/projects. No agent-run installation over the user's working
copy, real research upload, hardware experiment or separate service activation is
part of this release. Automatic crash-report service intake remains inactive pending
its independent authenticated rollout. Clean-PC and physical runtime qualification
remain separate and must not be claimed as passed.

## Acceptance

- [x] Confirm latest public release and crash-fix ancestry; fetch current remote refs.
- [x] Run initial packaging focused checks (181 passed).
- [x] Authenticate/download/extract the exact 2.4.1 baseline and preserve its inventory.
- [x] Bump/verify 2.4.2 metadata, commit and push the initial build candidate.
- [ ] Build full installer, direct patch, update JSON and checksum sidecars.
- [ ] Verify frozen source/native inputs, complete ownership and patch reconstruction.
- [ ] Run approved visible packaged startup/shutdown and updater smoke checks.
- [ ] Upload a draft and verify all asset digests before immutable publication.
- [ ] Verify public tag/body/assets/attestations and updater selection.
- [ ] Record final evidence, complete this release plan and push documentation.

## Existing source evidence

Merged source has 78 passing visible Qt checks, 52 repo-focused and ten documentation
checks, passing Ruff/compilation/mypy and configuration audits. The full safe suite
passed 2,918 cases with 11 Windows symlink skips and one exact retry-count assertion
failure; all eight serialization tests passed on recheck. The complete record is in
[automatic crash reporting](automatic-crash-reporting.md#october-9-remote-integration).
Release-specific frozen checks remain required.

## Candidate preparation

The public 2.4.1 release and downloaded full installer pass actual GitHub release and
asset attestation verification. Its 300,686,648-byte installer matches SHA-256
`3aa9557c89518863b6bc5858fbc84b12ba4e0c5c895565c91e04822238ead551`.
The verified portable extractor is checksum-pinned and never executes setup.
All 7,987 extracted owned files match the shipped inventory, whose SHA-256 is
`dcf7bcf859ad3068fb1eaa02aa9dd58ed3f9421c95dad97441af0cfd97414a29`.
Version 2.4.2 source/editable metadata and the candidate packaging focused checks
pass (181 tests); documentation focused passes ten. Runtime constraints are derived
from the authenticated baseline's package metadata, including Qt 6.11.2 and
cryptography 50.0.2. Evidence remains in ignored `build/release-2.4.2-baseline/`.

Initial candidate `33e6a13` and the crash/merge commits are pushed. Additional frozen
version inspection found idna 3.18 on this host versus baseline 3.20; the packaging
environment was aligned before rebuilding. All 29 checked package versions now match
the authenticated baseline. The interrupted build/verification logs are retained.
The Studio executable builds successfully. The independent updater's packaging guard
needed the shared `gui.thread_completion` module added to its narrow GUI allowlist;
the scientific/runtime exclusions remain intact. Rebuild the updater and installer
with that packaging correction before publication.
