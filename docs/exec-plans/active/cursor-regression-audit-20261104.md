# Cursor regression audit

Status: Active

The original Creatine report was on the experiment computer directly. The user
reproduced an invisible/unusable cursor here on exclusive fullscreen response screens
viewed through Parsec, despite native visibility flags and accepted clicks. The earlier
native-state checks were insufficient physical acceptance. The teardown and
frame-rendered response-cursor repairs are implemented. The user has now confirmed
visible movement and aligned clicks in the same exclusive fullscreen/Parsec case;
physical Escape and post-Escape relaunch also passed. Source verification is complete.
Keep this plan active for the original reporter's direct-host
qualification; that machine-specific cause has not been established here.

## Current repair and acceptance

- Implemented Pyglet's supported drawable image cursor on Windows mouse-response screens,
  with a high-contrast pointer inside the presented frame. Keep existing click
  capture and coordinates, keyboard handling, scoring and timed FPVS playback.
- Restores the previous cursor and visibility on every exit; creates and releases its
  texture on the presentation thread. Unsupported pointer setup must fail explicitly.
- Added fake native-cursor lifecycle/failure tests, including rejection without
  deletion of a shared texture; final verification is listed below.
- Passed exclusive fullscreen Creatine image/word checks through the user's Parsec
  connection. The user confirmed visible movement and aligned clicks. Native flags
  alone cannot pass this gate. Physical Escape and return/relaunch passed too.

## Reproduction after the initial audit

A physical fullscreen Escape retry returned `aborted=True, key="escape"` and closed
with the native cursor visible. A later image retry accepted `apple-target`, but the
user reported visible images with an invisible/unusable pointer and confirmed Parsec
as the viewing/input connection. This is a failed cursor-visibility test, regardless
of the successful input or native `CURSOR_SHOWING` flag. The software-cursor change
addresses the presentation path; it does not establish the original reporter's
machine-specific cause.

