# GUI visual audit

Status: Completed

Date: 2026-10-31

## Brief and boundaries

The researcher needs to author, save and revisit experiments in Studio's sparse
scientific-tool interface. Inspect the real `StudioMainWindow`, using its existing
navigation and shared components as the reference. Home's setup actions, Setup's
Next/Save and Return Home, and dialog Apply/Save actions must remain easy to find.

Use synthetic projects and isolated profiles in the approved visible environment.
Inspect both themes and record surface, size, state and scale with each capture.
Fix only visually confirmed issues; preserve participant-authored content, actionable
warnings, validation, saved settings and existing workflows. Move redundant,
nonactionable explanation into tooltips. Keep runtime, experiment timing and formats
outside this audit.

## Confirmed findings and fixes

- Shared cards, the fixation editor and preview titles retained stale local colors
  across palette changes. Existing palette observation now refreshes those styles;
  pixel regressions reproduced the defects before the fixes and pass afterward.
- Home's four-action row clipped Edit Setup at `760x520`. It now uses a two-by-two
  layout there and one row at `1120x720`. Empty descriptions are hidden, authored
  descriptions are preserved, and ordinary project titles fit.
- Setup could shrink to `960x640`, clipping Timing and Fixation. It now enforces
  the documented `1120x820` minimum/default size.
- Repeated question help moved to tooltips; assignment stays in the parent dialog.
  The response-folder button exposes the full CSV path through its tooltip and
  accessible description. Successful Preview clears stale validation errors.

## Visible evidence and verification

`build/visual-audit-after/` contains 46 final real-window captures in both themes,
including native chrome: Home at `760x520`/`1120x720`, all eight Setup steps at
`1120x820`, condition order at `700x520`/`780x620`, and all four Settings tabs at
`700x720` with AB options. Inspection used a `1920x1080` display at 100%/DPR 1.

`build/visual-audit-questions/` records three ordered questions in each phase at
`1000x680`/`1060x740`, previews at `700x500`/`760x560`, invalid-to-valid Preview,
and basic/expanded modifiers at `1100x720`, in both themes.

Registered visible Qt checks passed **215 distinct tests**: 141 question, 21 modifier,
23 wizard, 16 component and 14 focused Home cases. The final GUI-focused route passed
136 tests plus changed-file Ruff/compilation; log: `build/visual-audit-final-focused.log`.
The docs-focused route passed 10 tests and plan/doc audits. Final changed-file
Ruff/compilation passed, and mypy passed across 261 source files in the clean QA
checkout. `git diff --check` passed.

## Residual verification limits

The full Home module was aborted in a queued-launch test's native event loop. A
read-only review also found an older selected-run-count expectation; it was not changed.
Other display scales and resolutions were not qualified by this audit.

Non-Qt precommit recorded **4,389 passed, 2 failed, 13 Windows symlink-privilege
skips and 24 subtests passed**. The known
`test_1500_acknowledged_sessions_retire_exact_history_and_keep_latest` stress case
was explicitly deselected. The two failures were Windows `WinError 5` during bundle
import staging renames. A serial selection recorded 106 passed, 1 failed and 2 skips:
the bundle case passed, while an origin case still failed in QA. Both origin parameters
passed on clean baseline `e904dac`; relevant bundle/test/conftest hashes were unchanged.
The workspace/path/transient cause remains unproven. Full precommit is not green.
