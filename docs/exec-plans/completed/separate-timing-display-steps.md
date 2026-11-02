# Separate Timing and Display setup steps

Status: Completed

## Workflow and acceptance

Researchers edit Timing in step 3 and Display in step 4. Session becomes step 5;
Image/Character Size, Fixation, Response and Review follow as steps 6–9. Keep the
quiet Setup hierarchy and all nine complete step labels at the 1120x820 default/minimum.
Timing retains the existing 1040 px FPVS / 880 px native AB workspace; Display uses a
760 px form. Frequency, duration, counts and oddball cadence belong to Timing;
monitor refresh, optional Check refresh rate and background belong to Display.

Keep document bindings, pending timing edits and compiled frame schedules intact.
The optional display check must stay optional. Preserve experiment/timing
entry points for Timing; display/runtime entry points open Display. Review summaries
and edit links must distinguish both surfaces. Active check workers prevent navigation
until completion. No new project schema or runtime policy is needed.

The user's follow-up requires all image frequencies in a mixed-rate project to fit
the same selected display frame grid. Core validates whole-frame compatibility for
every image condition, including inherited rates. Setup, atomic timing proposals,
project readiness and compilation share this rule. Uniform-rate approximation behavior
and word-only timing retain their existing contracts; no requested rate is rounded to
repair an incompatible image-rate mix.

## Implementation and verification

- Split the wizard surfaces and extract existing cadence controls as a reusable view
  of the same document bindings; standalone display-summary usage stays compatible.
- Update aliases, step counts, Next/Back/progress, blocking focus, Review links and
  references elsewhere in the GUI.
- Update registered Qt coverage for all nine steps, all categories, both themes,
  long labels, optional-check idle/busy/failed/successful states and draft preservation.
- Add safe non-Qt navigation regressions. Run GUI focused and repository precommit;
  run docs focused after completing the plan. Do not run Qt without approval for a
  safe visible environment.

## Progress

- Baseline GUI focused: 143 tests passed.
- Implemented nine-step navigation, split surfaces, cadence extraction, native AB
  timing summary, deferred timing drafts, Review links and updated help text.
- Added core mixed-image-rate compatibility checks to proposals, readiness and compilation.
- GUI focused: 152 passed; compiler focused: 794 passed; docs focused: 13 passed.
- Targeted navigation/rate checks: 86 passed. Precommit Ruff, compilation, mypy and
  repository audits passed. Its non-Qt suite had 4623 passed, 13 Windows symlink skips
  and one unrelated Windows file-lock retry assertion (four attempts instead of three).
  The unchanged serialization test group passed all 10 tests on isolated rerun.
- Registered Qt coverage is updated at 1120x820 in both themes, using existing fake
  controllers/dialogs, progress tasks and engines. Visible Qt execution is unperformed.

## Visible manual smoke path (not performed)

At 1120x820 in both themes, walk Project through Review, use Back and progress links,
and check complete labels and controls without required scrolling. Edit Timing, move
to Display, change refresh/background, return and confirm drafts/settings are preserved.
Continue without checking refresh, then exercise a stubbed/approved optional check and
confirm busy navigation and failure recovery. Review's Timing and Display edit links
must open their matching pages. Repeat with native AB Character Size and masking.
