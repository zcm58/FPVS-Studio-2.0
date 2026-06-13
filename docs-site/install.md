# Install

## Requirements

- Windows 11.
- A local folder for FPVS Studio projects.
- A lab computer configured for the current BioSemi-compatible trigger setup.

FPVS Studio is distributed as a Windows installer. You do not need Python,
PsychoPy, or developer tools on the computer that runs the installed app.

## Install the App

1. Open the [latest GitHub Release](https://github.com/zcm58/FPVS-Studio-2.0/releases/latest).
2. Download the `FPVS-Studio-Setup-*.exe` installer.
3. Run the installer.
4. Launch FPVS Studio from the Start Menu or the Desktop shortcut.

Windows SmartScreen may warn you because the installer is not signed by a
large software publisher. If your lab allows the install, choose the option to
run it anyway.

## Choose a Root Folder

On first launch, FPVS Studio asks you to choose an **FPVS Studio Root Folder**.
This folder will hold your projects, saved runs, logs, and reusable condition
templates.

Choose a stable local folder, for example:

```text
C:\FPVS Studio
```

Avoid OneDrive, Dropbox, Google Drive, network drives, or other synced folders
when possible. Sync tools can rename, lock, or move files while FPVS Studio is
trying to save or run a project.

You can reopen the root-folder guide later from the app settings.
