# Studio 2.4.4 minor bug fixes

Status: Active

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
- [ ] Version/source/editable metadata agree and the source candidate is pushed.
- [ ] Canonical isolated full/patch builds, packaged smoke, frozen-source/native
  inventory and exact patch reconstruction pass.
- [ ] Draft uploads match audited hashes; public notes/tag/assets/attestations and
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
must confirm this reviewed omission without native additions or changes.
