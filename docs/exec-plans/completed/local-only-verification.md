# Local-Only Verification

Status: Completed

## Goal

Make repository quality verification a local developer workflow instead of an
automated GitHub test gate. Preserve the existing focused, precommit, and optional
comprehensive checks while removing cloud-only terminology and configuration.

## User Workflow

- Run `./scripts/verify.ps1 -Scope <scope> -Tier focused` while developing.
- Run `./scripts/verify.ps1 -Scope repo -Tier precommit` before committing or merging
  shared changes.
- Run `./scripts/verify.ps1 -Scope repo -Tier full` only when the required optional
  dependencies are installed and a safe visible Qt environment has been explicitly
  approved.
- Do not depend on a GitHub test workflow to repeat those checks.

## Implementation

1. Remove `.github/workflows/ci.yml` while retaining the independent documentation
   build and publishing workflow.
2. Rename the verification tier `full-ci` to `full` and the scope configuration field
   `ci_tests` to `full_tests` without changing which tests each tier selects.
3. Keep normal `focused` and `precommit` verification non-Qt. Preserve the explicit
   `FPVS_ALLOW_QT_TESTS=1` opt-in for the optional full tier and prohibit local
   offscreen Qt execution.
4. Update current repository guidance, skills, planned work, wrappers, and regression
   tests to describe the local-only policy.

## Boundaries

- Do not change application behavior or test contents beyond verification-harness
  naming and policy assertions.
- Do not remove the GitHub Pages documentation workflow.
- Do not run Qt tests locally without approval for a safe visible environment.
- Leave earlier completed execution plans unchanged as historical implementation
  records.
- Preserve unrelated workspace files, including untracked output.

## Outcome

- GitHub no longer runs the repository test and code-quality workflow. The independent
  documentation build and publishing workflow remains unchanged.
- Focused and precommit verification are local and non-Qt, including when the caller
  has an inherited Qt opt-in environment variable.
- The optional comprehensive tier is now named `full`; it requires explicit Qt opt-in,
  rejects offscreen Qt, and retains the registered GUI and PsychoPy integration tests.
- Current guidance and planned work consistently describe the local-only policy.
- GitHub reported no branch protection or rulesets requiring the deleted quality-gate
  status.

## Verification

- `./scripts/verify.ps1 -CheckConfig` — passed for 12 scopes.
- `./scripts/verify.ps1 -Scope repo -Tier focused` — passed; 32 tests.
- `./scripts/verify.ps1 -Scope docs -Tier focused` — passed; 9 tests.
- `./scripts/verify.ps1 -Scope repo -Tier precommit` — passed; Ruff, compilation,
  mypy for 130 source files, repository/docs audits, and 604 tests passed with one
  expected Windows symlink-permission skip.
- `./scripts/verify.ps1 -Scope repo -Tier full -List` — passed and listed the expected
  comprehensive commands without executing Qt.
- Registered Qt tests were not run because no safe visible run was requested.
