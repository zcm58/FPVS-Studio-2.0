# FPVS Studio v1 Architecture Specification

Version: 0.2
Status: Approved for repository scaffolding and model implementation
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
- condition-based workflow
- project-level fixation cross task
- preprocessing wizard with grayscale support
- control generators for:
  - `rot180` (orientation inversion)
  - `phase_scrambled`
- test mode
- rich session export
- settings surface for trigger backend/serial port selection

## 4. Out of scope for this phase

- full GUI implementation
- full PsychoPy presentation loop
- final serial-trigger implementation
- photodiode patch
- additional behavioral tasks
- user-editable base/oddball frequencies in v1

## 5. Project folder structure

```text
<ProjectRoot>/
  <ProjectSlug>/
    project.json
    stimuli/
      source/
        <set_id>/
          originals/
            *.jpg|*.jpeg|*.png
      derived/
        <set_id>/
          grayscale/
            *.png
          rot180/
            *.png
          phase_scrambled/
            *.png
      manifest.json
    runs/
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
```

## 6. Image rules

- Supported source image formats are only `.jpg`, `.jpeg`, and `.png`.
- Extension matching should be case-insensitive.
- All images in a stimulus set must have the same resolution.
- A condition's base and oddball stimulus sets must also match in resolution.
- No automatic resizing is allowed as a validation shortcut.
- Derived assets are saved into the project and then reused from disk.

## 7. Architecture rules

- Use a **src layout** for the Python package.
- Keep core models and validation engine-neutral.
- Only code in `engines/` may import PsychoPy.
- GUI communicates with runtime by compiling a neutral `RunSpec`.
- Runtime writes a neutral `SessionExport`.
- Derived image generation happens before any test/run, never inside the time-critical presentation loop.

## 8. Core persisted models

The repository scaffolding pass should define stable schemas for:

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
- `SessionSummary`
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

Expose trigger settings in project settings, including a serial port string and backend selection. The actual lab-specific serial implementation may remain a placeholder in this phase, but the interface boundary should be present.

## 11. Repository-scaffolding phase goal

This phase should end with a trustworthy domain layer, a clear repo layout, validation/tests, and enough runtime/engine scaffolding that later GUI and PsychoPy work can plug into stable contracts.

