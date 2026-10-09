# Upload And Download Security Hardening

Status: Completed source audit and hardening; external/runtime acceptance remains explicit

Date: 2026-10-07

## Scope And Success Criteria

The user requested a future plan for reporting-history archiving followed by an
implemented audit and hardening of Studio's uploads and downloads. The future work
is recorded in [long-running reporting](long-running-results-reporting.md);
this plan covers the security implementation only.

Review Library enrollment, catalog and bundle transfers; local bundle review/import;
condition submissions and maintainer publishing; results and support reporting;
and updater metadata, downloads, cache and installer handoff. Treat remote metadata,
archives, response bodies and project-local receipts as untrusted. Preserve existing
consent, private credentials, exact reviewed submission identity and research files.

1. Inventory the transfer entry points and existing protections, and establish focused
   baselines. Verify installed dependencies against current upstream advisories.
2. Reproduce confirmed weaknesses with synthetic archives, temporary files and fake
   transports. Patch the existing owner and add focused regression coverage.
3. Run affected focused routes and repository precommit; document findings and residual
   acceptance limits. Commit and push the completed source changes.

No live attack traffic, real research uploads, installer execution, experimental
runtime, trigger changes or new release publication is part of this audit. Qt checks
require explicit approval for any newly changed surface. Dependency changes must be
supported by an advisory and compatible with the supported Python/runtime contract.

## Audit Record

- Future reporting plan written; docs focused verification passed (10 tests).

| Boundary | Finding and implemented protection | Regression evidence |
| --- | --- | --- |
| Updater release/patch downloads | Final-response host validation occurred after urllib could follow an untrusted redirect. The shared opener validates the initial destination and every redirect before connecting; official GitHub CDN redirects remain supported. | Host spoofing, HTTP downgrade, loopback, userinfo, port, control-character and fragment fixtures; existing digest/cache/handoff coverage. |
| Results and support responses | Filling reads could postpone total-deadline checks while a peer trickled bytes. Use bounded `read1`, identity encoding and checks after reads including EOF; close HTTP error bodies. Support also normalizes deeply nested JSON failures and checks cancellation before accepting success. | Fake responses prohibit filling reads, expire during reads, cancel at EOF and verify closure. |
| Maintainer publishing | Response reads lacked a total budget/cancellation checkpoint; upload reads could be unbounded. Add bounded reads, request/upload deadlines, identity encoding, safe JSON/network errors and checks before accepting responses. | Fake publishing responses, cancellation and existing immutable retry/publication tests. |
| Bundle review/import | JSON payloads inherited the 4 GiB asset allowance, then loaded wholly into memory; ZIP directory limits ran after allocation. Limit project/stimulus metadata to 16 MiB each, stream/count the central directory before parsing with a 64 MiB directory budget, and retain existing payload/digest/path checks. Publisher review uses the same guard. | Oversized JSON never reaches the loader; oversized directories and forged member counts are rejected before `ZipFile`; valid ZIP64/comments and existing bundle round trips pass. |
| Bundle compression | CPython's older BZIP2/LZMA ZIP readers have unbounded-allocation exposure, even when callers request bounded reads. Accept only stored/DEFLATE members, matching Studio's exports. | Tiny valid BZIP2/LZMA archives reproduced acceptance before the guard and are rejected before decompression afterward. |
| Bundle compilation | Small JSON can request huge schedules through condition, block and fixation counts. Before compilation, cap conservative run occurrences at 1,000 and weighted stimulus/fixation events at 100,000, accounting for masking overlays and catch trials. These are bundle validation budgets, not participant/session collection limits. | Huge counts reach the fake compiler before the fix and are rejected before it afterward; existing export destination survives. Normal FPVS, AB, masking and task bundle workflows pass. |
| Image intake/processing/previews/runtime | Extensions alone did not stop Pillow selecting unsupported vulnerable decoders. Every Studio Pillow read now has an explicit decoder allowlist; preserve JPEG/PNG and the existing permissive BMP/TIFF inspection/import/resizer workflows. | Valid TGA renamed as PNG is rejected by inspection, resize and derivative generators; JPEG/PNG/BMP/TIFF acceptance checks. Registered modifier-preview error coverage added, not run. |
| Dependency graph | Installed-version audit initially returned 129 raw advisory records in 15 packages. Update compatible dependency floors and the environment; the repeated package audit returns 37 raw records in Pillow/setuptools only. These include duplicate advisory records. | Resolver dry run, installed-package rescan and `pip check`; native Qt advisory review additionally requires PySide6 6.11.2+. |

