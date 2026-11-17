# FPVS Studio product specification

## Mission

FPVS Studio helps researchers prepare stimuli, author reproducible visual experiments,
and run participant sessions through a consistent desktop workflow. Image and word
FPVS paradigms are both part of that mission. Researchers should be able to reuse a
saved experiment without rebuilding its settings for each participant, while retaining
inspectable stimulus provenance, timing decisions and session results.

Studio should make common research workflows accessible without requiring researchers
to write experiment code. Its controls must describe the choices researchers make,
automate routine preparation where the method is well defined, and report unsupported
inputs or unmet requirements explicitly. Current support is defined by the contracts
below; support for every published FPVS method remains a direction, not a claim of
feature parity.

## Research workflow

1. **Prepare stimuli, when needed.** Researchers can use externally prepared images
   directly or use Studio's optional Image Resizer and Image Equalizer utilities.
   Resize/crop before equalizing, since geometry changes can change pixel statistics.
   These tools create separate files. Researchers explicitly select the prepared
   folders during experiment setup. Native word lists do not pass through image tools.
2. **Author and validate an experiment.** Select compatible conditions and image pools
   or word lists, timing, display/session settings, image or character size, fixation,
   responses and participant questions. Reusable projects, templates and supported
   Library workflows reduce repeated authoring. Setup validation reports requirements
   before participant playback.
3. **Run repeated participant sessions.** Ready projects open to Home. Runtime consumes
   compiled frame schedules and session plans, handles participant flow and tasks,
   records results, and supports the current recording/recovery workflows.
4. **Review and transfer results.** Review participant/task results and timing evidence,
   and use the existing export and Toolbox handoff contracts for subsequent analysis.

## Current scope and boundaries

| Area | Current contract |
| --- | --- |
| Desktop audience and interaction principles across Studio and Toolbox | [Shared OpenFPVS desktop guidance](../DESIGN.md#shared-openfpvs-desktop-experience) |
| Image and word oddball FPVS, Cognitive Load FPVS, retained native attentional-blink support; Standard FPVS remains disabled | [Experiment categories](../EXPERIMENT_CATEGORIES.md) |
| Guided Setup, Home, image intake, Tools and participant-facing controls | [GUI workflow](../GUI_WORKFLOW.md) |
| Optional grayscale mean/RMS matching across multiple folders | [Image Equalizer](image-equalizer.md) |
| Frame timing, condition and ordered-session compilation | [RunSpec](../RUNSPEC.md), [SessionPlan](../SESSION_PLAN.md) |
| Playback, tasks, recording, diagnostics, results and recovery | [Runtime execution](../RUNTIME_EXECUTION.md) |
| Windows acquisition and experimental macOS source support | [Architecture](../../ARCHITECTURE.md), [macOS support](../MACOS_SUPPORT.md) |
| Sharing whole experiments and installing reviewed updates | [Experiment Library](../EXPERIMENT_LIBRARY.md) |

Optional preparation operates independently of saved project data and must never
silently change project stimuli or originals. Both tools are optional outside guided
Setup.

Monitor calibration, physical luminance, viewing conditions and hardware timing
qualification remain researcher responsibilities. Equal pixel statistics and successful
software checks do not establish equal measured light output or EEG marker reception.
Offline Image Equalizer parameters do not change runtime temporal contrast modulation.

Detailed behavior has one canonical owner in the linked contracts. The archived v1
architecture specification remains historical context rather than an implementation
checklist.
