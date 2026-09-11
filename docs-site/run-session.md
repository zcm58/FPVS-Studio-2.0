# Run a Session

Use a saved project to launch each participant session.

## Before the Participant Arrives

Confirm that:

- the intended project is open
- the lab monitor is connected and set to the expected refresh rate
- the display resolution matches the project display settings
- the BioSemi recording setup is ready
- participant response devices are connected if fixation accuracy tracking is on
- the project is not stored in a synced folder such as OneDrive or Dropbox

## Launch

1. Open FPVS Studio.
2. Choose **Open Projects** and select the project.
3. On Home, choose **Launch Experiment**.
4. Enter the participant details when prompted.
5. Start the EEG recording when your lab protocol says to begin.
6. Follow the fullscreen prompts.

The participant details prompt asks for:

- Participant Number
- Age
- Sex
- Handedness

Participant Number must use digits only, such as `0012`. If FPVS Studio finds a
previous session for that participant number, it checks whether the project allows
repeat visits. Keep the same number, including any leading zeros, at each visit.

## Returning Participants

For a study in which participants return more than once:

1. Open **Setup > Project**.
2. Enable **Allow repeat participant sessions** and save the project.
3. Launch the experiment with the participant's existing Participant Number.
4. Review the proposed session number and choose **Start Session 2** (or the next
   available number).

FPVS Studio assigns Session 1 to a participant's first visit and a separate number
to each later visit. These numeric labels distinguish visits without changing the
participant ID. If repeat sessions are disabled, an already-used participant number
is blocked until you correct the number or enable repeat sessions for the project.

Earlier session data stays in place. Aborted or interrupted sessions keep their
allocated number, so a later launch uses a new number. Canceling the repeat-session
confirmation does not start a session.

## During Playback

Playback opens fullscreen on the default display.

Use:

- `Space` to start each condition or continue after a block break
- `Space` for fixation accuracy responses when that task is enabled
- `Escape` only to abort a run when needed

If the participant tutorial is enabled, FPVS Studio shows a short fixation
practice before the first condition.

Condition order is randomized automatically for each launch. Participant screens
use generic condition numbers, while the real condition names are saved in the
run files.

## Outputs

With full run exports enabled, each session has its own folder inside the project.
For participant `1`, the first two session folders are:

```text
runs\
  P1_session01\
  P1_session02\
```

Project-level history and summaries are saved under:

```text
logs\
```

Useful summary files include:

- `logs\session_condition_history.csv`
- `logs\participant_summary.xlsx`
- `logs\participant_summary.csv`

The participant summary CSV and Excel workbook include both **PID** and
**Session Number**. Use the pair to identify a visit, for example PID `1`, Session
Number `2`. The condition history CSV records these as `participant_number` and
`participant_session_number` for new sessions. Compact export mode keeps the
project-level logs and summaries without creating detailed session folders.

You can also create a group-level workbook from the app with:

```text
File > Export > Group Summary...
```

Keep the whole project folder, including `runs\` and `logs\`, when archiving or
transferring study data.
