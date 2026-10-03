# FPVS Studio 2.2.5 Release

Status: Active

## Scope

Release the requested compatibility fixes for bundle transfers, opening imported
projects, root/template setup, Windows path handling and scaled display calculations.
Build from committed master using the existing executable/installer scripts with
isolated release-2.2.5 outputs. Include the full installer, a direct 2.2.4 patch,
update metadata and checksum files.

## User Authorization And Check Boundary

The user requested publication and then explicitly said "skip release checks to be
faster." Additional release tests, installer extraction/reconstruction audits, source
and native payload audits, GUI smoke, installed-upgrade tests and live updater-selection
tests are waived for this release. Existing implementation verification remains recorded
in the active private-library audit. Packaging focused had already started before the
waiver and completed with 181 tests passing.

The build retains required metadata/inventory checks and its bounded updater backend
diagnostic. Baseline identity is required for patch creation. Publication uses the
resulting installer/update files and confirms GitHub accepted the assets; waived tests
must not be described as passed. No existing installation or project data is modified.

## Release Notes

Use the user's exact text:

Improved backend handling of long windows filepaths causing errors on some systems.

## Progress

- Version bumped to 2.2.5 in the canonical pyproject.toml metadata.
- Published latest baseline confirmed as v2.2.4.
- Compatibility fixes and version committed and pushed to master at
  `c63990f17e6a9d5d01c4b14aac67499fc6e67579`.
- Editable package metadata refreshed to 2.2.5 without changing runtime dependencies.
- Published 2.2.4 installer downloaded and its ownership inventory prepared for the
  direct patch. Build and publication pending.

## Resume Checkpoint

The user requested a checkpoint because the PC was about to lose power. At that
checkpoint no build, upload, draft release, tag or publication had started, and no
release subprocesses were left running. The user resumed work on October 2, 2026;
the release-check waiver and exact release note remain in force.

Current checkout: master in `C:\Users\zcm58\PycharmProjects\FPVS-Studio-2.0`.
The source commit above is pushed. This checkpoint document is the only intended
new tracked change after that commit; build helpers and evidence are ignored.

Prepared files in `build/release-2.2.5/`:

- `build.ps1`: clean-master build using the existing sanitized PATH, isolated
  outputs, `-SkipInstall -SkipSmoke`, and the authenticated direct 2.2.4 baseline.
- `source-commit.txt`: c63990f17e6a9d5d01c4b14aac67499fc6e67579.
- `baseline.json`, `previous-release.json`, `prepare_baseline.py`, and
  `baseline-2.2.4/`: downloaded baseline and extracted ownership inventory.
- `publish.py`: upload six assets to a new GitHub draft, then publish stable/latest.
  Credentials come from the existing protected Git credential helper in memory.
- `release-notes.md`: the exact user-provided sentence, with no added release text.

Baseline inventory SHA-256:
`9037a79a974a5307b4ea5428b67ced6056d69a4e4e153ff3f2e530628e56b459`.
Baseline installer SHA-256:
`f542c3230ded3fd0960b814c759fff12606d67659d4746e6350339c86bee3dac`.
Inno compiler: `C:\Users\zcm58\AppData\Local\Programs\Inno Setup 6\ISCC.exe`.
GitHub CLI is unavailable here; the prepared publisher uses the GitHub API.

When the user resumes:

1. Inspect status and current remote master; preserve any new user changes. Read this
   checkpoint before exploring the repository. Keep the user's waiver of additional
   release checks and exact release note in force.
2. Commit this checkpoint documentation before building so the checkout is clean.
   Update `build/release-2.2.5/build.ps1`'s release commit and `source-commit.txt` to
   that final release-source commit; push master. If source changed since this
   checkpoint, reconcile the release scope before packaging.
3. Run `./build/release-2.2.5/build.ps1` in native Windows execution context. It writes
   `build.log`; report progress without running the waived audits. The build still
   includes its mandatory no-GUI updater packaging diagnostic.
4. After a successful build, create/push `v2.2.5` at the exact built source commit.
   Run `.venv3.10\Scripts\python.exe build/release-2.2.5/publish.py draft`, then
   `publish.py publish`. Publication readback checks uploaded sizes/digests and the
   exact release note; installer extraction, reconstruction and live updater-selection
   tests remain waived.
5. Record artifacts/publication and skipped checks, move this plan to completed,
   update the packaging release link and private-library audit release status, commit
   and push the documentation. Remove only the fully merged
   `codex/bundle-transfer-reliability` branch created for this task; preserve unrelated
   branches and all prior/user-owned output. Report the release URL and clean state.