Pyglet's installed Win32 backend already supports `ImageMouseCursor`, drawing it just
before the buffer swap and managing native cursor bookkeeping. This avoids cursor
counter manipulation and a second mouse-coordinate implementation. [Pyglet cursor
guide](https://docs.pyglet.org/en/development/programming_guide/mouse.html#changing-the-mouse-cursor).
Parsec also documents hardware-cursor/capture failure modes; those are possible
additional causes, not a diagnosis of the original local report. [Parsec input
troubleshooting](https://support.parsec.app/hc/en-us/articles/32381827815188-Mouse-and-Keyboard-Isn-t-Working-Correctly-When-Connected).

## Scope and repair

Reviewed the shared response renderer, recall/AB delegation, native window lifetime,
refresh probes, GUI worker reuse and shutdown. Studio's authoring UI has no blank
cursor or application-wide cursor override. Clickable response screens already
enable the pointer and restore its previous state on success, abort and errors.

PsychoPy closes its backend before restoring cursor visibility. Backend teardown
can fail first, leaving the hidden pointer state behind. Session and refresh-probe
cleanup now explicitly restore visibility while the native handle exists, then
attempt close even if that restoration fails. Restoration failures are logged and
propagated when close succeeds. Existing close exceptions retain precedence.

Added nine teardown failure/ordering cases and four image/text recognition-feedback
cycle cases. Runtime timing, task selection/scoring and project formats are unchanged.

## Creatine and interpreter checks

The current Creatine project compiles at its saved 60 Hz. Its image and word
recognition modules each repeat four single-choice grids with one-second feedback.
They use the shared mouse-response renderer and have no project cursor setting.
Required task assets exist. The project file was unchanged after the checks:
SHA-256 `a166410b20a116a7d36b74d157da018b3914296685e7a54da9498f96e6320739`.
Participant records and experiment outputs were not read or changed.

PyCharm's configured `.venv` loads this checkout's source, using Python 3.10.11,
PsychoPy 2026.1.3 and Pyglet 1.4.11. The harness uses PsychoPy 2026.1.1; the relevant
PsychoPy and Pyglet cursor/window files are byte-identical between environments.

## Initial source verification, before the software pointer

- Engine focused checks: 577 passed, with changed-file Ruff and compilation passing.
- Targeted engine/mouse/recall checks in PyCharm's interpreter: 265 passed.
- Repository precommit: 5,236 passed, 32 platform/permission/dependency skips;
  Windows/Darwin type checks and repository audits passed.
- Counts overlap and must not be added together.

## Initial approved native checks, before the software pointer

Used copied task screens/assets, isolated settings/profile folders and the real
Studio persistent presentation worker/current engine. No EEG transport, real
participant session or production project writes were involved. Native cursor
observations use read-only `GetCursorInfo`; qualified response samples require the
presentation window to be foreground and the pointer inside its client area.

The nonexclusive 1280x720 borderless diagnostic explicitly used
`allowGUI=False` to exercise the native hidden-to-visible transitions:

- Four image and four word recognition/feedback cycles accepted target clicks.
- All 6,416 qualified response-flip samples had `CURSOR_SHOWING` and
  `mouseVisible=True`; all 494 qualified feedback samples had the expected hidden state.
- Switching focus away and back preserved response cursor visibility.
- Host-button engine abort succeeded, then a relaunched image screen accepted a
  ninth target click. This was engine cancellation, not an observed Escape key.
- All three native windows used one presentation thread and closed with the cursor
  visible. No errors/deadlines occurred; the diagnostic exited with code zero.

An exclusive fullscreen check completed its refresh probe. A subsequent attempt
recorded 3,593 qualified response-flip samples with native visibility over about
60 seconds. Its renderer back buffer contained the correct Creatine grid, but
desktop capture showed stale/blank content, preventing verified fullscreen clicks.
Both fullscreen attempts reached their bounded response deadlines and restored the
cursor cleanly. A separate ordinary windowed check accepted image/word clicks too.
These native-state checks did not establish participant-visible cursor acceptance;
the subsequent user report reproduced the failure despite those flags.

## Software-pointer native acceptance

The repaired production engine ran two image and two word recognition/feedback
cycles in exclusive fullscreen at 1920x1080, followed by a reopened physical Escape
screen and a post-Escape image response, on the same persistent presentation thread.

- The user confirmed: "Visible, moving, and clicks align" through Parsec.
- Five target clicks were accepted (three apple, two Pen), four feedback screens
  completed, and physical Escape returned `aborted=True, key="escape"`.
- All 1,068 qualified response-flip samples used `ImageMouseCursor`, with drawable,
  logical visibility and inside-window state true. Native hardware flags were zero,
  as expected while Pyglet rendered the pointer into the frame.
- All 247 qualified feedback samples restored the default cursor and hidden state.
- Three native windows used one presentation thread. Every close restored the
  default cursor and native visibility; no setup/cleanup errors or deadlines occurred.
- The diagnostic process exited with code zero. Texture ownership/deletion is
  additionally covered by the fake lifecycle tests; no per-texture native counter
  was recorded.

## Final source verification

- Final software-pointer engine focused checks: 608 passed, including the
  shared-texture rejection regression, with changed-file Ruff/compilation passing.
- Final targeted engine/cursor/mouse/recall checks in PyCharm's interpreter:
  296 passed.
- Repository precommit: 5,270 passed, 32 platform/permission/dependency skips.
  It began before the last unsupported shared-texture rollback refinement; the final
  focused and PyCharm checks above, plus targeted helper mypy, cover that refinement
  and its additional regression. Counts overlap and must not be added together.
- Changed-file Ruff/compilation, Windows all-source and Darwin adapter type checks,
  verification configuration (15 scopes), and documentation focused checks passed.

## Limits

The original reporter's direct experiment-computer state and cause remain
unqualified. The complete Studio launch/preflight/export workflow and physical
timing were not exercised. Automated Escape was not received by the low-level
keyboard path and was not counted as passing; the later human Escape was recorded
and passed. Screenshot cursor overlays alone were not treated as proof of visible
cursor behavior. All diagnostic processes exited cleanly.
Automatic approval review blocked temporary-folder deletion with "blocked by policy";
the task-owned evidence remains outside the repository in the local Temp folder
`fpvs-cursor-smoke-d856d1dc17`.
