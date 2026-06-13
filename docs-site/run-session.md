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
previous completed session for the same participant number, it warns you before
continuing.

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

Detailed session and run outputs are saved inside the project folder under:

```text
runs\
```

Project-level history and summaries are saved under:

```text
logs\
```

Useful summary files include:

- `logs\session_condition_history.csv`
- `logs\participant_summary.xlsx`
- `logs\participant_summary.csv`

You can also create a group-level workbook from the app with:

```text
File > Export Group Summary...
```

Keep the whole project folder, including `runs\` and `logs\`, when archiving or
transferring study data.
