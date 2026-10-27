# Consolidate features and retire obsolete branches

Status: Completed

Date: 2026-10-26

## Authorized outcome

Confirm that the primary branch has all current features, integrate missing branch
work, then delete obsolete local and remote feature branches. The repository's
primary branch is named `master`; no branch rename or new release was requested.

## Audit and preservation

- Starting local and remote master: `321044698c18835275962939a4081041b2962b22`.
- No open pull requests or other checked-out worktrees. Ten stale remote-tracking
  refs were pruned after fetch confirmed their branches were already deleted.
- Ten local feature tips are ancestors of master. Local `codex/condition-review`
  is represented by replay `af85be7`, with matching changes plus a documentation heading.
- Remote `codex/experiment-library` contains missing post-import download cleanup.
- Remote `codex/library-bundle-validation` contains missing compiler workload and
  cancellation guards, bounded image validation and Library inventory safeguards.
  Its repository-rename commit is already represented by master.
- A self-contained Git bundle preserving all 15 original local/remote refs passed
  `git bundle verify` and its ref listing matches the audit. It is retained at
  `build/branch-cleanup-2026-10-26/before-cleanup.bundle`, alongside audit JSON.

## Execution and verification

1. Merge bundle-validation into current master, retaining newer project formats,
   path/security/provenance protections, condition publishing and compiled behavior.
   Verify compiler, project-I/O, preprocessing and Library coverage without Qt.
2. Merge Library cleanup, retaining current signed-provenance and transfer behavior.
   Verify cancellation, failed cleanup, lease release, repeated operation and
   preservation of imported projects and unrelated files.
3. Run repository precommit after integration. Push verified master, then recheck
   every branch's ancestry or equivalent-patch evidence before deletion.
4. Delete obsolete remote refs only at their audited tips, remove local feature
   branches and prune tracking refs. Confirm only primary branch remains locally
   and remotely, clean and synchronized; preserve release tags and bundle recovery.

## Boundaries

No publication, new installer, hardware test or Qt run is part of this cleanup.
The existing published 2.5.0 artifacts retain their recorded release source.

## Integrated features

Merge `7584fb5` incorporates bundle validation and compiler resource limits while
preserving newer signed provenance, Windows namespace paths, condition-only
publication, text-height calculation, overall JSON/event/run guards and scheduling.
Ordinary authored compilation retains `limits=None`; Library preparation opts into
additional resource budgets. The existing overall 16 MiB bundle
JSON guard remains stricter than the 32 MiB standalone stimulus-manifest cap.

Merge `6bbebc0` incorporates post-import/review download cleanup. It preserves the
current signed-proof and view-only access checks. Updated tests sign the actual
bundle metadata and explicitly simulate retained files from interrupted processes;
temporary archive cleanup preserves imported projects, unrelated files and leases.

Both original remote branch tips are now ancestors of master. The separately
verified condition-review replay remains on master, so its old local tip can be
retired without reinstating an obsolete version of that feature.

## Verification

- Ruff and Python compilation pass for every Python file changed since the starting
  primary commit. Mypy passes all 243 source files; harness and docs audits pass.
- Library focused: 386 passed, three Windows symlink-permission skips and 24 passing
  subtests. Client/cache subset: 122 passed and one symlink skip.
- Compiler/publisher suites: 343 passed and 24 passing subtests. Final bundle module:
  81 passed. Independent image-inspection and serialization checks: 40 passed.
- Repository precommit unit run: 3,568 passed, 12 Windows symlink-permission skips,
  24 passing subtests and one failure in 875.89 seconds. This is not an all-green
  precommit result. The existing duplicate-import test hit Windows error 5 at the
  directory-rename commit boundary. Its exact unchanged rerun passed in 0.69 seconds;
  the final complete 81-case bundle-module run had also passed. No retry behavior
  or filesystem fallback was added to production code for this intermittent failure.
- All ten already-deleted remote branch tips were additionally checked as ancestors
  of consolidated master. No feature work was missing from those pruned refs.

## Branch deletion and recovery

Verified code tip `6bbebc01b904b462675f83441a3780efc2e270cc` was pushed before branch
deletion. Remote refs were deleted atomically with exact-tip leases, so a concurrent
change from another PC would stop deletion. Final server and local branch listings
each contain only `master`; tracking refs were pruned. The `v2.5.0` source tag still
resolves to `9341de5cf1ddcadc289ba518a60c53703ce98550`.

Deleted remote branches:

- `codex/experiment-library`
- `codex/library-bundle-validation`

Deleted local branches:

- `codex/backend-reliability-efficiency`
- `codex/condition-review`
- `codex/electrode-exclusion-sharing`
- `codex/experiment-data-sharing`
- `codex/frontend-usability-polish`
- `codex/library-reconnect-2.2.6`
- `codex/library-review-2.3.0`
- `codex/openfpvs-domain-2.2.7`
- `codex/openfpvs-project-reporting`
- `codex/studio-toolbox-integration`
- `codex/upload-download-hardening`

The self-contained backup was cloned into an isolated bare recovery repository;
all 15 original refs were restored and `git fsck --full` passed. Bundle SHA-256:
`eacf7af8cd076c5650739dc13d9bc34cacc3c3197084196cb58cd0f5ac027797`.
The backup, recovery copy, exact ref inventories, equivalent-patch proof, test logs
and deletion report remain under ignored `build/branch-cleanup-2026-10-26/`.
Automatic approval review blocked recursive removal of the temporary recovery-test
repository as a policy-blocked command; that disposable verification copy was
retained alongside the backup. The requested active-repository branch deletions
completed successfully.
