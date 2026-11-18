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

<a id="planned-safeguard-for-changes-during-collection"></a>

## Safeguard for changes during collection

Authors can edit, save and restore protocol versions without collection warnings
until a visit yields participant research data. A partial visit with collected
data counts. Setup, Test/Pilot runs and a research launch that ends before
collecting data leave the project in ordinary authoring mode. Use retained
research history for existing projects, including after restart or **Reopen Collection**.

Once a project holds research data, treat changes to experiment settings as
exceptional. This includes replacing images in a condition (even under the
same filename), changing, adding or
removing conditions, base or oddball frequencies, timing, display, task,
randomization, trigger, recording and scoring settings. Ordinary participant
entry, project-title corrections that are purely descriptive, and saves with
no experiment change use the usual workflow.

Once participant data exists, recommend **Save as new study**. Applying a
change to the collecting project requires **two separate warning dialogs**.

1. **Review changes to this study.** Explain that collection has already
   started. Compare the saved and proposed settings, grouped by condition.
   For example, show the old base frequency of 6 Hz alongside the proposed
   7.5 Hz. For stimuli and conditions, identify additions, removals and
   replacements. **Save as new study** creates a separately named project
   with the proposed settings and stimuli, a fresh study identity and an
   empty roster. Show **Created from [study], version [name/date]** in the
   new study, using the saved version date when it has no name. Keep visits,
   results and reporting enrollment with the original. Only **Continue in this
   study** requires acknowledgement of the reviewed changes and opens the second
   warning.
2. **Confirm the risk to earlier data.** Explain that earlier participants
   experienced the previous protocol. Comparing or pooling their data with
   future visits may be invalid, and earlier data could be unusable for the
   intended analysis. Require a short reason for the in-place change and explicit
   acknowledgement of that risk before **Apply to future visits**. Store the reason
   with the saved revision and include it in the handoff for the Toolbox analyst.
   Cancellation is the default in both dialogs.

Save the new study before switching to it. Cancelling creation or a failed
save leaves the original study active and its protocol intact.
Confirm an in-place change once per revision. Cancelling either dialog keeps
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

### Local version history

From the first saved protocol, automatically retain one local version for each
save that changes the experiment. A version can have an optional name.
Show the save time, what changed and which research visits, if any, used it.
Opening a version for inspection leaves the active experiment alone. Version
history works offline and requires no Library publication.

Retain the settings and exact stimuli needed to restore a saved version,
including an image later replaced under the same filename. Reuse unchanged
assets across versions. If a historical asset is missing, name it and leave
the current protocol active until the saved version can be restored exactly.

From history, the author can **Save as new study** using that version or
**Restore this version** inside the existing study. Restoring records a new
current version, preserves the intervening versions and affects future visits.
Use the same two warnings for an in-place restore that changes a protocol
after participant data exists. Each earlier visit keeps its recorded version.

Verify that a project with only Test/Pilot data can save and restore without
collection warnings. After a partial research visit, verify that saving the
edited experiment as a new study starts an empty roster and keeps the original
active protocol and visits intact. In a separate check, collect under two
versions and restore the first. Both earlier visits must still identify the
version and stimulus contents each used.

## Collection workflow

Once collection ends, the operator can explicitly mark the Studio project
**Data Collection Complete** and prepare one handoff covering the whole study.
The analyst opens it in Toolbox, selects the EEG folder once and reviews the
batch before processing. The paired source implementations preserve repeated
visits, recorded versions, historical evidence gaps and previously confirmed
recording matches when the roster changes. [Study export and compatibility](../PROJECT_CONFIG.md#whole-study-handoff)

Welcome’s **Open Project** and **File > Manage Projects** share **Active**,
**Completed** and **Archived** tabs. Marking collection complete moves a project from Active
to Completed. On the completed Home, **Review results** opens fixation accuracy
and hit-weighted mean reaction time for FPVS, or recall accuracy for attentional
blink. **Export results** offers the group summary workbook and the whole-study
Toolbox handoff. Both exports are also in **File > Export**. To run another research session,
choose **Reopen Collection**, which returns the project to Active.
**Archive** moves it to the Archived tab and preserves its files and collection
state. **Restore** returns it to Active or Completed according to that saved state.

Local completion and study export work offline, including for unlinked projects.
For a linked project, show its local state and the last collection status
confirmed by OpenFPVS under **File > Linked OpenFPVS Study**. Only an OpenFPVS administrator or a designated lead
explicitly authorized to close collection for that study can close it study-wide.
Reopening collection on OpenFPVS requires service authorization as the OpenFPVS
administrator or a PI of the lab that owns the study.
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

### Learning and development priorities

**File > Tutorials** opens the OpenFPVS getting-started guide. Link YouTube
tutorials from the site as they become available. Keep the immediate instruction
needed to complete an action in Studio so ordinary local work remains usable offline.

Deliver and verify the Studio workflow before its Toolbox counterpart. Retain
workflow qualification, broader hardware or paradigm support, and additional tools
as future candidates. Scope and verify each separately before advertising support.

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
