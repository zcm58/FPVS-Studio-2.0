# Attentional-Blink Letter Stream Study

Status: Completed (software implementation)

Updated: 2026-09-10

The user approved implementation of the 10 Hz letter-stream study and its clear
three-condition GUI on 2026-09-10. Work covers defaults, authoring, saved timing,
playback, and the existing post-condition questionnaire path. The implementation is
complete; physical display/trigger measurements and behavioral piloting are separate
scientific acceptance work and were not run during this GUI/software task.

## Implementation outcome

- New projects use the explicit letter-stream template: 10 Hz, 20-character cycles,
  shared digit/T1/T2 pools, red T1 and white T2, and the three requested SOAs.
- Design shows typed character pools, editable SOAs, intervening-digit counts, target
  roles and an onset bracket. Next applies the shared draft atomically. Character Size
  edits native text height; Timing requires exact whole frames. Legacy image-pair
  projects and templates retain their original editor and scientific timing.
- Stream project/config/run schemas are 1.5/1.3/1.3. Custom template clones preserve
  explicit layout and fixation defaults. Layout changes are blocked; added conditions
  select unused markers. Default SOA names track edited values without renaming custom names.
- Playback uses existing native TextStim resources and the frame loop, with separate
  target markers and versioned character event exports. The existing task runner asks
  the unscored visibility question after each completed condition entry.
- Verification: 1,285 non-Qt tests passed (five Windows symlink skips); 113 selected
  visible GUI checks passed, including all nine steps at 1120x820 in both themes,
  expanded designer sizes, source edits, profile cloning, and legacy image/oddball editors.
  Core focused verification passed 319 tests (one symlink skip). GUI Ruff/compilation,
  docs hygiene, harness audits and verification configuration passed.
- Repository precommit stops at the pre-existing mypy error in `gui/controller.py:373`
  (`object` returned where `str` is expected). No new source typing errors remain.
- Reviewed screenshots are retained locally under `build/ab-ui-review/` for all three
  SOAs in light/dark themes. Real PsychoPy presentation and hardware triggers were not launched.

## Confirmed study requirements

- Keep the existing, locked Attentional-Blink experiment category.
- Present digits as the base stream and letters as T1 and T2.
- Use a uniform 10 Hz stream. Digits continue between targets; no blank separator.
- Vary target-onset separation (SOA), not offset-to-onset ISI. The user explicitly
  clarified this distinction and approved 100, 300, and 500 ms SOA conditions.
- Keep this as one study with three conditions, using existing session/run machinery.
- Simplify the AB authoring GUI; manual drag/drop assembly is not necessary for this
  protocol. Preserve a visual explanation of the selected condition.
- Include the requested post-condition visibility questionnaire through existing tasks.
- Retain the FPVS extension: repeat a stable stimulus pattern within each EEG block.

## Confirmed timing

A uniform 10 Hz stream has one character onset every 100 ms. The user approved
100, 300, and 500 ms SOAs so all three conditions fit the same whole-character grid.
Each digit, T1, and T2 is displayed for 100 ms without a blank between characters.

| Condition | SOA | Target lag | Intervening digits | Time from T1 offset to T2 onset |
| --- | --- | --- | --- | --- |
| SOA 100 ms | 100 ms | 1 | 0 | 0 ms |
| SOA 300 ms | 300 ms | 3 | 2 | 200 ms |
| SOA 500 ms | 500 ms | 5 | 4 | 400 ms |

Validate any edited SOA against the character-onset grid. For example, a 250 ms
request must be rejected at 10 Hz rather than rounded, shortened, or filled with a
blank. The 100 ms condition has adjacent targets, which is deliberately different
from the other conditions' intervening-digit pattern.

All three labels should state the actual SOA, such as "SOA 100 ms". Do not label
conditions conscious/unconscious: those are experimental outcomes. The approved
500 ms condition is not a guaranteed fully recovered recognition condition.

## Recommended study defaults to review

