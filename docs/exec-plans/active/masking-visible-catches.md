# Masking visible catch conditions and instruction design

Status: Active

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
and 2,157 unit tests, with ten Windows symlink skips. Release build/audit/publication
and live Library replacement remain pending.
