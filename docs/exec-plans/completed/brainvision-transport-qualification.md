# BrainVision transport qualification without hardware

Status: Completed

Software investigation, demonstrated fixes and visible setup verification are complete.
Physical acceptance remains separate and is listed in `docs/RUNTIME_EXECUTION.md`.

## Requested outcome and assumptions

Diagnose the reported COM4 access denial and close demonstrable software gaps in
Studio's supported USB TriggerBox rev.02/Plus paths: actiCHamp/actiCHamp Plus with
BrainVision Recorder 2, and LiveAmp with Recorder 1 through wired eight-bit STE input.
The operator has no hardware access now and does not want vendor software installed.
The operator confirmed both Recorder/amplifier pairings; TriggerBox revision remains unknown.
Do not imply support for every Brain Products transport or certify physical behavior.

## Boundaries and work

1. Compare setup, serial protocol and Recorder guidance with official vendor sources.
2. Run existing focused tests and replay the original failure through real pySerial
   with the Windows device boundary intercepted before any actual port access.
3. Use a localhost receiver with real pySerial to verify complete marker bytes,
   zero resets and reconnection. This is a software transport test, not USB emulation.
4. Reproduce and repair concrete pending-write, cleanup, discovery or runtime gaps.
   Preserve flip scheduling, explicit errors, port selection, and no automatic resends
   or fallback. Any completion wait must be bounded and must not silently delay a
   marker to a later flip.
5. Run applicable focused and repository checks, record remaining physical acceptance
   requirements, update canonical guidance and commit/push the completed work.

## Initial evidence

- The supplied traceback fails in Windows serial open before any trigger write.
  An occupied COM port best fits the user's report of Test IO running successfully,
  but access denied cannot identify the owning application or prove that root cause.
- Baseline: trigger scope 295 passed; runtime recording 155 passed, 1 unrelated
  Windows directory-symlink privilege skip. Existing busy-port/retry tests use fakes.
- Official programming examples specify 2,000,000 baud, 8N1, no flow control and
  one raw byte for the lower eight output bits. Studio's selected protocol matches.
- LiveAmp timing/serialization/backend support already exists, but generic Recorder
  lower-eight-bit guidance omitted its required STE input. Setup now names the wired
  eight-bit extension, Recorder 1, compact prerequisites and extension-specific mapping;
  actiCHamp guidance includes Recorder 1/2 and Recorder 2's Workspace Editor.
  Native LiveAmp jacks and Wireless Trigger are not interchangeable with this route.
  No marker inversion or persistent format changed.
- Real pySerial Win32 open now has native denied/missing-port replay coverage (157
  runtime-recording tests passed, 1 unrelated privilege skip). A real pySerial
  localhost test received all 255 event codes with zero resets and reconnected.
- Native-write simulation reproduced a separate defect: Windows pending writes
  could reuse the same completion structure before finishing, and close could
  cancel the final pending zero without reporting failure. The fix tracks one
  pending write, retains its buffer, observes completion/errors and drains cleanup
  outside the display-flip callback. This did not cause the original open failure.

## Implementation and verification

- Native completion ownership now includes bounded startup/reset/close drains,
  terminal cancellation checks, and retained storage with restart guidance when
  Windows cannot confirm completion. The initial two regression cases failed before
  the fix; all 12 native cases now pass. Independent review found and corrected an
  exception self-cause in initial-zero failure handling before final signoff.
- Trigger focused verification: 308 passed, including the real localhost transport.
  Runtime recording: 157 passed, 1 unrelated directory-symlink privilege skip.
  GUI non-Qt focused verification: 178 passed. Documentation: 13 passed, hygiene
  passed, verification configuration passed for all 15 scopes.
- Operator-approved visible Recording Setup run: 183 passed, 14 failed. The new
  amplifier-specific guidance and geometry checks passed. Broader coverage exposed
  detection overwriting explicit COM choices, a clipped failed-save explanation,
  and stale expected dictionaries missing an already-existing parallel-address key.
  Repaired the combo's selected-row ownership and reduced Recording tab spacing;
  updated the stale expected field without changing persistence. All 197 visible
  Recording Setup checks then passed, including minimum-size/error states in both
  palette variants. A further regression reproduced selecting COM9, typing COM42,
  then Detect displaying COM9 while checking COM42. Preserving the draft through
  tooltip refresh fixed it; all 111 affected visible cases passed afterward.
- Final combined visible run: 195 passed, one import rename access failure and two
  settings-write fixture errors in Home/Unicorn checks. All three cases passed in a
  separate visible rerun without code changes. The rename failure resembles the
  pre-existing Windows issue recorded in the plain-language-error-recovery plan;
  the transient access failures' cause remains unconfirmed. The final manual-port
  change also passed the 178 non-Qt GUI checks and its Windows type check.
- Repository precommit passed in a hash-matched short-path checkout excluding
  unrelated user-owned untracked files: 5,500 passed, 32 platform/permission skips,
  24 passing subtests; Ruff, compilation, Windows typing (272 files), macOS typing
  (9 files), source audits and documentation hygiene passed. An initial audit launch
  selected system Python 3.13; verification's process-local PATH was corrected to
  the existing project Python 3.10 environment. The final small Detect draft-text
  preservation change and its registered test landed during that run and were
  verified separately by the GUI checks and type check above.

## Sources and limits

- [Vendor application interface](https://www.brainproducts.com/download/triggerbox-programming-examples/)
- [Vendor software and drivers](https://www.brainproducts.com/downloads/more-software/)
- [Windows exclusive communications handles](https://learn.microsoft.com/en-us/windows/win32/devio/communications-resource-handles)
- [Windows pending-write ownership](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-writefile)
- [pySerial simulated transports](https://pyserial.readthedocs.io/en/latest/url_handlers.html)
- [Recorder compatibility](https://www.brainproducts.com/downloads/recorder/)
- [LiveAmp STE input and prerequisites](https://www.brainproducts.com/solutions/liveamp-ste/)

No vendor software/driver installation, actual COM opening, EEG receipt or physical
latency qualification is authorized by these software simulations. The operator
separately approved visible Qt checks using simulated hardware on November 5.
The training statement about a constant 1 ms delay remains attributed guidance;
software tests cannot measure the actual display-to-EEG pathway.
