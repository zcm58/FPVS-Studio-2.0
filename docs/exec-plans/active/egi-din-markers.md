# Net Amps 400 wired event markers

Status: Active

The sender and reader have been verified in software. The lab has no access to
the amplifier. Physical marker receipt and display timing remain unverified.

## Workflow and implementation

1. In Recording settings, select the EGI DIN output and configure a compatible digital output interface. Use Trigger Tester to confirm the emitted words in Net Station. Net Station owns acquisition, recording and the saved MFF.
2. Use the standard playback schedule and trigger log for a short FPVS condition. Reuse the existing Windows parallel-port data-line writer for a candidate latched byte interface. The lab must establish electrical compatibility of the specific device and cable. Codes 1–255 represent events on this candidate path and zero is idle. A high pulse and a detectable return to idle must separate identical codes. The width is a setup parameter.
3. Use **EGI DIN marker verification** in the [Toolbox recording contract](https://github.com/zcm58/FPVS-Toolbox/blob/bb5a37390cb7a9dd8d8cae95ed7325a1e95abce4/docs/agent/architecture/eeg-loading-contract.md#egi-din-marker-verification). The paired source branch in both repositories is `codex/egi-din-markers` and the Toolbox commit is `bb5a3739`. Compare the recorded identities and order with the actual Studio trigger log. Preserve repeated events, simultaneous rows and recording-relative sample positions. Keep MFF outside EEG processing admission.
4. Exercise the configured sender and normal playback seam with a fake byte writer. Test input validation, connection and write failures, edge spacing, reset, and matching/mismatching receiver records. Check the existing trigger and import regressions. Montage editing, EGI preprocessing and ECI are separate projects.

## Software verification on 2026-11-27

The Studio playback test compiled a short 60 Hz Faces condition and exercised the
normal run worker, PsychoPy flip callbacks, parallel pulse worker and run export.
The display clock and LPT driver were simulated. A fake port at `0xDC00` with a
1 ms pulse recorded a return to zero between nonzero writes. These are test
values, not settings for a particular amplifier.

| Studio event | Display frame | Byte written | Fixture source identity | Recording sample (1,000 Hz) |
| --- | ---: | ---: | --- | ---: |
| Faces start | 0 | 1 | STRT | 16 |
| Oddball | 40 | 55 | ODDB | 683 |
| Oddball | 90 | 55 | ODDB | 1516 |

The cross-repository check built the fixture from the mock port writes,
independently of the Studio log. It used the two-second grid from Toolbox's
`tests.fixtures.egi_mff.write_mff_fixture`, with the fixture origin at 2 s on
the simulated clock. Toolbox compared all three rows with the exported
`runspec.json` and `trigger_log.csv`. Changing the ODDB mapping to 54 produced
a mismatch on row 2. SHA-256 checks of all seven MFF members agreed before and
after both comparisons. Separate receiver tests covered distinct codes and
multiple identical rows at the same timestamp. To regenerate the Studio
artifacts run `test_egi_din_exports_compiled_markers_from_the_presentation_flips`
in `tests/unit/test_psychopy_engine.py` with pytest's `--basetemp` pointing
to a new temporary directory. Its `egi-transfer` folder contains both run
files and `mock_wire_edges.json`.

Studio passed 460 trigger tests, 1,200 runtime tests, 202 non-Qt tests in the
GUI scope and the repository precommit suite (6,692 passed, 41 skipped). The
project-I/O suite passed 931 tests. All 52 project-config tests passed on the
final export changes. A separate check used Toolbox v3.1.2 to confirm it still
accepts a BioSemi setup and a completed Unicorn session after switching away
from EGI. The visible Qt interaction tests await an approved desktop. Toolbox's
project-I/O check passed 1,572 tests with 15 skips. Its repository precommit
check passed 228 tests with two skips.

An independent read of the public NA400 recording from Net Station 5.2.0.2
(r18488) with MNE 1.9.0 agreed with Toolbox on the 1,000 Hz rate, 21,926
samples and all eight source rows, including two successive DIN7 events. The
fixture has no corresponding Studio or photodiode record. The software checks
ran on Windows build 26300 with Python 3.10.11 for Studio and 3.13.9 for Toolbox.
[Pinned MFF](https://github.com/mne-tools/mne-testing-data/tree/20cc221d737a37a6ee3a9c007e91bd69541fefe9/EGI/test_egi.mff)
· [MNE 1.9 EGI reader](https://mne.tools/1.9/generated/mne.io.read_raw_egi.html)

### Independent Windows software checks

EGI lists supported macOS and amplifier firmware combinations and supplies Net
Station downloads through support. Even analysis on a personal Mac requires a
Net Station license key. The Windows checks below used saved recordings and
simulated output. [EGI system requirements](https://www.egi.com/knowledge-center/item/97-net-station-mac-os-and-net-amps-firmware-compatible-verisons)

- EGI's Java MFF library 1.2.2, run directly with OpenJDK 21.0.8, agreed with
  Toolbox on the original codes, labels, timestamps, durations and order of
  all eight public NA400 events. It also preserved the three simulated playback
  events and all four rows in a separate test with sub-microsecond timestamp
  precision, including two identical rows and a different code at the same
  instant. The EGI writer also created a fresh event track from the three mock
  port writes in a synthetic MFF. Toolbox matched the saved Studio log at
  samples 16, 683 and 1516. [Java library distribution](https://github.com/arnodelorme/mffmatlabio/tree/fa8dbf19c8c1cbbfc891fb2f1d28a1d793673c68)
- An isolated installation of `mffpy` 0.11.0 independently read the public
  recording and agreed on every event's code, label, time, duration and sample.
  Its writer generated a fresh MFF from Studio's three mock port writes. Toolbox
  matched that file against the original Studio run log and rejected an
  intentionally incorrect oddball mapping. A second event track retained
  `55, 55, 128, 255` in source order, all at sample 100. File hashes matched
  before and after inspection. [mffpy 0.11.0](https://pypi.org/project/mffpy/0.11.0/)

## Physical qualification if an equipped site becomes available

An equipped site can provide a de-identified continuous MFF, the matching Studio
run files, and a photodiode channel or event track captured on the recording clock.
Record the NA400 variant and serial number, firmware, Net Station Acquisition
version/build, sample rate, workspace DIN mode and event names, Windows output
device/driver/address, cable/adapter part numbers, connector bank and verified
pin/bit mapping. Record polarity, idle state, voltage compatibility, minimum
pulse and low interval, and the chosen settings.

EGI describes TTL-style DIN markers and up to 255 unique markers. Its Net Station 5.4 timing example uses the EGI AV Tester and a photocell on the participant display. Neither reference qualifies a particular PC output cable or establishes this installation's minimum pulse width. [DIN overview](https://www.egi.com/knowledge-center/item/75-synchronizing-different-types-of-stimulus-events-with-net-station) · [Timing setup](https://www.egi.com/knowledge-center/item/91-how-to-set-up-a-timing-test-in-net-station-5)

With the lab-approved wiring and acquisition workspace:

- Confirm the word-to-recorded-name mapping, including single-bit, multi-bit and repeated values. Send an idle reset and inspect the event track for spurious events. Record the actual observed values and gaps.
- In Studio enable detailed run folders. Start a fresh Net Station recording for the short FPVS condition, separate from the tester sequence. Use known start and oddball codes, repeated oddballs and a visible transition at each onset under test. Save the de-identified, continuous MFF and Studio run artifacts. Retain any missing/extra rows in the comparison.
- Capture a photocell transition on the participant display using a separately identifiable recorder input. Ensure the chosen line and event codes cannot alias the stimulus word. Record the refresh rate, photodiode position and threshold, and recording rate. Pair stimulus markers and physical transitions in recording time. Report missing/extra pairs and signed photocell-minus-marker offsets in samples and milliseconds (range, median and jitter). Use the lab's agreed timing limits and retain the underlying rows. Studio callback times alone cannot measure this offset.
