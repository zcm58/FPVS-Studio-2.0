# Setup Next validation dialog and optional description

Status: Completed

Date: 2026-10-30

## Requested outcome

An experiment author can leave Project's description empty and use **Next** to
continue Setup. When a requirement is missing, clicking Next shows a modal naming
the current blocker and how to resolve it. The existing eight-step frameless wizard
and bottom navigation remain the visual reference. Next remains the primary action.

## Boundaries

- Keep description editable and persisted, including an empty value; project name
  and other existing requirements remain validated. Description refresh must preserve
  pending project-name edits.
- Keep idle Next enabled on incomplete steps. Replace the `To continue` footer and
  `Show field` action with the click-triggered blocker dialog. Opening a page or
  typing must not open a dialog automatically.
- A blocked click stays on the current step and preserves drafts. Retain existing
  validation, atomic edit handling, image readiness and normalization gates.
- Image import, normalization and display verification still disable Next while busy,
  with separate concise status. Keep navigation and worker ownership unchanged.
- Reuse the shared dialog conventions. Preserve `1120x820` no-clipping acceptance
  in both themes, including wrapped Display status inside its bounded card on the
  wider Timing page. No core, runtime or persisted-format change is required.

## Implementation and acceptance

1. Make Project description optional and update Next's idle/busy states and blocker
   presentation in the existing wizard. Verify that valid steps advance normally and
   missing requirements show an actionable modal only after a Next click.
2. Update registered shell/project/Conditions/display coverage. Include blank and
   whitespace-only descriptions, missing project name, missing image and word
   sources, an unverified/busy display, pending project-name edits during description
   refresh, image busy states, normalization and wrapped display status.
   Confirm dismissal preserves the step and values, correction permits advancement,
   and empty/nonempty descriptions survive save/reopen.
3. Run GUI and docs focused verification, then repo precommit. Document the visible
   smoke path: at `1120x820` in both themes, leave description blank, trigger and
   dismiss blockers, correct fields, and exercise import/normalization/display busy states.
   Run Qt only in an approved visible environment under the existing repository rule.

## Evidence

- GUI focused verification: 136 passed. Docs focused verification: 10 passed.
- Registered visible Qt coverage: 167 distinct tests passed across the Project,
  Timing/Display, shell, timing-table, randomization and condition-order modules.
  The final bounded-width and both-theme clipping checks passed again after the
  Display layout refinement. Empty/whitespace descriptions survive save/reopen;
  blocked clicks preserve values, and corrections permit navigation.
- A synthetic project in an isolated profile exercised the actual main window at
  `1120x820`, Windows display scaling 100%, in light and dark themes. Six real modal
  states covered no conditions, a long missing-word-source message and an unverified
  display. The optional description, readable Display width and native title bars
  were visually inspected. No experiment presentation or hardware output ran.
- Changed-file Ruff, compilation and final three-module mypy checks passed.
  The clean QA precommit snapshot also passed the 261-file mypy, GC and docs audits.

## Broad verification limitations

The safe non-Qt precommit suite ran in a separate checkout to preserve existing
user-owned scratch files. It reported 17 failures before the unchanged 1,500-session
retirement test exceeded its 600-second timeout. Worker recovery then stalled; the
task-owned runner was interrupted and did not produce an aggregate summary or
tracebacks. Bounded filesystem probes passed 244 tests, so a path-related cause for
the earlier failures is unconfirmed. The broad suite is not claimed green. Core,
runtime and data-sharing source were unchanged by this work.

Local screenshots, smoke reports and test logs remain under ignored `build/` paths.
