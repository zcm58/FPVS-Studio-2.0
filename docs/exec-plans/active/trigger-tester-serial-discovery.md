# Trigger Tester serial discovery

Status: Active

## Current baseline

Studio 3.1.0 includes serial discovery shipped in
[Studio 3.0.0](../completed/release-3.0.0.md). The Trigger Tester opens and closes
the single named BrainVision or BioSemi candidate before enabling digit sends.
Generic BioSemi interfaces use the configured port or the one port identified by
an unplug/reconnect scan. Detection and manual COM edits apply only to the dialog.
Recording uses the saved port and baud rate from **Settings > Recording**.

All 17 registered Trigger Tester tests passed in native Windows at 560 × 340 and
100% scaling with simulated hardware. The operator separately confirmed the
tester and marker sending on a physical 2026 actiCHamp setup with Recorder 2 and
a USB TriggerBox. The retained bench result covers marker sending. Discovery and
reconnect have their own physical acceptance steps below.

## Verification, 2026-11-19

On Windows at `313f0bd`, 278 non-Qt tests passed for BrainVision and BioSemi
discovery, serial access, failure guidance and fake trigger backends. The
fixtures exercised named-port filtering, the single added-port rule for BioSemi
reconnect, rejection of unrelated port changes, and manual open/close at the
configured baud rate without sending a byte. They also covered denied access,
cleanup and cancellation. Two separate visible Windows Qt cases passed for
BioSemi reconnect with one or multiple ports added using controlled inputs.
Physical COM discovery/reconnect, recorder receipt and saved-setting
preservation checks remain open below.

## Remaining acceptance

- [ ] With physical BrainVision hardware on Windows, verify one named TriggerBox
  is automatically selected, checked and released without sending a marker.
  Exercise disconnected, occupied and multiple-device cases, the mismatched
  manual port message, and a successful manual retry. Check that digit sends stay
  disabled until the target port passes and that Recorder 2 sees explicit sends.
- [ ] Verify a uniquely named BioSemi port is checked automatically when such a
  device is available. With a generic BioSemi interface, check the configured
  port and baud rate, including missing and occupied-port recovery. Run **Find
  Port…** and confirm only the single port added on reconnect is checked. Repeat
  with an unrelated serial-device change and verify neither candidate is opened.
  Send digits `1`, `9` and a repeated `5` and confirm receipt in ActiView.
- [ ] Confirm the recorded project port and baud rate are preserved after the
  tester closes, including after a detected reassignment or manual override.

Close when the recording-lab operator and Studio maintainer have recorded the
build, device/driver and recorder versions, port decisions, connection recovery
and receiver observations for both devices. Use the
[Trigger Tester smoke path](../../GUI_WORKFLOW.md#trigger-tester) and the
[trigger adapter guide](../../../src/fpvs_studio/triggers/AGENTS.md).
