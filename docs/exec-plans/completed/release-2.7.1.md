# Studio 2.7.1 release

Status: Completed

Date: 2026-11-05

## Scope and authorization

The user requested bundling and publishing all recent Studio changes on GitHub.
The latest published release is the immutable stable v2.7.0. This patch release
includes USB TriggerBox discovery cancellation, cleanup and plain-language error
guidance; Test Mode starting off each app launch; and requirements installation
including the PsychoPy engine and sounddevice. Parallel-port work remains secondary.

## Source and dependency freshness

Exact source `08c250dece40a33a417d29764e74296b09dd0cbe` was pushed to master
and bound to annotated `v2.7.1`. A requested fresh pull confirmed master was
current; ancestry checks prove it includes `v2.7.0`. Frozen Studio and updater
code objects match that exact source, with no local scratch modules included.

The first candidate was superseded without publication after comparison with the
authenticated public 2.7.0 installer exposed older helper packages in this PC's
preserved environment. The user required avoiding pre-2.7.0 content. Six packages
were updated to the actual versions shipped in 2.7.0:

| Package | Final version |
| --- | --- |
| beautifulsoup4 | 4.15.0 |
| markdown-it-py | 4.2.0 |
| platformdirs | 4.10.0 |
| tomli | 2.4.1 |
| arabic-reshaper | 3.0.1 |
| trove-classifiers | 2026.9.21.13 |

All 94 affected modules match 2.7.0 exactly. Arabic reshaper's embedded version
constant was stale; its real distribution was recovered by matching official
wheel source code, rather than trusting that constant. Newer pytest 9.1.1 and
Pygments 2.21.0 were retained and authenticated against official wheels. All other
frozen third-party code matches 2.7.0. Existing native bytes are unchanged; five
verified CPython/Tk binaries and their support files accompany the newer pytest
collection. Every added payload file is traced to its build input, with no user
or experiment data. Updater dependency code/native bytes are identical to 2.7.0.

## Build and acceptance

- Final label: `release-2.7.1-final`, built from a clean isolated checkout.
  Evidence: `build/release-2.7.1-final-evidence/`. The initial candidate and
  superseded acceptance are retained separately and blocked from publication.
- Corrected-environment packaging focused passed 192 tests. Safe precommit
  passed 5,263 tests, 24 subtests and 32 platform/environment skips, Windows
  mypy for 269 files, Darwin mypy for nine files, and repository/docs audits.
  Dependency consistency passed; the other 136 dependency versions were preserved.
- All 7,987 extracted installer files match the staged ownership inventory,
  SHA-256 `b229494030d9b818b8a520e10694894dd3fc94da52f8c678691f54dfffdf40f1`.
  Metadata, resources, sidecars, source objects and dependency comparisons passed.
  All 151 base-library modules match 2.7.0; 21 reviewed build warnings are unchanged.
- The user explicitly approved visible checks and publication. The exact final
  Studio executable passed version, runtime-import, Test/Pilot control and layout
  checks. The updater passed standalone repair and repair-after-failure screens
  with network and installer execution disabled. A surrounding shell command
  checked a stale exit code; both fresh process reports independently passed.
- [Exact-source CI](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/42110245250)
  passed Windows, native Intel/Apple Silicon Mac and both cross-platform return
  checks. Documentation CI passed too.

## Publication

[v2.7.1](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.7.1)
was published at `2026-11-05T22:02:17Z` as latest, stable and immutable,
release ID `435788428`. The four draft assets, exact notes, live remote source,
annotated tag and immutability setting were checked before publication.

Independent public downloads match every local size/hash. GitHub release and
all four asset attestations verify. Ten live updater cases passed, including
older/current versions, explicit repair and downgrade rejection, without
executing an installer.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.7.1.exe` | 301,036,495 | `9aa8aa970ec70cc318df0fb8acc19855c98926d74d5bbd7a5b018cd30a6dd76d` |
| `FPVS-Studio-Setup-2.7.1.exe.sha256` | 95 | `ad9e5d3e692ff4cb3c5581044eff87e1b584be63d3999d2b18e9b2219a5c5269` |
| `FPVS-Studio-Update-2.7.1.json` | 107 | `3ca5379d2657a13ca0eea562c5579d1ad0ee6ea62630ef2fa4949e051710f645` |
| `FPVS-Studio-Update-2.7.1.json.sha256` | 97 | `145b981a2baddc6baeffdfbc9c454ebeb36b3c9707ef8439824b983a4b3bc4e6` |

## Limits

Mac remains source-only. Production installation, upgrade/uninstall, real EEG
and physical display timing are separate acceptance tasks. TriggerBox hardware
testing remains deferred at the user's request. User projects, settings and
the working installed application were not modified by the packaged checks.
