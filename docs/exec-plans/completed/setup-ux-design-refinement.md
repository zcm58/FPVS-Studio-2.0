# Setup UX And Shared Visual Design Refinement

Status: Completed

## Release completion (2026-09-10)

Completed for 1.5.0. The final Setup has eight steps, combining Timing and Session,
with frameless, centered content at 1120x820. Later dated implementation notes
supersede earlier proposals. Focused visible checks passed; the final non-Qt
precommit suite passed 1244 tests with five platform skips.

## Shared frameless Setup layout (2026-09-10)

The user selected the attentional-blink Design screen as the visual reference for
every Setup step and requested removal of the bottom divider. All nine steps now
share its left-aligned task heading, step count, transparent shell, progress position,
and vertical content budget at 1120x820. Project, Timing, Size, Session, and Review
outer settings cards are flattened; content is top-aligned with bounded form widths.
Navigation, validation, draft application, and scientific settings stay unchanged.
This replaces the older eight-step/1120x720 layout guidance below.

Acceptance covers both themes and all nine steps for oddball and native AB projects,
including fixation enabled/disabled, header/footer geometry, and navigation behavior.
Visible checks use the user's existing authorization; no runtime is launched.

Verification: the final six all-step light/dark layout cases pass for native AB
(fixation on/off) and oddball, including shared left-edge alignment. The shell suite
(17 checks), Timing/Size/Session suite (9), and isolated legacy Design Next/apply
check pass. GUI/docs focused checks and mypy pass; the repo precommit run passed
1306 unit tests with five Windows symlink skips. A combined Qt batch timed out during
palette refresh and a legacy multi-size batch exited during Qt teardown; focused
layout runs and visible captures were therefore isolated. This is not a claim that
the complete combined Qt suite passed. Captures cover all nine steps in both themes
at 1120x820. Manual review: open Setup, traverse the stepper, and check the frameless
background, aligned heading/form, and bottom navigation without a divider.

## Implementation Approval (2026-09-05)

The user approved implementing the concept on this branch and explicitly allows
additional steps to give controls more space. This replaces the original six-step
constraint. The implementation uses Project, Conditions, Timing, Image Size,
Session, Fixation, Response, and Review, retaining `1120x720` as the design minimum.
Timing keeps the existing `experiment` navigation key for compatibility. Image Size
and Session get their own pages using the existing document-backed editors.

Implementation includes shared theme/control states, Conditions scope and source
details, display verification wording, useful Review summaries and edit navigation,
non-blocking save feedback, and supporting dialog consistency. Scientific behavior,
save semantics, and first-time validation gates remain intact. Registered Qt tests
will be updated; visible acceptance is deferred to the user's manual review.

## Recommendation

Refine Setup into an eight-step workflow around clearer decisions, consistent
controls, and trustworthy feedback. Keep the compact Windows desktop shape and
extend the shared visual language through every app-owned supporting dialog.

The recommended direction is restrained: neutral surfaces, a small blue/cyan accent
area, clear typography, consistent spacing, and explicit interaction states. The
scientific settings must remain readable and discoverable. A modern appearance should
make an experiment easier to configure and verify.

Review date: 2026-09-05. Baseline: `ce63afe` (1.4.1 source).
Review branch: `codex/setup-ux-design-review`.
The baseline findings below retain the rationale for this implementation. The
implementation record and pending acceptance checks describe the current branch.

## Evidence And Limits

The review inspected the current workflow documentation, wizard shell, shared
components/theme tokens, condition and runtime editors, Review logic, and a sample of
supporting dialogs. Parallel reviews covered workflow and visual consistency.
The supplied Settings screenshot is the only live application image used here.
No Qt application or Qt tests were launched. Consequently, source-supported findings
below are not claims of observed clipping or measured user difficulty.

Expected usability benefits are design hypotheses. Validate them with visible Windows
walkthroughs and task observation before calling the redesign successful. The concept
shown with this review uses sample content and illustrates Conditions/Experiment;
it omits some controls and does not demonstrate that the complete PySide6 screens fit.

## Preserve

- Project, Conditions, Timing, Image Size, Session, Fixation, Response, Review form
  the eight guided steps. Existing document-backed editors keep their ownership.
- First-time setup keeps sequential validation gates. Ready-project Edit Setup keeps
  its existing clickable stepper; direct navigation is already implemented.
- Home stays the daily launch surface. No new permanent application sidebar is needed.
- All eight complete steps must fit at `1120x720`, with no required page scrolling or
  hidden controls. Retain the stable stepper and bottom navigation positions.
