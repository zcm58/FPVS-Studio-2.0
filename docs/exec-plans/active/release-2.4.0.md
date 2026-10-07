# FPVS Studio 2.4.0 live results sharing release

Status: Active

Date: 2026-10-07

## Scope and authorization

The user requested a new public installer release with the exact note below.
Use minor version 2.4.0 for the new reporting workflow, integrating the reviewed
`codex/openfpvs-project-reporting` source with released master. Build from the
committed, clean master candidate. Preserve the independent 2.2.7 draft.

The existing OpenFPVS backend is already deployed. Studio connects through an
approved lab/project grant and requires separate per-experiment opt-in. Results
are private to the lab and administrator and refresh when the project page loads.
Counts represent completed sessions. Participant numbering and Toolbox reporting
remain deferred. This release produces a Windows installer; cross-computer and
browser sharing does not establish a Linux installer or hardware qualification.

Support one direct patch from the authenticated public 2.3.0 installer, alongside
the complete installer. Use the existing packaging environment and scripts.

## Exact release note

Studio now supports live results sharing across platforms

## Verification gates

- [x] Verify current release/source state and integrate the tested reporting branch.
- [x] Pass packaging focused verification and safe repo precommit: 181 packaging
  tests and 2,748 non-Qt tests pass; 11 Windows symlink-privilege checks skip.
- [ ] Commit and push the clean, versioned master candidate before packaging.
- [x] Authenticate public 2.3.0 baseline bytes and extract its ownership inventory.
- [ ] Build the full installer, direct patch, update metadata and checksums.
- [ ] Verify exact full extraction, patch reconstruction, native dependencies and
  every embedded Studio source module, including the reporting packages.
- [ ] Run the previously authorized bounded visible packaged startup/updater smoke.
- [ ] Upload a draft and verify exact asset names, sizes and server/local digests.
- [ ] Publish with the exact user note; verify the public release, updater choices,
  remote master and tag, then complete this release record.

## Verification boundaries

The reporting implementation passed 144 focused checks, 13 approved visible dialog
checks and 2,748 non-Qt tests, with 11 Windows symlink privilege skips. Backend tests
and synthetic desktop/browser integration passed before this packaging request.
Reuse those results for unchanged behavior and verify the final packaged source.

Visible checks are bounded startup checks under the user's earlier approval;
no experiment, real report upload or installed upgrade will run. Fresh installation,
installed upgrade/uninstall, physical display/EEG/trigger timing and real two-PC
study acceptance remain separate operational checks and must not be claimed passed.
