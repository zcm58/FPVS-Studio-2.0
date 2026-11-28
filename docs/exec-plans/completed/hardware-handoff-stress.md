# Recorder support and hardware handoff checks

Status: Completed

## Software checks

Studio compiled fresh synthetic sessions on Windows. A separate Toolbox
process opened their setup, completed-session and study exports. The 17
configurations covered all seven recorder selections, each supported cap, and
an unspecified cap. All 45 processing handoffs succeeded. All six EGI and ANT
processing attempts pointed to the corresponding marker diagnostic. Repeating
each study export produced identical bytes. A mixed 17-visit study preserved
all 15 processing visits and identified both marker-only visits for review.

The cohort stress test exercised 320 visits, including 280 matched and 40
deferred. Changed assignments, stale approvals, and incompatible raw files
required review. Each marker diagnostic matched 1,081 markers in a synthetic
15-minute recording and rejected a missing, extra or substituted marker and
an inconsistent Studio visit summary. The recording inputs retained their
original hashes. The stress tests also covered truncated signals, out-of-range
BrainVision markers and repeated exports after an input failed validation.
A second condition exported from the same output connection retained trigger
indices 3, 4 and 5. Toolbox matched that per-run log to the saved native data.

Recording settings display the lab's trigger-support classification next to
the selected recorder. Visible Windows Qt tests used fake hardware. Each
run retains its actual output and receipt evidence. Independent recording logs
are needed to distinguish visits with identical marker sequences. Physical
receipt and display timing for EGI and ANT still require a bench.