- Digit pool: 2-9; uppercase letter pools for both targets. Avoid easily confused
  glyphs in the initial preset. T1 and T2 in a pair must differ. Avoid adjacent
  identical digit distractors. Compile seeded selections and record exact symbols.
- Equal character exposure, derived from the stream rate. T2 no longer fills leftover
  time. Changing SOA changes target positions rather than target exposure.
- Proposed repeating cycle: 20 characters at 10 Hz, lasting 2 seconds. Keep T2 in
  slot 16 (one-based), leaving four digits afterward. Move T1 earlier by the chosen
  lag. T1 occupies slot 15, 13, or 11 for the 100, 300, or 500 ms condition. This
  accommodates the approved separations with pre-T1 and post-T2 context.
- Keep digit pool, target pools, colors, font, size, cycle duration, T2 position, and
  condition-run duration the same across the three conditions. Only SOA varies.
- Proposed color scheme, matching the user's white-letter question: red T1, white
  T2, and white digits on a dark background. This is a reviewable design choice,
  not a claim that red T1 is required by research. Keep it constant across conditions.
- Participant instructions should direct attention to both target letters. The
  requested white-letter questionnaire alone cannot verify that T1 was attended or
  identified; record that measurement limitation until target reports are added.
- Keep existing session block/repeat/order behavior; do not introduce new order or
  counterbalance algorithms as a dependency of this feature. Preview actual order.
- For this new preset, recommend a static fixation option with the competing fixation
  color-detection task disabled. Preserve its existing implementation and all old
  project settings. Clearly distinguish optional fixation scoring from AB outcomes.
- Run length and repetitions remain explicit Session choices. The two-second cycle
  is not a proposed two-second EEG recording block.

At the example two-second cycle, each target repeats at 0.5 Hz. Both contribute to
the same repetition frequency; separate trigger codes do not separate their frequency
responses. Moving T1 changes the combined waveform. This is an experimental FPVS
extension requiring behavioral and physical-timing validation, not a verified T2-only
frequency tag or an automatic measure of unconscious processing.

## GUI plan

Use the existing nine-step Setup shell and shared components at 1120x820, in both
themes. Keep the initial creation screen category-only. The alphanumeric study
preset is selected within the existing Attentional-Blink creation/template flow.

| Surface | Adaptation |
| --- | --- |
| Project | Preserve category locking and existing project metadata. New preset creates the three conditions once, with stable IDs. |
| Conditions | Show three real condition rows with names and SOAs. Reuse existing instructions and task bindings. The preset has three conditions; do not impose a global three-condition restriction on every AB project. |
| Design | Replace manual image-pair construction for this preset with shared digit/letter settings, a three-condition timing table, and one selected-condition timeline preview. |
| Timing | Reuse display verification; show requested and achieved rate/SOA, item duration, and frame counts. Reject unsupported exact schedules explicitly. |
| Image Size | Reuse text sizing/geometry controls with an AB-specific "Character size" label. No image-folder normalization for native text. |
| Session | Reuse run lengths/repeats/order. Show cycle repetition frequency, condition duration, total acquisition time, and questionnaire placement. |
| Fixation / Response | Explain the selected fixation behavior and the post-condition visibility report separately. Expose the existing questionnaire editor through the AB flow. |
| Review | Summarize all three achieved SOAs, symbol/color rules, condition order, target repetition frequency, and post-condition questions. |

The Design page should contain:

1. A compact shared row: stream rate, digit pool, target letter pool(s), and color
   samples. Inputs are typed; there are no spin arrows or required source folders.
2. Three rows with condition name, requested SOA, achieved SOA, target lag, and
   number of intervening digits. Achieved timing stays unset until a refresh rate
   is available. A 250 ms request at uniform 10 Hz is visibly invalid.
3. A read-only timeline for the selected row: pre-target digits, T1, intervening
   digits, T2, and post-target digits, with onset labels. It uses the same core
   description as compilation; the GUI does not implement independent timing math.
4. A small slowed-preview control and collapsed timing detail. Label the preview
   as illustrative; it does not verify display or trigger timing.

