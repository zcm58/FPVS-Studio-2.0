# Windows Rational Refresh Verification

Status: Completed

## Objective

Use the active Windows display path's rational refresh mode to distinguish fractional
rates such as `60000/1001` from integer `60/1`, then use PsychoPy's fullscreen frame
measurement only as a stability and delivery check. Apply the same verification during
Setup and runtime preflight without changing persisted project, `RunSpec`, or
`SessionPlan` schemas.

## Implemented workflow

- `Detect My Refresh Rate` queries the exact configured mode for the primary Windows
  presentation display.
- FPVS Studio opens the existing temporary fullscreen PsychoPy probe and confirms that
  synchronized frame delivery is stable and agrees materially with the configured mode.
- Setup reports the configured rational mode, PsychoPy's observed rate, and the approved
  FPVS rate applied to the project.
- A configured `60000/1001` mode applies `59.94 Hz`; a configured integer `60/1` mode
  applies `60 Hz`, regardless of small PsychoPy sampling variation.
- Runtime preflight repeats both checks once per launch so Home and Run cannot bypass
  exact mode verification.

## Implementation boundaries

- Runtime owns the Windows-only `QueryDisplayConfig` adapter and the combined neutral
  verification result.
- Engines continue to expose only the neutral measured-Hz method; only the PsychoPy
  engine imports PsychoPy.
- Core keeps the approved authored-rate list and engine-neutral timing contracts.
- GUI starts the combined verification through its existing worker and renders the
  result; workers do not touch widgets.
- Windows Dynamic Refresh Rate is not treated as an exact fixed-rate mode. Detection and
  runtime preflight surface an actionable error rather than silently accepting it.
- Failure to obtain the Windows rational mode is blocking. PsychoPy-only classification
  is not an acceptable fallback for distinguishing 59.94 from 60.
- The Windows value is the exact driver-configured mode, not a claim of external
  photodiode-level physical oscillator measurement.

## Verification completed

- Rational selection, `59.94` versus `60`, Windows 10 query fallback, Dynamic Refresh
  Rate rejection, native failures, non-approved exact modes, and PsychoPy stability are
  covered by registered runtime unit tests.
- Runtime preflight coverage proves that a `60000/1001` Windows mode rejects a session
  compiled for integer `60 Hz`, even when PsychoPy observes `59.998 Hz`.
- Registered pytest-qt coverage exercises exact/fractional status copy, success, failure,
  busy state, persistence, and the `1120x720` no-clipping contract. Per repository policy,
  this coverage remains for CI or an explicitly approved visible Qt run.
- Focused runtime, GUI, core, engine, and docs verification passed.
- Repository precommit passed with mypy clean and `348` unit tests passing.

## Assumptions retained

- Current supported launches use the primary/default fullscreen presentation display;
  display-index selection remains outside the user-facing workflow.
- Windows 10/11 active display paths expose usable `DISPLAYCONFIG_RATIONAL` data through
  `QueryDisplayConfig`.
- Existing whole-frame scheduling, compilation, runtime scoring, exports, and trigger
  behavior remain unchanged.
