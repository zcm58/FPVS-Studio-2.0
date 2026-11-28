# Studio–Toolbox config format

`core/project_config.py` owns the `.fpvsconfig` exchange contract;
`core/project_config_legacy.py` isolates historical normalization and validation.
Setup and
completed-session exports use one format; application release numbers identify
the producer and do not select a different schema for each authoring feature.

## Current envelope

| Field | Meaning |
| --- | --- |
| `format` | Exact string `fpvs-handoff`. |
| `format_version` | Integer `2`; strings and booleans are invalid. |
| `kind` | `setup` or `completed_session`, consistent with the completion payload. |
| `producer` | Creating application, application version and export time. |
| `metadata` | Optional descriptive extensions; never executable configuration or scientific interpretation. |

Current files do not contain the historical top-level `schema_version` field.
Project identity, conditions, protocol, session settings, triggers, recording
declarations and optional completed evidence retain their explicit fields.
`completed_session` adds captured execution evidence to the same setup contract;
it does not define another format revision.
The deprecated nested `toolbox.handoff_schema_version` remains readable in
historical files but is omitted by current writers.

The application validates scientific fields and their relationships. Unknown
fields outside the documented metadata area, unknown format revisions and
inconsistent document kinds fail explicitly. A consumer may support fewer
scientific designs than Studio; recognizing the envelope does not establish
support for every frequency policy, experiment category or recording route.

## Versioning and maintenance

Add optional descriptive information inside `metadata` without changing the
format revision. A breaking structure change or a change to existing scientific
meaning requires an explicit new revision and migration. Do not restore
feature-selected envelope numbers or silently ignore unknown scientific fields.

Keep application release provenance separate from format compatibility. Paired
Studio-producer/Toolbox-consumer fixtures establish source compatibility; tested
installer releases and physical hardware acceptance remain separate evidence.
For a handoff, check the export format against the separately installed Toolbox
version. Toolbox builds that accept only 1.x configs reject revision-2 exports.
Updating Studio leaves the Toolbox importer at its installed version. The
producer version identifies the Studio build. Establishing the minimum compatible
published Toolbox version requires testing its release.

Internal project, RunSpec, SessionPlan, acquisition-evidence, hardware-profile
and processing-method versions retain their own contracts. They are not aliases
for the config format or application release.

## Historical files

Readers accept supported historical `schema_version` values `1.0.0` through
`1.15.0`, apply their historical validation/migration rules, and normalize them
at the config model boundary, including retained runtime snapshots. Writers emit
revision 2. Older files are not
rewritten merely by reading them; their recorded producer and completed-session
evidence remain source provenance.
Missing legacy producer information remains unknown; normalization does not
attribute an old export to the current application version or export time.

Restoring a Studio project uses the current editable-project contract and the
validated config content. It does not infer a project schema from the handoff
revision. Existing scientific schedules and seeded realization remain unchanged.
Descriptive `metadata` survives config reads/writes, but is not promoted into the
authored `project.json` contract when creating a Studio project shell.

## User workflow and limits

Use **File > Export** and choose the artifact for the next operator.

