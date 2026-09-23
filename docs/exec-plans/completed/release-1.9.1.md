# Prevent duplicate Library installations and release 1.9.1

Status: Completed

The user reproduced duplicate Masking downloads and authorized a fix, merge to the
repository's main branch (master), version 1.9.1 and release publication.

## Acceptance

- Scan the configured Studio Root Folder in workers before Library downloads.
  Use stable service/item/version receipts; include nested projects and renamed copies.
- Mark equal/newer installed versions as installed and block repeat downloads.
  Offer explicit review of an existing project for newer or unknown versions.
- Legacy ID/title matches are possible existing projects, not trusted associations:
  block ordinary download and require explicit linking/version review.
- Recheck before download and import; the project-version flow must also detect a
  release already installed elsewhere. Preserve all existing projects and participant data.
- Add a regression at the importer (observed failing before the fix), pure scanner/
  decision/download tests and registered GUI coverage. Run focused and precommit gates.
- Publish full v1.9.1 and a direct patch from authenticated published v1.9.0; verify
  embedded code, payloads, reconstruction, GitHub digests and live updater selection.

Visible Qt, installed upgrades and physical EEG/display checks remain unrun unless
separately authorized. Existing duplicates are retained, not deleted or merged.

## Progress

The failing regression confirms the second same-release import creates a duplicate.
The Library had no installed-project scan; general bundle import collision naming
is intentional, but is inappropriate for repeated Library installation.

Implemented worker-side discovery and status, legacy review, duplicate transfer gates,
existing-project handoff and same/newer receipt checks at bundle commit. A read-only
scan of the configured local Root found six projects and correctly classified Masking
as an unlinked review candidate; it wrote no project files.

Verification: Library focused 223 passed / 3 Windows symlink skips; project-io focused
232 passed / 2 skips; GUI focused non-Qt checks 7 passed. Repo precommit passed Ruff,
compilation, mypy (206 source files), repository/docs audits and 2,085 tests with 10
Windows symlink skips. Final receipt/scanner/download tests (including two additional
import cases) passed 42 / 2 skips; final changed-controller mypy passed. Registered
Qt coverage includes installation states and long paths at both Library sizes, stale
catalog click checks, existing-project Save/handoff guards and updates already installed
elsewhere. Qt coverage is not executed locally.

Packaging used the authenticated published 1.9.0 installer: SHA-256
`242445b4bdf6707b50d3c172279103f8043c1bf6b412f9c95d5cc49c468f3504`,
inventory SHA-256 `57bac84e4af57c154573382a1bdc82f3fb22f29eb5baf3b93a569e293efcd797`.

## Published result

- Release source on master and annotated tag `v1.9.1` identify commit
  `8f4b82757056579c78881c9a0c3c5e55fcbaa5a8`.
- [Release v1.9.1](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v1.9.1)
  (ID 394730137) is the latest stable release. All six public assets match local
  sizes and GitHub SHA-256 digests. Public checksum files and the update manifest
  were downloaded anonymously and verified.
- Full-installer extraction verified all 7,985 owned files. The direct 1.9.0 patch
  changes/adds 13 files, removes eight obsolete files and retains 7,972. Patch
  reconstruction matches every full-target hash and the advertised transaction.
- All seven changed embedded application modules match compiled release source.
  The updater's non-GUI packaging diagnostic passed. All 493 native-library inputs
  match published 1.9.0 bytes; no runtime dependency upgrades were introduced.
- Live updater discovery selects the patch for the authenticated 1.9.0 inventory,
  the full installer for 1.8.0 and unregistered 1.9.0/1.8.2 installations, and no
  update for 1.9.1. These checks do not execute an installer.
- Evidence is retained in `build/release-1.9.1/`; distributables are in
  `dist/release-1.9.1/installer/`. Existing experiments and duplicates were not modified.
- Visible Qt/packaged GUI, clean-PC installation, installed upgrade, physical display
  and EEG checks remain unrun, as disclosed in the release notes.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-1.9.1.exe` | 300984155 | `088cb8d77218e18c6a9bacfac78df98163fb921a608b85957394f8a4c9328e76` |
| `FPVS-Studio-Patch-1.9.0-to-1.9.1.exe` | 72346287 | `4c348c63cfb716b569efce4e61bec34f05fa59a4cd31ae575c9413e6c8af1b49` |
| `FPVS-Studio-Update-1.9.1.json` | 435 | `787aa75ba2af8e1377d36870265c40730ef399c61cbda3606bb889b27207b3b7` |

Each artifact has a published `.sha256` companion. Other baselines use the full installer.
