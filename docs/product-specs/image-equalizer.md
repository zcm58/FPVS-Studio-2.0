# Image Equalizer

## Workflow

Open **Tools > Image Equalizer** in an open project. Add one or more
input folders. Each row suggests a sibling `<input-folder>-equalized` destination;
**Change Output** selects a different empty folder. Select a row to change its output
or remove the pair. Full paths remain available in tooltips and accessible text.
**Equalize Images** processes all rows together with automatic settings.

The tool converts color images to grayscale and matches every image to the same mean
intensity and RMS contrast target across every selected folder. Include all relevant
conditions in the same batch to avoid introducing separate condition targets. It saves
8-bit grayscale PNG copies using the source stem and an `image-equalizer-report.json`
in every output folder. **Open Output** opens the selected successful destination.
The report describes the entire batch, including any non-image files/subfolders skipped.

Use Image Resizer or external cropping/resizing first. Import the resulting images
through Conditions when ready. The tool operates on the selected folders independently
of the open project's stimulus sets, manifests, RunSpec and SessionPlan.
Native word paradigms continue to use word lists;
rendered word images can use this tool like other images.

## Matching contract

- Apply EXIF orientation, decode the stored values and convert to Pillow `L` grayscale.
  RGB conversion uses approximately `0.299 R + 0.587 G + 0.114 B`, rounded to 8-bit,
  as documented by [Pillow](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.convert).
  Existing grayscale values are retained for analysis.
- Analyze the whole image canvas, including its background. There is no segmentation,
  background estimation, ICC profile transform or gamma correction. Units are digital
  code values from 0 to 255. This is not measured physical luminance equalization.
- For each image calculate population mean `mu`, population standard deviation `sd`,
  minimum and maximum. Define normalized RMS contrast as `sd / mu`; record both
  standard deviation and normalized RMS explicitly.
- Use common target mean `M = 128`. The requested target standard deviation is the
  median of the individual image standard deviations (each image has equal weight).
  For each non-flat image, its no-clipping bound is
  `min(M * sd / (mu - min), (255 - M) * sd / (max - mu))`.
  The actual target `S` is the smaller of the requested target and all image bounds.
- Transform each pixel using `M + (pixel - mu) * S / sd` and round to the nearest
  8-bit code value. Do not clip out-of-range pixels. Reducing a common target protects
  the affine transformation rather than saturating highlights/shadows independently.
- Decode each saved PNG again. Its mean and standard deviation must each be within
  **0.501 code levels** of the targets and its contrast must remain nonzero. Thus
  outputs match within quantization tolerance rather than exactly. The report records
  achieved means, standard deviations, ranges and normalized RMS contrast.

An extreme image can lower the batch target substantially. Completion explicitly notes
any reduction; the report identifies limiting images and requested/actual targets.
Researchers can inspect those inputs and prepare a different batch. A flat image has
no contrast to rescale and is rejected, rather than forcing the entire batch flat.

Using the same monitor does not make code values proportional to physical luminance.
Researchers handle display calibration and verification externally. Matching image
statistics also does not match spatial-frequency content, histograms or local contrast.

## Input and preservation contract

- Read immediate JPG/JPEG, PNG, BMP and TIF/TIFF files, in deterministic filename order.
  Subfolders are not traversed. Files with supported extensions that cannot be decoded
  are errors, not silently skipped. Every selected folder must contain images.
- Accept single-frame 8-bit RGB/grayscale and palette/binary images. Alpha must be fully
  opaque; flatten transparent inputs onto the intended experiment background first.
  Reject CMYK, higher-depth and floating-point inputs with conversion guidance.
- Reuse image-intake limits: 64 MiB encoded, 8192 pixels per axis and 16,777,216 pixels.
- Resolve paths before checking them. Inputs may appear only once. Output folders must
  be new or empty, separate from every input (including ancestor/descendant aliases),
  and separate from one another. Duplicate PNG output stems are rejected, including
  case-only collisions. Existing destination content is never overwritten.
- Analyze the complete batch before writing. Hash each source again during conversion
  and reject mid-batch changes. Use exclusive creation for output files. On failure or
  cancellation, wait for workers and remove only files created by this batch. Empty
  directories can remain. Cleanup failures identify incomplete files explicitly.
- A successful report records algorithm/version metadata, source/output hashes, folder
  mappings, target selection, achieved statistics and skipped entries. Reports are
  written after every output passes verification. No source files are modified.

## Execution and acceptance

`preprocessing/equalization.py` owns the pure service. It uses up to four threads,
bounded by available CPUs and image count, for both analysis and conversion. Analysis
retains scalar measurements rather than all decoded images. `gui/image_equalizer_dialog.py`
uses the app-owned ProgressTask lifecycle, cancellation signals and a window-modal
dialog. File enumeration, reads, transforms and writes stay off the GUI thread.

The dialog is 960x640 minimum and 1120x720 by default. A plain shared dialog header,
folder-action toolbar and full-width table share one set of margins, without nested
page cards. Status sits directly below the table; Close and Equalize Images remain
in the footer. Only the table scrolls for large batches. Folder paths deliberately
elide with full tooltips/accessibility values. Add,
change, remove and close are disabled during a batch. Cancellation is available in
the progress dialog. Closing cannot abandon an active worker; error/cancel states
retain folder pairs for correction or retry.

Numerical, deterministic-parallel, decoding, cancellation, race and preservation
coverage lives in `tests/unit/test_preprocessing_equalization.py`. Registered visible
GUI coverage lives in `tests/gui/test_image_equalizer_dialog.py`. Run preprocessing,
GUI and docs focused verification, then repository precommit. Visible Qt checks are
separate: inspect minimum/default sizes, both themes, long paths, multiple pairs,
empty/busy/error/cancel/success states, output reports and repeated-batch conflicts.
