# Condition Order Preview and Saved Arrangements

Status: Planned

## Purpose and confirmed decisions

The user added this feature while the three-seed plan was in verification and
explicitly requested both generated pseudorandom orders and manual reordering.
They also asked to prioritize simplicity in the GUI. Execute this plan after the
seed plan is verified/committed/pushed, before the post-condition questions plan.

In Timing & Session, expose one **Condition order...** action. Its compact editor
shows each requested presentation in a plain ordered list, with **Generate**,
**Move up**, **Move down** and **Save** actions. Standard drag/drop may supplement
accessible move buttons if it stays simple. Keep numerical seed details optional.
Do not add a top-level page, extra reuse switches or a second timing table.

Saving a chosen order selects the existing overall **Same for every participant**
mode, preserving the other configured stimulus/fixation roots. A concise decision
line makes that effect clear before Save. The exact chosen list is reused across
participants, whether generated or manually arranged. New-for-each-participant mode
uses fresh seeded ordering; a retained saved list is inactive in that mode.

## Source and boundaries

- `core/session_ordering.py` owns exact counts, no-adjacent feasibility and generated
  order. `core/randomization.py` owns roots and fixed/new behavior.
- `core/compiler.py` owns SessionPlan ordering; runtime plays the compiled entries.
- GUI timing/count drafts live in `condition_timing_table.py`; seed controls live in
  `randomization_editor.py`; project updates remain atomic through the document.
- Global order is project/session state, not a condition template default or RunSpec
  responsibility. Persist only stable condition IDs in the selected list, including
  repeated occurrences; no participant/run IDs or independent occurrence UUIDs.

## Implementation sequence

1. Add an optional saved condition-order list to the canonical session model and
   compatible config/bundle serialization with narrow capability versions. Omit it
   when absent; preserve historical sources/compiled plans and no-rewrite loading.
2. Centralize validation of known IDs, exact requested multiplicities and no adjacent
   duplicate IDs. Do not silently insert/drop presentations, repair an edited list,
   change counts or reshuffle a saved choice.
3. Compile the saved list when active in overall fixed mode. Otherwise use the
   existing seeded constrained generator. Record the actual ordering policy in the
   compiled SessionPlan and protocol identity; keep run namespaces based on stable
   condition ID and chronological within-condition presentation number.
4. Add the small order editor. Preview generation uses core logic, without requiring
   stimulus decoding or a physical display. Generated candidates may repeat when
   constraints permit only one outcome. Manual moves update visible chronological
   occurrence labels and validate before Save. Invalid drafts remain editable.
5. Integrate pending count/timing changes and order changes atomically. A changed
   count may invalidate a saved list; offer an in-editor way to create a matching
   order rather than leaving a dead end. Validate frequency confirmations and all
   combined drafts before committing. Never apply part of a rejected draft.
6. Tuck seed numbers under optional **Seed details**, preserving explicit editing.
   Keep the overall fixed/new choice visible. Reject stale dialog/worker results if
   current condition/count settings changed during generation.
7. Preserve native AB and specialized masking workflows. Keep their existing
   grouping controls and explain unsupported order overrides before mutation.

## GUI acceptance

- Default screen remains compact: one order action plus the existing overall reuse
  choice. No algorithm/version terminology in routine controls.
- Editor default 780x620, minimum 700x520, with an intentional scrollable order list,
  long-name tooltips, keyboard-accessible movement and a clear Save action.
- Setup still fits 1120x820 in both themes, including expanded Seed details and long
  validation text. Use existing components and registered geometry coverage.
- Save records the chosen arrangement and clearly switches to overall fixed reuse.
  Cancel changes no project values. Unknown IDs/count mismatches/adjacent duplicates
  never become an accepted project/compiled session.

## Verification

- A3/B2 previews ABABA; invalid manual AABAB is rejected. Use a nondegenerate pool
  to demonstrate both seeded alternatives and a valid manually chosen arrangement.
- Save/reopen/config/bundle and two-participant fixed runs retain the exact order.
- Count edits plus matching order updates commit together; invalid/stale drafts do
  not partially change counts, timing, seeds or order.
- Condition-occurrence stimulus/fixation schedules stay attached to chronological
  condition occurrence, independent of global position. Source changes, not
  participant IDs, determine reproducibility limits.
- New mode does not accidentally apply an inactive saved list. Protocol fingerprints
  include an active saved list and ignore an inactive one deliberately.
- Recovery replays original compiled order/identity; no recompile of frozen plans.
- Run core/compiler/runtime/GUI/project-I/O focused checks and repo precommit.
  Registered Qt coverage is maintained, but local Qt needs its existing explicit
  approved-visible environment. Report that limit without adding an approval gate.

## Scope limits

No independent per-domain reuse switches, order balancing beyond the approved
no-adjacent rule, extra repetitions, block design tools, task-order editor, condition
renaming or broad visual redesign. Post-condition question work remains its separate
next plan. Update current workflow/architecture/agent routes when this feature lands.
