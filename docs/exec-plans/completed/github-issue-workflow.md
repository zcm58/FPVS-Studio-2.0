# Serial GitHub Issue Workflow

Status: completed

## Scope

Standardize Studio issue diagnosis, reproduction, focused repair, verification
and plain-language reporting. Configure a desktop watcher for newly created
issues in Studio and its private Feedback repository. Dispatch GPT-6.1 Sol one
issue at a time. Preserve existing open reports and private diagnostics.

## Implementation and Verification

- Add a thin repo-local skill and one canonical workflow; link agent entry points.
- Add a transactional queue outside tracked files; test concurrent claims,
  duplicates, restart and ambiguous dispatch without live writes.
- Run docs/repo focused checks, harness configuration validation and applicable
  precommit checks. Independently exercise the written procedure with synthetic
  scenarios.
- Dry-run discovery, initialize the activation boundary and configure the desktop
  heartbeat. Verify the saved schedule/model dispatch instructions and empty queue.
- Record actual desktop/first-live-run limitations. Do not claim a real issue was
  fixed by the synthetic acceptance tests.

## Decisions

- Use the existing desktop scheduler and GitHub connector; no separate webhook
  service, API key, new cloud deployment or background Windows service.
- SQLite in the Git common directory holds one durable active slot across
  worktrees. Ambiguous launches hold the slot until reconciled.
- Default delivery is a tested PR. Direct default-branch pushes, releases and
  external reporter messages require standing authorization.
- This desktop exposes a scheduled coordinator chat, not a separate Dot assignment.

## Evidence

- Added the canonical workflow, thin skill, agent routing and transactional queue.
- Skill validation, harness configuration and docs focused checks passed. Repo
  focused checks passed (118 passed, one platform skip at the first checkpoint);
  the final queue suite passed all 45 tests, including coordinated retry.
- Independent procedure and code reviews passed after correcting claim ordering,
  control-checkout anchoring, partial-fix outcomes and stopped-worker evidence.
- Repository precommit ran in an isolated checkout to preserve unrelated local
  untracked files. Ruff, Windows/Darwin mypy and harness/docs audits passed.
  The non-Qt suite reported 5,916 passed, 33 skipped and 24 subtests passed, with
  one failure in the unchanged serialization retry-count test. The file saved
  correctly but required four replacement attempts rather than the asserted
  three. A module rerun reproduced that assertion on a different Windows-error
  parameter (nine passed, one failed). No application or unrelated test was
  changed to hide this separate verification limitation.
- Initialized the private queue with discovery boundary
  `2026-11-10T05:57:31.267217Z`; live GitHub discovery found no new issues and the
  queue was empty. Older open reports remain outside the automatic backlog.
- Activated and read back desktop heartbeat `studio-github-issue-watcher` on
  2026-11-10 UTC: five-minute checks in the coordinator chat, exact worker model
  `gpt-6.1-sol`, serial dispatch and tested-PR delivery. Existing paused
  automations were preserved.
- Actual dispatch/fix/PR delivery for the first new report remains operational
  acceptance. Synthetic tests did not create a live issue or worker. This local
  watcher requires the desktop app/computer and GitHub connection to remain
  available; no separate personal Dot assignment or cloud webhook was configured.
