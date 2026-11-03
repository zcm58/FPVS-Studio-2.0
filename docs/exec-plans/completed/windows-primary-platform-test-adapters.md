# Windows-primary platform test adapters

Status: Completed

## Requested outcome

Keep Windows as Studio's primary authoring/acquisition platform while making its
tests runnable on a secondary macOS source host. Test adapters must select the
intended platform at the owning seam, rather than changing the process-wide host
or bypassing production Mac safeguards. Inventory local Python environments and
remove only confirmed obsolete environments; preserve working project environments
and the interpreter on which Studio's active `.venv` depends. Commit and push the
verified changes together with the preceding Mac environment repair.

## Boundaries and implementation

- Preserve compiled contracts, persistence, acquisition policy and engine scheduling.
- Keep primary Windows behavior assertions; give fake engines/launchers explicit
  platform adapters and retain independent Mac source/Retina/process coverage.
- Make primary Windows type checking explicit and check the secondary Mac adapters
  separately. Resolve actual Mac adapter type errors without changing runtime flow.
- Keep Qt opt-in and native-service/hardware restrictions. The user has approved the
  visible Mac environment; use controlled GUI services, never offscreen execution.
- Keep verification audits equivalent on both hosts. Use an official temporary
  PowerShell distribution for existing audits instead of replacing their rules.

## Work and acceptance

- [x] Complete environment inventory and any justified cleanup.
- [x] Add focused platform test adapters and adapter regression coverage.
- [x] Run the full safe suite on the Mac with Windows contracts explicit.
- [x] Run focused Mac checks and both type passes; record visible Qt limitations.
- [x] Update canonical verification guidance and prepare the verified commit/push.

## Environment cleanup

Inventory found three project environments. Preserve Studio `.venv` and its required
repository-local standalone CPython 3.10.20 base; preserve Toolbox `.venv` and its
working uv-managed CPython 3.13.5. Removed `~/PyCharmMiscProject/.venv` (Python 3.9.6):
the parent held only IDE metadata and the environment, with no source or running
interpreter. The incomplete Studio `.venv3.10` created during the preceding repair
was also removed. No system Python, working project environment, cached Library
bundle, real project or normal Studio setting was removed.

Studio's editable `dev,engine` install passes `pip check`, with packaging 25.0,
PySide6/shiboken6 6.11.3, PyQt6 6.11.0 and PsychoPy 2026.2.5. PyCharm's Studio
interpreter already points to `.venv/bin/python`. Removal of the obsolete Misc SDK's
IDE registration remains a metadata follow-up: the Mac is locked and computer use
cannot access PyCharm. The environment itself is gone.

## Implementation and verification boundaries

`tests/platform_adapters.py` gives each owner a local platform view, so primary
Windows launch/recording/rendering contracts run on a Mac without changing the
process-wide host. Mac display, credential, native-file, Retina and process tests
use the same boundary and retain their refusal/error assertions. Shared fake-engine
tests now cover both backing-pixel success and refusal through the real preparation
path. Private-child test commands resolve POSIX executable links and retain parent
imports; the production helper's executable/link security guard stays intact.

Repo mypy explicitly checks all source for Windows, then six Mac adapter owners
with Darwin branches enabled. Precise launch-keyword types and a non-optional
validated display rate correct Mac typing without changing launch behavior. Removed
a redundant method-local `sys` import so the existing controller owner can be tested.
Native Python/PowerShell launchers preserve environment priority and POSIX links;
Mac setup reuses `.venv`. The existing source CI lane now runs primary Windows repo
precommit before the secondary Mac jobs. No new GUI, persistence, scientific timing
or acquisition behavior is introduced.

Verification uses the repaired `.venv` on macOS 26.5.2/arm64. A verified official
temporary PowerShell 7.6.9 runs the original audits rather than replacing/skipping
their rules. Native wrapper integration also runs from a different working directory.
Local Windows-policy tests and Windows-targeted mypy are not native Windows execution;
the added CI gate must report its own result after push.

Final local verification:

- Native `scripts/verify.ps1 -Scope repo -Tier precommit -Workers 4`: **4,973 passed,
  64 native-platform/filesystem skips, 24 subtests passed**. Changed-file Ruff,
  compilation, original PowerShell audits, Windows mypy (266 source files) and
  Darwin adapter mypy (six owners) passed.
- Mac focused: **1,376 passed, 15 platform/native-opt-in skips**. The final added
  PowerShell-wrapper test subsequently passed in the 37-case harness selection
  and full precommit above. Config validation passed all 15 scopes.
- `pip check`, whitespace checks and explicit Windows/Linux dependency-marker
  regression assertions passed. No Windows/Linux dependency range changed.

Further visible Qt execution is blocked by the locked Mac. The preceding repair's
76 approved visible Library/worker/shutdown tests and successful offline import of
the retained large bundle remain evidence, while the native QMessageBox failures,
original intermittent crash qualification and physical display/service/hardware
acceptance remain open in [Mac Phase 1](../active/macos-source-phase-1.md). No offscreen Qt,
real service enrollment, presentation run or hardware probe was used for this task.
