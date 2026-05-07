# FPVS Toolbox Image Prep Tool

Status: Planned

## Summary

Adapt the imported FPVS Toolbox image resizer files in `src/fpvs_studio/tools/`
into a future Studio-native image preparation tool. The tool should help users
normalize image folders before assigning them to FPVS conditions, especially when
Studio detects mixed image sizes during source inspection.

This plan is a scaffold only. The imported files are reference material and should
not be treated as final production architecture.

## Ground Truth Files

- `src/fpvs_studio/tools/image_resize_core.py` is the behavioral ground truth for
  batch resizing and file-type conversion.
- `src/fpvs_studio/tools/pyside_resizer.py` is a UX reference only. Rebuild the UI
  with `fpvs_studio.gui.components` instead of preserving its current widget layer.
- Keep the current imported files unchanged until this plan moves to active
  implementation.

## Key Changes

- Refactor the resize/conversion behavior into a Studio preprocessing service:
  - use `pathlib.Path` instead of string path assembly
  - return structured results rather than GUI log strings
  - validate missing folders, same input/output folder, invalid dimensions,
    unsupported formats, and write failures explicitly
  - preserve center-crop resize behavior unless the active implementation plan
    chooses a different policy
- Build a Studio-native PySide6 tool surface:
  - use `fpvs_studio.gui.components` for cards, path display, buttons, status
    badges, and styling
  - do not import `Main_App.gui.*`
  - keep routine validation non-blocking where possible
  - run batch work through Qt workers and signals
- Add FPVS-specific output options after the resize/conversion service is stable:
  - normalized original copies
  - grayscale
  - rot180
  - deterministic Fourier phase-scrambled images
  - image inversion only if explicitly scoped in the active implementation pass
- Treat generated folders as ordinary image folders users can select for base or
  oddball condition sources. Do not silently mutate conditions or project schema.

## Setup Wizard Direction

The future Setup Wizard order should put `Stimuli` before `Conditions`:

1. `Project Details`
2. `Stimuli`
3. `Conditions`
4. `Display Settings`
5. `Session Design`
6. `Fixation Cross`
7. `Review`

This order lets users prepare image folders before they are asked to assign those
folders to base and oddball sources in condition setup.

The dedicated tool should also be accessible outside the wizard. Wizard
integration is a convenience path, not a hidden validation fallback.

When source inspection detects mixed image sizes, the wizard may show a clear
action such as `Prepare Images...` that opens the tool with the relevant source
folder prefilled. The wizard should still surface the validation problem directly
and should not silently resize images to make readiness pass.

The `Stimuli` step should become an image preparation workspace rather than only
an assets-readiness snapshot. It can expose:

- input folder and output folder selection
- target size and output format controls
- optional generated variants, such as grayscale, rot180, and phase-scrambled
- a non-blocking validation/readiness summary for supported formats and mixed
  resolutions
- a clear output-folder summary that users can select later in `Conditions`

The `Conditions` step should remain focused on experiment structure:

- condition name
- trigger code
- participant instructions
- base image folder assignment
- oddball image folder assignment
- condition-level readiness

Do not automatically wire generated outputs into conditions unless the active
implementation plan explicitly scopes that behavior. The safer default is for the
Stimuli step to prepare folders and for the Conditions step to let users choose
which prepared folders belong to each condition.

## Boundaries

- No project JSON, compiler, runtime, `RunSpec`, `SessionPlan`, export, or
  PsychoPy engine contract changes in the first implementation pass.
- Preprocessing owns resize, conversion, inspection, derived variants, manifests,
  and deterministic transform metadata.
- GUI owns user intent, progress display, cancellation, and non-blocking status
  only.
- Runtime and engines must never perform image preparation.
- Persisted project-facing paths remain project-relative POSIX strings when users
  later attach prepared folders to conditions.

## Test Plan

- Unit tests for resize, conversion, output naming, overwrite behavior,
  cancellation, invalid dimensions, unsupported formats, missing folders, and
  same-folder rejection.
- Unit tests for grayscale, rot180, and deterministic phase-scrambled outputs
  using `tmp_path`.
- Path tests confirming default project output placement and no hard-coded user
  paths.
- Focused pytest-qt smoke tests for folder selection state, option controls,
  start/cancel state, progress/status updates, and completion summaries.
- Wizard regression tests confirming mixed-resolution detection can point to the
  tool without hiding validation errors.
- Wizard order tests confirming `Stimuli` appears before `Conditions` and that
  Conditions assignment remains explicit after image preparation.

Verification commands:

```powershell
python -m pytest -q tests\unit\test_harness_docs.py
.\scripts\check_preprocessing.ps1
.\scripts\check_gui.ps1
.\scripts\check_quality.ps1
```

For this planned-doc scaffold, only the harness-doc test is required.

## Assumptions

- The imported files under `src/fpvs_studio/tools/` are intentional reference
  material from FPVS Toolbox.
- The final Studio UI should share the same component layer as the rest of the
  application for easier UX updates.
- The first production pass should reuse behavior from the imported files, not
  preserve their module structure or legacy imports.
- The desired future wizard order is `Project Details`, `Stimuli`, `Conditions`,
  `Display Settings`, `Session Design`, `Fixation Cross`, `Review`.
