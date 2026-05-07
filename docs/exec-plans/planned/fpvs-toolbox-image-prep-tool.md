# FPVS Toolbox Image Prep Tool

Status: Planned

## Summary

Adapt the imported FPVS Toolbox image resizer logic in `src/fpvs_studio/tools/`
into a Studio-native Conditions-step normalization gate. Users should assign
condition image folders normally. Studio should only prompt for resizing and
file-type conversion when the selected condition images are inconsistent.

This plan is a scaffold only. The imported files are reference material and should
not be treated as final production architecture.

## Ground Truth Files

- `src/fpvs_studio/tools/image_resize_core.py` is the behavioral ground truth for
  center-crop batch resizing and file-type conversion.
- `src/fpvs_studio/tools/pyside_resizer.py` is a UX reference only. Rebuild the UI
  with `fpvs_studio.gui.components` instead of preserving its current widget layer.
- Do not import or preserve legacy `Main_App.gui.*` dependencies.

## Key Changes

- Refactor resize/conversion behavior into a Studio preprocessing service:
  - use `pathlib.Path` instead of string path assembly
  - return structured results rather than GUI log strings
  - validate missing folders, invalid dimensions, unsupported formats, and write
    failures explicitly
  - preserve center-crop resize behavior unless the active implementation plan
    chooses a different policy
- Add a Conditions-step readiness gate:
  - scan all distinct base/oddball stimulus sets referenced by conditions when the
    user clicks `Next`
  - silently advance when selected images already share one resolution and one
    compiler-ready file type
  - prompt only when selected condition images have mixed sizes, mixed file types,
    or source formats that need conversion
  - offer only `512x512` and `256x256`, defaulting to `512x512`
  - output PNG files only
  - run batch work through Qt workers and signals
- After successful normalization, update affected `StimulusSet.source_dir` values
  to project-relative folders under `stimuli/normalized-images/<set-id>/`.

## Setup Wizard Direction

The Setup Wizard should remain Conditions-first:

- condition name
- trigger code
- participant instructions
- base image folder assignment
- oddball image folder assignment
- condition-level readiness

When the user clicks `Next` from Conditions, Studio should scan selected image
sets. If the images are inconsistent, show a small component-layer dialog that
summarizes the problem and offers `Normalize Images`. On success, Studio should
automatically repoint affected condition image sets to the normalized PNG folders
and continue to the next setup step.

This feature must not include grayscale, 180 degree rotated, phase-scrambled, or
control-condition creation. Those workflows remain separate.

## Boundaries

- No compiler, runtime, `RunSpec`, `SessionPlan`, export, or PsychoPy engine
  contract changes.
- Preprocessing owns resize, conversion, inspection, derived variants, manifests,
  and deterministic transform metadata.
- GUI owns user intent, progress display, cancellation, and non-blocking status
  only.
- Runtime and engines must never perform image preparation.
- Persisted project-facing paths remain project-relative POSIX strings.

## Test Plan

- Unit tests for scan results, resize/PNG conversion, target-size validation,
  unsupported formats, missing folders, and project-relative output placement.
- Focused pytest-qt smoke tests for the Conditions `Next` gate:
  - uniform images advance silently
  - mixed images prompt for normalization
  - accepted normalization updates stimulus-set paths and advances
  - cancellation keeps the wizard on Conditions without mutating paths

Verification commands:

```powershell
python -m pytest -q tests\unit\test_preprocessing_assets.py tests\unit\test_preprocessing_inspection.py
python -m pytest -q tests\unit\test_preprocessing_normalization.py
python -m pytest -q tests\gui\test_layout_dashboard.py
python -m pytest -q tests\unit\test_harness_docs.py
```

## Assumptions

- The imported files under `src/fpvs_studio/tools/` are intentional reference
  material from FPVS Toolbox.
- The Studio UI should share the same component layer as the rest of the
  application.
- Production code should reuse behavior from the imported files, not their module
  structure or legacy imports.
- Conditions remains the image-assignment step.
- Normalization is opt-in after a prompt and outputs PNG only.
