# Publication and Citation

Use this page when recording which FPVS Studio version was used for a study.

## Software Identity

- Name: FPVS Studio
- Package name: `fpvs-studio`
- Current package version: `1.0.0`
- Repository: <https://github.com/zcm58/FPVS-Studio-2.0>
- License: GPLv3 or later

## What to Record

For each study, save:

- the FPVS Studio version
- the GitHub Release tag
- the installer file name, such as `FPVS-Studio-Setup-1.0.0.exe`
- the project `.fpvsconfig` export, if your lab uses it for handoff records
- the final project folder, including `runs\` and `logs\`

Use the release tag, not only the website URL, when documenting a study.

## Suggested Methods Wording

FPVS experiments were authored and launched with FPVS Studio, a Windows desktop
application for guided Fast Periodic Visual Stimulation experiment setup and
fullscreen PsychoPy-based runtime execution.

Before submission, replace this general sentence with the exact version, release
tag, trigger setup, display setup, and study-specific configuration details.

## Current v1 Scope

The current 1.0.0 package is a beta release intended for Windows 11 lab
computers and BioSemi-compatible serial trigger workflows. It uses a fixed FPVS
timing template with 6 Hz base stimulation and oddballs every 5th item.

Lab timing precision still needs validation on the actual computer, display, EEG
system, and cabling used for data collection.
