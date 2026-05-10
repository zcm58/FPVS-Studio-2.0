# FPVS Studio

![FPVS Studio](docs/assets/fpvs-studio-readme-header.png)

FPVS Studio steamlines the process to create and run Fast Periodic Visual Stimulation experiments
without needing to write code. The workflow is designed for non-expert user, with a guided setup wizard for 
creating your conditions, selecting base and oddball images, assigning trigger codes, and includes a unique 
fixation cross accuracy tracking task to guage participant attention on each condition. 

The current beta package is compatible with Windows 11 and BioSemi systems. Future updates will bring compatibilty 
to other data formats. 


## Installation Instructions

Download the latest FPVS Studio installer from the GitHub Releases page.

Run the installer, then launch FPVS Studio from the Start Menu or Desktop shortcut.
You do not need to install Python or open the source code.

On first launch, FPVS Studio asks you to choose an **FPVS Studio Root Folder**. This
folder is where all of your future FPVS experiments will be stored. 

Sometimes, using OneDrive or other services that sync with a cloud service can cause 
issues with loading and running your experiments, so I recommend placing your root folder
outside of one of those directories.


## Create Your First Project

1. Open FPVS Studio.
2. Choose `Create New Project`.
3. Enter a project name.
4. Follow the Setup Wizard instructions :) 

The Setup Wizard walks through:

- `Project`: project name, description, and experiment template.
- `Conditions`: condition names, trigger codes, instructions, and selecting your base and oddball images.
- `Experiment`: display refresh rate, background color, and how many times you'd like your conditions to repeat.
- `Fixation`: fixation cross timing and target schedule.
- `Response`: optional fixation cross accuracy tracking task. 
- `Review`: Double check things before saving! 

## Prepare Images

FPVS Studio assumes that you've placed all of the images you'd like to display for each condition 
in their own folder. This makes setting up your projects easier. 

Each condition needs:

- a dedicated base image folder
- a dedicated oddball image folder
- All images must be the same square size and filetype (256x256, 512x512, etc. .png is the recommended file format)

FPVS Studio can optimize your images for FPVS using the built in image resizer tool. You can quickly resize all your images and change 
them to .png. 


## Run An Experiment

After setup is complete, return to Home and choose:

```text
Launch Experiment
```

Before playback starts, FPVS Studio checks the project and asks for a participant number.
Playback opens fullscreen and uses `Space` for start/continue prompts.

Run outputs are saved inside the project folder under:

```text
runs\
```

Project-level run history is stored under:

```text
logs\
```

## Reopen Existing Projects

Use:

```text
Open Projects
```

After you've set up a project, FPVS Studio allows you to run those experiments in just a few clicks. 

## Manage Projects And Templates

Use the `File` menu to manage projects, change settings, and manage condition templates.
Custom condition templates are stored in your FPVS Studio Root Folder. 


## Updating FPVS Studio

Use `File > Check for Updates` inside FPVS Studio. You can download and install future updates from this screen. 


## Current Beta Notes

FPVS Studio is currently in beta release and is only compatible with BioSemi systems for now. 

Future updates will bring compatibility to other common EEG filetypes. 
