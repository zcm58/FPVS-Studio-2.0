# Studio 2.4.8 minor bug fixes release

Status: Completed

Date: 2026-10-25

## Authorized outcome

Commit, push and publish version 2.4.8 with the exact GitHub release title
`minor bug fixes`. Build a full Windows installer and direct 2.4.7 patch from the
isolated crash-recovery worktree, preserving the primary checkout's unrelated
edits and the installed 2.4.7 application.

## Scope and source

Runtime fixes are committed and pushed as
`1d27c33833e53a1808a7cd8194b439f0af963859`. They cover reusable task graphics and
cleanup, finite numeric input, restoration after task-input setup failures,
durable completed results during later failures, interrupted-condition recovery,
and deferred-launch/persistent-worker lifecycle races. The
[runtime reliability audit](runtime-reliability-audit.md) records
the implementation and source verification.

Only package version and release documentation change during this release task.
There are no new scientific methods, runtime formats or architecture boundaries.
No architecture update is needed.

## Verification and release source

Release source `a2f5a6d84af2779a14b48951bd837619766f14b5` was committed and pushed
to master before building. The annotated `v2.4.8` tag resolves to that exact commit.

- Packaging focused: 181 tests passed after refreshing editable app metadata.
- Updates focused: 311 passed, four Windows symlink-permission skips.
- Documentation focused: ten tests and documentation audits passed.
- `pip check` passed; installed build metadata and source version agree at 2.4.8.

The source audit's broad precommit had 3,276 passes, 20 passing subtests, 12
Windows symlink-permission skips and two intermittent Windows directory-rename
failures. Both exact failed cases passed unchanged on immediate rerun. See the
runtime audit record for commands and evidence; this is not an all-green full run.

## Build custody and artifact acceptance

The authenticated immutable 2.4.7 baseline full installer has 300,764,605 bytes and
SHA-256 `2c08d51976796dcb38dfffa939eef1724aea2f81b88385c568d54a4a5ffae1bd`.
Its signed release and asset attestations were reverified. Fresh extraction verified
all 7,989 owned files and both embedded inventory copies. Baseline inventory SHA-256:
`520ebb0394aa538de6e8adf196534a2c931aa6b6414ae15d5bf2ae12232cbd3b`.

The existing isolated Python 3.10.11 environment and dependency versions were
preserved; only editable application metadata was refreshed with `--no-deps` and
`--no-build-isolation`. The restricted build-process PATH matches the prior release
and excludes unrelated application directories. The Windows `threadpoolctl`
exclusion remains unchanged. Inno Setup 6.7.3 built both installers. These commands
used that process environment:

```powershell
.\scripts\build_exe.ps1 -SkipInstall -BuildLabel release-2.4.8
.\scripts\build_installer.ps1 -SkipSmoke -BuildLabel release-2.4.8 `
  -InnoCompiler "$env:LOCALAPPDATA\Programs\Inno\ISCC.exe" `
  -BaselineInventory 'build/release-2.4.8-baseline/extracted/{app}/fpvs-owned-files-v1.txt' `
  -BaselineInventorySha256 520ebb0394aa538de6e8adf196534a2c931aa6b6414ae15d5bf2ae12232cbd3b
```

The extracted full installer matches all 7,989 target owned-file hashes. The patch
reconstructs the exact target using 12 changed/added files and 7,977 retained files,
with no unchanged files rewritten. Its eight removals are only obsolete 2.4.7
application distribution metadata. Target inventory SHA-256:
`0a8ca26283f8ce2b5df37422765ef6c4f764eb5abaa8013268410786f58cacda`.

All 240 frozen Studio modules, 22 updater modules and both entry points match the
release source. All 4,448 Studio and 126 updater dependency modules match baseline
module sets and normalized code. Both 151-entry standard-library ZIPs match baseline
headers and code. All 487 native payload files, 491 final Studio native analysis
records and 69 updater native inputs match baseline bytes and approved source roots.
All 7,961 non-application payload files are unchanged, with no metadata exceptions.
The GUI-free updater diagnostic confirms frozen version 2.4.8, protocol 1 and no GUI
imports. Seven audit-helper self-checks reject dependency payload and frozen-code drift.

## Publication

Immutable release `423459120` is published as latest stable with the exact title
`minor bug fixes` at
[v2.4.8](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.4.8).
All six uploaded asset sizes and SHA-256 values, exact notes/title and source tag
passed draft verification before publication. Public metadata, update manifest,
the signed release attestation and all six signed asset attestations pass.
All six independently downloaded public assets match audited sizes and SHA-256
values; signed downloaded-file attestations also pass for all six.

Eleven candidate and eleven public updater cases pass. Authenticated 2.4.7 selects
the direct patch; older versions, missing registration/inventory, forced full and
repair select the full installer. Current 2.4.8 reports no update, with full reinstall
available for explicit repair. Evidence is retained under ignored
`build/release-2.4.8-evidence/`, `build/release-2.4.8-baseline/`, and the isolated
release build directories. Authenticode is not configured; GitHub immutable-release
attestations are separate signed provenance.

## Published assets

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.4.8.exe` | 300758326 | `b06a20817ca2cf65a52edd8b6aff33a65c23dfefb585d1bbbcdcf3ea47cd5ef8` |
| `FPVS-Studio-Patch-2.4.7-to-2.4.8.exe` | 72236235 | `70763451717594de0a3c23885342a7835e1f387875644cba596b19930cede13b` |
| `FPVS-Studio-Update-2.4.8.json` | 435 | `d90e4c57f4a212733b99fc0a4f81ac742d21485a8335a5a4233512506138d6c4` |
| `FPVS-Studio-Setup-2.4.8.exe.sha256` | 95 | `28730a760b49dba3d89c2c7767b111387e75650b8f91622382aa7fb616013c4d` |
| `FPVS-Studio-Patch-2.4.7-to-2.4.8.exe.sha256` | 104 | `a9f143691aa2edb8b07f7a9aab34d17e5ab8d6e7329671785132ecebaab45270` |
| `FPVS-Studio-Update-2.4.8.json.sha256` | 97 | `7433a14df6355ed7053565a21ffdc3d62c3902748fb482fb9346159a940998ce` |

## Acceptance boundaries

Visible Qt/native graphics, physical display/EEG timing, clean-machine installation
and destructive installer lifecycle checks remain unperformed. Artifact checks do
not establish those results. No installer was executed on the working machine
for this release task. The installed app remains 2.4.7. Automatic crash-email
service activation is separate and remains pending; the release does not deploy
the feedback service.
