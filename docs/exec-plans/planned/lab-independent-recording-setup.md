# Lab-Independent Recording Setup

Status: Planned

## Decision And Purpose

The user accepted this future direction on 2026-09-05. Implementation has not started.
This document records a separate future project; it does not authorize changing the
current setup redesign or weakening existing recording checks. Move it to `active/`
when implementation becomes the selected task.

Give researchers named recording profiles for this computer: participant display,
supported trigger output and serial port, and recording-confirmation policy. Keep the
existing Sophia behavior available as an explicit lab preset.

## Problem, Alternative, And Benefit

The application assumes an enabled serial connection on COM3, verifies the primary
display, and launches on the default display. Settings exposes the Sophia recording
confirmation, which defaults on and names NERD Lab and BioSemi. These choices suit the
original installation but are difficult to inspect or change through the GUI elsewhere.

Replace those implicit assumptions with a concise Recording setup editor and a visible
selected-profile summary before launch. Researchers select an identified participant
monitor and a supported output configuration, then verify that exact configuration.

This makes the machine configuration understandable without editing project files.
Named profiles support different acquisition arrangements on one computer, while local
ownership prevents a transferred experiment from silently inheriting another lab's port
or monitor. The expected benefit is fewer setup mistakes and easier adoption across FPVS
labs; it remains a design hypothesis pending operator walkthroughs.

## Current Evidence And Reuse

- [TriggerSettings](../../../src/fpvs_studio/core/models.py) stores SERIAL, enabled,
  COM3, baudrate, pulse and reset settings in the editable project today.
- [LaunchSettings](../../../src/fpvs_studio/runtime/launcher.py) already accepts a
  display index and serial options; this is an existing runtime capability.
- [document_runtime.py](../../../src/fpvs_studio/gui/document_runtime.py) composes
  project trigger settings into runtime launch options.
- [run_page.py](../../../src/fpvs_studio/gui/run_page.py) launches with
  `display_index=None` and fullscreen enabled, and owns the current recording prompt.
- [display_refresh.py](../../../src/fpvs_studio/runtime/display_refresh.py) verifies
  the primary display through native mode queries and engine measurement; simply
  exposing an engine display index would not make selected-monitor verification work.
- [controller.py](../../../src/fpvs_studio/gui/controller.py) persists the default-on
  Sophia preference; [settings_dialog.py](../../../src/fpvs_studio/gui/settings_dialog.py)
  presents it. [triggers](../../../src/fpvs_studio/triggers) supplies serial and null
  adapters. Named profiles, monitor identity reconciliation, and migration UX are new.

## Proposed User Workflow

1. Open Recording setup from Settings; create or choose a clearly named local profile.
2. Choose the participant display from identifiable connected devices. Show a concise
   name, resolution, configured refresh and an explicit Identify display action.
3. Configure supported output: serial device/port and applicable communication values,
   or an explicitly chosen no-output configuration whose launch meaning is visible.
4. Choose a generic recording confirmation or the Sophia lab preset. Preserve the
   existing preset's wording and typed confirmation behavior for users who select it.
5. Review and apply the profile, then verify the selected monitor. Applying edits
   invalidates affected verification; saving a profile does not prove hardware readiness.
6. Before launch, show profile, participant monitor, output configuration and verification
   status. Missing devices or unresolved profile selection lead back to Recording setup.

Use shared components, semantic status colors, wrapping, and one clear Apply action.
Target `760x620` minimum/default for the editor and the existing `1120x720` main window;
confirm this budget with long device/profile names and every error state before coding.
Full device identities must be accessible through details even when summaries elide.

## Decisions To Resolve Before Implementation

- Define a versioned, per-user local profile store behind the app-preference service.
  Specify its neutral data contract, validation, stable profile identifiers and backup
  behavior before choosing the serializer; GUI widgets must not own persistence rules.
- Decide whether profile selection is global or locally associated with a project.
  Either choice stays outside portable experiment and compiled timing contracts.
