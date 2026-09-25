# Masking catch trials and 50 ms restoration

Status: Active

The user approved all summarized email changes except base-pool expansion and requests
replacement of the old Library version. The follow-up explicitly confirms one EXTRA
full-length catch per variant block (30 trials total), mask timing sampled from that
block's SOAs, four-choice identity retained, PAS No experience used for correct
rejection and catch identity accuracy unscored.

## Acceptance

- Restore 16.666667/50/100 ms (1/3/6 frames at 60 Hz). Preserve all pixels, RGB triples,
  geometry, static fixation, 26 face base objects and 16 face exemplars.
- Randomize the order of all three complete variant blocks on fresh GUI launches.
  Finish all nine ordinary trials and one randomly inserted catch before changing
  variant; retain three independently shuffled SOA passes per block.
- Catch trials preserve stream duration, masks/base/overlays/fixation and have ZERO
  target flashes. Log target identity as absent, never fabricate an identity.
- Add editable optional catch settings in Condition Modifiers; all selected SOAs of
  a variant must agree. Codes 1-9 remain ordinary condition/SOA starts; 10/11/12
  identify Color/Faces/Number catches. Preserve trigger transport.
- Instructions explain possible absence, fixation, blinking during breaks and separate
  visibility/forced-choice reports. Do not automatically rewrite custom instructions.
- New versioned trial CSV joins PAS, catch status, detection outcome and identity
  scoring; retain historical v1 files untouched and preserve durable raw journals.
  Partial/aborted exposure must not be scored as a correct rejection.
- Preserve catch-disabled payloads and explicitly version new contracts to prevent
  older Studio builds silently presenting ordinary targets for catches.
- Publish Studio 2.0.0 (explicitly selected by the user) and Masking 1.2.0 requiring
  that build because catch scheduling, GUI and scoring are new Studio capabilities.
  Project-only revisions must not require a newer Studio version without a feature
  dependency. Prepare and verify all
  local artifacts first, then unlist the old Library entry before publishing the new
  item. Do not delete user projects, data or old immutable release evidence.
- Focused compiler/runtime/engine/project-I/O and safe GUI checks plus repo precommit.
  Register Qt coverage without executing Qt locally. Full/patch extraction, embedded
  source, remote digest and live updater/Library verification precede completion.

## Ownership

Core models/compiler/schema work: catch_core agent. Runtime exports: catch_runtime.
Modifier GUI and registered tests: catch_gui. Root owns preflight, engine verification,
instructions, project migration, docs, integration verification and publication.

## Verification boundaries

Visible GUI, actual installer execution and physical display/EEG checks are not part of
the authorized local verification environment. Report them as unrun, not passed.

## Implementation and local evidence

- Catch settings, schema guards, whole-block scheduling, and four-choice unscored catch
  identity are implemented. Actual per-condition occurrence counts include the extra
  catch, so custom last-occurrence tasks still execute after their final occurrence.
- Condition Modifiers has a Masking-only Catch trials tab. New runtime output is
  `masking_trials_v2.csv`; historical v1 files are not rewritten.
- The authoring project is updated and backed up under ignored
  `build/masking-1.2.0/`. Eighteen explicit session seeds passed compilation/preflight
  (540 sequences), covered all six block orders and every target exemplar, and retained
  all 126 source-image SHA-256 values. Instruction font metrics fit 1920x1080; this is
  a static check, not physical display acceptance.
- Focused routes passed: compiler 276; runtime 416 (one Windows symlink skip); engine
  306; project I/O 235 (two Windows symlink skips); packaging 181; safe GUI 7; docs 9.
  The verification configuration check passed. Ordinary plans matched the original
  compiler across eight explicit seeds.
- Repo precommit passed: Ruff, compilation, mypy (206 source files), harness/docs
  audits and 2132 non-Qt tests, with ten Windows symlink skips. The first full pass
  encountered an existing exact-retry-count assertion after a transient Windows lock;
  the serialization file passed independently (8 tests) and the complete rerun passed.
- Library preparation passed the canonical publisher dry run. Publication remains
  pending until Studio 2.0.0 is available and the old catalog entry is removed.
- Release notes use only short bullets summarizing major changes, as requested by
  the user; verification evidence and installer guidance are not included in them.
