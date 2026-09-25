# FPVS Condition Modifiers

Condition modifiers keep a participant activity's before/after screens, sustained
instruction, settings, and response rules together. Open **FPVS Condition Modifiers**
from Setup > Conditions. Ordinary modifiers retain the condition's Design and Timing
settings. Masking modifiers supply native visual pools and within-item windows while
retaining the FPVS item and oddball cadence.

## Authoring

The editor lists modifiers added to the selected condition and separates **Overview**, **Settings**, and
**Participant preview**. Overview describes the full workflow and recorded data.
Settings exposes the relevant counting, memory or masking controls. Preview uses example
numbers and does not reserve a session, consume its seed, or write participant data.

**Add modifier** opens **Built-in** and **My presets**. Built-ins include **Backward
counting**, **Remember four images**, and **Masking: Color, Faces, Number**. Add assigns the new modifier to the current
condition when it has no sustained activity. **Choose conditions…** explicitly changes
the assignment to other conditions;
one sustained activity or masking stream is supported per condition. Additional
ordinary instructions and questions remain available in the advanced task editor.
Existing custom tasks retain their original ordering, response rules, and media.
No imported protocol is inferred to be a generic memory task.

**Remove from condition** detaches the modifier only from the condition being edited.
Other conditions retain a shared modifier, its settings, and their task order and
binding options. The Apply button counts changed conditions, including removals.
Shared settings still affect all assigned conditions; **Make a copy for this condition**
creates an independent version before editing those settings.

Older standalone counting tasks remain unchanged on open and Apply. **Group existing
counting…** explicitly converts eligible linked counting tasks into a modifier,
preserving saved numbers, timing, and instructions. Its review explains the change
to baseline selection: the grouped baseline is requested only when a counting
condition is selected. Conversion remains a draft until Apply.

Edits stay in a detached draft until **Apply**. Image selections are staged outside
the project. Apply validates the complete draft and media before updating the live
document; the ordinary project Save lifecycle still applies. Cancel discards the
project draft and its staging files. Existing project images are never deleted by
removing or replacing a modifier.

## Masking

Masking variants add native visual source pools, exact target-to-mask SOA and
source-style before/after screens. Their stream windows compile into RunSpec,
independently of task clocks. **Setup > Conditions > Add Catch Condition** creates a
visible, once-per-variant condition sharing the selected ordinary condition's modifier
and tasks. Its ID, name and EEG marker belong to that condition. The modifier's
**Catch trials** tab preserves Studio 2.0.0 automatic extra sequences; those settings
do not create condition rows. Explicit and automatic catches cannot coexist within
a variant. The action explains when existing automatic settings must first be disabled,
without editing shared modifiers automatically.

Instruction steps expose positioned display items in the existing task editor. Text
items support left/center/right alignment within their width while retaining a center
X/Y anchor, independent item sizes/colors and a shared step font. The delivered
Masking 1.3.0 instruction redesign uses this contract; it does not rewrite built-in
factory instructions or other projects. See [Masking](MASKING.md) for authoring, variant grouping,
version requirements, migration corrections and physical acceptance limits.

## Backward counting

One modifier owns the optional timed session baseline, random-number start prompt,
silent counting instruction, and final-number response. Factory defaults are
subtract 13, a random starting integer from 1000 through 9999, and a 120-second
baseline. Existing saved values, including a 30-second baseline, are retained.

The compiler gathers baseline requests from selected counting conditions and runs
one compatible baseline before the first actual session entry, including when that
entry has no load. A test selecting only no-load conditions has no baseline request
from unselected modifiers. Legacy standalone baseline bindings retain their previous
occurrence behavior. Conflicting baseline settings or overlap with legacy baseline
bindings must be resolved explicitly.

The starting-number prompt is the final before step and replaces the ordinary
condition readiness gate. Counting starts at image onset and stops at image offset.
The endpoint question is the first after step. Its response time is outside the
counting interval. Counting duration follows compiled FPVS duration, independently
of the baseline duration.

