# Remove upstream Builder examples from the Windows bundle

Status: Active

Date: 2026-11-22

## Workflow and evidence

Windows users download a full installer for a fresh install or a full update.
The [PyInstaller spec](../../../packaging/pyinstaller/fpvs_studio.spec) collects
PsychoPy package data, including upstream Builder examples. The retained Studio
3.1.4 bundle contains 152 files under `_internal/psychopy/demos/builder/`
totaling 21,546,628 bytes before installer compression. The Library's color
oddball demo uses [Studio-owned assets](../../../src/fpvs_studio/gui/library_dialog.py)
in `fpvs_studio/assets/oddball-demo/`. The compressed-installer savings still
need measurement.

## Scope and behavior to preserve

Confirm that no supported frozen Studio path reads the Builder examples. Exclude
only that upstream subtree from Windows data collection. Preserve Studio's own
demo, PsychoPy playback and monitor resources, and existing native dependency
and ownership inventory handling. Use the ordinary build and installer entry
points in the [packaging contract](../../PACKAGING.md#build-the-app).

## Verification

- Build baseline and candidate using the same source, dependencies and packaging
  tools except for the exclusion. Compare frozen inventories and bytes, account for
  incidental build metadata, check DLL origins, and record the actual installer
  sizes and installed data bytes.
- Run packaging focused verification. In disposable Windows, check clean install,
  upgrade from a build containing the Builder examples, and uninstall. Verify
  owned-file reconciliation and preservation of unrelated files and project data.
- In an approved native smoke session, exercise Studio startup, fullscreen
  Test/Pilot playback, PsychoPy monitor tools, and the Library color oddball demo
  preview with the frozen candidate.

## Implementation

Filter the component-exact Windows subtree from `Analysis.datas` after the
PsychoPy hook runs. Spec tests exercise Windows, macOS, and Linux and preserve
the order of every other item. The packaged diagnostic reads PsychoPy's test
monitor calibration and checks that the Library loads both real preview images
through Qt. The hosted fresh install also requests one fullscreen Test Mode
condition with synthetic images and the null trigger backend. Its fixture
compiled to 50 frames in source checks. Exact installer comparison and the
disposable install lifecycle use the 3.1.5 release candidate.

Packaging focused verification passed 216 tests. Updates passed 377 tests
with four Windows symlink-permission skips. Docs, verification configuration,
and the changed diagnostic's Windows type check passed.
