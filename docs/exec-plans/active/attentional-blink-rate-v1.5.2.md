# Editable Attentional Blink Rate And v1.5.2

Status: Active

## Outcome

Expose the existing project-wide presentation rate in Setup > Design for native
Attentional Blink streams. Keep 10 Hz as the default, accept positive finite decimal
rates, and preserve exact whole-frame presentation and onset-to-onset SOA validation.
Changing rate does not silently rescale authored SOAs or round presentation timing.
Build and publish v1.5.2 with a full installer, a direct v1.5.1 patch, and update JSON.

## Implementation And Verification

1. Add a model-backed draft rate control to the existing Design header. Apply rate,
   sources, colors, and all SOAs atomically; invalid changes leave the project intact.
   Update timeline and quarter-speed preview copy/timing from the draft rate.
2. Verify decimal rates, persistence, unchanged SOAs, compiled event timing, invalid
   rate/frame combinations, and draft apply/cancel behavior. Retain registered GUI
   geometry coverage at the existing 1120x820 wizard minimum.
3. Run focused GUI/core/packaging/docs checks and repository precommit. Visible Qt
   execution requires an approved safe session and is otherwise reported as skipped.
4. Authenticate the exact published v1.5.1 baseline, retain build dependencies, build
   isolated v1.5.2 artifacts, verify patch/full equivalence and GitHub digests, then
   publish and check the public updater feed. Keep release notes to one sentence.

## Progress

- Initial GUI and core focused checks passed. Core already supports non-10 Hz rates;
  the editor lacks a rate field. Exact frame/SOA rules remain authoritative.
- Added the shared rate draft, atomic apply, dynamic timeline/preview timing, and
  full-precision editable SOAs. Animation rejects timer intervals outside its range
  without clamping authored rates. Independent code review found no remaining blockers.
- Core focused: 345 passed, one Windows symlink privilege skip. Atomic document
  rate tests: 24 passed. Packaging focused: 168 passed. GUI non-Qt checks, docs
  hygiene and nine docs tests passed.
- Repository precommit passed Ruff, compilation, mypy, repository audits, and all
  1,353 non-Qt unit tests, with five Windows symlink permission skips. The process
  used `PYTEST_ADDOPTS=--basetemp=build/ut152` to avoid known Windows temporary-path
  limits without changing the harness. Evidence: `build/release-1.5.2/precommit.log`.
- The v1.5.1 baseline matches published GitHub assets and all 8,030 owned files.
  Its exact inventory SHA-256 is
  `9961840684982e9c4ff1f1cce253a6a50250ed40777da77babf46b9e84f85073`.
- Only FPVS Studio metadata changed in the build environment, from 1.5.1 to 1.5.2;
  runtime dependencies were retained. Isolated release artifact build is running.
- Registered GUI coverage includes rate drafts, fractional SOA persistence, invalid
  input, extreme-rate preview behavior, and both-theme wizard geometry. Visible Qt
  tests and packaged GUI smoke remain unrun without approval for a safe visible
  session; manual acceptance steps are in `docs/GUI_WORKFLOW.md`.
