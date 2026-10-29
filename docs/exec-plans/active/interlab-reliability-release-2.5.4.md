# Inter-lab reliability and Studio 2.5.4

Status: Active

Date: 2026-10-29

## Authorized outcome

Pull remote changes, review Library and data-sharing workflows from the installed
Studio user's perspective, fix concrete low-risk defects, and commit, push and
publish the next GitHub patch release. Preserve projects, reports, credentials,
the working installation and unrelated UI behavior.

## Scope and acceptance

1. Fast-forward Studio and its clean OpenFPVS service checkout. Trace enrollment,
   catalog permissions, downloads/version checks, project submissions, report
   delivery and matched comparisons against their current owners and contracts.
2. Reproduce defects and add focused regression checks. Keep existing protocol,
   consent, immutable retry identity and secure-store boundaries. Run Library,
   data-sharing, GUI-safe and packaging checks, then repository precommit.
3. Commit the exact 2.5.4 candidate and build an isolated full Windows installer
   with the preserved dependency environment and update manifest. Verify frozen
   application source, ownership inventory, extracted payload, native dependency
   provenance, checksums and updater selection.
4. Publish the audited assets with short bullet notes. Independently verify public
   downloads, immutable GitHub attestations, the source tag and live updater choices.

The user approved visible compiled-app checks in an isolated test profile.
No installer, uninstaller, real experiment, hardware test, or authenticated research
upload is part of the local smoke. Source tests and mocked HTTP do not establish
real lab enrollment, email delivery or cross-lab upload acceptance.

## Progress

- Studio fast-forwarded from `3611a7c` to `79b315d`, including releases through
  2.5.3. OpenFPVS fast-forwarded from `f48aac6` to `9c86b5e`. Both started clean.
- Packaging baseline: 181 passed. Library baseline: 386 passed, three Windows
  symlink-permission skips and 24 subtests.
- Library project-version checks now respect fresh view-only permission before
  offering downloads. Focused Library checks passed 390 cases and 24 subtests,
  with three Windows symlink-permission skips. Safe GUI checks passed 95 and
  documentation checks passed ten. Both Library bugs failed before their fixes.
- Submission preparation could complete while a canceled worker drained, leaving
  prepared bytes detached from the retry controls. Retain those exact bytes and
  author identity without starting an upload until the user retries.
- OpenFPVS binds pending results credentials to the requested study. An explicit
  reset-and-retry flow will recover a rejected change of study/code, guarded by
  the exact pending credential and the existing reporting lock. Registered access
  and saved sharing choices remain intact.
- OpenFPVS contract checks: 62 passed. Anonymous live probes confirmed current
  Library/results authentication responses and the retired API upgrade response,
  with no redirects. No backend changes or deployment were needed.
- Data-sharing baseline passed 257 cases. Excessively nested bounded server-error
  JSON now becomes a protocol error instead of escaping the error classifier.
- The packaged smoke now requires frozen execution, redirects both Qt settings
  scopes, and renders synthetic Library/version/sharing states at their documented
  sizes. It records screenshots and control/layout checks without live HTTP.
- Only editable `fpvs-studio` metadata changed from 2.5.0 to 2.5.4 in the existing
  environment. All other installed distribution versions are unchanged and
  `pip check` passes. Build outputs use the isolated `release-2.5.4` label.
- Final targeted sharing checks passed 133 cases plus five confirmation/retry
  cases. Independent review found no blocking issue and passed 14 relevant cases.
  Safe GUI checks passed 95; packaging passed 183 and docs passed ten. Ruff,
  compilation, mypy and repository audits pass. Full safe precommit tests are
  running while the unchanged committed candidate is packaged; publication waits
  for their result and compiled/artifact checks.

## Evidence

Keep generated release evidence under ignored `build/release-2.5.4-evidence/`
and packaged artifacts under `dist/release-2.5.4/`. Detailed Library and reporting
contracts remain in `docs/EXPERIMENT_LIBRARY.md` and `docs/DATA_SHARING.md`.
