# Masking visible catch conditions and instruction design

Status: Completed 2026-09-25

The user supplied an instruction-screen photo and explicitly relaxed the old
PsychoPy visual-mirroring requirement. Remove the variant-block heading and improve
instruction typography/layout while preserving task functionality. Make catch trials
real authored conditions 10/11/12 within their existing variant blocks. Update the
Library experiment, and update Studio only if new support is needed.

## Decisions and acceptance

- Studio 2.0.0 cannot express once-per-block, target-absent authored conditions;
  it repeats every authored Masking condition and only inserts implicit modifier
  catches. Therefore release Studio 2.1.0 and Masking 1.3.0, with a minimum Studio
  version reflecting that feature requirement. Do not approximate catch trials with
  transparent targets or display-only condition rows.
- Twelve actual conditions: ordinary 1-9 repeated three times; Color Catch 10,
  Faces Catch 11, Number Catch 12 scheduled once each. Three intact variant blocks,
  independently randomized block order and ordinary SOA passes, random catch position
  and SOA. Total remains 30 full-length sequences at 16.6667/50/100 ms.
- Explicit catches own their condition IDs/names/trigger codes, share native Masking
  sources and tasks, and retain absent-target/PAS scoring semantics. Preserve legacy
  automatic-catch projects and seeded ordinary payloads. Reject double-catch designs.
- Catch-only launches sample ordinary same-variant SOAs from the project; mixed
  selections sample selected ordinary same-variant SOAs. Validate all eligible sources.
- Setup Conditions exposes real catch creation and readable once-per-block summaries.
  Do not silently edit other conditions/modifiers when creating a catch condition.
- Replace the dense centered instruction paragraph with separate editable text items,
  clear heading/body hierarchy, left alignment and a distinct Space prompt for all
  three variants. Retain instruction-before-first-run, fixation, PAS/identity/frequency
  questions, break behavior and keyboard/mouse semantics. Keep scientific stimulus
  images/colors/geometry/timing and base pool unchanged.
- Add the smallest reusable text-alignment support needed by the instruction design;
  default-centered legacy tasks serialize and render unchanged.
- New editable project/config contracts require schema guards; compiled catch scenes
  and runtime detection reporting already support the requested behavior.
- Prepare and validate new Library bytes before withdrawing the old listing; publish
  the required Studio release first. Preserve immutable old assets and user data.
- Release notes remain short major-change bullets, without verification summaries or
  installer instructions, per the user's saved preference.

## Ownership and verification

Core agent: condition contract, authoring helper, scheduler, schema/config guards and
core regressions. GUI agent: Setup Conditions action, summaries and registered tests.
Runtime agent: editable text alignment, task layout/rendering/editor and regressions.
Root: instruction design, actual project revision, integration, docs and publication.

Run focused compiler/runtime/engine/project-I/O and safe GUI routes, then precommit.
Compile real project across seeds; verify 12 visible conditions/30 runs, true catch
IDs and EEG codes, intact blocks/SOA passes, no target flashes, unchanged media and
correct report attribution. Preview the authored instruction layout at 1920x1080 and
smaller 16:9 resolution, with static font-metric bounds and native-constructor tests.
Register Qt coverage without local Qt execution. Report visible GUI, installed-update
and physical presentation/EEG checks as unrun unless separately performed.

## Implementation and project review

The core catch-condition flag, immutable authoring helper, once-per-variant scheduler,
identity/marker preservation and strict schema guards are implemented. Setup Conditions
can add and display catches; the task editor exposes positioned instruction items and
text alignment. Applying non-centered text to an older project promotes its schema
before validation, with centered defaults unchanged.

The authoring project has twelve conditions in variant order, with codes
`1,2,3,10,4,5,6,11,7,8,9,12`. Its automatic modifier catches were explicitly removed.
All 126 active image assets match their original hashes; normalized project comparison
confirmed only catch rows/order, schema and the nine instruction steps changed.
Compilation/preflight across 24 seeds produced 720 full-length sequences, all six
block orders, all three catch SOAs and independent target sampling. Catch-only launches
retain their own condition IDs and codes. Static Open Sans layout previews and font
bounds fit all three variants at 1920x1080 and 1366x768; these are not display captures.

