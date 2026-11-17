# Library update dialog refinement

Status: Completed

Researchers need to compare a Library update, choose how to download it, and see
what Studio is doing during the transfer. Use the existing Studio updater rail and
motion preference. Keep Library access, validation, backup, rollback and import
handoff in their existing owners.

1. Compact the review and use a focused activity view while downloading or applying.
   Verify long-form details and every action fit at minimum and default size.
2. Connect both transfer routes to reported bytes and show the in-place verification
   and apply stages. Verify progress, cancel and return to review through worker fakes.
3. Defer an automatic offer for 30 minutes per release when requested. Verify polling,
   manual access, later releases and the existing automatic-check preference.

The review uses 640×470 minimum and 700×500 default sizes. Worker-fake coverage
passed for byte reporting, stage changes, cancellation and reminder timing. The
registered Qt tests cover both themes, long details, motion settings and the
return to review.

Visible Windows smoke on the internal laptop panel at 100% scaling passed 60
dialog and shared-progress cases. Rendered review, download, apply and cancellation
states fit at both sizes. A synthetic Library result verified reminder dismissal
and manual reopening without contacting the service. Four surrounding Home, Setup
and recovery cases failed identically on the pre-change baseline.

Focused GUI and docs checks, platform type checks and repository audits passed.
Precommit's unit run passed 6,463 tests. The 45 cases affected by Windows path
length were rerun with a shorter pytest base path. Of those, 44 passed and one
was skipped because the Windows account cannot create symlinks.
