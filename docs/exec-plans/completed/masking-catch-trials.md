# Masking catch trials and 50 ms restoration

Status: Completed 2026-09-25

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
- Library preparation passed the canonical publisher dry run. Studio 2.0.0 was
  published before removing the old catalog entry and publishing Masking 1.2.0.
- Release notes use only short bullets summarizing major changes, as requested by
  the user; verification evidence and installer guidance are not included in them.

## Published release evidence

Source commit `8110827cb21b96bd9dddf5b611c3adc028fbe45a` was fast-forwarded to
`master`, pushed, and tagged `v2.0.0`. The stable release is
[FPVS Studio 2.0.0](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.0.0).

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| FPVS-Studio-Setup-2.0.0.exe | 300980327 | `027fcacd290dbda0051401c01ad262a5caa6e31b52ad61afcf8956ed5ece08b0` |
| FPVS-Studio-Patch-1.9.2-to-2.0.0.exe | 72348710 | `f3c979dc8025138f27cf5387b980d7bac63c0281a57ef65d22398c2e1229e877` |
| FPVS-Studio-Update-2.0.0.json | 435 | `81aa87af58121109fc8df9bcb36254bbc2aa9acb36af8bb4efa01fca3521a77c` |

All 7985 extracted full-installer payload files matched the target inventory
`d96173451cb37abf74fb78dd9e1b3ae7447cd9009771f21f6882b41787cac997`.
The authenticated 1.9.2 patch adds/changes 11 files, removes eight and retains 7974;
reconstruction equals the complete target exactly. All 493 native dependency inputs
match published 1.9.2 bytes, and all 18 changed embedded modules match the source.
The six public assets have matching local/server sizes and digests. Live updater
selection chooses the patch for an authenticated 1.9.2 inventory, the full installer
for older or unregistered installations, and no update for 2.0.0. Evidence is retained
under ignored `build/release-2.0.0/`; this does not establish actual installation.

## Library replacement

Masking 1.1.0 was removed from the catalog in commit
`0e533a5785e6b70fd9a2b4ce5b98a1994290eac2` before publishing Masking 1.2.0 in
`c8180197a4536cfe0413abe038ae44b2a93f330a`. All seven unrelated catalog entries are
unchanged. Historical immutable release assets and user projects/data remain intact.

- Bundle: `masking-1.2.0.fpvsbundle`, 31431066 bytes, minimum Studio 2.0.0.
- SHA-256: `832d611f8b6d2f2282b93b6b3609ea440d3d1ab32fcaf37ba756be42c53a2830`.
- Private Library tag: `masking-v1.2.0`; asset ID `588417538`.
- Live enrolled-client verification found only Masking 1.2.0, downloaded and verified
  the bundle, imported all 128 payload files including 126 unchanged images, compiled
  the 30-trial design, and confirmed the origin receipt and duplicate-import block.
- No participant data was included. The authoring project remains titled Masking.
  Evidence is retained under ignored `build/masking-1.2.0/`.

Actual installer execution, installed application launch, Qt/visible GUI acceptance,
and physical display/EEG acceptance remain unrun. The unused preliminary
`build/release-1.10.0/` preparation folder remains because automatic approval review
blocked recursive cleanup; it is not a published or built release.
