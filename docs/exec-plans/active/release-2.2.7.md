# FPVS Studio 2.2.7 OpenFPVS Connection Release

Status: Active

Date: 2026-10-06

## Scope

The user approved direct Studio Library access through `https://openfpvs.com` and
accepts a one-time lab-code reconnection. Build from released master `baf4dcf` on
`codex/openfpvs-domain-2.2.7`, excluding the separate results-sharing feature.
Keep native `/v2` and schema `1.0`; no experiment/runtime/trigger contract changes
or server-wide account/device revocation are part of this release.

The default and exactly allowlisted previous managed origins select openfpvs.com.
OS-protected credentials and download caches remain bound to the selected origin;
never transfer old tokens. New-origin enrollment is explicit and retry-safe.
Existing projects remain local. Recognize only the two known previous managed
origins as the same Library for receipt/version comparisons, preserving receipt
bytes and strict custom-origin isolation. Version updates still require review
and a separate project import.

The private service checkout is now the independent sibling PyCharm project
`OpenFPVS`, retaining its private Git repository, configuration and database.
Normal user pages do not advertise administrator sign-in. Direct `/admin` and
`/admin/sign-in` remain protected by the existing backend authentication.
The private service plan owns deployment/website acceptance.

## Release note

- FPVS Studio now connects to the OpenFPVS Experiment Library at openfpvs.com. Re-enter your lab access code once after updating; existing experiments remain available offline.

## Gates

- [x] Verify endpoint selection, fresh service-bound enrollment, retry/reopen behavior and exact receipt comparisons.
- [ ] Pass Library/core/packaging/update/documentation focused checks and repository precommit.
- [ ] Commit the exact released-base candidate and record source/master identity.
- [ ] Build the full installer and direct 2.2.6 patch with authenticated baseline inventories.
- [ ] Audit complete payload, exact patch reconstruction, native dependencies and embedded source; exclude results-sharing files.
- [ ] Obtain approval for and run visible registered startup/Library tests and bounded packaged smoke.
- [ ] Publish installer, direct patch, update JSON and checksums with the release note.
- [ ] Verify GitHub asset digests, updater patch/full fallback selection and clean remote refs.

## Verification boundaries

Tests use synthetic credentials and project fixtures. They never submit real lab
codes, send email or run experiments. Record native GUI, installed upgrade/repair,
physical-PC and server acceptance separately. Do not treat an unrun check as passed.
The existing production domain migration preserves the database and legacy native
routes; changing Studio's selected origin does not reapply SQL access-reset migrations.

## Source verification before packaging

Focused checks pass: Library 297, core 548, safe GUI 17, documentation 9,
packaging 181 and updates 309 tests. Windows privilege restrictions skip eight
symlink cases across these routes. Changed-file Ruff/compilation, mypy on all
213 source files, architecture garbage-collection checks and docs hygiene pass.
The complete safe precommit suite is still running and remains a publication gate.
Registered Qt/startup and packaged visible smoke remain approval-gated and unrun.
