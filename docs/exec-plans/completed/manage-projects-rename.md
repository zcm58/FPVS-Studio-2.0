# Rename Projects in Manage Projects

Status: Completed (2026-09-09)

Add Rename to the existing Manage Projects dialog, including the open project.
The display name changes; folder, project ID, source paths and historical runs do
not move. Persist only name/update-time metadata, preserving legacy schema and
unrelated unsaved edits. Cancel, invalid names and write failures leave disk intact.

1. Add atomic metadata-only rename in the existing project service; verify unchanged
   identity/assets/legacy fields and write-failure rollback with temporary projects.
2. Wire the dialog/controller/live document; verify selection, filtering, invalid
   states, cancellation and open-project title/dirty-state synchronization.
3. Run focused routes and approved visible checks at 860x520 in both themes, then
   update workflow documentation. Existing user approval for visible Qt checks persists.

Implemented the metadata-only service, Rename action, controller prompt and live
document synchronization. No real user projects were test inputs.

Verification:
- Project-I/O focused route: 85 passed with a short temporary test path. The default
  deeply nested harness path hit existing Windows path-length failures in bundle tests.
- Visible rename GUI coverage: 9 passed, including open/closed projects, cancellation,
  invalid names, failed writes, selection and minimum-size checks in both themes.
- Light/dark screenshots inspected at 860x520: `build/rename-light.png` and
  `build/rename-dark.png`.
- Full safe unit suite: 1198 passed, 5 skipped because Windows symlinks are unavailable.
- Ruff, compilation, documentation checks and harness garbage-collection checks passed.
- Precommit remains blocked by the existing unrelated controller.py:373 mypy error
  (object returned where str is declared); remaining safe checks passed separately.
