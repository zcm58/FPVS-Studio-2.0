# Image Normalization Promotion Recovery

Status: Planned

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
