# TriggerBox full-exit guidance and Studio 2.7.3

Status: Active

## Scope and authorization

The user requested explicit guidance that TriggerBox testing software must fully
exit to release its COM port, plus investigation of other Windows causes and
whether Studio can take priority ownership. Carry forward the earlier authorized
commit/push/release workflow and visible fake-hardware Qt checks. Published 2.7.2
is immutable; this follow-up requires a new patch installer.

Change only user-facing wording, its tests and documentation. Preserve serial
ownership, native writes, timing, compiled contracts and diagnostic details.
Do not install vendor tools/drivers, open actual COM ports, terminate other apps,
force-close their handles or claim that a specific owner has been detected.

## Implementation and evidence

- Shared busy-port errors, legacy launch explanations, Recording Setup and its
  tooltip, and the USB launch reminder now require full exit. Pressing Stop can
  leave the port occupied. Other apps using the selected port are named as a
  possibility; the raw access error remains in diagnostic details.
- Windows documentation establishes exclusive ownership and device permissions
  as distinct access-denial mechanisms. CPU scheduling priority does not evict a
  port owner. Microsoft warns that forcibly closing handles can destabilize an
  application or Windows. The exact cause on the other PC remains unproven.
- Vendor documentation notes that original rev.02 COM entries can remain listed
  after unplugging. Port metadata is not proof of attachment or marker receipt.
  Sources and persistent-failure recovery are in `docs/RUNTIME_EXECUTION.md`.
- Existing regression expectations failed before the wording change (three
  selected cases), then all 405 affected backend/explanation/runtime checks passed;
  one Windows symlink-privilege case skipped. Trigger focused: 316 passed.
- Visible GUI: 77 passed, including setup and Detect states at 700x640 in both
  themes, USB/parallel reminders at 480x170 and 520x180, and busy-port popups.
  Safe GUI focused: 178 passed; documentation: 13 passed. Ruff/compilation and
  whitespace checks passed. No layout changes were required.
- Independent factual review passed. The prior published baseline is 2.7.2 at
  `e8c77a3b30383f7bd397951a8619e848f31d61df`; user-owned untracked files and
  retained release artifacts remain outside scope.

## Release gates

1. Refresh canonical package metadata to 2.7.3 without changing dependencies;
   run packaging focused and repository precommit checks.
2. Build from a clean isolated exact commit, verify frozen source/dependencies
   against authenticated 2.7.2, and run approved visible packaged checks.
3. Verify exact-source CI and updater selection, stage all four assets as a draft,
   compare remote hashes, publish immutable/latest, then independently verify
   public downloads and release attestations. No production installer execution.

Build, exact-source precommit/CI, packaged acceptance and publication are pending.
Physical EEG receipt and timing remain separate hardware acceptance tasks.