Use Next as the single apply/navigation action, preserving current pending-edit,
save, condition-switch, and invalid-draft behavior. Put shared controls in one place;
apply shared edits atomically to the underlying canonical owners for all preset
conditions. Do not maintain an independent GUI copy of the study definition.

Remove the new preset's image-folder cards, image/blank ISI selector, compound-slot
editor, and automatic leftover T2 display. Keep the existing FPVS-Oddball designer
and preserve the legacy image-pair editor when opening existing AB projects.

## Post-condition questionnaire

Reuse one existing questionnaire module bound to all three conditions, running after
every completed condition entry and after its final stimulus-offset flip. Keep the
existing abort/task-occurrence policy; do not move questionnaire rendering into the
timed stimulus loop.

Recommended block-level wording: "Did you notice any white letters during that
sequence?" Responses: Yes / No / Unsure. If the colors make this ambiguous, use
"Did you notice any second target letters (T2) during that sequence?" Prompt text
must match the configured task and must not silently overwrite user-authored wording.

Keep correctness and score unset. Existing task response records provide participant,
condition, run, block, question, answer, and response-time linkage. A Yes answer after
many pairs indicates at least one reported sighting; it is not per-pair recognition
accuracy and must not be exported as T2 correctness or proof of awareness for a delay.

An additional short-sequence behavioral validation mode is recommended future work:
report the actual T1 and T2 identities, optionally rate T2 visibility, and calculate
T2 accuracy given correct T1. That requires explicit pair-to-answer binding, which
static questionnaire answer keys do not provide. It is not a prerequisite for the
requested block-level questionnaire and is not silently included in this first slice.

## Implementation boundaries and reuse

The feature changes the AB timing model and character support, not just the GUI.

| Owner | Planned work |
| --- | --- |
| `core/models.py`, `enums.py`, `validation.py`, `experiment_categories.py` | Add an explicit AB stream layout alongside the existing within-slot layout; permit native character stimuli only for the new layout. Keep `Condition.attentional_blink` the condition timing owner and existing project protocol/source owners for shared data. |
| `core/attentional_blink.py`, `compiler_attentional_blink.py`, `compiler.py` | Describe and compile independent T1/T2 slots, fixed item durations, derived intervening digits, complete cycle coverage, seeded symbols, and target markers. Dispatch before ordinary oddball scheduling. |
| `core/run_spec.py`, `presentation.py` | Add versioned stream metadata without pretending T1/ISI/T2 are subdivisions of a single slot. Reuse text payloads and role presentation; allow explicit T1/T2 color distinction. |
| `core/migrations.py`, `serialization.py`, `project_config.py`, `project_bundle.py`, template services | Persist/round-trip layout, symbols, timing, and questionnaire references; validate old/new representations and export compatibility. |
| `gui/design_setup_step.py`, new focused AB form, `condition_setup_step.py`, `setup_wizard_page.py`, document services | Route the new preset to the compact form, create three conditions once, bind shared edits, reuse shell/Next/size/condition selection, and preserve legacy routing. |
| `gui/components.py`, existing text presentation controls | Reuse theme, typography, spacing, numeric input, and character geometry; no new UI framework or broad redesign. |
| `core/task_models.py`, `compiler_tasks.py`, `gui/condition_task_dialog.py`, `runtime/task_runner.py` | Reuse single-choice questionnaire definitions, post-condition occurrence rules, and existing response collection/export. No second questionnaire subsystem. |
| `runtime/preflight.py`, `engines/psychopy_stimuli.py`, `psychopy_engine.py` | Validate the stream layout and text assets/geometry; reuse existing TextStim resources, explicit frame-event rendering, onset capture, and flip-synchronized markers. |
| `core/execution.py`, `runtime/session_export.py` | Export layout, actual symbol, role, cycle/pair index, requested/achieved SOA and rate, frame counts and observed onsets, with task-response joins. |

