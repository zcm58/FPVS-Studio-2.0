# Image Equalizer In-Place Rounding

Status: Completed

Baseline reviewed against Studio 3.1.4 on 2026-11-22.

## Baseline workflow and evidence

**Tools > Image Equalizer** matches grayscale mean and RMS contrast across the
chosen folders. The [equalizer](../../../src/fpvs_studio/preprocessing/equalization.py)
used a float32 array to decode each image and compute its adjusted intensities.
It then allocated a second float32 array for the rounded values used by the
rest of the transform.

An isolated 4096 × 4096 probe measured 67,109,392 bytes of peak traced allocation
for the rounding step before the change and 408 bytes with in-place rounding.
All 16,777,216 float32 values matched bit for bit. A two-image run through
`equalize_image_folders` matched PNG bytes, report bytes, return values, progress
messages and source files. That probe measured the rounding allocation only.

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

## Implementation

Each transform owns the writable float32 array returned by its grayscale decode.
The affine transform already writes into this array. Rounding now uses the same
array as its NumPy destination, then checks the rounded minimum and maximum
before encoding the uint8 PNG. The private array is never shared between workers.

An independent ownership and rounding check covered the six admitted Pillow
modes and their applicable PNG, TIFF, BMP and JPEG inputs. It confirmed that two
decodes never share their float32 storage. The results matched bit for bit at
half ties, signed zero, neighboring floats and the 0 and 255 boundaries.

Twenty comparisons through `equalize_image_folders` used the same fixture paths
and one or two workers. The successful cases matched all ten PNGs and eight
JSON reports byte for byte, along with return values, progress and source bytes.
They covered grayscale and RGB decoding, output at 255 and reduction of the
contrast target. Rejected images, cancellation, write conflicts and an injected
out-of-range result produced equivalent errors and preserved the expected files.
The only variable diagnostic component was a process-local Pillow address
included in the corrupt-image error.

## Memory and timing

The 4096 × 4096 rounding result matched all 16,777,216 float32 values bit for
bit. The isolated rounding step allocated 64 MiB with the original operation
and zero traced bytes after the input array had been allocated with in-place
rounding.

Fresh Windows process pairs ran the same four 4096 × 4096 grayscale and RGB PNGs
at the same paths. Table values are medians from four measured pairs per worker
count. PNGs, reports, return values, progress and input bytes matched.

| Workers | Peak working set before | Peak working set after | Batch time before | Batch time after |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 397.3 MiB | 333.4 MiB | 1.735 s | 1.696 s |
| 4 | 1,288.7 MiB | 1,055.9 MiB | 686.5 ms | 672.7 ms |

Small-batch wall-time differences were inconclusive in fresh and warmed paired
runs. Warmed paired medians were 5.36 ms longer with one worker and 1.58 ms
longer with multiple workers, with variable results by order. In a separate
192 × 256 array comparison without disk I/O, the shared input-copy,
round, range-check and cast steps went from 27.10 to 26.42 microseconds per
iteration and were faster in 21 of 24 pairs.

## Verification

Preprocessing focused passed 112 tests. The safe GUI route passed 184. Docs
focused passed 13. These checks ran without opening Qt.
Safe repo precommit passed Windows and Darwin type checks, repository audits,
and 6,612 tests with 41 platform or permission skips.
