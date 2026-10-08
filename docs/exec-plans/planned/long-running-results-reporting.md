# Long-running results reporting without a lifetime session ceiling

Status: Planned

Date: 2026-10-07

## Purpose and current behavior

The user requested a future execution plan for free, local reporting-history
housekeeping. This plan does not authorize implementation or change the released
512-record limit. Canonical behavior remains in [Data sharing](../../DATA_SHARING.md).

Each local project folder has separate active capture and outbox collections bounded
to 512 records. A session attempt can retain capture evidence even when aborted or
ineligible. Successfully uploaded reports and their finalized captures also remain
active until **Archive uploaded history** moves older acknowledged pairs to the
archive. That action retains the latest report in each project/protocol scope and
preserves local evidence and server totals. It cannot archive ineligible captures.
At capacity, local research collection continues but reporting capture can fail.

## Intended behavior

- Keep active storage bounded without making lifetime session count determine whether
  a project can continue reporting. Use existing project-local storage; no new paid
  service, server migration, participant numbering or Toolbox reporting is required.
- Automatically archive older, successfully acknowledged reports and matching
  finalized capture evidence through the existing archive owner. Retain the latest
  eligible local report per OpenFPVS project/experiment/version/protocol for comparison.
- Provide explicit review and evidence-preserving archiving for terminal aborted or
  otherwise ineligible captures. Show the reason and selected record count before
  moving them. They must never be retrospectively uploaded or relabeled.
- Protect pending/held/failed reports, running captures and eligible captures awaiting
  proof or queueing. Ambiguous crash states and malformed/conflicting evidence require
  review; automatic housekeeping must not guess that these are disposable.
- Explain active capacity and blocked housekeeping in the existing sharing dialog.
  Manual archive remains available. Sharing stays default-off and archive work never
  opts in, sends a report, resets server totals or modifies research exports.

## Ownership and implementation sequence

1. Reproduce capacity exhaustion using synthetic projects with uploaded, aborted,
   ineligible, unfinished and pending records. Define which terminal states can be
   safely archived and how an interrupted move resumes.
2. Extend `data_sharing/storage.py`'s existing guarded archive operations. Preserve
   exact UUIDs, payload bytes, receipts, scope metadata and private mappings. Validate
   every source/destination under the active project root before moving; reject links,
   reparse points, conflicting destinations and unsafe paths.
3. Run acknowledged-history maintenance under the existing reporting lock and worker
   ownership before active capacity becomes full. Keep hashing/file work off the GUI
   thread and outside experiment presentation. Preserve cancellation and retry behavior.
4. Add explicit terminal-capture review/archive controls through the existing sharing
   dialog/controller. Archive only states established as safe in step 1; preserve
   incomplete evidence for a separate recovery decision.
5. Update the canonical sharing contract and active reporting plan after acceptance.
   Move this plan to `active/` when implementation starts, then `completed/` only after
   implementation and the required checks finish.

## Acceptance checks

- At least 1,500 synthetic completed sessions in one project continue reporting with
  a bounded active collection, exact retained evidence and correct server totals.
- Repeated participant visits consume session records independently of participant
  identity; distinct PC/project folders remain independent local collections.
- More than 512 terminal ineligible/aborted attempts can be reviewed and archived
  without losing evidence, affecting local research files or changing website totals.
- Pending, failed, held, running and uncommitted records survive housekeeping; offline
  backlog capacity remains explicit and never causes silent dropping of reports.
- Failure injection covers each archive move, cancellation, restart, conflicting
  destinations, revoked/reconnected scopes and changed protocol/version. Retries
  resume safely and cannot re-upload archived acknowledged reports.
- Path/link/permissions regressions use temporary synthetic roots; preserve existing
  archive formats and all participant/session research exports.
- Run `data-sharing`, `runtime`, `project-io` and safe `gui` focused scopes, then repo
  precommit. Registered Qt checks require explicit approval for the new visible scope;
  verify longest-content layouts at the documented minimum/default sizes.
- Conduct an explicitly approved two-PC synthetic service check for long collection,
  interruption/retry, opt-out, project switching and shutdown before broad lab rollout.

## Exclusions

This is a local retention/recovery change, not a higher arbitrary cap, automatic
deletion policy, historical-results backfill, public dataset publication or change
to participant identity, timing, scoring, triggers or the Results wire envelope.
