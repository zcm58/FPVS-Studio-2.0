# Security

FPVS Studio is a local desktop application. Security work is mostly about safe local file
handling, dependency discipline, and avoiding accidental data exposure.

## Guardrails

- Keep project file I/O rooted in the active project root.
- Preserve existing project formats and avoid hidden fallback paths.
- Do not log participant-sensitive data unless a feature explicitly requires it and the
  behavior is documented.
- Do not commit secrets, tokens, local machine paths used as credentials, or generated
  private data.
- Use structured logging for diagnostics instead of `print`.

## Related Docs

- Environment notes: `ENVIRONMENT.md`
- Runtime/export flow: `RUNTIME_EXECUTION.md`
- Path-sensitive skill: `../.agents/skills/project-path-audit/SKILL.md`

## Upload And Download Trust Boundaries

- Library and results credentials live in separate OS-secure namespaces. Receipts and
  imported project metadata cannot select a different credential destination. Library,
  results, support and maintainer publishing reject redirects on authenticated requests.
- Updater requests use `updates.validation.urlopen`: every redirect destination is checked
  before connection, allowing only HTTPS GitHub/API and the two official release CDN
  hosts. Initial release URLs remain bound to the fixed repository and selected version.
  Size and official SHA-256 are required before cache reuse or executable handoff; a local
  receipt is not an independent trust anchor.
- Transfer readers use bounded single socket reads with total deadlines, response-size
  limits and cancellation checkpoints. Results and publication responses are checked
  after reads as well as before them. Ambiguous writes retain their immutable identity
  and require receipt reconciliation rather than creating another submission.
- `core.project_bundle` owns archive inventory, path containment, case-collision checks,
  member/size/compression limits, checksums and staged import. Before ZIP parsing, a
  streaming directory check limits directory bytes to 64 MiB and counts actual entries;
  project and stimulus JSON each have a separate 16 MiB limit before whole-file loading.
  Only stored/DEFLATE ZIP members are accepted, excluding the older CPython
  [BZIP2/LZMA allocation vulnerability](https://www.python.org/downloads/release/python-31022/).
  The tail reader follows the supported CPython ZIP/ZIP64 format and has regression coverage.
  Before source compilation, conservative bundle workload limits cap run occurrences
  at 1,000 and weighted stimulus/fixation events at 100,000, including catch-trial
  allowance and masking overlays. These bound one bundle's validation work and do not
  limit collected participants/sessions or change locally authored runtime contracts.
  Do not execute bundle
  contents or introduce a second archive extractor. Clean Library preparation excludes
  participant results, local reporting/enrollment state and unselected files.
- All Studio Pillow reads explicitly restrict image decoders. Experiment intake,
  derivatives, previews, preflight and engine reads allow JPEG/PNG; the shared image
  inspection, permissive import and standalone resizer additionally allow their documented
  BMP/TIFF inputs.
  A misleading extension must not enable PSD, FITS, JPEG2000 or other unsupported
  decoders. Preserve Pillow's existing decompression-bomb checks.

See the [security audit execution record](exec-plans/completed/upload-download-security-hardening.md)
for verified findings and checks. These desktop protections do not replace server-side
authorization, intake validation, quotas and review of the exact submitted bytes.

## Dependency Advisories And Compatibility Exceptions

The October 7, 2026 audit queries pinned installed package versions with `pip-audit`,
then verifies relevant advisory fixes against upstream. Development/documentation
dependencies are counted separately from exploitable Studio transfer paths; duplicate
advisory records are not separate vulnerabilities. `pyproject.toml` records security
floors for compatible dependencies already required by the selected extras.

Two upstream restrictions remain explicit:

- MoviePy 2.2.1, required by PsychoPy, requires Pillow below 12. The newest compatible
  Pillow is 11.3.0. [Pillow's PSD advisory](https://github.com/python-pillow/Pillow/security/advisories/GHSA-cfh3-3jmp-rvhc)
  documents decoder restrictions as a workaround; the Studio boundaries above also
  exclude FITS and other affected unsupported formats. The installed package still
  carries advisory matches and must not be described as fully patched. Move to Pillow
  12.3+ only with a supported MoviePy/PsychoPy dependency graph and runtime acceptance.
- PsychoPy 2026.1.1 pins setuptools 78.1.1. Its
  [source-distribution exclusion advisory](https://github.com/pypa/setuptools/security/advisories/GHSA-h35f-9h28-mq5c)
   has a scanner-reported fix floor of 83.0.0, but the upstream advisory currently names
   no patched version. Studio does not build downloaded experiments as Python packages;
  use the isolated Hatchling build backend and do not build untrusted source packages
  in this engine environment. A supported upstream pin change is needed to remove
  this remaining package match without overriding dependency requirements.

PySide6 has a 6.11.2 minimum to carry the upstream
[SVG marker fix](https://www.qt.io/blog/security-advisory-type-confusion-and-heap-buffer-overflow-vulnerability-in-qt-svg-marker-handling)
and [XML recursion fixes](https://www.qt.io/blog/security-advisory-cve-2026-19248).
The updated Qt runtime still requires visible acceptance before release.

The package advisory scan does not cover CPython/OpenSSL, codec DLLs or every native
transitive library. The current build interpreter is CPython 3.10.11; the
[3.10 series reached end of support on October 1, 2026](https://www.python.org/downloads/release/python-31022/).
The bundle workaround does not patch the interpreter's other vulnerabilities. Moving
the supported engine/build environment to maintained Python needs its own compatibility
and runtime acceptance work. Review the packaged native inventory and current upstream
advisories before a security release; source tests alone do not certify those binaries.
