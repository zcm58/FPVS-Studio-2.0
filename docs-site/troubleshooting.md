# Troubleshooting

## The App Will Not Install

Windows SmartScreen may warn you that the installer is from an unknown publisher.
If your lab allows the install, choose the option to run the installer anyway.

If the installer still fails, confirm that you downloaded the Windows setup file:

```text
FPVS-Studio-Setup-*.exe
```

## Projects Fail to Save or Reopen

Check whether the FPVS Studio Root Folder is inside OneDrive, Dropbox, Google
Drive, a network drive, or another synced folder. Move the root folder to a
stable local path when possible.

A good example is:

```text
C:\FPVS Studio
```

## A Project Is Not Ready to Launch

Open the project and choose **Complete Setup** or **Edit Setup**. Review each
Setup Wizard step.

Common blockers are:

- a condition has no base or oddball stimuli
- a condition trigger code is missing or set to `0`
- image files were moved, renamed, or deleted
- the display refresh rate does not work with the selected timing template

## Image Folders Need Cleanup

If FPVS Studio reports mixed image sizes, non-square images, or mixed file types,
use the cleanup option shown during setup. The app can create project-local PNG
copies at `512x512` or `256x256`.

You can also prepare images before setup from:

```text
Tools > Image Resizer
```

## Fullscreen Launch Fails

Before launching a participant session, confirm that:

- the intended monitor is connected
- Windows is using the expected display resolution
- the project display settings match the lab monitor
- no other fullscreen app is blocking the display

If the project has an intended display resolution and the actual fullscreen
resolution is different, FPVS Studio stops before stimulus playback.

## BioSemi Triggers Do Not Appear

Confirm the hardware setup before running participants:

- the BioSemi USB Trigger Interface is connected
- Windows shows the expected COM port
- the EEG recording software is ready
- the trigger cable is connected correctly

New projects use a BioSemi-compatible serial trigger setup by default. The
default port is `COM3`, and oddball onset markers use code `55`.

Software checks cannot prove that the physical EEG/status channel is wired
correctly. Validate the full lab setup before data collection.

## Participant Number Warning Appears

FPVS Studio warns if it finds a completed session for the same participant
number. Check that the participant number is correct before continuing.

## Updates Do Not Appear

Use **File > Check for Updates** first. If the in-app check cannot reach GitHub,
open the [GitHub Releases page](https://github.com/zcm58/FPVS-Studio-2.0/releases/latest)
in a browser and compare the installed version with the latest release tag.
