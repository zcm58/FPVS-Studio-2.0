# Setup UX And Shared Visual Design Refinement

Status: Planned

## Recommendation

Refine the existing six-step Setup workflow around clearer decisions, consistent
controls, and trustworthy feedback. Keep the compact Windows desktop shape and
extend the shared visual language through every app-owned supporting dialog.

The recommended direction is restrained: neutral surfaces, a small blue/cyan accent
area, clear typography, consistent spacing, and explicit interaction states. The
scientific settings must remain readable and discoverable. A modern appearance should
make an experiment easier to configure and verify.

Review date: 2026-09-05. Baseline: `ce63afe` (1.4.1 source).
Review branch: `codex/setup-ux-design-review`.
This document proposes changes; no application behavior has been implemented.

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

- Project, Conditions, Experiment, Fixation, Response, Review remain the six steps.
- First-time setup keeps sequential validation gates. Ready-project Edit Setup keeps
  its existing clickable stepper; direct navigation is already implemented.
- Home stays the daily launch surface. No new permanent application sidebar is needed.
- All six complete steps must fit at `1120x720`, with no required page scrolling or
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

**Change:** Keep the step, but order its groups as Display and verification, Timing,
Image geometry, and Session. Use a concise "Verify display" action and explain before
activation that it briefly opens a fullscreen check. Show requested and realized rates
in aligned labeled rows; keep frame counts available without burying warnings.
Show the Neutral Gray requirement immediately beside Contrast Modulation selection,
with an explicit route to the Experiment background control.

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
| Six-step geometry and navigation | `tests/gui/test_setup_wizard_shell.py:202`, `:523`, `:538` |

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

1. Shared components and all six Setup steps, including field errors and busy states.
2. Settings/root setup, condition templates, presentation overrides, pre/post tasks,
   normalization, and control-condition creation.
3. Welcome/Home and project management; import/export progress and result surfaces.
4. Image Resizer, fixation accuracy/results, and update check/download/cancel/error states.

Use screenshots of each existing state before changing it, then compare against the
same component rules. Native operating-system dialogs should remain recognizable.

## Delivery Sequence And Acceptance

1. **Shared states and copy:** correct theme-aware validation text, modality-aware
   blocker language, and scope labels. Add focused behavior/contrast coverage.
2. **Setup composition:** refine Conditions and Experiment within the existing shell;
   preserve every currently available control and the six-step flow.
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

## Review Verification

- GUI focused baseline passed; the current route performed no Qt execution.
- This branch changes planning documentation only; application code remains unchanged.
- Docs focused verification passed: documentation hygiene and 9 harness-doc tests.
  `git diff --check` passed.
- Qt geometry, playback, and real Windows interaction checks remain unperformed.
- The active updater acceptance plan is unrelated and remains untouched.

## Decisions For Implementation

Recommended first scope: proposals 1, 2, 3, 4, and the shared foundations of 6.
Use the refined existing blue/cyan language in both current light/dark modes. Keep the
six steps and current settings requirements. A future request could separately consider
making project description optional or restructuring the Fixation/Response steps;
neither is necessary for this design refinement and neither is included here.
