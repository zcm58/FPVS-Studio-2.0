# Named Local Recording Profiles

Status: Planned

Baseline reviewed: Studio 3.1.0 (2026-11-19)

The user accepted this future direction on 2026-09-05. The remaining goal is
to let an operator choose a named, reusable recording configuration on the
current computer and see the effective configuration before launching.

## Current baseline

- **Settings > Recording** already supports a computer default and a project
  override. With no explicit profile, keep the existing effective Recording
  settings and save actions. See [inline Recording settings](../completed/inline-recording-settings.md)
  and [default EEG hardware](../completed/default-eeg-hardware.md).
- Studio already lets operators choose the participant monitor for a launch.
  [Refresh verification](../../../src/fpvs_studio/runtime/display_refresh.py)
  queries the selected device and the engine resolves the playback screen.
  See [Windows monitor selection](../completed/experiment-monitor-selection.md)
  and [Mac monitor selection](../completed/macos-monitor-selection.md).
- The current [launch flow](../../GUI_WORKFLOW.md#launch) already supports the
  generic Recording Reminder for eligible BioSemi runs and a separate
  BrainVision reminder. Physical Unicorn receiver and timing acceptance have
  their own [recording plan](../active/unicorn-hybrid-black-support.md).

## Unattended baseline verification, 2026-11-19

At `313f0bd`, 89 non-Qt Windows tests passed for computer-default preferences,
launch settings and selected-monitor refresh and screen mapping. The recording
runtime checks also exercised project overrides and inherited defaults in
acquisition and handoff evidence. A broader launcher run and a targeted retry
hit the 30 s and 120 s test watchdogs in the existing repeated-participant
session check while resolving paths and writing temporary run exports. That
case remains unverified on this run. Named profile persistence, selection and
two-profile hardware acceptance are pending implementation.

## Profile workflow

1. In the existing Recording page, create or select a named local profile
   containing a participant display identity, a supported recording device
   and its transport settings, and the Recording Reminder policy.
2. Show the selected profile and effective display, transport/port and reminder
   before launch. Use the existing per-launch display chooser and show a clear
   way to select a device again when a saved match is missing or ambiguous.
3. Resolve the selected display to the current OS device and engine screen.
   Reuse the current refresh and hardware preflight for the resolved settings.
   Saving a profile supplies inputs to preflight. Verification evidence is
   tied to the resolved device, configured mode and applicable launch inputs.

## Decisions and implementation

1. Define a versioned local record and stable profile identifier in application
   preferences. Decide whether the active selection applies computer-wide or
   can be associated locally with a project. Document how an explicitly chosen
   profile interacts with an existing project override. Preserve existing
   settings and precedence when a profile has never been chosen. An explicitly
   referenced missing or deleted profile requires a new choice.
2. Check which device identities are stable enough to persist on each supported
   platform. Store identity outside the portable project, `RunSpec` and
   `SessionPlan`; resolve the current screen index at launch. Handle reorder,
   reconnect, duplicate identities and mode changes explicitly. Decide whether
   the existing chooser needs an Identify action based on an operator walkthrough.
3. Add the smallest profile editor to Settings > Recording using its existing
   fields. Pass the resolved settings through the existing launch/preflight
   owners and expose applicable errors and repair actions. Carry forward reminder
   eligibility and `Confirmed` handling, Test/Pilot behavior and effective trigger
   checks. A missing device or failed configured trigger requires explicit
   resolution before a recording launch.
4. Update the [GUI workflow](../../GUI_WORKFLOW.md) and owning runtime and
   architecture guidance once the workflow is implemented.

## Verification and acceptance

- Test local persistence, legacy defaults and precedence, missing profile
  references, device resolution and inactive/eligible reminder behavior. Cover
  monitor reorder and disconnect, mode change, ambiguous device identities,
  and failed trigger readiness using the existing launcher and verification tests.
- Verify save/reopen and transfer of a portable project without changing compiled
  timing, scientific event codes or the existing project format. Check the
  chosen preflight inputs and the actual engine screen in a fake-engine run.
- Register visible Qt coverage for profile selection and editing, legacy and
  unresolved states, keyboard access and clipping at the documented Settings
  minimum/default sizes. Run focused GUI/runtime/trigger routes and precommit.
- In an approved hardware session, use two profiles on one computer. Confirm
  the intended physical monitor and configured serial/receiver path, then
  demonstrate actionable failures for a disconnected display and unavailable
  transport. Record which combinations were exercised.

Done means operators can reuse named local setups, see their effective settings,
and safely resolve stale hardware choices using the existing launch checks.
