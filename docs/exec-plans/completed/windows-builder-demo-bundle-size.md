# Remove upstream Builder examples from the Windows bundle

Status: Completed

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

## Release evidence

The one-freeze 3.1.5 comparison compiled a reference with the 152 Builder
files restored. All shared payload bytes and timestamps and the legacy ownership
inventory matched. The full setup fell from 299,577,255 to 282,494,129 bytes,
a reduction of 17,083,126 bytes (5.70%). Installed size fell by 21,546,628
bytes. The 481 native DLL/PYD hashes and 2,284 other PsychoPy data hashes
matched 3.1.4. The Windows payload contains 6,918 owned files.

The [accepted hosted run](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/45052929017)
matched the ownership inventory on the fresh install, the full upgrade from
3.1.4, and every direct patch. It verified removal of the previous Builder files
without changing the settings or project sentinels. Each installed phase
opened the two bundled Color Oddball Demo preview images and read PsychoPy's
isolated monitor calibration.

The fullscreen Test Mode fixture compiled to 50 frames. The runner reported
its OpenGL version below PsychoPy's minimum before opening the window. The
acceptance rerun used the same draft bytes and recorded the exact reported
graphics limitation. The raw report remains in the installer evidence.
