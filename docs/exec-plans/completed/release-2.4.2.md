# FPVS Studio 2.4.2 startup crash fixes release

Status: Completed

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
- [x] Build full installer, direct patch, update JSON and checksum sidecars.
- [x] Verify frozen source/native inputs, complete ownership and patch reconstruction.
- [x] Run approved visible packaged startup/shutdown and updater smoke checks.
- [x] Upload a draft and verify all asset digests before immutable publication.
- [x] Verify public tag/body/assets/attestations and updater selection.
- [x] Record final evidence and archive this completed release plan.

## Existing source evidence

Merged source has 78 passing visible Qt checks, 52 repo-focused and ten documentation
checks, passing Ruff/compilation/mypy and configuration audits. The full safe suite
passed 2,918 cases with 11 Windows symlink skips and one exact retry-count assertion
failure; all eight serialization tests passed on recheck. The complete record is in
[automatic crash reporting](../active/automatic-crash-reporting.md#october-9-remote-integration).
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
the scientific/runtime exclusions remain intact. The updater and installer were then
rebuilt with that correction before publication.

## Published delivery and acceptance

[Studio 2.4.2](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.4.2) is the
latest public stable release, ID `407843116`, with `immutable: true`. Source, tag and
artifact metadata identify `18ce9ad44b386218fb5362b1170eb85fd32cad34`. The public body
is exactly the requested release note. All six uploaded assets match audited local
sizes and SHA-256; the separate 2.2.7 draft remains untouched.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.4.2.exe` | 298701268 | `6f42a547bd4139f0a7d0b10b3b5dd38afe11bc0e01f09d7830b456d3efc42b63` |
| `FPVS-Studio-Patch-2.4.1-to-2.4.2.exe` | 72128250 | `55ccb8a35bf298fbeea57ac2cdcde54d5a1ac32865675e2a69ec812a08300f29` |
| `FPVS-Studio-Update-2.4.2.json` | 435 | `4278a153b6e4a8ca4b86738074c1e497fbdec6cecf327b9ea08c739483fc3ffc` |

The three checksum sidecars complete the asset set. The full extracted installer
matches all 7,062 target-owned files. The direct patch changes/adds 31 files, removes
937 known obsolete files and reconstructs that exact target. Removed files comprise
old Tcl/Tk data, Python test extensions and stale packaging metadata; the supported
PySide6 and PsychoPy backend imports pass. All 234 embedded Studio modules and the
updater's 22 Studio modules match candidate source, including native thread cleanup.
All 488 collected DLL/Python-extension inputs match reviewed input paths and hashes
and are byte-identical to the authenticated published baseline. No foreign native
dependency is introduced. The target inventory SHA-256 is
`3f3c2863b5acacd0a88fd5de71aa8ce36996bf062550aa8710843d99240f9134`.

Native visible packaged Studio checks pass version, runtime imports, Settings/test
mode, pilot controls, themed update buttons and dismissal. The independent updater
passes backend-only packaging diagnostics, standalone repair UI and synthetic
failed-update repair, without networking or installer execution. The corrected
dependency-graph regression and packaging focused suite pass 181 tests, with Ruff
and compilation passing for the changed test.

The final full safe suite completes with 2,918 passes, 11 Windows symlink skips and
one Windows access-denied bundle-import failure in the existing COM3 publishing test.
All 15 Library publishing cases pass in a fresh profile recheck. This resembles the
already recorded intermittent Windows rename failures; no unrelated persistence
fallback or source change was added. The full gate's failed result is retained and
is not presented as a wholly passing run. Mypy over 234 modules and repo audits pass.

Anonymous public updater metadata and the downloaded update JSON pass exact digest
verification. Nine actual selection checks pass: 2.4.1 with authenticated inventory
selects the patch; older versions, absent registration/inventory and forced full/
repair select the full installer; 2.4.2 reports no update. Official GitHub CLI 2.96.0
cryptographically verifies the release and each of the six exact local assets against
GitHub's signed attestations. The source/tag/artifact association is immutable.

Evidence is retained under ignored `build/release-2.4.2/` and
`build/release-2.4.2-baseline/`: baseline attestations/inventory, runtime versions,
source/native/patch audits, packaged/updater reports, the full precommit log and
Library recheck XML, draft/public verification and all seven attestation results.
The first CLI draft request used an unsupported short target commit; its validation
failure created no release, and the retry used the verified full commit. Draft
verification used the confirmed release ID because the draft's tag endpoint returned
404; publication then exposed the canonical version URL.

Installer Authenticode remains unsigned; the separate GitHub attestation mechanism
binds exact published bytes. No fresh installation, live research upload, physical
experiment, EEG/trigger test or user-installation mutation was performed. Automatic
crash-email intake remains inactive pending the separate service's authenticated
rollout. The desktop changes are released; the service plan stays active.
