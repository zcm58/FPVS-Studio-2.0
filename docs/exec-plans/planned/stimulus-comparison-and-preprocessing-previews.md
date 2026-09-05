# Stimulus Comparison And Preprocessing Previews

Status: Planned

## Endorsement And Scope

The user endorsed this direction on 2026-09-05 and requested a future execution plan.
This records future work; it does not authorize starting implementation in this task.
Move this plan to `active/` when implementation is scheduled and its decisions are resolved.

## Problem And Evidence

Studio already inspects source files, checks uniform dimensions, normalizes inconsistent
sets, and records source/derivative provenance. The gap is helping researchers review
the content consequences and between-set differences before changing their stimuli.

- [Inspection](../../../src/fpvs_studio/preprocessing/inspection.py), lines 33-91,
  records hashes, format, dimensions, and set consistency.
  [Inspection models](../../../src/fpvs_studio/preprocessing/models.py), lines 24-46,
  do not currently carry pixel brightness or RMS contrast statistics.
- [Normalization](../../../src/fpvs_studio/preprocessing/normalization.py), lines
  389-405, scales to fill and center-crops the resulting square PNG.
  [Its confirmation](../../../src/fpvs_studio/gui/image_normalization_dialog.py),
  lines 39-50 and 90-104, provides explanatory text and output size, without a crop preview.
- [Manifest records](../../../src/fpvs_studio/preprocessing/models.py), lines 54-115,
  already provide source hashes, derivative parameters, seeds, timestamps, and a
  preprocessing version. Extend these owners where necessary.

These are source observations, not measured researcher error rates or visual acceptance.

## Proposed Alternative And Benefit

Provide an explicit `Compare stimuli` action within Conditions that opens a read-only
Base/Oddball report: dimensions, exact file duplicates, and representative previews.
Before the existing normalization confirmation, show original and proposed output
side by side with the actual crop extent and output dimensions.

Add pixel brightness and RMS contrast distributions only after the measurement method
is defined and validated. Present differences and outliers for review; do not label
sets scientifically equivalent or require all conditions to match.

This would make unintended stimulus overlap, edge-content loss, and image differences
easier to inspect before collection. It would also make preparation decisions easier
to document and repeat across FPVS projects. The expected UX benefit is fewer hidden
consequences when importing or normalizing stimuli; validate this with task walkthroughs.

The methodological motivation is consistent with
[Willenbockel et al. (2010), the SHINE toolbox](https://doi.org/10.3758/BRM.42.3.671),
which describes controlling low-level image properties. That paper motivates careful
measurement; it does not select an algorithm or establish FPVS Studio equivalence to SHINE.

## Scientific Boundaries And Dependencies

- Pixel statistics are not physical display luminance. Do not report calibrated units
  or infer monitor output without a separate measured calibration workflow.
- Between-set brightness, contrast, or duplicate stimuli may be intentional. Report
  observations with their scope; do not automatically reject, delete, or equalize assets.
- Exact duplicate means matching source-file bytes by SHA-256. Different encodings of
  the same image are not covered; perceptual duplicate detection is outside this slice.
- Keep static-image contrast statistics distinct from sinusoidal presentation modulation.
- The existing [luminance/RMS investigation](luminance-rms-equalization-investigation.md)
  owns equalization algorithm selection, output policy, dependencies, and verification.
  Resolve the measurement-method decisions there before adding brightness/RMS statistics
  here; link its adopted method rather than writing a competing algorithm specification.
- Optional equalization controls depend on that investigation's completed decisions.
  They must create explicit project-local derivatives, preserve originals, and record
  sufficient parameters and hashes to reproduce the chosen output. No automatic equalization.

## Decisions Before Implementation

1. Define comparison scope: selected condition Base/Oddball by default, with an explicit
   way to compare additional sets and distinguish source from active derived assets.
2. Agree which file identities and transform settings identify a report revision.
   Define how stale reports are invalidated after imports, replacements, or normalization.
3. Through the existing investigation, define RGB/grayscale interpretation, transfer
   function, alpha/background handling, region of interest, statistic units, and versioning.
4. Specify the preview sampling rule and full-file inspection path. Mark samples as
   samples; surface all cropped files in the report even when thumbnails are bounded.
5. Decide report persistence/export separately from disposable preview caches. Document
   any new additive manifest fields and preserve existing project/export compatibility.
6. Establish dataset-size and memory budgets using representative lab stimulus folders;
   measure cancellation latency, peak memory, and initial report responsiveness.

## Ownership And Performance

Preprocessing owns image decoding, measurements, crop geometry, and derivative production.
Core/document services own project changes and manifest coordination. GUI components own
presentation and user intent; runtime and engines consume existing compiled contracts.

Reuse the normalization calculation for previews so the shown crop agrees with output.
Do not add a second resize implementation in a widget. Run hashing, decoding, and report
generation in workers; workers emit data/progress and never access widgets. Decode in
bounded batches, cap thumbnail memory, and support cancel/retry without partial project edits.

Use the active project root and project-relative asset paths. Inspect external intake
sources read-only. Keep caches within an identified project-owned cache location, and
write reports only through an explicit export destination or documented project artifact.
Do not include machine-local source paths in portable manifests or overwrite original files.

## Implementation Phases

1. **Read-only comparison:** dimensions, set counts, exact duplicates, source/active scope,
   deterministic sampling, report identity, worker progress/cancellation, and source links.
2. **Normalization preview:** connect the existing normalization choice to side-by-side
   output/crop previews; keep application explicit and preserve cancellation semantics.
3. **Validated pixel statistics:** after investigation decisions, add distributions,
   per-image values, and selectable outlier details with method/version information.
4. **Optional derived equalization:** only after the dependency plan resolves its full
   algorithm/output/provenance/test decisions; preview changes and require explicit Apply.
5. **Handoff:** document report interpretation, limitations, supported workflows, and
   the visible acceptance results; archive this plan only when its accepted scope is complete.

Each phase should be reviewable independently. Phases 1-2 may proceed without inventing
an equalization algorithm; phases 3-4 remain dependent on the investigation outcomes.

## Verification And Acceptance

- Use synthetic square/rectangular images to verify dimensions, crop coordinates, source
  preservation, and preview/output agreement, including EXIF orientation and transparency.
- Test byte-identical duplicates within/across roles, distinct files with identical names,
  report invalidation, deterministic ordering, decode failures, cancel/retry, and bounded work.
- After method selection, test known grayscale/RGB fixtures, numeric tolerances, clipping,
  zero-variance images, alpha handling, and statistics before/after derived transforms.
- Test project-root containment, long Windows/Unicode paths, relative manifest records,
  explicit report destinations, and unchanged files/manifests when users cancel.
- Use existing shared GUI components. Budget the embedded Conditions step at `1120x720`
  without required scrolling; design the separate report at a documented `1000x680`
  minimum/default before implementation. Data tables may scroll; required actions and
  explanations must remain visible, with complete values available for intentional elision.
- Add registered pytest-qt coverage for empty/loading/canceled/error/populated/stale states,
  image/word applicability, long names/paths, light/dark themes, previews, and action wiring.
- Run relevant `preprocessing`, `project-io`, and `gui` focused verification; use repo
  precommit when shared contracts change. Qt tests require an approved safe visible
  environment and must not run offscreen locally.
- Manual acceptance: compare two representative sets, inspect a crop that removes edge
  content, cancel safely, apply to separate derived assets, reopen, and verify provenance.
  Inspect at documented sizes and Windows scaling settings; do not claim scientific
  matching or no-clipping acceptance from source checks alone.
