# Studio 2.4.4 minor bug fixes

Status: Completed

Date: 2026-10-09

## Authorized outcome

Fix all seven findings from the Studio review, summarize the fixes, bump the patch
version, commit/push and publish a stable release with the exact body:

minor bug fixes

The remote advanced to published 2.4.3 after review. Integrate its updater progress
and upload activation records, then use 2.4.3 as the authenticated patch baseline.

## Scope and acceptance

- [x] Project handoff honors one decision, preserves the current project on failure,
  and restores it when closing is declined after a new edit.
- [x] Upload authorization failures preserve unrelated Library credentials and exact
  submission ownership; New Upload binds the current project.
- [x] Crash opt-out persists independently of busy HTTP; logging budget or sink
  failure does not mark a running session clean or remove subsequent recovery.
- [x] Reporting exposes capture capacity and reviewed local archival of terminal
  ineligible captures, preserving private evidence and recoverable/accepted reports.
- [x] Launch drains ordinary reporting and the noncancelable opt-out persistence job.
- [x] Focused checks, registered visible synthetic Qt and repo precommit complete.
- [x] Version/source/editable metadata agree and the source candidate is pushed.
- [x] Canonical isolated full/patch builds, packaged smoke, frozen-source/native
  inventory and exact patch reconstruction pass.
- [x] Draft uploads match audited hashes; public notes/tag/assets/attestations and
  updater selection are verified; archive the completed record and push it.

## Boundaries

Use app-owned jobs and existing project/support storage owners. Preserve research
data, project/export formats, immutable receipts, capability namespaces and native
thread cleanup. No HTTP in fault handlers or presentation, silent permission fallback,
real research upload, hardware experiment, working-installation mutation or separate
crash-service activation is authorized by this release task. The existing approval
permits visible synthetic Qt and packaged checks with fake services and isolated
settings. Keep all release evidence in ignored versioned build/dist directories.

The active automatic-crash and reporting plans retain their independent rollout
items. Published whole-project backend activation is recorded in its refreshed plan.

## Progress

Fetched and fast-forwarded three remote commits through `817aa87`. Latest published
release is immutable 2.4.3. Initial packaging focused verification passes 181 tests.

All seven reviewed findings are fixed. Combined GUI verification also detected a
late startup sharing callback into disposed windows; validity checks now suppress it.
Focused checks pass: Library 372 tests (three Windows symlink skips), reporting 194
tests excluding only the full-gate stress case, support 61 tests (one symlink skip),
GUI 17 safe checks, packaging 181 and documentation ten. Source and editable metadata
agree on 2.4.4. The full non-Qt precommit gate passes: 2,960 tests and 11 existing
Windows symlink-permission skips in 495.72 seconds. Ruff, compilation, mypy over
234 modules and repo/docs audits pass. The 1,500-session stress case passes.

Registered visible acceptance passes 246 checks, including every changed workflow,
both reporting/upload sizes, blocked fake HTTP, worker cleanup and startup. One
unrelated existing Manage Projects clipboard check fails: Windows returns
`OpenClipboard Failed`/`0x800401d0`, including on an isolated recheck. It is retained
as an environment-dependent verification limit, not a passing clipboard check.
The 68 startup/Library/handoff checks also pass independently. Evidence is in
`build/release-2.4.4-visible.xml` and `build/release-2.4.4-clipboard-recheck.xml`.

The authenticated 2.4.3 baseline contains 7,987 owned files; inventory SHA-256 is
`bf50fff4989efdaa26d5b16f518fcdbdff69026760694a17473c85c285db82a3`.
All six assets and seven signed attestations pass. All 29 dependency versions match
the current build environment. The canonical current collector omits five optional
Python test/Tcl/Tk binaries and 922 associated data files, as the earlier 2.4.2 build
did; no Studio or installed PsychoPy workflow imports Tk. All 482 retained native
files match the baseline exactly. Final build audits and supported runtime imports
confirm this reviewed omission without native additions or changes.

Source candidate `b6328182486e70ed2dd3b9dc730571a5b32e8b38` and tag `v2.4.4`
are pushed. Canonical full and sparse-patch builds pass with isolated dependency
paths, the authenticated 2.4.3 inventory and unchanged runtime dependencies. Visible
packaged Studio/backend and updater smoke checks pass with network and installer
execution disabled. The frozen source audit matches all 234 Studio modules and 22
updater modules to the candidate. All 486 Studio and 69 updater native analysis
inputs have trusted custody; retained native bytes match the published baseline.

The full payload matches all 7,062 owned files. The 2.4.3-to-2.4.4 patch reconstructs
that payload exactly: 30 changed files, 7,032 retained files and 937 removals. These
removals are the reviewed 927 optional Python/Tk files, eight superseded Studio
metadata files and two harmless dependency `REQUESTED` markers. Target inventory
SHA-256 is `ca6f280bacc4bb689e5a90327933ee6e631f5af524dee94ea0aa3269974ddd89`.
Evidence is retained in `build/release-2.4.4-evidence/artifact-audit.json` and the
packaged smoke records. No installer was executed against the working installation.

Draft release `408423379` verifies the exact source/tag, title and notes, and all six
server asset sizes and SHA-256 digests match freshly hashed audited local files.
It was published as latest stable at
[FPVS Studio 2.4.4](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.4.4).
Public verification passes: the release is immutable and latest stable, with the
exact body `minor bug fixes`. Anonymous production release metadata and update JSON
match authenticated metadata. Registered 2.4.3 installations with the authenticated
inventory select the direct patch; 2.4.2, 2.4.1 and 1.4.0 select the full installer.
Missing registration/inventory, forced full and repair cases also select full.
Current 2.4.4 reports no update; explicit repair selects full. The signed release
and all six signed asset attestations pass. Evidence is retained under
`build/release-2.4.4-evidence/`, including `draft-verification.json`,
`public-verification.json`, public feed/manifest records and signed verification
records. No publication retry or artifact mutation was needed.

## Published assets

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.4.4.exe` | 298720508 | `02f351f3b6c01cd1533572c7eb4c597f9e54cf000538c50f12a702f16757f4e6` |
| `FPVS-Studio-Patch-2.4.3-to-2.4.4.exe` | 72135468 | `0f31f1d7b6bc2c0e2f878a6c839834f7e5236374267fee83798d1c53b76a9936` |
| `FPVS-Studio-Update-2.4.4.json` | 435 | `b13b5b33846e3943d9058dbbb41eb1374661a68241678c9b218e179c41712f05` |
| `FPVS-Studio-Setup-2.4.4.exe.sha256` | 95 | `70f9475c0d663ca066ed31780d0094074d93b3898db2e4b7ce32b6a09b6940f5` |
| `FPVS-Studio-Patch-2.4.3-to-2.4.4.exe.sha256` | 104 | `8b812751a78da90ce0cbc7d93714723a23f102b9ccaebe5c53ab59f6fb6e5e5c` |
| `FPVS-Studio-Update-2.4.4.json.sha256` | 97 | `ad6d05ab2ebb6366baf1011b3b1b412c15950f1e5eb354ff7803e4e0fe03015a` |

## Remaining qualification boundaries

The Windows clipboard refusal documented above remains an environment-dependent
verification limit. Clean-machine installation, an actual installed upgrade and
physical experiment/hardware qualification were not performed. The automatic
crash-email service still requires its independent authenticated activation and
rollout; desktop preference and recovery fixes are released here. Whole-project
upload backend activation was already recorded by the integrated remote changes.
The independent active crash-reporting and reporting plans retain their remaining
rollout/qualification items.
