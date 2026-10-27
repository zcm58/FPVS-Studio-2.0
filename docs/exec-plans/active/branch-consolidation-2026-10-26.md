# Consolidate features and retire obsolete branches

Status: Active

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
