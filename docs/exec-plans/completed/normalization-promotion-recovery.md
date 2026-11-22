# Image Normalization Promotion Recovery

Status: Completed

Baseline reviewed against Studio 3.1.4 on 2026-11-22.

## Current workflow and evidence

Condition Setup can normalize inconsistent image sets to project-local PNG copies.
The [document action](../../../src/fpvs_studio/gui/document_stimuli.py) passes the
active project root to
[`normalize_stimulus_sets`](../../../src/fpvs_studio/preprocessing/normalization.py)
and updates the stimulus references and manifest after it returns.

The backend tracks `.tmp-<set>` only after converting every image in that set.
A cancellation after the first PNG left the staging directory behind in a
temporary-project probe. The promotion loop also deletes an existing destination
before replacing it. An injected replacement `PermissionError` left the previous
normalized folder missing.

## Implementation and acceptance

- Allocate a unique staging directory under the active project's normalized image
  root before writing. Validate lexical and resolved containment using the
  existing core path helpers. Keep stage and backup paths owned by the operation,
  including during cleanup. Avoid following directory links or junctions outside
  the project and preserve unrelated paths.
- Stage every selected set before promotion. Preserve an existing destination
  through a same-volume backup until the whole batch is promoted. If conversion,
  cancellation or promotion fails, restore prior directories and unwind new
  destinations from that batch. Preserve the original exception and retain a
  recoverable backup if restoration itself fails. Guard overlapping promotions
  to the same destination so one operation cannot undo another's output.
- Keep existing result paths, dimensions, counts and ordering. Compare PNG bytes
  and source files for the same fixtures before and after. Confirm the document
  action still applies normalized references and manifests only after backend success.
- Use temporary projects to exercise cancellation after the first PNG, decode or
  save failures, a failure promoting a later set, a failure during restoration,
  reruns, overlapping calls, and redirected project paths. Include prior output in
  some sets and none in others. Assert original file hashes, path ownership,
  surfaced errors and cleanup. Run the `preprocessing` and `project-io` focused
  routes and safe precommit for the changed failure behavior.

## Implemented behavior and evidence

The backend holds an advisory lock under the project cache while inspecting,
staging and promoting the batch. Existing folders move into the batch's staging
directory by rename. If a later step fails, the backend unwinds the completed
renames in reverse order and raises the original error. If a rollback rename
fails, it logs the retained recovery directory.

The document action preserved both prior normalized image sets, the project
model and the manifest after an injected second promotion failure. The retry
published both new source references and rebuilt the manifest once. The test
used the document mixin without importing Qt.

An independent process attempting to normalize the same project was refused
before writing output. Its retry succeeded after the project lock released.

Before-and-after runs matched the relative paths, image counts, dimensions,
conversion order, authored sources and PNG bytes. The exact-byte cases
included EXIF orientation, ICC profiles, grayscale, transparency and CMYK
sources. The leaner staging layout and resize path reduced the overhead of
the recovery work. In 48 alternating comparisons of a warmed four-image
replacement, the median paired overhead was 6.3 ms. The user approved that
tradeoff on November 22, 2026.

In six balanced pairs replacing an 80-image batch across two sets, wall-time
medians were 3.95 seconds before and 3.80 seconds after. The second run of each
pair was faster regardless of order, so the test establishes byte parity and
shows no consistent large-batch slowdown. GUI event-loop timing was unmeasured.

The Windows preprocessing scope passed 112 tests. Project I/O passed 921 with
three symlink-permission skips. Safe repo precommit passed Windows and Darwin
type checks, repository audits and 6,609 tests with 41 platform or permission
skips.