Endpoint estimates, rate interpretation, and existing counting exports are described
in [Cognitive Load FPVS](COGNITIVE_LOAD_FPVS.md#results-and-interpretation). Modifier
provenance identifies a session baseline even when a no-load entry hosts it.

## Remember four images

The new generic template presents four target images together in a 2-by-2 study
screen. Study is self-paced with Space by default, or uses a configured duration.
Participants retain the images during FPVS. Immediately afterward they choose four
unique images from eight randomized options: the four targets plus four distinct
foils. Selections can be revised before explicit Submit/Enter. All choices are
selectable; incorrect choices are recorded without corrective feedback or retries.

Supply real target and foil images before running. Missing/incomplete media produces
an actionable compile error. Study and recognition share stable target identities;
duplicated target files must contain the same image bytes. Dedicated task seeds
realize order without changing FPVS stimulus, fixation, or session-order seeds.

This template does not replace an existing cognitive-decline or other imported
protocol. Its study timing, recognition timing, click rules, and scoring are its own
explicit defaults.

Memory records include target/foil identities, image paths, study and recognition
order, selected identities, response time, completion status, target hits out of four,
and exact-set correctness. Incomplete, timed-out, and aborted responses retain raw
input but do not receive a fabricated score. Aborting the stream skips recognition
and preserves the unscored study record. Existing task-response journals and full/
compact CSVs carry these values; ordinary participant/group summaries do not expose
raw task answers.

## Local presets and portability

**Save as local preset** is a deliberate local-library action separate from Apply. Name the
copy and optionally describe its purpose. Updating a saved preset identifies that
specific preset; duplicate display names do not overwrite another record. A local
save remains saved if the outer project draft is later canceled. The editor's status
states this distinction.

Presets live under the configured root at
`.fpvs-studio/templates/condition-modifiers/<preset-id>/preset.json`, with their own
contained media. Library reads do not create folders. Invalid records and missing
assets are reported rather than silently ignored. Presets contain no condition
assignments or participant responses.

Loading creates an independent project draft with new modifier/task/link identities.
Applying includes project-owned image copies beneath `stimuli/task-assets/<task-id>/`.
The experiment remains portable after its source library disappears. Project JSON,
`.fpvsconfig`, and `.fpvsbundle` retain grouping and complete media. Library changes
never propagate into previously applied experiments. Website downloads are outside
this implementation.

## Ownership and compatibility

- `core/condition_modifiers.py`: strict grouping definitions, built-in factories,
  explicit typed-counting adoption, and detached assignment operations. `apply_modifier_draft`
  applies assignment differences without rebuilding unchanged conditions' bindings.
- `core/modifier_presets.py`: local preset records, remapping, contained asset intake,
  and staged media commits. `task_assets.py` owns shared media path enumeration.
- `core/compiler.py` / `compiler_tasks.py`: selected baseline requirements, deterministic
  linked memory realization, and neutral task specs.
- `runtime/task_runner.py`: response validation, scoring, provenance, and checkpointing.
  Engines render steps; `RunSpec` retains its frame schedule.
- GUI: draft editing, explicit assignment and local-save actions, worker I/O, and
  document application. The existing detailed task editor remains available.

Projects using modifiers require project schema **1.6.0**; configs require **1.4.0**.
Older projects retain their schema and omit empty modifier grouping on serialization.
New schema versions are rejected by old strict readers instead of dropping behavior.
The portable bundle envelope is unchanged. Masking streams and catch conditions have
their own schema requirements described in [Masking](MASKING.md). Non-centered task
text requires project/config **1.9.0/1.7.0**, SessionPlan **1.5.0**, and modifier preset
**1.2.0**. Default-centered alignment is omitted, so existing centered task payloads
retain their previous formats and presentation.

## Verification and visible acceptance

Use core/compiler/project-io/runtime/engine focused routes and repo precommit after
shared changes. Registered GUI coverage is excluded from ordinary local runs. A
visible Qt session requires explicit safe-environment approval; do not use offscreen
Qt locally.

At the modifier dialog's 1100x720 minimum and 1120x760 default, check both themes,
long names, library empty/populated states, scope selection, validation, baseline
enabled/disabled, memory incomplete/complete, and local save/update. Check the entry
and summary in Setup at 1120x820. Required controls must fit without clipping.
Include visible catch creation, saved condition/marker identity, automatic-catch
blocking, and Instruction item alignment and preview. Registered coverage does not
establish visible acceptance unless it is actually run in an approved environment.

In a disposable experiment, preserve a 30-second baseline through open/cancel and
open/apply/save/reopen; verify explicit typed-counting adoption. Stage images then
cancel and confirm project media is unchanged. Save a local preset, cancel the project
draft, and reopen My presets. Apply to selected conditions and verify other conditions.
Assign one modifier to two conditions, remove it from the first, and Apply. Reopen
both editors: the first must be empty and the second must retain the modifier and
its settings. Add a different modifier to the first and verify the second again.
Repeat removal with Cancel and confirm neither condition changes.

Finally run short counting and memory sessions on the intended presentation machine:
check randomized no-load-first baseline, selected no-load-only testing, explicit memory
Submit, revised choices, incorrect responses, and Escape in each phase. Inspect full
and compact output. Source/fake-renderer checks do not establish physical display or
trigger acceptance.
