# Data sharing boundary

This GUI-neutral package owns project-local opt-in settings, the bounded durable
outbox, secure-store credentials and fixed-origin HTTP delivery. Core owns the
allowlisted wire models; runtime owns scoring and completion eligibility.

Never import GUI, engines or trigger code. No HTTP or credential operation belongs
in presentation callbacks. Credentials belong only in the operating-system secure
store. Settings are local sidecars, excluded from authored project/config/bundle
contracts. Every send rechecks opt-in and the registered protocol; paused reports
need an explicit release. Preserve immutable report bytes and UUIDs for retries.
For Library-linked projects, reuse `library_scope.py` and core's canonical Library
origin reader to require the exact installed item/version. A missing or malformed
version stays actionable; never substitute the latest catalog version.

Storage stays beneath the supplied active project root, rejects links/reparse
points, validates bounded regular files and replaces atomically. Malformed records
are actionable errors, never deleted or silently skipped. Reuse the existing
project reporting lock for atomic state transitions across threads and processes.

Reuse receipt-first archive cleanup after upload and before startup recovery.
Startup delivery rechecks saved protocol/scope/opt-in, preserves held reports and
skips comparison requests for unopened projects. A cleanup failure must not change
accepted status or cause another upload of an acknowledged record.

The canonical contract, operator workflow, automatic archive behavior and pending
live/visible acceptance are in `docs/DATA_SHARING.md` from the repository root.
