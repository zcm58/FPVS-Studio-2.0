# Python 3.11 user workflow verification

The experimental Windows build passed the tested authoring, Test Mode playback,
packaging and data-transfer workflows. Its compiled output matched the saved
conditions on main. Independently regenerating some PNGs with Pillow 13 can
still change the file checksums. The trial remains unmerged.

## Windows source and playback

Windows setup installed CPython 3.11.18 in an independent checkout. The project
and its IDE configuration now select that environment. The engine uses the
upstream MoviePy 2 revision compatible with both Pillow 13 and the API PsychoPy
imports. Its source archive is pinned by commit and SHA-256 and installs without
Git. The tested install passed `pip check`.

The fresh engine passed 2,781 compiler, runtime, trigger and reporting checks.
Four symlink checks required a Windows privilege unavailable on the test account.
Both native PsychoPy checks passed, including window creation and a complete
synthetic Test Mode condition with null triggers. Two independent 3.11 engine
installations produced 52 byte-identical files for four conditions, 7,200
planned frames and 148 synthetic trigger events.

## Assets and reports

- The importer preserves the recorded paths, bytes and timestamps of intact
  derivatives, including valid paths from older projects. A missing derivative
  is restored from its captured study checkpoint when available. Otherwise, a
  replacement for a recorded digest can only be published if its bytes match.
- Two equal-content sources such as `trial.jpeg` and `trial.jpg` could share a
  single output name. Import, normalization and standalone resizing now retain
  both. Existing noncolliding names are preserved.
- An isolated 3.10 → 3.11 → 3.10 Toolbox handoff retained all 14 study asset
  hashes and the seven-run plan. A separate corpus of 58 ordinary input images
  retained its decoded pixels. Eight freshly written 256-pixel PNGs had
  different compressed bytes between Pillow versions.
- On the clean engine, two contrast values in the Image Equalizer report differed
  by one binary64 spacing. Explicitly reducing squared deviations in the same
  8,192-pixel blocks as the reference matched all 729 tested arrays, including
  4K images. It also matched all statistics in the six-image end-to-end fixture.
  A worker uses up to 64 KiB for the squared deviations of one block.

Freshly generating a PNG independently on the two versions can still produce
different file checksums. Study identity uses the encoded bytes. The comparison
of existing studies uses their saved media. [Earlier scientific comparison](../../references/python311-scientific-parity.md)

## Saved conditions

On Windows, source commit `2f1f70f` with the freshly installed engine was compared
with main `b73cb3e` on CPython 3.10.11 and Pillow 11.3. All 73 standalone run
specifications, 73 selected-condition session plans and 13 whole-study plans
matched byte for byte. The comparison covered 69,725,237 serialized bytes. At
the stored seeds, two selected plans and two whole-study plans rejected the same
fixation counts on each stack. Those four comparisons matched in the projects'
ordinary fresh-seed mode.

The 13 project definitions were byte-identical before and after the read-only
comparison. The names, sizes and modification times of 38,205 stimulus files
also matched. These checks exercise compilation. Physical refresh timing and
EEG recording require instrumentation on the acquisition system.

## Native Windows authoring

Opening a protected study with a changed display resolution could prompt for a
version decision from the launch worker. The launch now sends the review to the
GUI thread and waits for the author's decision. Native tests verified that
accepting saves the new dimensions and declining preserves the project bytes.
Other fixes keep recording controls, nested warnings and metric headings visible
at supported window sizes, and allow Enter on the Home recording-settings link.

The Windows executable built from `2f1f70f` passed its native check of 28 Settings
pages across sizes and themes, all 59 simulated online workflow states, and
its runtime imports. Source startup and shutdown also exited cleanly with the
Welcome window alone and after a synthetic presentation job.

The full Windows installer compiled from the fresh checkout. The build verified
the origins of 460 Studio native files and 69 updater native files and wrote
the installer and ownership inventory locally. Installation over an existing
workstation, rollback and uninstall were outside this trial.

The SHA-256 of the qualified standalone Studio executable is
`c3f22d7ec30ac622fb6258a7d6d3cc73c27571ec26afd9abab200107a804da2b`.
The corresponding full Windows installer has SHA-256
`5350d4f0234184f1c144b7f222dbf21f2a0a2985dec8e5e409b346ed18d25857`.

Qt retains the first settings-write failure on a writer. After a failed attempt,
Studio now checks a retry with a fresh writer for the same file, format and
group. A failed recording, appearance or root choice preserves the previous
local value, including the absence of a local override when a default is
inherited. Studio updates its active root only after the setting is written.
Native tests temporarily blocked the settings directory, restored it, and
verified that subsequent saves succeeded without restarting Studio.

Across all 68 registered GUI modules, 2,570 cases passed and three skipped.
The three skips cover native Cocoa and two fixed-60-Hz cases. All 809 cases in
the 11 affected modules ran at `2f1f70f`. One initial Welcome fixture could not
write its temporary INI. The entire 93-case module passed on rerun. Two module
processes had previously crashed at interpreter exit after completing their
assertions. Draining Studio's workers and Qt's pending widget deletions in the
test fixture gave all final modules clean process exits. The final executable
also passed its smoke test and both windowed native engine tests passed on the
final source.

## Cross-platform checks

The final local non-GUI precommit run passed 6,668 tests with 48 skips. The
hosted run at `9f775f9`, which contains the same application code as
`2f1f70f`, passed 6,686 Windows tests with 30 skips. Apple Silicon and Intel
Macs each installed the complete engine and passed 2,028 tests with 14 skips,
including all five native OS-adapter checks. Windows-authored projects returned
from both Macs, and projects originating on each Mac returned through Windows
to the corresponding Mac. Eleven transfer receipts agreed on the project,
14 asset hashes and seven-run plan with its fixation schedule.
All six workflow jobs passed. [Hosted verification and transfer receipts](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/45933681222)
