# Sequential stimulus order

Status: Completed

1. Reproduce a same-image repeat between two passes through a shuffled pool when
   the other role intervenes. Verify the seeded scheduler prevents that repeat
   when the pool contains more than one distinct file, with counts and cadence intact.
2. Add **Sequential** to **Display & Session > Image / word display order**. Use
   the existing case-insensitive source filename order and authored word-list order.
   Verify that each role loops independently in the selected order and that saving,
   compiling, and exporting preserve the selected policy.
3. Run focused GUI and compiler checks and safe precommit. Cover the new choice
   in the registered 1120x820 Setup smoke for both appearances. On a visible setup,
   select Sequential, check Review, then save and reopen the project to confirm
   that the selection is retained.

Sequential is a project setting for ordinary FPVS. Stored compiled runs retain
their schedules. Runtime and engines continue to consume those schedules directly.

## Evidence

- The refill regression reproduced for separate and overlapping image paths before
  the fix. A 100-seed check of the 48-image, 480-slot design retained 8 base and
  2 oddball presentations per image in every run, with no repeat at any refill.
- The updated compiler baselines differ only in image paths and stimulus IDs
  within ordinary image schedules. Word and native AB baselines matched exactly.
- Compiler focused passed 813 tests and GUI focused passed 180 safe tests.
  Precommit passed type and documentation audits and 6,463 unit tests. The
  follow-up to its 46 failures shortened the Windows test paths and corrected the
  architecture word budget. That rerun passed 45 tests and skipped one because
  this Windows account cannot create symlinks.
- The registered Setup smoke checks both themes at 1120x820. Visible execution
  remains manual.
