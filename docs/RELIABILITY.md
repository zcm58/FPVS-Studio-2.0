# Reliability

Reliability work should preserve FPVS timing contracts, project persistence formats, and
clear launch-readiness feedback.

## Principles

- Core models and compiled contracts remain the source of truth.
- Runtime consumes `RunSpec` and `SessionPlan`; GUI widgets do not own session flow.
- PsychoPy imports stay lazy and isolated under `../src/fpvs_studio/engines/`.
- GUI launch labels must stay honest about supported runtime paths and test-mode limits.
- Long GUI work belongs in Qt worker patterns, not the UI thread.

## References

- Run contract: `RUNSPEC.md`
- Session contract: `SESSION_PLAN.md`
- Runtime/export flow: `RUNTIME_EXECUTION.md`
- Engine boundary: `ENGINE_INTERFACE.md`
