# Prevent duplicate Library installations and release 1.9.1

Status: Active

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

Packaging will use the authenticated published 1.9.0 installer: SHA-256
`242445b4bdf6707b50d3c172279103f8043c1bf6b412f9c95d5cc49c468f3504`,
inventory SHA-256 `57bac84e4af57c154573382a1bdc82f3fb22f29eb5baf3b93a569e293efcd797`.