Do not append new-format rows beneath an old AB CSV header. Use an explicitly
versioned character-stream event export or a tested header migration; existing
image-pair exports retain their meaning. Keep schema changes explicit in project,
config, bundle, compiled and execution contracts. Unsupported older consumers must
reject the new design rather than silently execute it as an oddball or compound pair.

Missing layout fields in existing projects must resolve to today's image-pair
behavior. New alphanumeric projects use the stream layout. Prevent mixing the two
AB layouts within a single new preset project, and never rewrite a saved scientific
schedule just by opening it. This does not introduce another master experiment type.

## Work sequence and acceptance

1. **Record and verify the exact schedule.** Use the approved 100/300/500 ms SOAs;
   finalize the proposed color defaults and example cycle. Describe requested versus achieved
   frame timing. At exact 60 Hz, uniform 10 Hz means six frames per item; at 120 Hz,
   twelve. This preset requires an integer frame count per 100 ms item; do not reuse
   nearest-frame rounding as permission to alter the requested rate. For example,
   144 Hz cannot provide exact 100 ms items. Validate the compiled display rate and
   expose any incompatibility; no alternating frame lengths or adjusted SOAs.
   Numerical comparison tolerance must be specified separately from the existing
   physical refresh-measurement tolerance. Verification of the real monitor stays
   with runtime and must not silently reschedule the compiled stream.
2. **Implement and verify the core stream layout first.** Add migration/serialization
   and deterministic frame/symbol schedules. Test all three conditions, boundary
   SOAs, invalid non-grid values, same target/digit exposure and post-T2 context.
   Capture unchanged legacy image-AB and FPVS-Oddball schedules for regression.
3. **Add the compact setup and preset.** Use one shared form/table/preview and current
   document/apply owners. Register GUI checks during implementation, including no
   duplicate preset creation, typed edits, invalid timing, and save/reopen behavior.
4. **Connect playback, questionnaire and exports.** Verify preflight and fake-engine
   frame plans; separate markers; questionnaire once per completed condition entry;
   response joins; abort behavior; and full/compact export compatibility.
5. **Complete desktop and scientific acceptance.** Run appropriate core/compiler,
   project-I/O/runtime/engine/GUI focused routes and repo precommit. Run registered
   Qt checks only in the user-approved visible environment, never offscreen. Inspect
   all nine steps at 1120x820 in both themes and the expanded window. Verify real
   display timing and EEG trigger alignment on the intended presentation system,
   then pilot behavioral outcomes before calling the study AB-validated.

During implementation update the canonical `EXPERIMENT_CATEGORIES.md`,
`VISUAL_EXPERIMENT_DESIGNER.md`, `GUI_WORKFLOW.md`, `RUNSPEC.md`,
`RUNTIME_EXECUTION.md`, `ARCHITECTURE.md`, agent routing and relevant scoped guides.
Until then those documents correctly describe the shipped image-pair implementation.
Do not amend the active setup-polish plan to imply this new study is implemented.

## Research grounding

- [Chun and Potter, 1995](https://pubmed.ncbi.nlm.nih.gov/7707027/): letter targets
  among digit distractors and delayed T2-report impairment.
- [Pincham and Szücs, 2012](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0037596):
  target timing, post-stream reports, and the importance of intervening items.
- [Martens et al., 2013](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0066185):
  alphanumeric and color-defined target tasks; individual differences and order errors.
- [Petro and Keil, 2015](https://pubmed.ncbi.nlm.nih.gov/26341931/): an AB task
  measured with steady-state EEG and behavioral target reports.

These sources motivate the design; they do not establish that the proposed repeating
FPVS schedule or its block-level questionnaire measures unconscious recognition.

## Planning verification

Current checkout inspected on 2026-09-10 at the pushed visual-designer branch.
Docs-focused baseline passed (9 tests and documentation hygiene). No application
code, project data, experiments, GUI windows, or hardware were changed or launched
while preparing this plan. Final documentation hygiene and all 9 docs-focused tests
passed. A separate read-only review checked timing arithmetic, legacy-layout
compatibility, questionnaire reuse, and export linkage.
