# Image Equalizer In-Place Rounding

Status: Planned

Baseline reviewed against Studio 3.1.4 on 2026-11-22.

## Current workflow and evidence

**Tools > Image Equalizer** matches grayscale mean and RMS contrast across the
chosen folders. The [equalizer](../../../src/fpvs_studio/preprocessing/equalization.py)
decodes a float32 array for each transform, computes adjusted intensities in that
array, then allocates a second float32 array to round the result. The worker
only uses the rounded values from that point onward.

An isolated 4096 × 4096 probe measured 67,109,392 bytes of peak traced allocation
for the rounding step before the change and 408 bytes with in-place rounding.
All 16,777,216 float32 values matched bit for bit. A two-image run through
`equalize_image_folders` matched PNG bytes, report bytes, return values, progress
messages and source files. Whole-process peak memory remains unmeasured.

## Implementation and acceptance

- Round into the existing per-image float32 array after confirming it is writable
  and owned by the transform. Keep the same NumPy operation, out-of-range checks,
  8-bit conversion, PNG encoding and reinspection. Retain the worker cap, batch
  target, report fields, cancellation and no-overwrite behavior in the
  [Image Equalizer specification](../../product-specs/image-equalizer.md).
- Repeat the public-entry-point comparison at identical paths and dependency
  versions with one and multiple workers. Include grayscale and RGB inputs,
  near-boundary intensities, a reduced contrast target and rejected input. Check
  deterministic PNG and report bytes, output hashes, progress, errors and cleanup.
- Measure rounding allocation and process peak memory for representative large
  images with the same worker settings. Compare elapsed time for large and small
  batches. Run the `preprocessing` focused route and the existing equalization suite.
