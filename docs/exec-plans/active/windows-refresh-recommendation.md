# Windows refresh-rate recommendation

Status: Active

## Current baseline

The advisory ships in [Studio 3.1.0](../completed/release-3.1.0.md). The native
adapter queries the selected Windows display at its current resolution in a
read-only worker. At 60 or 60.02 Hz, the dialog shows the highest available
fixed rate above the current rate and recommends the highest one Studio supports.
From Setup's refresh check, Run preflight or Home/Run launch, the operator can
continue into the normal native and PsychoPy checks or open Windows Advanced
display and retry.
The 60.02 Hz Toolbox advisory also appears when there is no higher mode.

## Remaining acceptance

- [ ] On a Windows display that offers fixed 60 Hz and 120 Hz at the same
  resolution, start at 60 Hz. In **Check refresh rate**, select that display and
  verify the 60/120 comparison, display number, resolution and both actions at
  520 × 280 and 560 × 300. Use Enter to open Advanced display and confirm Studio
  ends the pending action. Switch to 120 Hz and verify that **Check refresh rate**
  on the same display now passes the normal native and PsychoPy checks.
- [ ] Reset the display to 60 Hz. From Run preflight and Home/Run launch, verify
  that **Continue at 60 Hz** proceeds to normal checks and Escape cancels the
  pending action. Include a different primary display when available.
- [x] In an approved visible session, finish the mixed and unsupported-only mode,
  keyboard default and Settings-launch failure cases using the registered Qt
  coverage with fake modes. At 60.02 Hz, check the Toolbox copy and button fit at
  520 × 360 and 560 × 380, including the no-higher-mode case. Confirm Continue
  is the default when Studio has no higher supported option.

Close when the GUI maintainer and display operator record the Windows build,
display/driver, same-resolution mode list, observed workflow result, and dialog
checks. The owning [refresh-check contract](../../GUI_WORKFLOW.md#launch) and
[registered cases](../../../tests/gui/test_refresh_recommendation_dialog.py)
define the expected routing and recovery behavior.

## Office PC verification (November 19, 2026)

Studio's native query found one 1920 × 1080 display at fixed 60.02043 Hz.
Windows reported 48 Hz and 60 Hz at that resolution and offered no 120 Hz
mode. The real selected-display worker opened the 60.02 Hz timing advisory.
At 520 × 360 and 560 × 380 the Toolbox notice and both buttons fit. Enter
took the Continue path and Escape canceled without continuing.

All 119 focused native-adapter, display-selection and preflight tests passed.
The registered Qt recommendation and routing cases also passed with fake
modes and a stub Settings launcher. The physical 60/120 Hz switch still
requires a suitable display.

## Verification record

Non-Qt verification after the advisory polish passed 180 GUI-focused tests and
6,237 repository precommit tests, with 34 skips. The native adapter read this
host's fixed 60 Hz configuration without finding a higher rate at its current
resolution. Registered Qt coverage uses fake display modes and a stub Windows
Settings launcher.
