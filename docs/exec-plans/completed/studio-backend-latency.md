# Studio backend latency

Status: Completed

## Scope

Reduce latency in Manage Projects, the participant workbook freshness check,
compilation of large shuffle pools, and image launch preflight. Keep project list
contents, source freshness and containment, compiled plans, and validation and
failure behavior identical. Preserve the separate authoring and runtime launch
checks and keep acquisition timing out of scope.

## Manage Projects

Project discovery reads study status and saved-version count over one SQLite
connection when the second path resolution and live file identity match the first.
Each read has its own SQLite snapshot. A changed database path or identity uses the
existing version-count open. Legacy projects, malformed databases, and directory
paths at the database filename keep their previous handling.

The Windows discovery worker was compared with its baseline on 120 synthetic
mixed projects across nine alternating pairs. Complete entries and order matched.
Median discovery fell from 651.39 ms to 617.72 ms and SQLite opens fell from 195 to
105. An eleven-pair one-project check fell from 7.80 ms to 6.51 ms with two opens
reduced to one. The guarded implementation rereads the database path and file
identity at the second read boundary. Tests exercised a concurrent commit and a
Windows junction retarget between the reads.

## Exact shuffle search eligibility

After the existing bag validation, a lower bound on search states can rule out
exact search before sorting. Smaller pools use the original exact state estimate,
sorted key order, and seeded search. This keeps the change focused on pools that
already exceed the cap on the strength of their distinct key count alone.

On Windows, the public session compiler used 5,000 real PNGs per disjoint role
and 40 runs. Three alternating pairs after warm-up gave medians of 9.006 s and
8.578 s, with a median paired reduction of 4.28%. Final small-case medians stayed
within timing variation across alternating pairs with 100 PNGs per role, three
PNGs per role, and three overlapping words per role. Serialized plans matched
byte for byte. A direct comparison of 300 deterministic planner cases covered
overlapping pools and state limits. The focused work-count test confirms that
oversized pools skip sorting.

## Participant Results freshness

Each source inventory now uses a single project path resolver. Every source path
still resolves against the active project root. The check uses the existing
reporting lock, source ordering, and workbook freshness rules.

The Windows comparison used the actual post-session freshness entry point with
the same generated workbook and research files in both builds. Seven alternating
pairs with 400 compact visits reduced the median from 591 ms to 425 ms. The
number of project-root resolutions dropped from 404 to one. Twelve alternating
pairs on a one-visit workbook measured 7.5 ms and 6.9 ms. A separate source inventory
with 200 full visits fell from 1,625 ms to 1,111 ms in five pairs. Local benchmark
activity overlapped part of the large-run measurements.

The ordered source lists and existing workbook bytes matched. A newly introduced
pending journal was visible to both versions and an escaping journal reference
produced the same error. The Windows test also redirects a journal junction after
one inventory and checks containment on the next.

## Image preflight

Path-only preflight collects image paths for the existing sorted live checks.
Payload validation still checks presentation, and full-decode validation retains
the expected dimensions by role. Both launch validation passes remain independent.

Nine alternating runs of hardware-free public `preflight_session_plan` used fixed
plans and six real PNGs. Path-only median time fell from 21.44 ms to 18.99 ms for
eight runs and 5,840 image events, and from 713.39 ms to 574.50 ms for 32 runs
and 186,880 image events. Full decode on the eight-run fixture measured 32.24 ms
and 31.65 ms with two noisy baseline samples. Serialized plans matched. Missing
files, a redirected Windows junction, corrupt images and wrong dimensions had the
same results and error order. Direct preflight, Masking and duration tests passed
42 cases.

## Verification

The non-Qt GUI focused suite passed 184 tests. Compiler focused passed 817 tests,
and runtime focused passed 1,169 tests with four Windows permission skips.
Direct study version and collection tests passed 33 cases. Four-worker repository
precommit passed 6,597 tests with 41 platform or permission skips. The 1,500-session
archive fixture passed in 227 seconds. Lint, compilation, both Windows and Darwin
type checks, and repository audits passed. Measurements cover backend execution
on Windows. Visible desktop and physical acquisition timing were outside this pass.

For a visible smoke check on an approved desktop, open Manage Projects on a
populated root with active, archived, legacy and invalid projects. Check ordering,
saved-version counts, cancellation and a fresh scan on reopening.
