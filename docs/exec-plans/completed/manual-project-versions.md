# Manual project versions

Status: Completed

Native Windows workflow and storage regression checks passed.

- Capture the finished setup as version 1. For later protocol or stimulus edits,
  let the author choose whether to retain a restorable copy. Keep ordinary
  saves, opening projects and participant visits free of archive I/O.
- Keep as-run identities and post-collection review independent of that choice.
  Preserve existing history, standalone copies and explicit restoration.
- Expose numbered versions in Manage Projects and test normal Open, historical
  inspection, rollback and reopening after a save without a checkpoint.
- Regression coverage instruments stimulus capture on routine paths and exercises
  the real Setup and Manage Projects controls. A Library install keeps its own
  install backup and creates a working revision. Its first numbered rollback
  point follows the same Setup save rule.
