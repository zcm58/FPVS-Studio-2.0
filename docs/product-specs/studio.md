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
4. **Review and hand off.** Review session results and timing evidence. Send a runnable
   experiment to another Studio workstation or a protocol or completed-session config
   to the Toolbox analyst. [Export choices and limits](../PROJECT_CONFIG.md#user-workflow-and-limits)

## Planned safeguard for changes during collection

Protect the project's experiment settings once its first research session has
started, even if that session is interrupted. Use retained research history
for existing projects. The safeguard survives restart and **Reopen Collection**.
Setup and Test/Pilot runs alone leave the project in ordinary authoring mode.

Treat changes to experiment settings as exceptional. This includes replacing
images in a condition (even under the same filename), changing, adding or
removing conditions, base or oddball frequencies, timing, display, task,
randomization, trigger, recording and scoring settings. Ordinary participant
entry, project-title corrections that are purely descriptive, and saves with
no experiment change use the usual workflow.

Before a changed protocol can be saved as active or used for a research visit,
show **two separate warning dialogs** for the proposed changes.

1. **Review changes to this study.** Explain that collection has already
   started. Compare the saved and proposed settings, grouped by condition.
   For example, show the old base frequency of 6 Hz alongside the proposed
   7.5 Hz. For stimuli and conditions, identify additions, removals and
   replacements. **I have reviewed these changes** opens the second warning.
2. **Confirm the risk to earlier data.** Explain that earlier participants
   experienced the previous protocol. Comparing or pooling their data with
   future visits may be invalid, and earlier data could be unusable for the
   intended analysis. Require an explicit acknowledgement of that risk, then
   **Apply to future visits**. Cancellation is the default in both dialogs.

Confirm the exact change once per revision. Cancelling either dialog keeps
the prior protocol active. A different proposal requires fresh confirmation.
The confirmed revision applies only to visits that start afterward.
Apply this rule to normal edits, bulk changes and in-place Library updates.
If stimulus files change outside Studio, require review before the next
research visit can use them. Preserve each earlier visit's protocol and
stimulus identities. Its saved evidence must continue to describe what ran.

Verify with a study that already has research visits. Independently change a
frequency, replace an image under the same filename, and add or remove a
condition. Cancel at each step, then confirm a change and reopen the project.
Only later visits should carry the new revision in the [study handoff](../PROJECT_CONFIG.md#planned-whole-study-handoff).

## Planned collection workflow

Once collection ends, the operator can explicitly mark the Studio project
**Data Collection Complete** and prepare one handoff covering the whole study.
The analyst opens it in Toolbox, selects the EEG folder once and reviews the
batch before processing. [Study export and compatibility](../PROJECT_CONFIG.md#planned-whole-study-handoff)

Welcome's **Open Project** and **Manage Projects** share the same project list.
Today it lists projects together. The planned manager has **Active**, **Completed**
and **Archived** tabs. Marking collection complete moves a project from Active
to Completed. Review and export remain available. To run another research
session, choose **Reopen Collection**, which returns the project to Active.
**Archive** moves it to the Archived tab and preserves its files and collection
state. **Restore** returns it to Active or Completed according to that saved state.

Local completion and study export work offline, including for unlinked projects.
For a linked project, show its local state and the last collection status
confirmed by OpenFPVS. Only an OpenFPVS administrator or a designated lead
explicitly authorized to close collection for that study can close it study-wide.
Reopening collection on OpenFPVS requires a separately authorized transition.
A closed study stops accepting new Studio reports and still accepts authorized
Toolbox results.
Account for pending reports before closing intake. Cross-app lifecycle decisions
live in `DESKTOP_EXPERIENCE.md#completing-and-archiving-a-study` in the private
OpenFPVS checkout.
[Shared spec locator](../DESIGN.md#shared-openfpvs-desktop-experience) · [Existing reporting policy](../DATA_SHARING.md#private-openfpvs-project-reporting)

## Role in OpenFPVS

Studio and Toolbox are separate desktop products with their own installers and
release schedules. A combined standalone OpenFPVS distribution is outside the
current scope. A single launcher for both apps is a longer-term possibility
without a committed implementation or release.

Researchers can author and run local projects offline. OpenFPVS hosts the
[Experiment Library](../EXPERIMENT_LIBRARY.md) and [enrolled study results](../DATA_SHARING.md).
Toolbox owns EEG registration, processing and analysis. As the platform grows,
preserve local work, explicit sharing choices and the provenance of each handoff.
Maintainers track cross-app work in the private umbrella checkout's `INTEGRATION_PLAN.md`.

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
