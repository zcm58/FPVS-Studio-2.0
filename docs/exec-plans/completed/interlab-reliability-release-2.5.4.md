# Inter-lab reliability and Studio 2.5.4

Status: Completed

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
  prepared bytes detached from the retry controls. Studio retains those exact bytes and
  author identity without starting an upload until the user retries.
- OpenFPVS binds pending results credentials to the requested study. An explicit
  reset-and-retry flow recovers a rejected change of study/code, guarded by
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
  compilation, mypy and repository audits pass. Full safe precommit and compiled
  artifact results are recorded below.

## Evidence

Keep generated release evidence under ignored `build/release-2.5.4-evidence/`
and packaged artifacts under `dist/release-2.5.4/`. Detailed Library and reporting
contracts remain in `docs/EXPERIMENT_LIBRARY.md` and `docs/DATA_SHARING.md`.

## Final verification and publication

- Full safe precommit: **3789 passed, 12 skipped, 24 subtests passed in 1152.04s (0:19:12)**. Mypy, Ruff, compilation and repository audits passed.
- Compiled Studio reports version 2.5.4 and frozen execution. All 20 synthetic
  Library, project-version and sharing dialog states pass control/layout checks at
  minimum/default sizes. Native confirmation defaults to No. Screenshots were
  reviewed in the dark theme; other themes and DPI settings were not qualified.
  Both Qt settings scopes are isolated.
- Studio and independent updater packaged checks passed. No source-mode Qt test, installer, uninstaller, experiment presentation or authenticated research upload was executed.
- All 7,987 full-installer payload hashes match the target ownership inventory. Its SHA-256 is `4eb54afcbe5d1285ea271407aabf680bfd44ce3859431f76c8d730de872e2e32`. All 245 Studio and 23 updater application/entry modules match committed source.
- All 491 Studio and 69 updater native inputs match the preserved audited 2.5.0
  source paths and hashes. The 4,448 Studio and 126 updater frozen dependency
  modules retain their sets and normalized code. All 21 distinct build warnings
  are unchanged from that baseline.
- Source `d7e020d70359e2fd0f224e8469f7bab659eee89d` is the exact `v2.5.4` target.
  All four draft asset sizes/hashes were checked before immutable publication at
  [v2.5.4](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.5.4).
  Independently downloaded assets and signed release/asset attestations pass.
- Ten candidate and 10 live updater cases pass, including current-version repair, downgrade rejection and the real bounded manifest fetch with an installation root supplied. Older installs select the full installer; no direct patch is advertised.
- Real lab approval, authenticated cross-machine transfers, email delivery, installation/upgrade/uninstall and physical EEG/display validation remain unrun. Service code was pulled and reviewed without deployment or production mutations.

## Published assets

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.5.4.exe` | 300811691 | `0117e5499103115919cff0b2799c32b16d133c34f7206fb868847ea7287ae55a` |
| `FPVS-Studio-Setup-2.5.4.exe.sha256` | 95 | `90fb27e7301974193d5db54cb4fd2f240856bb1b29953871a5f8f503ff6ede87` |
| `FPVS-Studio-Update-2.5.4.json` | 107 | `084c7d3a920eae01f99e65c5b3ae7ea702daea7f55f164eec61bd64bd5afd82c` |
| `FPVS-Studio-Update-2.5.4.json.sha256` | 97 | `88bd89608a6f9851ac6fab4580f6869bb0139f74eddd2113f39311ce2b3dabb1` |

## Published notes

- Respect view-only Library access in project updates.
- Preserve prepared submissions when canceling.
- Recover pending data-sharing connections and handle malformed server errors.
