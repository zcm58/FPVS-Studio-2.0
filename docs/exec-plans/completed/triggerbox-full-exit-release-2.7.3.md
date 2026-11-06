# TriggerBox full-exit guidance and Studio 2.7.3

Status: Completed

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

## Release acceptance and publication

Source `22a2c8b324355489b0b4dee43dbbafd90c0f015b` was pushed to master and bound
to annotated `v2.7.3`. The clean isolated checkout `C:\Users\zcm58\fa273` built
label `release-2.7.3`; retained evidence is in the main checkout's
`build/release-2.7.3-evidence/`. All non-Studio package versions match 2.7.2.

- Packaging focused: 192 passed. Exact-source precommit: 5,520 passed, 32
  platform/permission skips and 24 passing subtests, with audits and Windows/macOS
  type checks passing. The full safe suite completed in 685.94 seconds.
- All 7,987 extracted installer files match the staged inventory, SHA-256
  `cdd0a0073cd4dd4b9369e182b8bd66cf26700764ab398f8f9ef2941ecbcd46e6`.
  All 272 Studio and 25 updater embedded modules match the exact candidate source.
  Third-party code, native libraries, bootstrap and base libraries match the
  authenticated 2.7.2 baseline. The same 21 build warnings remain; none were added.
- Visible packaged Studio passed startup, frozen/metadata version 2.7.3, runtime
  imports and control/layout checks. Independent updater update/repair checks passed
  with network and installer execution disabled; both screenshots were inspected.
- [Exact-source CI](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/42157625752)
  passed Windows, Intel/Apple Silicon Mac, Mac exports on Windows and both Mac-origin
  return checks. Documentation CI passed too.

[v2.7.3](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.7.3) was published
at `2026-11-06T03:57:37Z` as latest, stable and immutable, release ID `436082351`.
The exact source/tag, notes and four draft assets were verified before publication.
Independent public downloads match all local sizes/hashes; release and all four
asset attestations verify. Ten candidate and ten live updater cases passed,
including old/current versions, explicit repair and downgrade rejection.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.7.3.exe` | 301,056,024 | `aac2e10ce9fc8edc26a3c6faac0ca33a9d567f73a73bb7a00701161a9d74b465` |
| `FPVS-Studio-Setup-2.7.3.exe.sha256` | 95 | `4fee290793d722abee290f776d5001d44dbc2e13df69e7119b70b0eb60994d97` |
| `FPVS-Studio-Update-2.7.3.json` | 107 | `670e0320f2e877251099e446faf8d71d82194f9b9f40616d021e79ab6f00a585` |
| `FPVS-Studio-Update-2.7.3.json.sha256` | 97 | `cfb699db06ec4fa8afbd6b9806e0e9aeec3ef6641e9b296ad0ff4bc6f02450f8` |

No production installer was executed. Physical EEG receipt, timing and actual
port-owner diagnosis on the affected PC remain separate hardware acceptance tasks.
User projects, settings, installation and unrelated untracked files were preserved.
