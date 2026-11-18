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
| Review a participant visit in Toolbox | **Completed Project Config…** exports the latest retained completed-session snapshot. A completed native research session with recording enabled also writes `logs/acquisition/<execution_id>-completed.fpvsconfig` automatically. Test/Pilot and interrupted runs do not produce that handoff. [Runtime contract](RUNTIME_EXECUTION.md#completed-toolbox-handoff) |

In Toolbox, **Import FPVS Studio Config…** creates a local project for a supported
design. The operator confirms hardware and registers the external EEG recordings.
Import copies neither raw EEG nor stimulus or task media. Completed evidence
starts unbound. Matching participant labels or Studio's trigger-send logs alone
cannot identify a recording or establish EEG sample timing.

Saving a reviewed link between a Studio session and its Toolbox recording is
planned. See `../FPVS-Toolbox/docs/agent/architecture/project-io.md` from the
Studio checkout for current support and the adjacent `hardware-pipeline-studio-roadmap.md`
for planned protocol coverage.

Studio config import creates a new project shell under the configured Studio
root. FPVS stimulus image libraries remain separate; hashed modular-task media
retain their existing portable import behavior. See the
[GUI workflow](GUI_WORKFLOW.md) for the config and bundle actions.

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
