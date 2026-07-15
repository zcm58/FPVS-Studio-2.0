# FPVS Studio v1 Architecture Specification

Version: 0.3
Status: Current v1 baseline; implementation has progressed beyond scaffolding
Project: FPVS Studio Development
License target: GPL-3.0-compatible open source distribution

## 1. Product purpose

FPVS Studio is a standalone desktop application for building and running fast periodic visual stimulation (FPVS) experiments without requiring end users to write code. The desktop shell will use **PySide6**. The timing-critical stimulus presentation runtime will use **PsychoPy** behind an engine abstraction so it can be swapped later if needed.

## 2. v1 protocol decisions

### 2.1 Built-in template

v1 includes one built-in protocol template whose values seed editable project timing:

- `template_id = "fpvs_6hz_every5_v1"`
- `base_hz = 6.0`
- `oddball_every_n = 5`
- `oddball_hz = 1.2`

Projects may edit `base_hz` and integer `oddball_every_n`; `oddball_hz` is derived.

### 2.2 Duty-cycle modes

Each condition may choose one of two duty-cycle modes:

- `continuous`: stimulus visible for the full resolved frame cycle
- `blank_50`: stimulus visible for half the resolved cycle, followed by an equal blank interval

### 2.3 Sequence repeat default

Each sequence defaults to **146 oddball cycles**.

With the default oddball every 5th stimulus:

- `oddball_cycle_repeats_per_sequence = 146`
- `stimuli_per_sequence = 146 * 5 = 730`
- `oddball_presentations_per_sequence = 146`

The true per-sequence duration is derived from the active display's refresh-compatible frame timing.

## 3. Locked v1 product features

- standalone desktop app
- welcome screen with create/open project
- user-selected project root
- project JSON persistence
- Home and Setup Wizard GUI workflow
- image-based and word-based conditions
- project-level fixation cross task
- fixation accuracy tracking and optional participant tutorial
- preprocessing and guided image normalization
- control generators for:
  - `rot180` (orientation inversion)
  - `phase_scrambled`
- test-mode fullscreen PsychoPy launch
- rich session export
- trigger backend contracts and optional BioSemi-compatible serial backend, with
  end-user GUI exposure limited by the current workflow docs

## 4. Out of scope for this phase

- photodiode patch
- lab-validated BioSemi/BDF trigger timing
- additional behavioral tasks
- user-editable base/oddball frequencies in v1
- configurable FPVS protocol timing

## 5. FPVS Studio root and project folder structure

```text
<FPVSRoot>/
  .fpvs-studio/
    templates/
      condition_templates.json
  <ProjectSlug>/
    project.json
    stimuli/
      original-images/
        <set_id>/
          *.jpg|*.jpeg|*.png
      generated-variants/
        <set_id>/
          grayscale-variants/
            *.png
          rotated-180-variants/
            *.png
          scrambled-variants/
            *.png
      manifest.json
    runs/
      # written only when full run export mode is enabled
      P<participant>/
        session_plan.json
        session_summary.json
        run-001-condition-<n>/
          runspec.json
          run_summary.json
        conditions.csv
        events.csv
        responses.csv
        frame_intervals.csv
        trigger_log.csv
        display_report.json
        warnings.log
    cache/
    logs/
      session_condition_history.csv
      participant_summary.csv
      participant_summary.xlsx
      group_summary.xlsx   # manual export default
```

## 6. Image rules

- Supported source image formats are only `.jpg`, `.jpeg`, and `.png`.
- Extension matching should be case-insensitive.
- Raw image-folder import may be permissive, but launchable image stimulus sets must
  resolve to square images.
- A condition's base and oddball stimulus sets may use different square source
  resolutions because playback size is controlled by compiled display geometry.
- No automatic resizing is allowed as a validation shortcut.
- Generated variants are saved into the project and then reused from disk.

## 7. Architecture rules

- Use a **src layout** for the Python package.
- Keep core models and validation engine-neutral.
- Only code in `engines/` may import PsychoPy.
- GUI communicates with runtime by compiling neutral `RunSpec` and `SessionPlan`
  contracts.
- Runtime writes neutral run/session execution artifacts.
- Derived image generation happens before any test/run, never inside the time-critical presentation loop.

## 8. Core persisted models

The core layer defines stable schemas for:

- `ProjectFile`
- `ProjectMeta`
- `ProjectSettings`
- `DisplaySettings`
- `FixationTaskSettings`
- `TriggerSettings`
- `StimulusSet`
- `Condition`
- `TemplateSpec`
- `RunSpec`
- `SessionPlan`
- `RunExecutionSummary`
- `SessionExecutionSummary`
- `RuntimeMetadata`
- `StimulusEvent`
- `TriggerEvent`
- `FixationEvent`
- `StimulusManifest`
- validation/report models

## 9. Timing rules

After a display is selected, all timing becomes frame-based.

For v1 project timing:

- `frames_per_cycle` is the nearest positive whole frame count to
  `refresh_hz / requested_base_hz`
- authored `refresh_hz` is one of `59.94`, `60`, `120`, `144`, or `240 Hz`
- exact ratios are reported as exact timing
- non-integral ratios are accepted with requested-versus-realized rate warnings
- `blank_50` requires an even resolved `frames_per_cycle`
- setup and runtime compare the configured rate to an explicit engine measurement of
  the connected presentation display; measurement state remains machine-local

Derived values should include:

- `image_on_frames`
- `blank_frames`
- per-sequence frame totals
- per-sequence approximate duration in seconds
- fixation event durations/gaps in frames

## 10. Trigger model

Trigger settings stay in project/runtime settings while serial-port details remain
outside `RunSpec` and `SessionPlan`. Runtime wires either the logged null backend or
the optional BioSemi-compatible serial backend. Normal event codes are `1` through
`255`; code `0` is reserved for explicit manual reset behavior. FPVS Studio locks
`oddball_onset` to marker code `55` by default; a nonstandard oddball marker is only
valid when the project records the user-directed
`allow_nonstandard_oddball_trigger_code` override.

## 11. Participant metadata

Runtime execution summaries can carry launch-time participant metadata. The default GUI
launch workflow collects Participant Number, Age, Sex, Handedness, and colorblind status
for every project. Participant Number stays the required runtime identity and
duplicate-history lookup key; Sex is constrained to `Female` or `Male`; Handedness is
constrained to `Right handed`, `Left handed`, or `Ambidextrous`; colorblind status is
constrained to a required `Yes` or `No` answer. Age, Sex, Handedness, and colorblind
status remain runtime metadata fields outside `RunSpec` and `SessionPlan`.

## 12. Participant-facing condition titles

Authored condition titles are internal experiment metadata. Runtime preserves condition
names in `RunSpec`, `SessionPlan`, and execution artifacts, but participant transition
screens always render generic headings such as `Condition 1 of 4`.

## 13. Current repository goal

Keep the GUI, core contracts, preprocessing, runtime/session flow, engine boundary,
trigger backends, exports, and harness docs aligned so future changes can start from
the narrow task recipes in `../ARCHITECTURE.md` instead of rediscovering package
boundaries.
