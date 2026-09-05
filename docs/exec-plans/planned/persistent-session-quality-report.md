# Persistent Session Quality Report

Status: Planned

The user endorsed this direction on 2026-09-05 and requested a separate future
execution plan. Implementation has not started. Move this plan to `active/` when
the work is scheduled; existing completion and export behavior remains authoritative.

## Problem And Intended Outcome

The main Home launch path reports successful completion through a generic information
dialog and a five-second status message. The application already exports condition
completion, timing findings, fixation performance, and available graphics diagnostics,
but the operator must inspect separate files to assess those facts after a run.

Provide a persistent **Session Results** surface with one row per condition occurrence,
showing completion/abort state, timing findings, fixation accuracy/RT, and available
hardware observations. Include explicit unavailable states and links to relevant
exports. A completed session must not automatically appear to have clean timing.

The benefit is quicker review before the next participant, easier troubleshooting,
and consistent access to evidence across labs. This is a presentation/behavioral
quality report; fixation accuracy is not an EEG-quality measure.

## Existing Owners And Evidence

- `src/fpvs_studio/gui/main_window.py`: Home launch completion and abort feedback.
- `src/fpvs_studio/gui/run_page.py`: detailed session text and run output links.
- `src/fpvs_studio/core/execution.py`: authoritative session/run results and optional
  runtime metadata; preserve these meanings rather than interpreting success flags.
- `src/fpvs_studio/runtime/session_export.py`: persistent condition-occurrence history,
  timing violation fields, available graphics observations, and compact summaries.
- `src/fpvs_studio/runtime/fixation_report.py`: existing reporting-service patterns
  to inspect and reuse where applicable; do not create a second metric definition.
- [Runtime/export documentation](../../RUNTIME_EXECUTION.md) describes compact logs,
  full run folders, participant summaries, seeds, and recording metadata.

Software frame records do not establish physical light-onset timing by themselves.
[PsychoPy timing guidance](https://psychopy.org/general/timing/millisecondPrecision.html)
documents monitor/driver delays that may not appear in software logs. The report
must preserve that distinction without implying that missing hardware measurements
are successful checks.

## Scope And User Workflow

1. After completion or abort, retain the result on a Session Results surface reachable
   from Home. Identify the session, participant or rehearsal context, and completion time.
2. Display one row per condition occurrence, including block/order so repeated
   conditions are distinguishable. Summarize completion and recorded timing findings.
3. Selecting a row reveals available frame-interval/timing details, fixation counts,
   accuracy/RT, warning or abort explanations, and applicable hardware observations.
4. Provide Open/Copy actions for available exports and compact project logs. Explain
   when detailed run output was disabled or has since been removed.
5. Allow reopening the latest session result from persisted records after application
   restart. Historical browsing beyond that can follow after the first slice is accepted.

## Implementation Sequence

1. **Define the field/source map.** Document each displayed value's existing owner,
   unit, denominator, optionality, and availability in compact/full export modes.
   Distinguish not recorded, disabled, skipped, and failed where source data permits;
   use unknown/unavailable when legacy records cannot support a finer distinction.
2. **Add a neutral reporting query.** Follow the runtime reporting boundary to read
   existing result contracts and persistent history. Identify occurrences by stable
   session/run/block/order fields; preserve ordering and avoid double counting.
   Keep CSV/JSON parsing and metric interpretation out of widgets.
3. **Build the persistent surface.** Use shared GUI components and non-blocking reads.
   Retain Home as the daily launch surface; expose details intentionally and prevent
   the result panel from growing or obscuring the compact launch UI.
4. **Connect every launch outcome.** Handle normal and rehearsal completion, abort,
   launch failures without a session summary, partial exports, and a subsequent run.
   Replace redundant success acknowledgments with the persistent result while keeping
   actionable errors and recovery paths.
5. **Validate against source records.** Compare the visible result with known exports
   from successful, aborted, timing-warning, compact, and legacy sessions. Document
   unavailable details rather than reconstructing unsupported measurements.

## Boundaries And Decisions

- Runtime/core result meanings and exporter formats are authoritative. Prefer reading
  existing fields; document any required additive contract/export change before coding.
- Do not introduce new timing thresholds, a composite quality score, automatic reruns,
  participant exclusion, or changes to existing inclusion decisions.
- Define whether fixation results shown are condition-level or aggregated. Reuse
  existing weighted calculations for any aggregate; do not average percentages or
  mean RTs without the established weighting and denominators.
- Reuse metric definitions, not participant-analysis inclusion filters. The existing
  fixation reporting query filters test IDs and aborted sessions; this occurrence
  report must retain rehearsals, aborted runs, and analysis-excluded records with
  their labels intact, without changing any inclusion decision.
- Reuse approved path-opening/copy helpers and active-project-root resolution. Missing
  output is recoverable; viewing the report must not rewrite history or repair exports.
- The first slice includes latest-session persistence. Full study analytics, EEG
  processing, photodiode integration, and unrestricted historical dashboards are out of scope.
- Decide the exact Home entry point and detail-surface minimum/default size before
  implementation. Long warning text and repeated conditions must remain inspectable.

## Acceptance And Verification

- Results remain accessible after dismissing the initial view, navigating Home, and
  reopening the project. A new run cannot leave the previous result mislabeled as current.
- Repeated conditions appear as separate occurrences; aborted and unstarted entries
  are identified from actual source evidence. Export/read failures remain actionable.
- Compact mode works without a run folder; detailed-only values are unavailable there
  when no authoritative source remains. Legacy missing fields never become zero or pass.
- Timing/graphics/fixation values reconcile with source contracts and files, and
  rehearsal outputs remain distinguishable when authoritative provenance exists.
- Add neutral query tests using temporary compact/full/legacy/partial fixtures,
  repeated blocks, aborted/rehearsal/excluded records, missing outputs, and disabled
  fixation scoring. Verify no source files are modified by reads and no new inclusion
  decisions are produced.
- Register pytest-qt tests with fake queries/workers and stubbed file openers. Cover
  loading, failure, empty, completed, aborted, warning, unavailable, and long-content
  states at documented sizes. Preserve keyboard access and full-value retrieval.
- Run runtime/GUI focused verification plus repo precommit for shared changes. Qt tests
  require a user-approved safe visible environment; no local offscreen execution.
- Record a visible manual smoke from Home launch through results, project reopen,
  output links, and the next participant, using both compact and full export modes.

## Dependencies And Completion

Coordinate with [installed rehearsal](packaged-experiment-rehearsal.md) on authoritative
rehearsal provenance and [recording setup](lab-independent-recording-setup.md) on
available hardware observations. The report can begin with existing result fields
and must handle additional fields compatibly.

Update `docs/GUI_WORKFLOW.md`, `docs/RUNTIME_EXECUTION.md`, and affected core/runtime
guides for any new query or metadata ownership. Complete this plan when persisted
results reconcile with both export modes and visible acceptance is recorded.