- Define the supported Windows display-identity key and the mapping from native device
  identity to the engine's current screen index. Document duplicate/ambiguous identities,
  adapter replacement and unsupported platform behavior explicitly.
- Decide the smallest first-release trigger editor and no-output labeling. A rehearsal
  policy is a separate plan; no-output selection must not imply that timing checks passed.

## Display Identity And Verification Contract

Selection, native refresh query, fullscreen verification, and participant playback must
refer to the same physical display. Resolve a persisted OS identity to current devices
and to the engine index at verification and launch; never persist an index as identity.
Record the resolved identity and mode with verification evidence, alongside relevant
profile values. Reordering monitors must not redirect playback to a different monitor.

Disconnect, ambiguous identity, resolution/refresh change, profile edit, or a changed
identity-to-engine mapping invalidates the relevant evidence and blocks production
launch until resolved. Preserve existing exact refresh handling, stability checks,
VRR rejection, fullscreen requirements and timing QC. Do not silently use the primary
monitor, nearest display, unverified mode, or a null trigger after a configured failure.

## Legacy Resolution And Migration

Inventory existing project trigger fields and persisted Sophia preferences first.
Present their effective values when offering a local profile; do not invent a successful
hardware match from a legacy COM port or default display index.

Define and test precedence explicitly: a user-selected valid local profile supplies
machine launch values; existing projects without that selection retain a clearly labeled
legacy configuration until the user reviews and adopts a profile. Resolve and verify
that legacy configuration before production launch rather than silently substituting it
when a named profile is missing. A missing/deleted profile requires explicit selection.

Keep legacy project fields readable and round-trippable in the first delivery. Do not
silently rewrite project JSON or remove fields; any later schema cleanup needs its own
migration decision. Preserve scientific trigger codes, event order and timing unchanged.

## Implementation Phases And Owners

1. Define profile storage, precedence, migration cases and selected-display identity
   contract. GUI/controller owns preference editing; runtime owns neutral launch resolution.
2. Extend runtime platform display adapters and verification to the chosen identity.
   Engines translate resolved runtime display choices into presentation operations;
   PsychoPy imports remain lazy and confined to `engines/`.
3. Implement profile editing, selection, full-value details and verification invalidation.
   Runtime remains responsible for preflight and exporting actual launch evidence;
   `triggers/` remains responsible only for supported device communication.
4. Connect launch summaries and explicit repair actions, exercise legacy migration, and
   update architecture, GUI workflow, runtime guidance and agent verification routes.

Machine identifiers, ports and profile state must remain outside `RunSpec` and
`SessionPlan`. Preserve core compilation, session scheduling and export formats unless
an explicit compatible extension is required to record runtime configuration evidence.

## Verification And Acceptance

- Unit-test profile validation/round trips, migration precedence, missing/deleted profiles,
  serial errors, explicit no-output selection and Sophia-preset preservation with fakes.
- Test display reorder, duplicate identities, disconnect/reconnect, mode changes and
  mismatched native/engine mappings; unresolved or stale verification must block launch.
- Add registered pytest-qt coverage for Apply/Cancel, keyboard navigation, busy/error
  states, profile changes, full identities and no clipping at the documented sizes.
- Run focused `gui`, `runtime`, and `triggers` scopes as implicated, then repo precommit.
  Do not run Qt locally without a user-approved safe visible environment; never use
  offscreen execution. Ordinary checks must not open hardware or transmit triggers.
- In an approved visible hardware session, identify two monitors, verify and launch on
  the chosen one, then disconnect/reorder it and confirm blocking or correct remapping.
  Check busy/missing serial devices and the Sophia preset; send test markers only with
  explicit authorization and a known receiving setup. Report untested hardware cases.

Done means the selected physical display is the verified presentation display, effective
output configuration is visible, migration is explicit, and failures remain actionable.
Arbitrary EEG drivers, participant-intake redesign, automatic trigger fallback, and changes
to FPVS scheduling, fixation scoring or participant-task semantics are outside this plan.
