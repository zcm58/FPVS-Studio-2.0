# Masking protocol feedback and publication

Status: Completed

The user requests a revised Library experiment covering all three variants, random
variant-block order with SOAs shuffled inside each block, fresh targets on repeated
launches, identification/blink instructions, static fixation, trial answers and EEG
start codes. They explicitly chose 50 ms -> 33 ms. At 60 Hz this means 33.333333 ms
(two frames); 16.666667 and 100 ms remain unchanged.

## Acceptance

- Keep nine trials per variant (three shuffled SOA triplets), randomize the order
  of the three complete variant blocks, and retain deterministic explicit seeds.
- GUI Masking compilations use a fresh seed, including retries after an abort.
  Sample one target per trial, repeated within the stream; chance repeats remain valid.
- Update the editable Masking project with exact two-frame middle SOAs and clear
  variant-specific instructions. Preserve original pixels, color triples, geometry,
  all four choices and the 26-object face base pool. Faces has four emotional choices,
  with four exemplars per emotion (16 images), not four images total.
- Confirm static red scene fixation and disabled color-change detection; codes 1-9
  continue to identify each variant/SOA at stream start. No trigger transport change.
- Verify per-trial targets, selected answers and correctness survive normal and
  interrupted sessions in full/compact export modes; keep original journals intact.
- Publish Masking 1.1.0, requiring a companion Studio 1.9.2 fix, after validation.
  Retire the old Masking catalog entry only after the new download is verified.
- Run compiler/runtime/GUI focused checks and repo precommit; register relevant Qt
  cases without local Qt execution. Package, audit and publish Studio with its normal
  full/patch process. Document unrun visible GUI and physical EEG/display checks.

## Evidence and boundaries

Current compiler shuffles SOA triplets but keeps variant groups in insertion order.
Target sampling already uses the run seed; GUI retries only replace seeds after a
completed session, allowing interrupted trials to repeat exactly. Existing native
scene/task exports already retain target identity, selected options and correctness.
No user/source images or participant data will be removed. The project JSON will be
backed up and checked for concurrent changes before its targeted update.

## Implementation and verification progress

- Compiler now shuffles complete variant groups. GUI Masking recompilation refreshes
  its seed without marking the document dirty; explicit compiler seeds remain reproducible.
- Runtime adds the joined `masking_trials_v1.csv` on normal/graceful-abort finalization.
  Immediate raw response journals and pre-input plan checkpoints remain unchanged.
- Focused compiler: 263 passed. Runtime: 391 passed, one Windows symlink skip.
  GUI safe route: seven passed; registered Qt retry regression was not executed locally.
- Revised authoring project validated across 18 seeds (486 trials): all six block orders,
  all target exemplars, three occurrences of each EEG code, and 1/2/6-frame SOAs.
  A reversible JSON audit confirms only SOAs, condition labels and instructions changed;
  original project backup and all source asset hashes are retained in ignored build evidence.
- Library bundle: 128 files, 31,431,021 bytes, SHA-256
  `36bfc0406f5d651ebb9213e0f507ec2d073fd76d4c655157b5d0f5e3bdf64459`.
  Publisher dry run validated Masking 1.1.0, minimum Studio 1.9.2.
- Repo precommit passed: 2,093 tests, ten Windows symlink skips; Ruff, compilation,
  mypy (206 source files), harness and docs audits passed. Docs focused: nine passed.
  Isolated bundle import compiled 27 trials and verified all 126 image bytes by hash.
  Instruction text metrics fit the 1920x1080 display; visible playback remains unrun.

## Published result

- Studio source on master and annotated tag `v1.9.2` identify
  `f72ebac064a7960730ad7ba2a99944ea938fe00a`.
  [Studio 1.9.2](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v1.9.2)
  (release ID 394802942) is published with six digest-verified assets.
- Full extraction verified 7,985 files. The 1.9.1 patch changes/adds 11, removes eight
  obsolete files and retains 7,974; reconstruction matches every full-target hash.
  All five changed embedded modules match source. All 493 native inputs match 1.9.1.
  The updater's non-GUI packaging diagnostic passed.
- Live updater discovery selects the patch with the authenticated 1.9.1 inventory,
  the full installer for older/unregistered installations and no update on 1.9.2.
  GitHub briefly returned a stale release list immediately after publication; the
  unchanged production client passed once the remote feed refreshed.
- Masking 1.1.0 published under stable item ID `masking`, tag `masking-v1.1.0`,
  minimum Studio 1.9.2. Catalog publication commit:
  `ccf0fcf884e49938d30a89d2128354c983c45718` in the private Library repository.
  A researcher-client download verified SHA-256, imported/compiled 27 trials,
  preserved all 126 assets and rejected a duplicate installation.
- Catalog commit `e24ec99` unlists only Masking 1.0.1 after that verification.
  Old immutable release assets, user project folders and participant data remain intact.
- Evidence: `build/release-1.9.2/` and `build/masking-1.1.0/`; installers:
  `dist/release-1.9.2/installer/`. The original authoring JSON is backed up separately
  from the updated local Masking project. The original PsychoPy folder is untouched.
- Visible GUI/packaged playback, installer execution, physical display timing and EEG
  checks were not run; these boundaries are also stated in the public release notes.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-1.9.2.exe` | 300944386 | `bb855ca27ef801a736fbf5a638710cb005388d22cd5d4ec77ee77ec5254b983e` |
| `FPVS-Studio-Patch-1.9.1-to-1.9.2.exe` | 72342190 | `a2141fe2b9f1668189065751189e5ea1a0d48e1f95643653d02940c16d772a66` |
| `FPVS-Studio-Update-1.9.2.json` | 435 | `b98c47b21d1f79fbae1c05ac2830929ebe39f97862b5030c4703861ea7f94e34` |

Each artifact has a published `.sha256` companion. Target inventory SHA-256:
`b76ec8fcc8957fe4cefcec528d593321dbe80b86b931ae1612ee512b4efc4f27`.
