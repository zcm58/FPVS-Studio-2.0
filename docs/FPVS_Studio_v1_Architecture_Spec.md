# FPVS Studio v1 Architecture Specification

Version: 0.3
Status: Current v1 baseline; implementation has progressed beyond scaffolding
Project: FPVS Studio Development
License target: GPL-3.0-compatible open source distribution

## 1. Product purpose

FPVS Studio is a standalone desktop application for building and running fast periodic visual stimulation (FPVS) experiments without requiring end users to write code. The desktop shell will use **PySide6**. The timing-critical stimulus presentation runtime will use **PsychoPy** behind an engine abstraction so it can be swapped later if needed.

## 2. Locked v1 protocol decisions

### 2.1 Built-in template

v1 includes exactly one built-in protocol template:

- `template_id = "fpvs_6hz_every5_v1"`
- `base_hz = 6.0`
- `oddball_every_n = 5`
- `oddball_hz = 1.2`

These are fixed in the v1 GUI.

### 2.2 Duty-cycle modes

Each condition may choose one of two duty-cycle modes:

- `continuous`: image visible for the full 6 Hz cycle
- `blank_50`: image visible for half the 6 Hz cycle, followed by an equal blank interval

### 2.3 Sequence repeat default

Each sequence defaults to **146 oddball cycles**.

Because oddballs occur every 5th image:

- `oddball_cycle_repeats_per_sequence = 146`
- `base_cycles_per_sequence = 146 * 5 = 730`
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
      <SessionId>/
        runspec.json
        session.json
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

For v1:

- `frames_per_cycle = refresh_hz / 6.0`
- `continuous` requires integer `frames_per_cycle`
- `blank_50` requires integer and even `frames_per_cycle`

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
launch workflow collects Participant Number, Age, Sex, and Handedness for every project.
Participant Number stays the required runtime identity and duplicate-history lookup key;
Sex is constrained to `Female` or `Male`; Handedness is constrained to `Right handed`,
`Left handed`, or `Ambidextrous`. Age, Sex, and Handedness remain runtime metadata
fields outside `RunSpec` and `SessionPlan`.

## 12. Participant-facing condition titles

Authored condition titles are internal experiment metadata. Runtime preserves condition
names in `RunSpec`, `SessionPlan`, and execution artifacts, but participant transition
screens always render generic headings such as `Condition 1 of 4`.

## 13. Current repository goal

Keep the GUI, core contracts, preprocessing, runtime/session flow, engine boundary,
trigger backends, exports, and harness docs aligned so future changes can start from
the narrow task recipes in `../ARCHITECTURE.md` instead of rediscovering package
boundaries.