- Preserve explicit saving, confirmation before abandoning unsaved changes, staged
  task edits, normalization consent, and background workers.
- Core validation remains authoritative. Timing, display verification, contrast-mode
  constraints, trigger semantics, exports, and project formats stay unchanged.
- The app already has light/dark tokens, button roles, status labels, and substantial
  layout coverage. Extend these owners instead of introducing a second theme system.

## Prioritized Proposals

Priority 1 items should be the first implementation slice. Priority 2 items follow
after the common components and feedback patterns have been validated.

### 1. Make validation readable and actionable — Priority 1

**Observed:** `validation_text_stylesheet()` in
[`components.py`](../../../src/fpvs_studio/gui/components.py) uses fixed `#a1332b`,
although `StudioTheme` already supplies a dark-mode error foreground. Calculated
against the current dark page and elevated surface tokens, that fixed red provides
approximately 2.32:1 and 1.80:1 contrast respectively. Those are token calculations;
the actual rendered backgrounds still require inspection. General theme contrast
tests do not cover this error helper.

**Change:** Resolve error text through the shared semantic theme, test the actual
foreground/background combinations, and pair error color with readable explanation.
For setup blockers, show the message beside the responsible field/source and retain
one compact navigation hint. When possible, provide a focused correction action.

**Why:** A user should be able to identify the problem and find its control without
scanning an entire step. WCAG's error-identification guidance calls for textual
identification; use its contrast criteria as design targets for this desktop app,
not as a claim of full WCAG conformance.
[Error identification](https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html),
[contrast minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).

**Concrete example:** An incomplete word condition currently reaches the generic
"Assign base and oddball folders" footer in `_current_step_blocker()` in
[`setup_wizard_page.py`](../../../src/fpvs_studio/gui/setup_wizard_page.py).
Use "Add oddball words to Faces" for a word-list gap, or "Choose an oddball image
folder for Faces" for an image gap. Use the actual condition name and missing role.

**Tradeoff and acceptance:** Reserve message space so error states do not grow beyond
the compact layout. Do not validate every intermediate keystroke as a failure. Test
image/word, missing name, trigger, and multi-condition blockers plus keyboard focus.

### 2. Separate experiment-wide and selected-condition settings — Priority 1

**Observed:** Conditions mixes selected-condition fields with project-wide Target
Stimulus Repeats (`condition_setup_step.py`, construction and `_update_target_repeats`).
Project also holds the default image-timing template, while Conditions has a
per-condition presentation-mode selector and a separate Presentation dialog.

**Change:** Keep the useful list/editor split. Give the condition editor a clear
selected-condition heading, place its presentation mode next to stimulus sources,
and visibly separate a small "All conditions" area for project-wide repeat targets.
Use consistent scope names: "Default for new conditions", "This condition", and
"All conditions". Differentiate "Presentation mode" from "Size, position and transforms".

**Why:** Grouping by scope makes the impact of an edit predictable. It also reduces
the chance that a global value is mistaken for a per-condition override.

**Tradeoff and acceptance:** Scope labels consume space. Replace redundant headings
instead of adding another nested card. Keep the existing template apply-to-all
confirmation and inheritance/reset behavior. Verify that changing the current
condition never visually suggests a project-wide setting has become local.

### 3. Give Experiment a clear order of decisions — Priority 1

**Observed:** Experiment combines display refresh, protocol timing, background,
calibration, presentation defaults, and session repetition in one compact card.
Display verification already has waiting, busy, warning, error, and verified states in
[`runtime_settings_page.py`](../../../src/fpvs_studio/gui/runtime_settings_page.py).
The action is labeled "Detect My Refresh Rate", but it performs a fullscreen PsychoPy
stability check as well as reading the configured mode.

**Change:** Separate Timing and display verification, Image Size, and Session into
three focused pages using the existing editors. Use a concise "Verify display" action and explain before
activation that it briefly opens a fullscreen check. Show requested and realized rates
in aligned labeled rows; keep frame counts available without burying warnings.
Show the Neutral Gray requirement immediately beside Contrast Modulation selection,
with an explicit route to the Timing background control.

**Why:** This groups related decisions and makes a mandatory hardware check easier to
understand. The existing asynchronous verification remains the source of truth.

**Tradeoff and acceptance:** This is a layout/copy change, not permission to bypass
verification or silently change the background. Preserve 59.94 Hz approximation,
VRR rejection, stale-verification invalidation, and requested/realized distinctions.
Keep the first-time step gate intact when directing users toward a later setting.

### 4. Turn Review into a useful last check — Priority 1

