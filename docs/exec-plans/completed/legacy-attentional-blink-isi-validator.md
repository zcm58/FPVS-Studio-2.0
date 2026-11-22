# Shared Legacy Attentional Blink ISI Validation

Status: Completed

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
  [Toolbox config](../../PROJECT_CONFIG.md) bytes, and compiled frame schedules
  with fixed inputs. Historical within-slot image-pair projects now open for
  read-only review. Compare the original input bytes and existing compile,
  save, and export rejection messages for those projects. Use supported letter
  streams for the compiled schedule comparison.
- Use the existing Attentional Blink model, compiler and project-config tests.
  Run focused `core`, `compiler` and `project-io` checks and safe precommit for
  the shared validation paths.

## Implementation and results

Both model hooks delegate to the same raw-input transformation. It copies only
legacy within-slot mappings that omit both `isi_stimulus_set_id` and `isi_mode`.
Explicit nulls and sources reach the existing validators unchanged.

The Windows parity probe ran 17 inputs through each of the two model types.
It captured error text, serialized values, and whether the caller's input was
copied. It also compared read-only retired image-pair inputs, six public rejection
cases, and project, Toolbox config, and compiled run and session bytes for a
supported letter stream with fixed seeds and clocks. The transcript matched
exactly before and after with SHA-256
`25107436f9fafa89c05c4715ed8834ed969035cb9fccdc1269f3c8c0c853cb80`.

Core focused verification passed 935 tests with one Windows symlink-permission
skip. Compiler focused verification passed 817 tests. Project I/O focused
verification passed 921 tests with three Windows symlink-permission skips.
Repo precommit passed both platform type checks, repository audits, and 6,622
unit tests with 41 platform or permission skips. Docs focused verification
passed all 13 checks.
