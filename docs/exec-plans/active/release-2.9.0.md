# Studio 2.9.0 release

Status: Active

## Requested outcome

Authorized on 2026-11-10. Bump Studio and publish a new GitHub release with the
Settings category sidebar and scrollable right-side pages. Include the previously
requested restricted Windows build PATH and pre-upload DLL-origin verification.

Use 2.9.0 for this user-facing Settings redesign. Build from an isolated source
checkout and copied, pinned dependency environment. Preserve the existing controls,
per-computer preferences and project recording callbacks.

## Acceptance

- [x] Source Settings checks passed 99 visible cases at the prior feature commit.
- [x] Verify the reviewed DLL-origin changes and new version in the release checkout.
- [x] Expand frozen Settings smoke coverage to all categories and overflow scrolling.
- [ ] Commit the exact build source and run focused, precommit and GitHub CI checks.
- [ ] Build the full installer and update manifest with restricted build PATH.
- [ ] Run native packaged Studio/updater checks and verify frozen Settings behavior.
- [ ] Audit DLL origins and compare native dependencies with authenticated 2.8.2 output.
- [ ] Create a draft with all assets, verify remote hashes and publish immutable/latest.
- [ ] Verify fresh public downloads, attestations and updater selection.
- [ ] Record the exact source, artifacts and checks, and archive this plan.

## Scope

Settings uses General, Recording, Appearance, Workspace, Advanced and Diagnostics.
Each category retains its controls and scroll position. Navigation and Close remain
fixed while page content scrolls. Native visible checks use the approved Windows
desktop and synthetic inputs. Installer acceptance uses extraction and disposable
output, with real acquisition hardware qualification outside this UI release.

The Windows artifact route produces a full installer, update JSON and SHA-256
sidecars. Direct patches are optional and require an authenticated matching baseline.
Release notes use short user-facing bullets. Detailed verification belongs here and
under ignored `build/release-2.9.0-evidence/`.

## Source preparation

- The isolated dependency copy retains the existing runtime versions. Refreshed
  editable package metadata and the source both report 2.9.0.
- Packaging focused verification passed 212 tests, including process PATH restoration,
  foreign DLL rejection and release receipt mismatch detection.
- The expanded visible Settings smoke helper passed 24 category/size/theme cases and
  two wheel-overflow cases in source before freezing the application.
- The published immutable 2.8.2 installer and sidecar passed asset attestation and
  digest verification. Its extracted inventory verifies all 7,987 owned files.
