# Visual FPVS Experiment Designer

Status: Completed

Implemented and visibly verified on 2026-09-07.

## Scope and accepted design

Work is on `codex/visual-fpvs-designer`, branched from
`codex/setup-ux-design-review`. The user approved implementing the latest image mockup
and explicitly requested experimental playback on 2026-09-07. This supersedes the
earlier preview-only implementation scope and conventional target-lag concept.

The native designer provides three source cards, equal-duration cycle slots, an
expanded proportional target slot, editable T1/ISI and automatic T2, separate folder
buttons, and a slowed preview. Its minimum is 1040x680 and default 1400x920 when the
screen permits. Standard FPVS and backward-masking preview remain separate tabs.

New attentional-blink drafts default to 4 Hz, three Base slots plus one target-pair
slot. The pair contains T1 for 50 ms, exactly one Base separator image for 50 ms during
ISI, and T2 for 150 ms. T2 fills the remaining 250 ms slot. The separator fills the ISI;
there is no additional blank. Four normal slots give six image onsets per second in
this example. The design is custom and does not claim that these timings guarantee
an attentional blink.

Use this design applies condition timing and project-wide cadence through the
existing document. Source imports are immediate condition edits; Cancel discards
unapplied timing. Save from Setup as usual. Backward masking remains preview-only.

## Ownership and implementation

- Core models own optional AB settings and a separate T2 source reference.
- `core/attentional_blink.py` owns requested and achieved timing.
- `core/compiler_attentional_blink.py` expands each target slot to frame events.
- RunSpec carries phase identity, slot indices and dedicated T2 presentation geometry.
- Runtime and engine retain their existing orchestration, fixation and frame loop.
  T1 retains the oddball marker; T2 has its own marker. Observed onsets and AB CSV
  exports follow the core result contract.
- GUI owns interactive widgets and cancellable slowed preview. Source intake and
  thumbnail decoding run on workers; QPixmaps remain on the UI thread.
- Condition copies/removal, normalization, configuration interchange and portable
  bundles preserve third-source ownership. Ordinary FPVS schedules remain unchanged.

Canonical workflow and research: [Visual designer](../../VISUAL_EXPERIMENT_DESIGNER.md).
Contracts: [RunSpec](../../RUNSPEC.md), [Runtime](../../RUNTIME_EXECUTION.md),
[Engine interface](../../ENGINE_INTERFACE.md).

## Acceptance criteria

1. Exact default frame arithmetic, minimum phase durations, invalid inputs, marker
   uniqueness and persistence roundtrips pass non-Qt tests.
2. Dedicated T2 assets/geometry, phase onsets, preflight, exports and ordinary schedule
   regressions pass with fake presentation resources.
3. Source-folder actions do not add timeline blocks. Imports, stale thumbnails,
   preview cancellation, draft switching and deferred close have registered GUI tests.
4. The designer fits 1040x680 and its default size in valid/invalid, populated/empty,
   light/dark states. Compare actual screenshots with the approved mockup.
5. Safe focused and repo checks run; existing unrelated failures remain documented.
6. Physical timing and trigger checks are explicitly distinguished from simulations.

## Verification record

The complete safe unit/integration suite passed: 1142 tests, with five Windows
symlink-privilege skips. This includes timing, compiler/config/bundle, runtime,
engine, preflight, graphics, export, and no-Qt document-mixin regressions. Core focused
passed 240 tests with one skip; repo focused passed 32 tests, docs focused passed nine
tests and hygiene checks. Changed sources pass Ruff and compilation; targeted mypy
passes for the changed GUI, core, and runtime modules.

The final repo precommit run stopped at an existing `gui/controller.py:372` mypy error
(object returned where str is expected), unchanged from the source branch. Earlier
bundle test failures were Windows path-length errors in the default deep temporary
directory; those tests pass with a fresh short workspace basetemp.

The user explicitly approved visible Qt checks. All 52 registered designer tests pass,
including real coordinate folder hit targets, source intake, Apply/Cancel, T2 persistence,
preview lifecycle, exact 1040x680/1400x920 sizes and valid/invalid layout states. The
first visible run exposed a test that opened a real context menu; the test now stubs
the menu constructor. A later layout expansion exceeded the compact minimum; responsive
font sizes, margins and canvas dimensions now preserve the documented size.

Final visible screenshots with isolated copies of real images are retained in
`build/ab-visible-4fe05a/`: dark default, dark minimum, and light minimum. Source projects
were read only. The rendered dialog follows the mockup's source/cycle/expanded-slot
layout with mathematically proportional durations and native Studio styling.
No PsychoPy presentation or trigger hardware was launched. Physical presentation/trigger
timing remains unverified; simulated tests do not certify it.
