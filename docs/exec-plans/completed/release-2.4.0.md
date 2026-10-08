# FPVS Studio 2.4.0 live results sharing release

Status: Completed

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
- [x] Commit and push the clean, versioned master candidate before packaging.
- [x] Authenticate public 2.3.0 baseline bytes and extract its ownership inventory.
- [x] Build the full installer, direct patch, update metadata and checksums.
- [x] Verify exact full extraction, patch reconstruction, native dependencies and
  every embedded Studio source module, including the reporting packages.
- [x] Run the previously authorized bounded visible packaged startup/updater smoke.
- [x] Upload a draft and verify exact asset names, sizes and server/local digests.
- [x] Publish with the exact user note; verify the public release, updater choices,
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

## Published source and artifacts

[FPVS Studio 2.4.0](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.4.0)
is published as latest stable, release `406245367`. The exact built source and
published tag are `e6a6802c4f7a637517f32605cd2c2481cb38086f`, verified against
GitHub master/tag before this documentation-only completion record. The release
body is exactly the requested sentence. The existing 2.2.7 draft is preserved.

The authenticated 2.3.0 baseline installer SHA-256 is
`0f772f38739a147c76ca5ad6ed2c1e33abc383e6b5fc07f2d8fb41de0f74b91d`.
Its extracted ownership inventory matches the preserved bytes and has SHA-256
`92eb924906f18b6257ff45471f11595841cc3992e143ace0b50d457a6c0979bf`.

Full extraction verifies all 7,986 payload files. The direct patch changes/adds 15
files and removes eight; it reconstructs the complete target exactly. All 487
native payload files and 493 native build inputs match the baseline. All 227
Studio modules match the pinned committed source and embedded bytecode, including
the eleven reporting modules. Checkout line-ending normalization is explicit.

The bounded visible Studio startup check reports matching 2.4.0 app/metadata
versions, runtime dependency imports and fitting controls. The independent updater
passes frozen backend diagnostics and visible repair/startup checks. No installer,
experiment or real upload runs in these checks. The build uses modern PowerShell;
an initial Windows PowerShell invocation stopped on informational PyInstaller stderr
before packaging and was rerun successfully without application source changes.

All six public asset names, sizes and GitHub SHA-256 digests match local files;
downloaded JSON/checksum sidecar bytes match too. Live updater selection chooses
the direct patch for authenticated 2.3.0 and the full installer for missing inventory,
forced repair and earlier versions (2.2.6, 2.2.5, 2.0.0 and 1.4.0). Version 2.4.0
correctly reports no update.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| Full installer | 301,102,759 | `59323a0a8ac02fc75f1fc74733d31ded796530f015ea5a2a87cd8476060a0e35` |
| Direct 2.3.0 patch | 72,470,132 | `c85381e09a5abf3ba81e9c3a4b1f47dc375d502de8a46a16addd57933954dd94` |
| Update JSON | 435 | `134cfb78a18deab0d77c72e66164f7e3a8faa91f2cb4d28b54f67b6090bd7062` |

Evidence is retained under ignored `build/release-2.4.0`; the six release assets
are under `dist/release-2.4.0/installer`. No private service backup or participant
data is a release asset. Source verification remains 2,748 passed/11 privilege
skips, packaging 181 passed and documentation 10 passed. The installed lifecycle,
Linux packaging, hardware and real two-machine study checks listed above remain
unperformed; publication does not claim that acceptance.
