# AGENTS.md

## Repository guardrails

- Read this file and any nested `AGENTS.md` files in directories you touch before editing.
- Keep editable project models in `src/fpvs_studio/core/models.py`.
- Keep the compiled execution contract in `src/fpvs_studio/core/run_spec.py`.
- Keep the compiled multi-condition session contract in `src/fpvs_studio/core/session_plan.py`.
- Keep execution-result/export contracts in `src/fpvs_studio/core/execution.py`.
- The compiler must transform project models into `RunSpec`; runtime and engines consume `RunSpec`, not `ProjectFile`.
- Session compilation must transform project models/session settings into `SessionPlan`; runtime consumes `SessionPlan` and iterates its ordered `RunSpec` entries.
- Session compilation owns realized fixation target-count selection for each ordered run (including randomized/no-immediate-repeat behavior when enabled); do not move that logic into GUI or runtime.
- Runtime execution must transform `RunSpec` / `SessionPlan` playback into core-owned execution-result contracts; exporters serialize those contracts without moving them into engine code.
- Runtime-only launch or machine options must stay outside `RunSpec`.
- Runtime owns inter-condition and inter-block session flow; engines render instruction, break, and completion screens.
- Runtime owns fixation-accuracy scoring and condition-level participant feedback flow; engines render the feedback screen content.
- Only code under `src/fpvs_studio/engines/` may import PsychoPy, and those imports must stay lazy inside the engine implementation.
- The PySide6 GUI is a first-class application surface in this phase; do not add end-user dependency fallbacks or alternate non-GUI modes around missing GUI dependencies.
- Preprocessing owns validated assets/manifests and must not depend on PsychoPy or runtime/engine code.
- `RunSpec` must remain single-condition. Do not merge multiple conditions into one `RunSpec`.
- Represent execution timing in frames inside `RunSpec`; do not reintroduce sleep-based timing abstractions.
- Fixation accuracy behavior is an engagement task; it must not alter FPVS base/oddball scheduling.
- GUI launch flows must stay honest about the currently supported runtime path; if launch remains test-mode oriented, keep that reflected in labels and help text.
- Fullscreen presentation behavior belongs to runtime launch settings and engine window creation, not widget logic.