**Observed:** Review builds every summary row with a check icon and mostly summarizes
condition count/modes, display, session, and a generic fixation-configured line.
Response key/window, accuracy setting, participant tutorial, and pre/post task flow are
not represented in `_review_checklist_sections()`.

**Change:** Use concise, factual summary rows with visible Edit links in the existing
ready-project editing mode. Include the response key/window, accuracy on/off, tutorial
on/off, and a compact task-flow summary. Distinguish "Configured" from live hardware
verification. Show a success check only when backed by the relevant validation result.
Keep one clear Save and Return Home action.

**Why:** The last step should help someone catch a meaningful configuration mistake,
not merely restate that earlier pages exist. A check icon should communicate verified
state rather than decorate every line.

**Tradeoff and acceptance:** Avoid an exhaustive report at this size. Use compact
summaries and existing detail surfaces; keep long names accessible. Do not let an Edit
shortcut bypass first-time setup rules. Test invalidated settings after revisiting a
step, task presence, word/image combinations, and all enabled/disabled response states.

### 5. Reduce routine interruptions and clarify saving — Priority 2

**Observed:** `_show_first_condition_prompt_if_needed()` opens an informational modal
after the first condition is added. `_save_from_review()` opens another after a
successful save. Review offers "Return Home Without Saving", while `_return_home()`
explains that edits remain in the current application state.

**Change:** Replace the first-condition reminder with short contextual guidance near
the list. On successful save, return Home and show one non-blocking confirmation.
Clarify the distinction between changes retained in memory and changes saved to disk
in the existing leave-setup confirmation. Do not relabel that action as "Discard"
unless the implementation actually discards edits.

**Why:** Routine success does not need another acknowledgement click. Clear save
semantics reduce uncertainty when leaving the wizard.

**Tradeoff and acceptance:** Preserve confirmations for actual data loss, destructive
actions, and normalization. Retain existing save-failure handling. Accessible status
announcements and keyboard focus must work after returning Home; no new autosave
behavior is proposed.

### 6. Use the same visual grammar in every app-owned surface — Priority 1

**Observed:** The shared component system is extensive, but sampled dialogs are not
uniformly assembled. Settings uses a plain form, Presentation uses group boxes and
tabs with shared theme application, and the task editor has its own dense structure.
Different construction does not prove a visual defect, but it identifies where a
shared-theme walkthrough is needed.

**Change:** Define and reuse common dialog header, form row, field help, action footer,
empty state, progress state, and error state patterns through `gui.components`.
Apply the same type scale, spacing, radii, button emphasis, and focus treatment to
Setup and its supporting dialogs. Preserve native file pickers and standard Windows
window controls.

Complete the form-control vocabulary as well: buttons and cards currently have more
explicit shared styling than line edits, combo boxes, spin boxes, tabs, and group boxes.
Inspect their native appearance before adding shared treatments. Keep recognizable
dropdown/spinner affordances and keyboard behavior. Preserve Settings' immediate
preference persistence versus the staged Apply/Cancel behavior in task/presentation
dialogs; a common shell must not imply common save semantics.

