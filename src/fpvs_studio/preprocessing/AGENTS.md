# AGENTS.md

## Scope of this directory

`src/fpvs_studio/preprocessing/` owns source-image intake, inspection, manifest generation, and derived-asset creation.

For the current phase, the priority is **deterministic derived-asset materialization plus manifest-backed provenance**, not a feature-complete preprocessing UI.

## Hard requirements

- Supported source formats are:
  - `.jpg`
  - `.jpeg`
  - `.png`
- Extension matching should be case-insensitive.
- All images in a stimulus set must have identical resolution.
- Base and oddball stimulus sets used together in one condition must match in resolution.
- Do not silently resize images.
- Generated derivatives should be written as PNG in the project folder.
- Persist enough metadata to make preprocessing reproducible.

## v1 derivative semantics

- `original` = imported source image copied into the project
- `grayscale` = grayscale PNG derivative
- `rot180` = 180-degree rotation, not color inversion
- `phase_scrambled` = deterministic Fourier phase scrambling

## Determinism

Phase scrambling and any future randomized preprocessing must record the seed in manifest metadata. The same source image + same transform parameters + same seed should reproduce the same file.

## Recommended responsibilities for this phase

- list and validate supported source files
- inspect image dimensions with Pillow
- build stimulus-set summaries
- create manifest models/utilities
- define transform metadata records
- materialize deterministic `grayscale`, `rot180`, and `phase_scrambled` assets
- keep the compiler/runtime consuming manifest-backed paths without moving image work into core/runtime

## Manifest expectations

The manifest should be able to record:

- source relative path
- source hash
- width and height
- source format
- available variants
- transform chain / parameters
- scramble seed where applicable
- preprocessing version
- timestamps

## Restrictions

- No PsychoPy imports here.
- No GUI code here.
- No runtime presentation concerns here.
- Do not make preprocessing aware of `RunSpec` or engine-specific execution details.
- The compiler may consume the serialized manifest, but preprocessing owns generating and updating it.
