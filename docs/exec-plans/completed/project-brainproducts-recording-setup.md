# Project Brain Products recording setup

Status: Completed

On the first normal launch with a Brain Products device, ask the operator to
confirm the amplifier and Recorder sampling rate for the open project. Prefill
the computer default when inherited. Apply saves through the existing atomic
project recording writer before participant entry. Cancel or a failed save
stops launch. A complete project override opens directly on later launches.
Keep Test/Pilot and the runtime's independent recording validation.

Use Studio's standard modal error for failed detection, invalid Apply, and
recording preference save failures. Keep discovery progress, results, and
instructions in the setup dialog. Exercise Apply/Cancel, Home/Run/re-run entry
points, reopened project and computer settings, and the 700×640 layout.

The focused GUI and non-Qt recording, persistence and error checks passed.
The registered Qt tests cover modal errors, launch cancellation and failed
saves, project reopen, and layout. Visible Windows and hardware checks remain
manual. See the acceptance steps in [GUI workflow](../../GUI_WORKFLOW.md).
