# Mac repair completion reports

Status: Completed implementation and service rollout (2026-11-16)

## Authorized outcome

Add `Repair Mac 2.command` and `Repair Mac 2.py` beside the original source repair entry point. Repair the
reported Apple Silicon SciPy load failure, make dependency errors specific, and
automatically send a concise completion report through reusable reporting code.
Keep the original repair entry point and unrelated workspace edits.

## Boundaries and decisions

- Keep Python 3.10 and the existing PsychoPy range; constrain SciPy on macOS to
  1.14.1, whose official CPython 3.10 arm64 wheel avoids the malformed zero-fill
  section found in 1.15.3. Native Mac acceptance remains required.
- Setup must exercise engine-owned lazy imports before declaring success.
- Keep one repair implementation. The second entry point selects automatic
  structured completion reporting, including the final PyCharm restart outcome.
- Support owns a standard-library-only workflow reporter usable when optional
  application dependencies cannot load. Bounded structured reports include OS,
  architecture, package versions, checks, actions and outcome; raw pip output stays
  local. Honor saved automatic-report opt-out and disabled reporting origins.
- `../FPVS-Studio-Feedback` owns installation registration, strict intake, quotas,
  idempotent receipts and existing maintainer notification delivery. Current service
  source lacks the automatic-crash endpoints described by older desktop docs;
  add the required workflow protocol explicitly rather than assuming it exists.

## Verification

1. Dependency/loader regression tests and Mac setup import gate.
2. Structured summary, fresh/broken environment, canceled/pending IDE restart,
   opt-out, offline/ambiguous delivery and duplicate receipt tests.
3. Service schema/authentication/quotas and completion notification tests.
4. Desktop macOS/repo focused checks and repo precommit; backend checks and dry-run.
5. Verify service rollout availability; report native Mac/visible GUI limitations
   separately. No local Qt execution or hardware claims.

## Progress

- [x] Diagnose log and compare official SciPy wheels; confirm current source hashes.
- [x] Inspect desktop and service contracts; assign implementation ownership.
- [x] Implement and integrate source entry point, summaries and automatic reporter.
- [x] Implement SciPy selection and accurate import errors.
- [x] Implement and verify service intake and delivery.
- [x] Run integrated checks and update canonical docs.

## Retained evidence

- Default-branch release checkout: 6,404 non-Qt tests passed, 41 platform/permission
  skips and 24 passing subtests. The sole failure was the architecture-map word
  budget; its added entry was shortened and the documentation checks rerun.
  Ruff, compilation, Windows/Darwin mypy and repository audits passed.
  Verification used an explicit short, forward-slash pytest temporary path inside
  the task scratch directory; default nesting exceeds Windows path limits.
- The final repair review added regression coverage for successive failure causes
  and detached reporting errors: 143 focused tests passed. A reporting failure
  cannot change the repair outcome or open the manual/browser submission flow.
- Feedback service commit `5d7f220` deployed migration 0006 and production workflow
  intake on 2026-11-16. All 44 service tests and both deployment dry runs passed.
  The actual Studio Python client submitted one explicitly synthetic production
  report; private Feedback issue 12 was created and email delivery was confirmed
  once. The disposable installation was revoked; staging intake/delivery restored
  to disabled. The service's `DEPLOYMENT.md` retains exact rollout/receipt evidence.
- Native repair on the affected Mac, the completion window and PyCharm restart
  remain physical acceptance checks under [macOS Phase 1](../active/macos-source-phase-1.md);
  backend acceptance does not establish those. No local Qt session was launched.
