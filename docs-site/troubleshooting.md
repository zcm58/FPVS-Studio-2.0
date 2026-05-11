# Troubleshooting

## Avoid Synced Project Folders

If projects fail to save, reopen, or run consistently, check whether the FPVS Studio Root
Folder is inside OneDrive, Dropbox, Google Drive, or another synced folder. Move the root
folder to a stable local path when possible.

## Missing Or Invalid Images

If a project cannot launch, review each condition and confirm that:

- base and oddball folders still exist
- image files were not renamed or moved
- images use consistent square dimensions and file types

## Runtime Launch Issues

Before a participant session, confirm that:

- the intended monitor is connected and configured
- the EEG recording setup is ready
- participant response devices are connected if fixation response tracking is enabled

## Updates Do Not Appear

Use **File > Check for Updates** first. If the in-app check cannot reach GitHub, open the
[GitHub Releases page](https://github.com/zcm58/FPVS-Studio-2.0/releases/latest) in a
browser and compare the installed version with the latest release tag.