| Next task | Studio action and output |
| --- | --- |
| Reopen and run the experiment in Studio | **Project Bundle…** writes a portable `.fpvsbundle` with the project and stimulus assets. Import it into Studio and review local setup before launch. |
| Set up a Toolbox analysis project | **FPVS Toolbox Config…** writes a setup `.fpvsconfig` with the authored protocol and recording declarations. |
| Review a participant visit in Toolbox | **Completed Project Config…** exports the latest finalized research session on demand. Full and compact sessions retain their setup and completion receipts locally. [Runtime contract](RUNTIME_EXECUTION.md#completed-toolbox-handoff) |
| Review the completed study in Toolbox | On the completed Home, choose **Export results** and the whole-study Toolbox handoff. **File > Export** offers the same action. [Whole-study format](#whole-study-handoff) |

In Toolbox, **Import FPVS Studio Config…** creates a local project for a supported
design. The operator confirms hardware and registers the external EEG recordings.
Import copies neither raw EEG nor stimulus or task media. Completed evidence
starts unbound. Matching participant labels or Studio's trigger-send logs alone
cannot identify a recording or establish EEG sample timing.

For whole-study files, Toolbox stores the confirmed links from visits to
external recordings and reuses them when the same study sends a revised
roster. See `../FPVS-Toolbox/docs/agent/architecture/project-io.md` from this
checkout for the supported protocol subset and review rules.

Studio config import creates a new project shell under the configured Studio
root. FPVS stimulus image libraries remain separate; hashed modular-task media
retain their existing portable import behavior. See the
[GUI workflow](GUI_WORKFLOW.md) for the config and bundle actions.

### Recording system and electrode montage

The Recording selection is stored in `recording.recording_backend`. A saved
cap choice adds `recording.electrode_montage` to setup and completed configs.
Studio restores both fields when importing a config. The accepted choices are
listed below.

| Recording system | Electrode montage IDs |
| --- | --- |
| BioSemi ActiveTwo 64 (`serial`) | `biosemi64` |
| BioSemi ActiveThree (`biosemi_active_three`) | `biosemi128` for the radial A–D layout, or `recorded` |
| Brain Products (`brainproducts_triggerbox` or `brainproducts_parallel`) | `brainproducts_acticap_gacs_64`, `brainproducts_acticap_gacs_128`, or `recorded` |
| Unicorn Hybrid Black (`unicorn_udp`) | `unicorn8` for the factory layout |
| EGI Net Amps 400 wired DIN (`egi_din`) | Marker output only. Leave the montage and acquisition profile unset. |
| ANT Neuro eego mylab, 8-bit TTL (`ant_mylab_ttl`) | Marker output only. Leave the montage and acquisition profile unset. |

ANT handoffs carry the configured parallel-port address, pulse width and eego
Recorder sample rate. Other recorder handoffs omit these ANT fields.

EGI handoffs include the configured parallel-port address and pulse width. When
another device is selected, Studio retains those preferences in its project and
omits them from the exported recording declaration for older Toolbox readers.

`recorded` instructs Toolbox to use available recording coordinates. Earlier
configs may omit the montage. ActiveTwo and Unicorn may still identify their
fixed layouts through an existing acquisition profile. An older ActiveThree or
Brain Products selection leaves the cap unspecified.

Completed configs repeat the launch selection in
`completed_session.acquisition_evidence.recording.selected_backend` and
`electrode_montage` on that same object. The whole-study export carries the
corresponding pair on each `visits[].recording`. Editing the project after a
visit cannot change its captured pair. Studio rejects conflicting setup and
session declarations. Historical completed exports with only a session plan
leave the electrode montage unspecified. A named declaration requires a
consumer that recognizes the montage field. Toolbox validates the selected
cap against the EEG file.

When a completed config contains acquisition evidence, Studio checks the
selected recorder and effective output, even when the cap was left unspecified.
The project, visit, execution, and ordered run and condition identities must
agree. During whole-study export, the prelaunch marker schedule must also
agree with the completed plan. A rehearsal can reuse the participant and
session identifiers of a research visit. Separate execution IDs keep the real
recording in the roster, while conflicting mode flags on the same recording
require review before export.
The [runtime contract](RUNTIME_EXECUTION.md#completed-toolbox-handoff) describes
acquisition profiles and the evidence captured at launch.

The portable condition map uses display names as keys. Give each condition a
distinct name, including after trimming surrounding spaces. New conditions and
duplicates receive an unused event code and skip the project's oddball marker.
Export preserves the saved codes. Repeated JSON fields in a handoff are ambiguous
and Studio reports the repeated key.

Where a block order is present, each completed run's global, block and
within-block indices must identify that same occurrence. For EGI DIN and ANT
TTL, any parallel address and pulse width declared in both the setup and the
active recording snapshot must agree. The same check applies to the ANT eego
Recorder sampling rate. Historical missing fields remain unknown.

### Display cadence in the handoff

Project saves retain the refresh target in `settings.display.preferred_refresh_hz`.
Both config kinds carry that setting in `display.preferred_refresh_hz`. A completed
config also carries the refresh used to compile the run in
`completed_session.refresh_hz` and the planned marker frames in
`completed_session.ordered_runs[].trigger_events`. The compiled rate applies to
every run in that session. The saved target can be absent or differ from the
compiled rate. Use the completed plan to describe a recorded session's planned
cadence.

For an ordinary periodic run, the frame gap between consecutive planned oddball
onsets and the compiled refresh determine the planned oddball rate. The oddball
rate times `protocol.oddball_every_n` gives the planned base rate. At 60.02 Hz, a
nominal 6 Hz image stream with an oddball every five images uses 50 display frames
per oddball cycle, giving 6.002 Hz base and 1.2004 Hz oddball. The authored rates
remain in `protocol` and condition overrides. Planned cadence is separate from
observed playback, the recorded marker positions and the EEG sample rate.

Toolbox keeps the configured and compiled rates in the project import receipt.
Both apps advise researchers of the tradeoff at 60.02 Hz. For a nominal 60 Hz
design, Toolbox keeps the requested frequencies for its standard FFT. The
1.2004 Hz planned oddball rate in this example is 0.0004 Hz above the 1.2 Hz
analysis target. At the same frame count, a nominal 120-second run is about
40 ms shorter at 60.02 Hz. Studio's software timing tests ended 36–38 ms earlier
than 120 s. The handoff leaves the recorded markers and sample clock intact.

<a id="planned-whole-study-handoff"></a>

## Whole-study handoff

The whole-study writer uses `format="fpvs-study-handoff"`, integer
`format_version=1`, and the same `.fpvsconfig` extension. The study UUID
identifies the collecting project. `roster_revision` is the SHA-256 digest
of the ordered visits serialized as compact sorted-key UTF-8 JSON.
`roster_sequence` orders revised exports locally. Re-exporting unchanged
evidence preserves both values. `visits` links each execution to an
as-run protocol version when known and to its scientific setup in `setups`.
Retained numbered participant or session history without acquisition evidence
appears in the roster with explicit issues. The file contains recording
declarations and local marker attempts. EEG, participant answers and stimulus
assets stay in the lab's source files.

After all participants finish, the operator marks **Data Collection Complete**
in Studio and exports one study handoff. The Toolbox analyst opens
that file once and selects the study's EEG folder once. Toolbox inventories the
recordings, presents unresolved or ambiguous visit matches for review, and runs
the supported batch after the analyst resolves the required checks. Raw EEG stays in the
lab's recording files.

Give the collecting Studio project a persistent identity that works offline.
Reopening the study preserves this identity and existing execution IDs. A
standalone study saved from an edited or historical protocol gets its own
identity and exports only visits collected in that study. The same rule
applies to a separate project created from a template or Library experiment.
Restoring a protocol in place preserves the collecting project's identity
and the as-run revision of each earlier visit. Identify the exported roster
revision so Toolbox can recognize an already applied snapshot and preview a
later revision in the same analysis project. The project title, protocol
fingerprint and export timestamp alone cannot establish that relationship.

The file covers the study's completed research visits, including repeat visits.
Each execution refers to the protocol revision used at launch. Include each
revision's common protocol information once. For an in-place change after
research data exists, carry the author's short reason with the revision so
the Toolbox analyst can read it when reviewing the affected visits. The OpenFPVS
protocol fingerprint excludes recording hardware and display geometry. For every
execution, retain the effective hardware, display settings and compiled refresh rate even when the
fingerprint matches another visit. Preserve the execution and visit identifiers,
condition order, randomization, planned marker frames, actual trigger attempts
and operator-reviewed electrode exclusions. Keep unknown exclusions distinct
from a reviewed empty list. The cohort review lists known unfinished research
executions, including interrupted or aborted visits, as exceptions with their
recorded status. Exclude them from the completed visit count and processing
batch. Retain Test/Pilot evidence locally and exclude those runs from the
research cohort.

Store the visit facts required for the final export in both compact and full
output modes. Build and write the distributable file at explicit study export.
Acquisition evidence, recovery and authorized session reporting keep their own
lifecycles. The export must work offline and must preserve the protocol used
for each visit even if the operator later edits the experiment.

Historical setup and completed-session files remain readable. New sessions retain
a content-addressed setup, the recording evidence and a private completion receipt.
The operator can export the completed session or the entire study later.
Verify a study with multiple participants, a repeat
visit, a mid-study protocol change, a Test/Pilot run, an unfinished research
execution and an ambiguous EEG match. The analyst must be able to identify the
included visits, see the unfinished execution as an exception and resolve the
recording match before batch processing. Also verify that two visits sharing a
protocol fingerprint retain their different hardware or display settings.
