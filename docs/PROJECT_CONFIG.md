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
Deploy compatible builds of both applications together: older Toolbox builds
that accept only 1.x configs reject revision-2 exports. Updating Studio alone
does not update Toolbox's importer. The producer application version is
provenance, not a minimum Toolbox release; source tests do not establish a
minimum published Toolbox version.

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

**Export > FPVS Toolbox Config…** writes a setup document. **Export > Completed
Project Config…** exports the latest retained completed-session snapshot. Native
research completion also writes one handoff per execution under
`logs/acquisition/`; see the [runtime contract](RUNTIME_EXECUTION.md#completed-toolbox-handoff).

A completed handoff describes one session, not an entire multi-participant study.
Raw EEG remains external. Toolbox owns hardware confirmation, recording
registration and the supported analysis interpretation. Participant/session
labels and send logs cannot independently prove which raw recording belongs to
the session or establish EEG sample timing.

Studio config import creates a new project shell under the configured Studio
root. FPVS stimulus image libraries remain separate; hashed modular-task media
retain their existing portable import behavior. See the
[GUI workflow](GUI_WORKFLOW.md) for the config and bundle actions.
