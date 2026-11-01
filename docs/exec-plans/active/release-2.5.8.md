# Studio 2.5.8 Release

Status: Active

## Problem and scope

Birth Control's four conditions share normal condition instructions, with no task
modules or authored instruction geometry. The saved project compiles to eight
runs. Runtime adds the block/item label to its authored instruction body.
Installed Arial metrics estimate nine wrapped lines at the old 1200 px width;
the body overlaps the heading by about 35 px even at 1920x1080. This is a shared
Studio text-screen layout defect, not a project-specific modifier or setup error.

Replace fixed text centers with measured heading/body/footer flow inside the
actual viewport. Use explicit pixel units and top anchors, remeasure after font
or wrapping updates, and reflow only for viewport/countdown changes. Preserve
one-time stimulus construction, all cleanup paths, wording, keys and countdowns.
Fit exceptional overflow only to a readable minimum, then report an actionable
error. Do not silently clip, delete text or introduce instruction pagination.

Leave local study JSON, stimuli, timing, triggers and participant data unchanged.
The renderer fix applies to all experiments using ordinary instruction, transition,
break, feedback and completion screens. No project bundle update is required.

## Verification and release

Add non-Qt rendered-bounds regressions using the Birth Control text, several window
sizes, long headings, resizing, countdown changes, fitting and explicit overflow.
Preserve resource reuse and error/abort cleanup coverage. Run engine focused,
repository precommit and packaging focused checks.

Ship as the next patch in the ongoing authorized Studio release workflow. Change
only canonical package version to 2.5.8, refresh editable metadata without changing
dependencies, and build with the canonical release script under an isolated label
and constrained native PATH. Compare warnings/native paths/hashes with 2.5.7.
Audit frozen source and the complete inventory, verify all four draft assets,
publish immutable/latest and check independent public downloads, attestations and
the production updater. Retain evidence in `build/release-2.5.8-evidence/`.

No Qt/PsychoPy windows or installers are run on the working installation. Visible
presentation, clean-PC installation, update lifecycle and physical timing checks
remain separate from non-Qt/static evidence. No claim of native screenshot
verification is made from font-metric estimates or fake rendered bounds.

## Progress

- Pulled master; clean and current at `0251743` before the repair.
- Engine focused baseline: 547 passed.
- Shared renderer now measures and separates instruction blocks. Twelve new
  regressions include the exact Birth Control text; all four viewport cases fail
  against the old renderer. Engine focused passes 559 tests, and participant input
  passes 41 tests after updating older fake stimuli to expose measurement APIs.
- All eight actual compiled study screens pass 32 simulated viewport/layout cases;
  project JSON remains byte-identical. Independent dependency/API review found no
  Windows blocker. No native window was launched.
- Packaging focused passes 183 tests; config checks pass all 14 scopes. Only
  editable application metadata changed among 145 distributions, and `pip check`
  passes. The final repository gate, build and publication remain in progress.