Library service requests already reject redirects, use bounded single reads, total
budgets, content/digest checks and protected credentials. Existing enrollment,
revocation, receipt/cache, path/link, clean preparation and exact-submission identity
tests remain the acceptance route. No new credential namespace, arbitrary URL,
participant payload, publication bypass or server permission was introduced.

The reporting plan was still Planned when this security audit completed. These
security changes did not alter its 512-record active capacity, consent or archive
behavior; its later lifecycle implementation is recorded separately above.

## Verification And Remaining Checks

Use the narrowest affected `library`, `project-io`, `updates`, `data-sharing`, support
unit tests, `packaging` and `docs` routes, then `repo` precommit for shared changes.
Record actual results here; a source audit does not establish an installed upgrade,
native dependency exploit test or a production backend penetration test.

Checks completed:

- Synthetic transfer/image/publisher/bundle regressions: 121 passed, plus 20 publisher
  subtests; three subsequent compilation-budget regressions also passed.
- Library focused: 309 passed, 3 Windows symlink privilege skips, 20 subtests.
- Final project I/O focused after compilation guard: 304 passed, 2 symlink skips.
  An earlier run had one Windows directory-rename access failure; its isolated rerun
  and the full focused rerun passed. No production retry/fallback was introduced.
- Updates focused: 309 passed, 4 symlink privilege skips.
- Data-sharing focused: 144 passed. Preprocessing focused: 30 passed after correcting
  the permissive BMP import regression found by the existing tests.
- Packaging focused: 181 passed; safe GUI focused: 17 passed; docs focused: 10 passed.
- Final precommit in the updated dependency environment: 2,783 passed, 11 Windows
  symlink privilege skips and 20 publisher subtests; Ruff, compilation, harness/docs
  audits and mypy all passed. The last bundle-budget change was verified separately
  by the full project-I/O focused route, its three reproductions and a fresh mypy run
  (227 source files). Registered Qt modules remained excluded throughout.
- Supported editable-install resolver dry runs and actual environment refresh passed.
  PySide6/Addons/Essentials and Shiboken are 6.11.2; `pip check` found no broken
  requirements. The final public installed-version advisory scan still returns the
  documented Pillow/setuptools matches. Ignored package-only audit evidence is retained
  under `build/security-audit/`; no project data or credentials were sent to the scanner.
This source verification does not certify an installer, deployment or native runtime
migration. Delivery uses the `codex/upload-download-hardening` branch; the task's final
response records the remotely verified commit.

## Remaining Acceptance And Compatibility Limits

- `docs/SECURITY.md` records the MoviePy/Pillow and PsychoPy/setuptools restrictions.
  Decoder restrictions mitigate the relevant unsupported-image paths; the package
  itself still has advisory matches. Studio does not accept arbitrary Pillow APIs,
  fonts or Python source from an experiment bundle. Do not override upstream pins to
  claim a clean scanner result.
- CPython 3.10.11 is not fully patched and Python 3.10 is now unsupported. The ZIP
  compression workaround does not fix every native/interpreter issue, including
  older HTTP parser handling of unbounded interim responses/trailers. Transport
  read deadlines are not a hard wall-clock limit inside those parser operations.
  Move the supported engine/build environment to maintained Python with dedicated
  compatibility, packaging and presentation acceptance before a security release.
- PySide6 6.11.2 carries the verified Qt SVG/XML fixes. PsychoPy's unused PyQt6 runtime
  is still a separate transitive installation; the Studio freezer excludes PyQt6.
  Audit the actual frozen native inventory (including OpenSSL and codecs) before
  certifying a release; package advisory scanning is not a native binary audit.
- Registered Qt coverage was added but not run. In an approved visible environment,
  inspect modifier preview failures at `1100x720` and `1120x760`, confirm responsive
  controls and unchanged project state, then verify normal JPEG/PNG previews. Exercise
  Library, reporting and updater fake-service success/cancel/error states at their
  documented sizes after the Qt upgrade. No hardware or real upload is needed.
- No installer was built/published and the already released 2.4.0 binaries are
  unchanged. Production multi-device/server authorization and Linux/native runtime
  acceptance remain external checks, not claimed results of these source tests.
