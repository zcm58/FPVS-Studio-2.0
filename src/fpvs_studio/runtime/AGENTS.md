# Runtime Guidance

Runtime owns separate-process orchestration, launch/preflight, participant/session
flow, scoring, recovery and exports. Read the relevant section of
`docs/RUNTIME_EXECUTION.md`; contracts are in core and playback is in engines.

## Execution Invariants

- Consume `RunSpec`/`SessionPlan`, never editable projects. Keep machine launch options
  outside compiled contracts; do not move session randomization/compilation here.
- Validate assets and timing before participant flow. Routine preflight checks paths
  and text without decoding entire image sets; engines prepare rendering resources.
- Use the configured display adapter and engine observation for refresh verification.
  Explicit Test/Pilot exceptions must not weaken normal-launch defaults.
- `recording.py` resolves hardware/configuration before visit reservation. Open selected
  transport before engine session flow. `unicorn_recorder.py` checks process/raw-file
  readiness in the launch worker, never the GUI thread or frame callbacks.
- Never fall back to null after hardware open/write failure. Normal launches use the
  selected hardware. Null requires explicit Test/Pilot; `serial_enabled=false` alone
  is insufficient. Preserve legacy selection precedence and pulse-spacing validation.
- Open/close one engine session; runtime sequences instructions, tasks, breaks,
  tutorials, feedback and runs. Engines render one neutral task step or run at a time.
  Runtime owns validation, branches, retries and fixation/answer scoring.
- Keep `escape` reserved for abort. Score fixation from same-clock hardware timestamps.
  Record trigger `sent` only after successful transport writes, export `error` and abort
  cleanly on failure. Trigger timestamps exclude warmup; drain pulses outside playback.

## Durability and Recovery

- Preserve participant visit reservations across full/compact exports, historical and
  aborted output. Snapshot reviewed electrodes/demographics per execution; repeat-visit
  bookkeeping never enters compiled timing.
- Checkpoint task responses and completed compact results before later screens. Commit
  numbered research rows idempotently before derived spreadsheets. Preserve partial
  answers, original errors and prior files when finalization/replacement fails.
- `condition_recovery.py` owns lifetime locks, immutable occurrence snapshots, rerun
  plans and separate acknowledgements. Discovery is read-only; never recompile missing
  original plans or overwrite earlier visits. Armed intent is not observed frame zero.
  Automatic notices omit acknowledged history; manual history retains it. Project-update
  readiness checks must not mutate evidence or claim a project-wide execution lock.
- `data_sharing.py` captures immutable eligible reports only after research commit
  proof, before derived XLSX. Recovery requires matching proof/rows; credentials/HTTP
  remain outside runtime. See `docs/DATA_SHARING.md`.
- `acquisition_evidence.py` writes versioned selection and sent/error evidence outside
  the frame loop, plus completed Toolbox handoffs after finalization. Configuration,
  operator association, receiver integrity and physical timing remain separate evidence.
- Full exports write numbered visit folders under `runs/`; compact writes project logs
  without detailed run folders. Canonical filenames/schema compatibility are in the
  runtime contract. Raw task answers stay out of general logs/summary workbooks.
- `attentional_blink_report.py` retains answered bursts after later aborts, separates
  SOA denominators and marks test/pilot identity. Never append through an unfinished
  journal line; preserve it for explicit repair. Native onset exports retain exact-grid
  coverage and legacy image headers remain compatible.

No Qt imports, direct PsychoPy use, engine-owned file formats or unqualified hardware
claims. Use the `runtime` focused route, adding related scopes for cross-layer changes
and repo precommit for shared behavior. Hardware acceptance remains a separate check.
