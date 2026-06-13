# Prepare Stimuli

FPVS Studio can run image conditions and word conditions. Prepare your stimuli
before you build the project so setup is easier.

## Image Folder Layout

For image conditions, keep each stimulus group in its own folder.

Each condition usually has:

- one folder for base images
- one folder for oddball images

For example:

```text
Faces_Base\
Faces_Oddball\
Objects_Base\
Objects_Oddball\
```

This makes it easier to select the correct folders in the Conditions step.

## Image File Rules

FPVS Studio supports `.png`, `.jpg`, and `.jpeg` source images.

For the cleanest setup:

- use square images
- keep images within the same folder at the same size
- use PNG when possible
- use clear file names

The source image size does not have to match the on-screen display size. The
on-screen size is set in the Experiment step.

## Fix Image Folders During Setup

FPVS Studio checks image folders when you leave the Conditions step. If a folder
has mixed sizes, non-square images, or mixed file types, the app can create clean
project-local PNG copies for you.

The normal choices are:

- `512x512`
- `256x256`

Use the cleaned copies for the project instead of editing the original files by
hand.

## Image Resizer Tool

You can also prepare a folder before project setup with the built-in Image
Resizer.

Open it from:

```text
Tools > Image Resizer
```

The tool creates optimized PNG copies in a new sibling folder. The default output
size is `512x512`, with `256x256` and `1024x1024` also available.

The Image Resizer does not change any open project. After it finishes, select the
new output folder when you set up a condition.

## Control Conditions

For image conditions, FPVS Studio can create optional control conditions from an
existing condition. Current options include grayscale, 180 degree rotation, and
phase scrambling.

Control-condition tools are for image conditions only. They do not apply to word
conditions.

## Word Stimuli

For word conditions, type or paste one word or short phrase per line in the
Conditions step. You do not need image folders for word conditions.
