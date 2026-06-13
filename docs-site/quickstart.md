# Quickstart

This guide walks through a first project. It assumes FPVS Studio is already
installed and that you have chosen an FPVS Studio Root Folder.

## Create a Project

1. Open FPVS Studio.
2. Choose **Create New Project**.
3. Enter a project name.
4. Add a short description if it will help your lab identify the study later.
5. Continue into the Setup Wizard.

FPVS Studio saves the project inside your Root Folder. You can reopen it later
from **Open Projects**.

## Work Through the Setup Wizard

The Setup Wizard has six steps:

1. **Project**: confirm the project name, description, timing template, and
   participant tutorial option.
2. **Conditions**: add each condition, choose image or word stimuli, enter
   participant instructions, and set the condition trigger code.
3. **Experiment**: set display refresh rate, presentation background, image size,
   and how many times each condition repeats.
4. **Fixation**: set the fixation cross and color-change schedule.
5. **Response**: choose whether participants press Space when the fixation cross
   changes color.
6. **Review**: check the project and choose **Save and Return Home**.

Most studies can keep the built-in FPVS timing. The current v1 template presents
base stimuli at 6 Hz and oddballs every 5th item.

## Add Conditions

Each condition needs:

- a clear condition name
- a trigger code of 1 or higher
- base stimuli
- oddball stimuli

Image conditions use base and oddball image folders. Word conditions use typed
base and oddball word lists, with one word or short phrase per line.

Condition order is randomized automatically each time you launch a participant
session. Participants see generic condition screens, such as "Condition 1 of 4",
not your internal condition names.

## Save and Reopen

On the Review step, choose **Save and Return Home**. Ready projects open to
Home, where **Launch Experiment** is the main action.

To change a ready project later, choose **Edit Setup**. To continue an incomplete
project, choose **Complete Setup**.

## Before Running Participants

Confirm that:

- each condition has valid base and oddball stimuli
- the display refresh rate matches the lab monitor
- the lab BioSemi trigger setup is ready
- condition trigger codes match the study plan
- fixation and response settings match the participant task
