# Project import progress

Status: Completed

Use the approved progress layout for the embedded import page and the Welcome
and Library dialog. Show current and completed stages once, reveal paths on
request, and use the shared animation preference. Keep the real failure on the
screen until the user closes it. Cancellation follows the Library worker's
existing commit boundary.

1. Match the stage rows to import and in-place update worker events.
2. Verify readable file wording, stage progress, and the outcome and path
   controls at minimum and default sizes in both themes.
3. Verify the ordinary import, Library cancellation and display review handoff
   using the existing worker and lifecycle contracts.

On 2026-11-16, the GUI focused checks passed 180 non-Qt tests and both affected
GUI test modules passed 111 tests on the laptop's built-in Windows display.
Visible checks covered light and dark themes, minimum and default sizes, reduced
motion, long file paths, cancellation, inline errors and the display-review handoff.
The inline failure screen keeps the existing diagnostic and bug reporting action
behind **Error details**.