Focused checks passed: compiler 288; project I/O 247 with two Windows symlink skips;
runtime 420 with one Windows symlink skip; engine 310; packaging 181. The generic
task-editing regression module passed 39 tests. Existing ordinary and automatic-catch
SessionPlan JSON matched the 2.0.0 implementation byte-for-byte for eight seeds each.
Safe GUI checks and registered coverage are in place; local Qt execution remains unrun.

The prepared Masking 1.3.0 bundle has 128 files and 31,431,953 bytes; SHA-256
`2d4161c95359935cdece1a33630110b51efb1368e946006c8fd48e38c4c11a6f`.
Its project schema is 1.9.0 and minimum Studio is 2.1.0. Publisher dry-run and
maintainer access checks passed. Isolated import verified all payload files, decoded
images, unchanged native geometry/pools/questions, and the exact instruction items.
The supported update path imports one explicit newer project copy; it does not replace
1.2.0 in place. Its original bytes and sentinel participant data remained unchanged,
and repeat 1.3.0 download/import were rejected. Studio 2.0.0 correctly rejects the
new incompatible bundle.

Repository precommit passed Ruff, compilation, mypy, repository/documentation audits,
and 2,157 unit tests, with ten Windows symlink skips.

## Studio 2.1.0 publication

The feature branch was merged into `master`. Release source and the annotated `v2.1.0`
tag target are `5a8826fe5776e88968bf9867c74a3fd2a3818d8b`; the later publication-record
commit changes documentation only. The published release is
[FPVS Studio 2.1.0](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.1.0).

The full installer and direct 2.0.0 patch were built from the clean release source.
All 18 changed packaged Python modules matched compiled source. Extraction verified
all 7,985 owned payload files; the patch changes/adds 11, removes eight and retains
7,974, reconstructing the exact full-install target. All 493 native inputs match the
authenticated published 2.0.0 baseline. The target inventory SHA-256 is
`6d0194870b976f7c44ecf758bb5b35a45dfc613b2b8984564208847f93c9d8c9`.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| FPVS-Studio-Setup-2.1.0.exe | 300,995,969 | `e33363f372105454d3976aa20f5bb1ef8b581614ab082e0c60b85bca27fc2164` |
| FPVS-Studio-Patch-2.0.0-to-2.1.0.exe | 72,355,675 | `5b3ffaa403e4cfe8ed8df174f5245c18ad60d885528db4a737390a7b9af3dec0` |
| FPVS-Studio-Update-2.1.0.json | 435 | `bea330a03213a1769743d014383e46c429d6f115d6273914087adf21b7b00fe1` |

GitHub release `396672901` contains those three artifacts plus their checksum files;
all six server sizes/digests matched local bytes. Public updater checks select the
direct patch for registered 2.0.0, the full installer for older/unregistered installs,
and no update for 2.1.0. Release notes contain only concise major-change bullets.
Detailed local evidence is retained under `build/release-2.1.0/`.

## Masking 1.3.0 Library replacement

After Studio publication passed, the old 1.2.0 catalog entry was removed in Library
commit `6da89f799c6c7919c887bb0597d7bc1a1860b0ec`. The canonical publisher then published
`masking-v1.3.0` and committed its catalog entry as
`0d66730724c847c661df4e34356cf4cb4c02637b`. The immutable bundle is asset `588527320`
in release `396675327`, with the digest and size recorded above. Seven unrelated
catalog entries remain identical; historical release assets and participant data
were retained. Both releases use the user's short-bullet notes format.

The ordinary enrolled Library client returned only Masking 1.3.0, downloaded bytes
matching the local digest, and imported the bundle into an isolated root. Checks
verified all 128 files/126 images, twelve condition identities and EEG codes, thirty
sequences in three intact blocks, catch-only launches, source image decoding, native
geometry/pools and the exact authored instruction layouts. A receipt was persisted;
repeated download and import of the installed version were blocked. Project-only
revisions still need no automatic Studio version bump: this revision's minimum is
2.1.0 because it uses the two newly added capabilities.

Evidence remains under `build/masking-1.3.0/`. The authoring project's `migration/`
contains the pre-change project backup, project audit, 1.2.0 withdrawal record and
1.3.0 publication record. The original PsychoPy source was not modified.

## Verification boundary

No local Qt execution, visible packaged-app smoke, real installer execution or
physical PsychoPy/display/EEG run was performed. Static instruction previews,
constructor checks, compiled timing and image-decoding preflight do not establish
physical timing, rendered font fidelity, GUI clipping or measured EEG onset.
The registered visible GUI and physical acceptance paths remain in `docs/MASKING.md`.
