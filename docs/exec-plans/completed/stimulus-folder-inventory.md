# Large stimulus folder inventory

Status: Completed

## Scope

Shorten fresh inventories used by Setup readiness, source inspection and import,
normalization, and filesystem-backed compilation. Preserve original enumeration
order, sort ties, Finder filtering, live file classification, exception behavior,
and project-root checks. Compare the existing entry points on identical fixtures
before keeping the implementation.

## Approach

`Path.iterdir` still supplies names and the original tie order. For a local Windows
folder with at least 64 entries, `GetFileInformationByName` first checks that the
source root supports the information class and then reads each ordinary file's
current attributes. `Path.is_file` handles alternate platforms, small folders,
unsupported roots, reparse points and query failures. Finder records still use
the same signature check. The compiler continues to resolve accepted paths against
the active project root. [Microsoft API and structure](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyname)

The earlier `scandir` prototype classified a removed file and entries retyped after
enumeration using their old metadata. A sequential `os.stat` prototype kept fresh
checks and provided no measured gain. The by-name query still looks up every file.

## Windows measurements

Five alternating pairs after warm-up used the same temporary folder of 5,000 valid
images, two Finder records and 66 ignored directories. Each row measures the normal
entry point, including its existing image reads where applicable.

| Operation | Baseline median | Updated median |
| --- | ---: | ---: |
| Inventory with default sort | 864 ms | 119 ms |
| Inventory with lowercase sort | 865 ms | 106 ms |
| Setup readiness with full image decode | 1,904 ms | 1,231 ms |
| Source inspection with SHA-256 | 3,327 ms | 2,307 ms |

Calls to `Path.is_file` fell from 5,068 to 66. Fresh-process scans of one file and
16 files stayed in the same timing range and skipped native initialization. Median
one-file timings were 0.181 ms and 0.190 ms inside 0.16–0.25 ms local variation.
The 16-file medians were 1.181 ms and 1.108 ms. Some timing runs overlapped other
local checks.

## Output and error parity

Ordered paths, readiness results, inspection records and source digests matched.
A filesystem-backed image session produced byte-identical serialized plans with
fixed seeds. All 192 normalized PNGs and 96 imported files matched by SHA-256,
along with the returned import and normalization records.

Native Windows checks covered extended paths, hard links, junctions, file/directory
replacement and deletion after enumeration, and Finder reads denied by permissions
or exclusive sharing. Source ordering, new entries added after enumeration, and
the previous `Path.is_file` fallback were exercised. File symlink creation requires
a privilege unavailable on this account. Preprocessing focused verification passed
100 tests and compiler focused verification passed 815. Visible desktop latency
and physical acquisition timing were outside this pass.

Four-worker repository precommit passed lint, compilation, Windows and Darwin
type checks, repository audits and 6,586 non-Qt tests with 41 platform or
permission skips.