**Why:** A coherent theme depends on repeated details and states, including failure
and cancellation. Fluent recommends semantic color tokens, restrained brand accents,
and hierarchy built from neutral surfaces.
[Fluent color guidance](https://fluent2.microsoft.design/color).

**Tradeoff and acceptance:** Do not flatten a complex task editor into a large generic
form. Reuse its structure while normalizing controls and actions. Check each surface
in light and dark themes, focused/unfocused windows, keyboard navigation, and error
states. Keep established semantic colors instead of applying cyan to every border.

### 7. Make dense settings explain their effective values — Priority 2

**Observed:** Fixation count limits depend on condition duration. The editor exposes
range/cap guidance while its usable spin-box maximum may be the minimum allowed
across all conditions (`fixation_settings_page.py`, target-count limit and refresh paths).

**Change:** Show the effective maximum and, where useful, the limiting condition.
When a timing edit causes an automatic count adjustment, explain the resulting value
without changing the cap or scoring rules. Keep Fixation and Response separate, but
use consistent layout and a small shared reminder of their relationship.

**Why:** Explanations should match what the control actually accepts. This makes
timing-dependent constraints easier to reason about without exposing compiler internals.

**Tradeoff and acceptance:** Essential bounds must remain visible. Longer scientific
explanations can use an existing help surface. Test unequal condition durations,
one condition, and enabled/disabled accuracy states with realistic long names.

### 8. Make selected image sources inspectable — Priority 2

**Observed:** The guided source cards intentionally hide folder paths and emphasize
count/resolution (`condition_setup_step.py`, `show_folder_path=False`, and
`SetupSourceCard` in `components.py`). Two different folders can share those metrics.

**Change:** Provide a compact, keyboard-accessible Source details action with the full
path and Copy path. Consider a cached representative thumbnail only after this smaller
improvement is accepted. Keep long filesystem paths out of the main form.

**Why:** Researchers can confirm which set they selected without reopening the picker.
This complements the existing Base/Oddball grouping and adds confidence to authoring.

**Tradeoff and acceptance:** Do not create new image-loading work on the UI thread.
Test long Windows paths, missing files, focus return, and full-value retrieval. Keep
repeat-balance guidance advisory; if its summary is later surfaced beside source
metrics, update the tests that currently expect those inline summaries to be hidden.

## Source Locations For Implementation

Line numbers refer to the reviewed baseline and will move during implementation.

| Finding | Owner and starting lines |
| --- | --- |
| Fixed error foreground | `components.py:804`, `:1726`; `design_system.py:187`; `tests/gui/test_components.py:162` |
| Global repeat target in local form | `condition_setup_step.py:480`, `:985`; per-condition mode update at `:994` |
| Folder wording for words | `setup_wizard_page.py:1189`; existing modality-aware status in `condition_setup_step.py:686` |
| Review checks and summaries | `setup_wizard_page.py:1051`, `:1063`, `:1142`; existing expectations in `tests/gui/test_setup_review.py:81` |
| Routine information dialogs | `setup_wizard_page.py:664`, `:881` |
| Supporting dialog construction | `settings_dialog.py:65`; `presentation_settings_dialog.py:936`; `condition_task_dialog.py:2856` |
| Effective fixation limits | `fixation_settings_page.py:807`, `:825`, `:853` |
| Hidden source path | `condition_setup_step.py:495`, `:843`; `components.py:589` |
| Baseline geometry and navigation | `tests/gui/test_setup_wizard_shell.py:202`, `:523`, `:538` |

Unqualified Python paths in this table are under `src/fpvs_studio/gui/`.

## Visual Specification To Explore

These are proposed design values, not validated replacement tokens:

| Element | Direction | Reason |
| --- | --- | --- |
| Surfaces | A neutral window background, one primary work surface, subtle raised controls | Makes the editor readable without competing frames |
| Accent | Existing blue/cyan family for the primary action and current selection | Preserves identity and directs attention |
| Typography | Segoe UI/system UI; keep the existing 13 px control, 16 px section and 24 px page scale as the baseline | Avoids introducing an unrelated font or shrinking dense labels |
| Spacing | Shared 4/8/12/16/24 logical-pixel rhythm; about 10 px surface radius | Predictable alignment while preserving the existing compact geometry |
| Actions | One strong primary action per decision area; quiet secondary actions; explicit destructive labels | Makes the next decision easy to identify |
| States | Neutral pending, readable warning/error, verified success; text plus color | Communicates status to users who cannot distinguish the colors |
| Motion | At most brief state transitions respecting reduced motion; no decorative loops | Keeps attention on experiment authoring |

Use Fluent's hierarchy and focus guidance as design reference while implementing
native PySide6 behavior. This does not propose a move to WinUI, React, or a browser.
[Fluent accessibility](https://fluent2.microsoft.design/accessibility).

## App-Wide Rollout Map

The review sampled supporting dialogs; the following list is the implementation
coverage inventory, not a claim that every surface has been visually audited:

1. Shared components and all eight Setup steps, including field errors and busy states.
2. Settings/root setup, condition templates, presentation overrides, pre/post tasks,
   normalization, and control-condition creation.
3. Welcome/Home and project management; import/export progress and result surfaces.
4. Image Resizer, fixation accuracy/results, and update check/download/cancel/error states.

Use screenshots of each existing state before changing it, then compare against the
same component rules. Native operating-system dialogs should remain recognizable.

## Delivery Sequence And Acceptance

1. **Shared states and copy:** correct theme-aware validation text, modality-aware
   blocker language, and scope labels. Add focused behavior/contrast coverage.
2. **Setup composition:** refine Conditions and split Timing, Image Size, and Session within the existing
   shell; preserve every currently available control and sequential validation.
3. **Review and completion:** improve summary content, save feedback, and precise
   confirmation wording. No changes to save ownership or persistence.
4. **Supporting surfaces:** apply the same patterns using the rollout inventory.

During implementation, extend the registered tests starting with
`tests/gui/test_components.py`, `test_setup_wizard_shell.py`, `test_setup_conditions.py`,
and the corresponding display/response/dialog tests. Cover actual visible states and
keyboard recovery rather than assertions that merely repeat the implementation.

Visible/manual acceptance must cover every complete step at `1120x720`, light/dark
themes, 100/125/150% Windows scaling where the desktop permits that logical size,
long names/paths, maximum realistic validation text, image/word conditions, and
busy/failure/cancel states. Maintain full-value access for intentional path elision.
Do not certify layout fit from the HTML concept or source inspection alone.

Observe a new user creating a two-condition experiment, an experienced user changing
one presentation setting, and a user recovering from missing stimuli/unverified
display. Record completion, wrong-scope edits, backtracking, and assistance requests.
Compare before/after; no percentage improvement is claimed without those observations.

## Implementation Record

The category overhaul adds a dedicated Design step, making the current workflow nine
steps. Image-source authoring moves from Conditions to Design. Current ownership and
acceptance are documented in [Experiment categories](../../EXPERIMENT_CATEGORIES.md);
the earlier eight-step observations below describe the reviewed baseline.

- Shared theme-aware validation and form controls now cover app-owned themed surfaces;
  added reusable dialog headers for Settings, Presentation, and Pre/Post Tasks.
- Conditions separates global repeat targets from selected-condition fields and exposes
  stored image-source paths with copy. Image/word-specific blockers have a `Show field`
  action. Routine first-condition informational dialogs were removed.
- Timing, Image Size, and Session use separate cards/pages. Verification has a visible
  fullscreen notice and keeps the existing worker and validation gate.
- Review summarizes response/accuracy, tutorial, and task bindings, with ready-project
  Edit shortcuts. Save uses the existing nonmodal confirmation; leave-setup copy explains
  in-memory versus disk state.
- Fixation shows the effective smallest limit and limiting condition. Corrected an
  existing widget-clamp synchronization defect so automatic count changes reach the
  document; scientific cap policy and fixation enablement remain unchanged.
- Settings groups preferences at `700x520` packaged / `700x610` source minimum/default.
  Presentation keeps its `900x600` minimum with compact preview selectors and a flexible
  preview. Apply/Cancel and immediate Settings persistence remain distinct.
- Added/updated registered Qt coverage for eight-step navigation, minimum geometry,
  source details, missing-field recovery, summaries/save behavior, and fixation limits.

## Verification And Pending Acceptance

### User Screenshot Follow-Up

The user's visible review identified overlapping Conditions status labels and clipped
participant instructions. Compatibility labels that are not part of a layout must
remain hidden; the condition form must reserve enough height for its instructions.
Trigger Code and Stimulus Type now share a row, ordinary presentation-mode guidance
is omitted, and the image/word source rows share a compact height. The Neutral Gray
requirement remains visible for contrast modulation, and instructions retain an
80-pixel editor with the complete text available through its normal scrolling.
The user also requested Review's completion actions in the shared bottom navigation,
outside the summary frame, and authorized committing and pushing the branch after the
fix. Return Home Without Saving replaces the left Return Home action on Review;
Back and Save and Return Home occupy the right side. Existing save/confirmation
callbacks and first-time navigation gates remain intact.

Registered coverage checks Conditions label visibility, wrapped text height and
instruction bounds with multiple conditions, plus Review footer placement and switching
between Review and Response at the compact/default sizes. Visible acceptance should
repeat the supplied Conditions case and check Review's footer in both themes.

### Check Results

- GUI focused lint and changed-file compilation pass. No Qt tests or app windows have
  been launched by the agent; manual fit is not established by source inspection.
- Final repo precommit passed: Ruff/compilation, mypy (137 source files), repository
  audits, docs hygiene, and 966 non-Qt tests. Five Windows symlink tests were skipped
  because this account lacks symlink privileges. Docs focused also passed its nine
  harness-documentation tests; `git diff --check` is clean.
- The branch is ready for the user's visible review. Keep this plan active until all
  eight steps and supporting dialogs pass manual acceptance.
- Follow the [visible smoke path](../../GUI_WORKFLOW.md#setup-design-and-manual-acceptance).
  Record clipping, focus, readability, and workflow feedback before deciding on merge.
- This slice applies the common control vocabulary throughout themed surfaces and
  restructures the sampled setup/support dialogs. A full state-by-state visual audit
  of every utility, updater, and import/export surface remains pending; no app-wide
  visual acceptance or measured usability improvement is claimed.
- Do not change project-description requirements, add autosave, or alter scientific
  contracts as part of this design review. The unrelated updater acceptance plan stays
  untouched.

## ISI designer extension (2026-09-09)

The user approved a taller Setup default for separate Base/T1/T2/ISI source controls.
Current Setup acceptance is 1120x820, with an unframed Design page and image/blank
ISI choice. See `../completed/attentional-blink-isi-sources.md`. Earlier 1120x720
measurements above describe the preceding layout.

Designer clarity follow-up: source order is Base, T1, ISI, T2; redundant source,
cycle and timing frames are removed. Typed cadence/duration fields have no step
arrows, and calculated T2 is plain text. The 68 registered designer checks pass,
including entry/commit behavior, source order, both categories and both themes.

## Designer Mockup Parity (2026-09-09)

The user approved implementing the generated dark desktop mockup. This slice keeps
the current timing, source-import and persistence owners. Setup > Design gets a
task-specific header, visible source names and Blank screen/Image controls, a
schematic target-pair overview connected to its proportional timing detail, and
aligned numeric controls. Next remains the single primary action and applies the
draft through the existing navigation gate; standalone editing retains Apply.

1. Refine the shared source/timeline widgets and embedded layout; verify readable
   T1 thumbnails, exact expanded proportions, source hit targets and keyboard entry.
2. Integrate the Design-only header and footer hint; verify Next applies valid
   drafts, invalid drafts stay on Design, and other wizard steps retain their shell.
3. Run focused checks and approved visible Qt coverage in both themes at 1120x820
   and the larger mockup size. Compare rendered screenshots with the mockup and
   record any remaining limitations. Run precommit for shared component changes.

Completed this slice: the shared designer now shows named sources and visible ISI
choices, a readable schematic pair, its labeled proportional detail and automatic
T2 explanation. Setup uses Design your sequence, a single Next action and anchored
navigation. The workspace fills larger windows while retaining a bounded layout.

Verification: 103 registered GUI checks passed across designer, Design integration,
wizard shell and components (101 on the combined run, then two successful focused
reruns after updating the wider Design expectation and a transient Windows clipboard
lock). The safe suite passed 1205 tests with five unavailable-symlink skips. GUI and
docs focused checks pass. Precommit reaches the pre-existing controller.py:373
object-to-str return type error; no new mypy errors were reported.

Visible screenshots cover 1120x820 and 1448x1086, image/blank ISI, a 15/50/185 ms
target pair, both themes and actual project thumbnails. The reviewed project.json
hash was unchanged. Timing inputs and the ruler do not overlap; Next applies a
valid draft without saving it to disk and invalid timing remains editable.

Implementation files: gui/experiment_designer_dialog.py,
gui/experiment_designer_widgets.py, gui/design_setup_step.py,
gui/setup_wizard_page.py and gui/components.py under src/fpvs_studio; registered
coverage is in test_experiment_designer.py, test_design_setup_step.py and
test_setup_wizard_shell.py under tests/gui. The canonical workflow is in
VISUAL_EXPERIMENT_DESIGNER.md and GUI_WORKFLOW.md, with ownership and verification
pointers updated in ARCHITECTURE.md and docs/agent/agent-index.md.

## New-experiment dialog clarity (2026-09-10)

The creation details page now uses the shared DialogHeader and vertical field groups
for name, template and save location. The selected template description is visible,
and an editable full-path field with tooltip is paired with a live new-folder name
hint. Back is separated from Create/Cancel, and keyboard navigation follows the
visible field order. The category-first choice and backend creation contracts remain
unchanged. Minimum/default sizes are 760x500 and 800x500.

Registered coverage in test_create_project_dialog.py exercises both sizes and themes,
long content, full-value access, summary updates, keyboard order and cancellation.
The manual smoke path is File > New Experiment, choose either available category,
then inspect details, change the template and folder, and use Back/Cancel. Check the
rendered description and destination hint before creating a new project.

Verification for this slice: 19 selected visible GUI checks pass, along with GUI
and docs focused verification, nine harness-documentation tests, and mypy for the
changed dialog module. Rendered dark/light captures at both sizes show unclipped
fields and actions. No PsychoPy playback or hardware triggers were used.

## Participant-task editor pages (2026-09-10)

The user requested no scrolling through the modular task dialog, no clipping and
clearer visual hierarchy. This slice replaces the long nested form in
`gui/condition_task_dialog.py` with focused pages within the existing dialog, budgeted
for 1100x720 minimum and 1120x760 default. Module selection stays on the left and the
participant preview on the right. Module settings and ordered steps occupy their own
page; step content, text/layout, responses and choice behavior have separate pages.
Questionnaire editing separates the question, answer options and routing rules.
Empty phases replace disabled editor forms with a short instruction.

The GUI retains draft objects, stable IDs, all task types, media staging, Apply/Cancel,
and existing core validation. Core models, runtime and export contracts are outside
this slice. Lists, tables and text editors retain data navigation for variable-length
content; no whole-form scroll area remains. Existing registered task-dialog tests
cover every task/question type, both sizes/themes, empty and validation states,
page traversal before lossless Apply, cancellation and staged asset import.

Verification: all 16 registered task-dialog checks pass, including the all-type
layout matrix. GUI/docs focused checks and dialog-module mypy pass. Visible captures
cover empty, question, answers and module-settings pages at both sizes in dark/light
themes with a main-window parent. The repo precommit gate still stops at the existing
`gui/controller.py:373` object-to-str return type error. No runtime or hardware check
was needed for this GUI-only change.

## Randomized digit illustration (2026-09-10)

The user requested random digit order after the timeline misleadingly showed the
typed pool in order. Playback already sampled digits randomly. The designer now
uses the same core cycle sampler, labels the pool's random-order behavior, and
offers Shuffle example without changing project state or the run seed. Slowed
preview cycles draw new symbols while preserving target positions and avoiding
adjacent repeated digits across cycle boundaries. The sampler was extracted from
the compiler with exact seeded output preserved; no persisted setting was added.

Verification covers golden pre/post-extraction sequences for all three default SOAs,
custom unsorted/two-digit pools, repeat prevention, unchanged preview-only drafts,
and default-size light/dark GUI layouts. Playback and timing remain compiled through
the existing RunSpec contract.

Results: 17 visible designer tests and 190 compiler-scope tests pass, with the
compiler run using `PYTEST_ADDOPTS=--basetemp=build/ab-cmp-qa` to avoid Windows test
staging path limits. GUI/docs focused checks and changed-module mypy pass; light/dark
captures fit the 1120x820 wizard. Precommit still stops at the existing
`gui/controller.py:373` return-type error. No hardware or PsychoPy session was launched.

## Visual target color selection (2026-09-10)

The user requested a visual hex editor using the FPVS Toolbox SNR Tool as reference.
The native AB designer now uses shared `components.ColorPickerButton` controls for
T1/T2: a color swatch beside the hex value opens Qt's visual color picker, with exact
hex entry available. The Qt picker is used consistently to retain hex entry on Windows.
Only accepted opaque colors update the timeline draft; Cancel leaves it untouched,
and Next applies the existing shared condition settings. No schema, timing or runtime
contract changes are involved. Source fields retain aligned tops at 1120x820.

All 19 visible designer checks pass, including both colors, keyboard activation,
Cancel, draft-only updates, all-condition save/reopen, and light/dark layouts at the
documented sizes. Manual captures inspect the picker and full wizard in both themes,
including real hex entry and confirmation. Changed-module mypy passes; precommit
still stops at the existing `gui/controller.py:373` return-type error. The manual
smoke path is Setup > Design > either target's color swatch; choose a color or type
its hex value, confirm, then use Next. No PsychoPy session or hardware was launched.

## SOA table cleanup (2026-09-10)

Removed the native AB designer's display-timing column at the user's request.
Condition names, SOA entries and between-target digit counts form a three-column
table. SOA fields have a centered, inset cell layout; table padding no longer clips
the entries. The sequence summary and accessible description use “0 digits between
T1 and T2” wording. Actual display checks remain in Timing and compilation.
Registered designer coverage checks the three columns, summary wording and field
containment/vertical alignment in both themes at the documented wizard sizes.
All 19 visible designer checks pass. Both 1120x820 captures show the fields fully
inside their rows without scrolling. GUI/docs focused verification and changed-module
type checking pass; the existing controller return-type error still blocks precommit.


## Frameless Setup hierarchy refinement (2026-09-10, complete)

Keep the accepted frameless shell. Center bounded forms horizontally while leaving
wide Conditions/Design workspaces available. Remove duplicate page headings and
non-actionable study recaps. Stack Project/Timing field labels with their controls;
align the denser forms consistently. Keep current-step errors and verification status
visible, with optional technical detail on the relevant control's tooltip. Conditions
retains participant instructions and task editing; Design owns stream/SOA explanations.

Acceptance: all nine steps at 1120x820, both themes, current validation states and
supported categories; registered visible Qt checks plus GUI-focused/precommit checks.
No experiment, timing, persistence or hardware behavior changes are intended.

Implemented centered forms, shared field-label alignment, single task headings, and
short verification states. Removed the Timing stream recap and duplicate Conditions
guidance; optional technical detail lives in tooltips. Native AB Review now describes
digits/target letters and character height instead of image presentation geometry.

Verified all nine native AB steps at 1120x820 in light/dark themes with fixation both
enabled and disabled (4 cases), plus both oddball layout cases. Project's 11 checks,
Timing's 11 checks, native Conditions and Session checks pass; Timing's retained
monitor-detail assertions now check tooltips. Earlier combined GUI batches stalled,
so those results were discarded and the relevant modules/cases rerun independently.
GUI-focused Ruff/compilation and changed-module mypy pass. Precommit checks passed,
including mypy over 150 sources and 1244 non-Qt tests (5 Windows symlink skips); its
changed-file input was filtered in-process to exclude the previously deleted legacy
AB compiler because the existing driver still passes deleted paths to Ruff.
The final Review-only copy change was then covered by the layout matrix, focused
checks and mypy. The harness itself was not changed.

Visible captures of all nine steps are retained in
`build/setup-hierarchy-review/accepted-dark/` and `accepted-light/`. Verification used
temporary projects and fake display checks; no participant experiment or hardware
trigger was launched. Manual path: open Setup, inspect Project/Conditions/Timing,
then the remaining steps; verify labels, field spacing and bottom navigation in both
themes, and hover Timing controls to inspect optional technical details.

## Combined Timing and Session, centered content (2026-09-10, complete)

Combine Display and Session in one frameless two-column step. Keep the `experiment`
navigation key and route existing `session` links to it. The wizard now has eight
steps; Image/Character Size remains separate. Vertically center each step's natural
content between the fixed progress indicator and footer, with no required scrolling
at 1120x820. Preserve model bindings and display verification gates. Verify all eight
steps in both themes/categories, navigation and Review links, combined-page validation,
and repeat-count persistence using registered visible Qt tests and screenshots.

Implemented in `gui/setup_wizard_page.py` using the existing editors and shared
surface. Display and Session keep their internal field groups; all step content uses
equal flexible space above/below its natural height. Headers, progress and navigation
stay fixed. Updated step counts, navigation tests, Review's Session destination, and
current architecture/GUI guidance. The existing session model and runtime are unchanged.

All 22 focused visible Qt checks pass: the eight-step native AB matrix with fixation
on/off in both themes (4), oddball layout matrix (2), combined-page validation (11),
stepper navigation (2), forward/back flow and Review editing (3). Screenshots of all
eight pages are retained in `build/combined-setup-review/dark/` and `light/` and were
inspected at 1120x820. No real participant experiment or display probe was launched.
GUI/docs focused checks, Ruff, compilation and mypy pass. Precommit's deleted-file
input workaround remains the same as the preceding slice; no harness code changed.

The first non-Qt run had 1243 passes and one bundle-import failure: the chosen test
directory produced 261-character oddball paths. The unchanged test passed with a
shorter temporary path, and the complete non-Qt suite then passed (1244 passes,
5 Windows symlink-permission skips). Bundle path handling was not changed in this
GUI task. Logs: `build/combined-setup-precommit.txt` and
`build/combined-setup-unit-final.txt`. Temporary test projects/helpers were removed;
the screenshots and logs remain.

## Two-page polish only (2026-09-10, complete)

Scope is limited to Timing & Session and native AB Conditions. In the combined
page, both editor groups use stacked labels and 240 px primary inputs. The active
Timing & Session caption retains its accent color with normal label weight so it
fits without elision. In AB Conditions, remove the enclosing detail card, stack
field labels, constrain the trigger field, keep task actions beside their summary,
and use a full-width Add action above aligned Duplicate/Remove actions. Preserve
participant text, settings, centered layout and all other Setup surfaces.

Registered coverage checks both themes, combined-page validation and input widths,
the complete step label, native condition actions and bounds. Screenshots are in
`build/two-page-review/dark/` and `light/`. Temporary screenshot projects are isolated.

Eight focused visible GUI cases pass, including the existing AB layout matrix to
check that other pages retain their geometry. Both requested pages were inspected
in both themes at 1120x820. GUI-focused Ruff/compilation and precommit checks pass
(1244 non-Qt passes, 5 Windows symlink-permission skips). Precommit used the same
deleted-file input filtering noted above and a short temporary directory; no harness
or runtime changes. Temporary projects/helpers were removed; screenshots and
`build/two-page-precommit.txt` are retained.
