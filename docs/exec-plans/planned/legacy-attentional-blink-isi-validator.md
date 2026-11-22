# Shared Legacy Attentional Blink ISI Validation

Status: Planned

Baseline reviewed against Studio 3.1.4 on 2026-11-22.

## Current workflow and evidence

Studio opens saved conditions through
[`Condition`](../../../src/fpvs_studio/core/models.py). Studio and Toolbox exchange
editable conditions through
[`ProjectConfigCondition`](../../../src/fpvs_studio/core/project_config.py).
Both models have identical Pydantic before-validators for old within-slot
Attentional Blink data. If `isi_stimulus_set_id` and `attentional_blink.isi_mode`
are both absent, the validators copy the payload and set the ISI stimulus source
from `base_stimulus_set_id`. The omitted `layout` defaults to `within_slot` for
this check. Seven direct cases matched between the two existing validators.

## Implementation and acceptance

- Share the legacy input transformation in core. Keep both model hooks so the
  transformation runs at the same point in each validation path. Preserve the
  distinction between missing fields and explicit null values, supported layouts,
  validation errors and the copy-on-change behavior.
- Exercise both public model paths with omitted fields, explicit null or a named
  ISI source, explicit image and blank modes, missing or invalid settings, and
  letter-stream settings. Compare validation outcomes, serialized project and
  [Toolbox config](../../PROJECT_CONFIG.md) bytes, and compiled ISI sources and
  frame schedules for the same legacy project and fixed timing inputs.
- Use the existing Attentional Blink model, compiler and project-config tests.
  Run focused `core`, `compiler` and `project-io` checks and safe precommit for
  the shared validation paths.
