# Cross-Platform Display Refresh Verification

Status: Completed

## Objective

Extend connected-display refresh verification to Linux without weakening or replacing
the existing exact Windows `QueryDisplayConfig` path. Keep PsychoPy responsible only
for confirming stable fullscreen frame delivery, and keep compiled frame schedules and
persisted project formats unchanged.

## User workflow

- Setup's refresh detection and runtime preflight query the active primary/default
  display through a platform-owned native adapter.
- Windows continues to use the exact rational primary mode and reject Dynamic Refresh
  Rate.
- KDE Linux uses structured KScreen output to select the enabled priority display,
  resolve its current mode, and reject `Always` or `Automatic` VRR policies.
- Linux X11 uses the active primary `xrandr` mode when KScreen is unavailable.
- The native mode selects one approved FPVS refresh target, then PsychoPy confirms
  stable fullscreen delivery and material agreement before launch continues.
- Missing, ambiguous, unsupported, variable-refresh, non-approved, or unstable modes
  remain blocking with platform-specific actionable errors.

## Implementation boundaries

- Runtime owns a neutral active-display mode contract and all OS/display-server
  adapters; runtime remains independent of PySide6.
- The existing Windows adapter remains unchanged behind the new neutral selector.
- Linux adapters execute read-only native display queries and do not modify display
  configuration.
- GUI workers continue to perform detection off the UI thread and widgets only render
  the neutral verification result.
- PsychoPy remains lazily imported inside the engine layer.
- `ProjectFile`, `RunSpec`, `SessionPlan`, execution exports, and scheduling behavior do
  not change.

## Verification

- Unit coverage exercises KDE JSON selection, current-mode parsing, VRR rejection,
  command failures, Windows rational preservation, Linux approved-rate classification,
  native versus PsychoPy disagreement, and runtime compiled-rate mismatch.
- Registered pytest-qt coverage exercises platform-neutral success, busy, and failure
  status copy at the Setup Wizard's `1120x720` default size. Per repository policy it
  remains CI-pending and was not run locally.
- Live read-only validation on KDE Plasma/Wayland selected `DP-2` at `239.914 Hz`,
  classified it as the approved `240 Hz` target, and detected the active `Automatic`
  Adaptive Sync policy before PsychoPy measurement.
- Ruff passed, mypy passed across all `118` source files, and all `374` safe unit tests
  passed. The PowerShell verification wrapper was unavailable on this Linux machine, so
  its underlying Python checks were run directly.

## Assumptions

- The current launch path still targets the primary/default fullscreen display and does
  not expose display selection.
- KScreen priority identifies KDE's primary/default output; X11's `primary` marker does
  the same for XRandR.
- Linux-reported floating refresh values are native mode metadata rather than exact
  rational clock contracts, so they select the nearest approved FPVS rate within the
  existing measurement tolerance before PsychoPy validates delivery.
