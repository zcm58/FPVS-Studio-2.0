# Windows refresh-rate recommendation

Status: Active

Show the highest fixed rate Windows offers at the current resolution when the
presentation display is configured at 60 Hz. Run the read-only query in a worker
before the Display refresh check, Run preflight, and Home or Run launch. The
operator needs to identify the display and choose a rate supported by Studio timing
checks. Let users continue at 60 Hz or open Advanced display settings and retry.

Use a modal with a 520 × 280 minimum and a 560 × 300 default. Verify supported,
mixed, and unsupported-only rates, selected display context, the keyboard default,
settings launch failure, dismissal, and button fit. Keep the native and PsychoPy
launch checks authoritative.

For visible smoke, use a 120 Hz-capable Windows display set to fixed 60 Hz at its
current resolution. Click **Check refresh rate** and select that display. At both
dialog sizes, verify the 60/120 comparison, display context, and both actions.
Press Enter to open Settings, select fixed 120 Hz, and rerun the check on the same
display. Repeat from Home launch and Run preflight at 60 Hz, including Escape.

Non-Qt verification after the advisory polish passed 180 GUI-focused tests and
6,237 repository precommit tests, with 34 skips. The native adapter read this
host's fixed 60 Hz configuration without finding a higher rate at its current
resolution. Registered Qt coverage uses fake display modes and a stub Windows
Settings launcher. Visible modal checks and confirmation on a display offering
both 60 Hz and 120 Hz remain pending.
