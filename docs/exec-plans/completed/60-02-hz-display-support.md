# 60.02 Hz display support

Status: Completed

Allow authors to select 60.02 Hz in the existing approved refresh selector.
On Windows, recognize a fixed 60 Hz desktop mode whose configured video signal
is near 60.02 Hz. Keep the existing 60 Hz target usable on that dual-reported
mode so saved projects still launch. Detection and launch verification remain
read-only and tied to the selected display.

Use the canonical authored rate for whole-frame compilation, expected duration,
and realized protocol rates. Keep the frame counts, marker ordering, and
whole-oddball-cycle constraint. Reference both the original protocol duration
and the compiled frame duration in the timing investigation. Use the ±5 ms limit
for comparison only. The bench requires no runtime timing-policy change.

Verify core validation and compilation, Windows mode classification and launch
compatibility, and selector/detection behavior. Repeat the fixed 144-cycle image
condition on the built-in 60.02 Hz signal, checking the 7,200 frame intervals and
145 local markers.

The November 14, 2026 fullscreen repeats used a configured 60.020425 Hz signal.
Both completed and delivered all 145 markers with no intervals over 1.5 refreshes.
Their software endpoints were 1.545 and 3.769 ms beyond the compiled 119.960013 s
duration, and 38.442 and 36.218 ms short of 120 s. Screen light was unmeasured.

Registered Qt smoke tests cover the rate selector and detection. For a visible
GUI smoke test, open the Experiment timing settings on
the selected Windows display, check refresh, confirm 60.02 Hz and the computed
rates, and inspect the current Setup size and both Run export modes.
