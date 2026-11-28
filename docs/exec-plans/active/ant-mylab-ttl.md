# ANT Neuro eego mylab wired event markers

Status: Active

## Scope and setup

The target is the eego mylab configuration with an eight-bit TTL input. The
lab has no amplifier or trigger adapter available. Software checks use a
simulated Windows parallel data port and native ANT CNT recordings. Other eego
models can have different inputs. ANT documents the XS-230 D-sub 25 adapter for
the EE-22x connector. Confirm the amplifier model and its supported adapter
before connecting a physical output. [mylab specifications](https://www.ant-neuro.com/products/eego-mylab) · [EE-22x manual](https://academy.ant-neuro.com/web/content/43636?download=true&unique=e22eaaa36decad62beea35309bb41cb67effcdbe) · [ANT FAQ, question 18](https://academy.ant-neuro.com/faq)

1. Select the ANT eight-bit output in Recording settings. Supply the actual
   Windows LPT I/O address, eego Recorder sampling rate and pulse width.
   Use a nonzero byte for each marker and zero for idle. Allow three recorder
   sample periods for high and for low, including between identical words.
   Verify individual and multi-bit values in Trigger Tester. Report open,
   write, overlap and reset errors. [ANT stimulus timing guidance](https://academy.ant-neuro.com/blog/application-notes-2/using-stimulus-presentation-packages-with-your-eegotm-system-25)
2. Enable detailed run folders and run a short condition with the normal
   frame-scheduled start and oddball markers. eego Recorder owns acquisition
   and saving. Keep the selected run's `runspec.json` and `trigger_log.csv`.
3. Read the original ANT `.cnt` with its companion files through the native ANT
   reader. Preserve source samples, event order, repeated words, simultaneous
   events and recorder annotations. Compare stimulus codes with the selected
   Studio run and retain timing as measured on each clock. The paired Toolbox
   branch is `codex/ant-mylab-ttl`. [Toolbox recording contract](https://github.com/zcm58/FPVS-Toolbox/blob/codex/ant-mylab-ttl/docs/agent/architecture/eeg-loading-contract.md#ant-eego-wired-ttl-marker-verification) · [MNE ANT reader](https://mne.tools/1.9/generated/mne.io.read_raw_ant.html)
4. Exercise real file parsing, the full byte range, repeated and coincident
   events, failed sends and incorrect mappings. Run existing trigger and import
   regressions. LSL, cap editing and EEG processing are separate work.

## Software verification on Windows 11 build 26300

Studio 3.1.6 used Python 3.10.11, PySide6 6.11.2 and an environment with
PsychoPy 2026.1.1. The playback test used the production compiler, frame-flip
callbacks and pulse/reset worker with a simulated 60 Hz display and a fake LPT
device at `0xDC00`. The configured Recorder rate was 512 Hz with a 6 ms pulse
and at least 6 ms idle. On the Windows desktop, 58 Recording settings and
Trigger Tester Qt cases passed with simulated output. The trigger scope passed
468 tests. Runtime passed 1,214 with four Windows symlink-permission skips.

The compiled Faces condition sent start word 1 at frame 0 and oddball word 55
at frames 40 and 90, with zero idle between sends. A separate writer used
libeep 3.3.179 to create a native RF64 CNT with 1,024 zero-valued EEG samples.
It placed each captured rising edge at the next 512 Hz sample after the edge,
relative to a simulated recording origin of 2 seconds. Toolbox matched words
1, 55, 55 to samples 9, 350, 777 against the original run log and metadata.
MNE's ANT reader returned the same samples and codes. File hashes matched
before and after inspection. Toolbox includes the synthetic recording and
the matching Studio files in its regression tests. [Saved playback fixture](https://github.com/zcm58/FPVS-Toolbox/tree/0ea9384c56e5f4eb9153a1f7e6427d9ba893d67c/tests/fixtures/ant_cnt/studio_playback)

Toolbox 3.1.2 ran on Python 3.13.9 with antio 0.7.1 and MNE 1.9.0.
Twelve public EE_225 and EE_226 recordings at 500, 1,000 and 2,000 Hz
contained 36 recorder events in total. These recordings had no stimulus words.
Three EE_225 files were cross-checked with MNE across RIFF and RF64. In the
1,000 Hz disconnection example, the reconnect event and an impedance check both
survived at sample 6075. Two 500 Hz recordings retained their named annotations.
The synthetic native regression fixtures also cover identical words at the same
sample. [Public ANT recordings at the tested revision](https://github.com/mscheltienne/antio/tree/8bbb1a87486653133461df55b27774e8a1899133/tests/data)

Studio's repository precommit checks passed 6,725 tests with 41 skips. Toolbox's
project I/O scope passed 1,614 with 15 skips, and its precommit checks passed
243 with two skips. A BIDS publication-lock regression needed a rerun on Windows
after observing an extra rename attempt. Both the isolated case and the repeat
of the full project I/O scope passed.

## Physical qualification

The lab had no amplifier, approved output device or adapter, Recorder installation,
or photodiode available for this pass. If an equipped site can contribute
evidence, record the amplifier model and firmware, eego Recorder version and
acquisition rate, stimulus output model and
driver, adapter and cable part numbers, pulse width and idle interval. Send
known words from Trigger Tester and inspect them in Recorder. Start a fresh
recording for the Studio condition, capture a photodiode on the participant
display on the recording clock, and preserve the de-identified CNT and its
sidecars. Compare every marker and optical transition, including drops or
extras. Report signed optical-minus-marker intervals in samples and
milliseconds, their range and their variation.
