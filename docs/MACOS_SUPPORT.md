# macOS source support

Phase 1 targets the Windows source application's non-hardware authoring and local
experiment-testing workflows on macOS. Source implementation is complete; native CI
qualification is pending. Physical Mac GUI/display/service acceptance was explicitly
deferred by the user on 2026-11-02 and remains open. No full software-parity or hardware
qualification claim follows from source changes or Windows/fake-backed tests.

This phase does not include a signed `.app`/DMG, Windows installer/update execution,
EEG acquisition or Mac hardware qualification. External Toolbox/vendor applications
remain outside this repository. The [active plan](exec-plans/active/macos-source-phase-1.md)
owns completion status; [Environment](ENVIRONMENT.md) owns dependency and verification
policy, [GUI workflow](GUI_WORKFLOW.md) owns authoring behavior and
[runtime execution](RUNTIME_EXECUTION.md) owns playback and export contracts.

## Current acceptance gates

| Gate | Recorded evidence/status |
| --- | --- |
| Implementation | Source helpers, adapters, local testing, bundle guards, handoff CLI and software inventory complete. |
| Safe Windows checks | Mac-focused scope: 345 passed, 4 native-only skips. Broader bundle/preprocessing/task/update checks: 228 passed; latest portability/handoff subset: 51 passed, including 3 CLI checks. Counts overlap. |
| Visible Windows checks | 7 new GUI cases plus 1 palette and 2 Save cases passed. Mac-only policy was faked; these are not native Mac GUI results. |
| Repo precommit | Running; final result pending. |
| Mac CI | arm64/x86_64 dependency/native checks and actual Windows -> Mac -> Windows artifact chain configured; successful-run evidence pending. |
| Physical Mac software | Visible GUI/PsychoPy/display, interactive secure-store/service, filesystem and failure/recovery acceptance deferred by user. |
| EEG/hardware | Phase 2; not implemented or qualified here. |

Keep the active plan open until its remaining native gates have evidence. Root will
record CI links and resolved versions after execution; candidate runners are not an
advertised supported matrix yet.

## Install, run and update from source

Use the same Studio version or commit on the Mac and Windows computers. Install
native Python 3.10 for the Mac's CPU architecture and obtain the source checkout.

Intel installation also requires Apple command-line tools, Rust 1.83 or later and
OpenSSL 3. The current [cryptography 50.0.2](https://pypi.org/project/cryptography/50.0.2/#files)
and [zeroconf 0.152.1](https://pypi.org/project/zeroconf/0.152.1/#files) releases provide
Apple Silicon wheels but build from source on Intel. Install Apple's tools with
`xcode-select --install` if absent. With [Homebrew](https://brew.sh/) already installed:

```bash
brew install openssl@3 rust
```

See [cryptography's native build requirements](https://cryptography.io/en/50.0.2/installation/#building-cryptography-on-macos).
Apple's system SSL libraries cannot substitute for OpenSSL 3. If setup cannot locate
Homebrew's OpenSSL, prefix the `setup` command below with its explicit location:

```bash
OPENSSL_DIR="$(brew --prefix openssl@3)" bash scripts/macos-source.sh setup
```

On either architecture, run from the checkout directory in Terminal:

```bash
bash scripts/macos-source.sh setup
bash scripts/macos-source.sh verify
bash scripts/macos-source.sh run
```

`setup` creates/reuses `.venv3.10`, installs the declared `dev,engine` extras and runs
`pip check`. Set `FPVS_PYTHON=/absolute/path/to/python3.10` if Python is not available
as `python3.10`. Dependency resolution must succeed without ignoring requirements or
mixing Intel and Apple Silicon environments. A clean install on an untested target
remains unqualified if wheels or compatible dependency versions are unavailable.

For source updates, close Studio, preserve any local source edits, update to the
chosen revision (for example, `git pull --ff-only` on an unmodified tracking branch),
then rerun `setup` and `verify`. An editable installation does not refresh changed
dependency requirements automatically. The Windows executable installer and repair
workflow are not Mac source updates.

Choose a local FPVS Studio Root Folder. Mac source testing uses the explicit local
Test/Pilot path and null trigger output; it must retain native display verification,
engine observation and timing QC. Test calibration is launch-local and must not save
over the experiment's lab settings. A successful local test is not EEG readiness or
physical timing qualification. Follow the current [launch contract](GUI_WORKFLOW.md#launch)
for unsupported display modes, timing constraints, test identity and eligibility.

## Evidence levels and software inventory

- **Shared:** the same models, services, GUI/runtime routes or contracts exist on both
  hosts. Existing safe tests support their logic; this does not establish native GUI,
  service-account or physical presentation success on macOS.
- **Adapter:** a Mac-specific seam has source/fake-backed coverage. Native execution
  is still required for that seam.
- **CI pending:** the Mac lane is configured; no successful run is claimed here until
  its OS, CPU, resolved dependencies, test report and commit are recorded.
- **Physical deferred:** requires an approved visible Mac session or two computers;
  hosted adapter tests cannot replace it.

| Software area | Current implementation/evidence | Remaining Mac evidence |
| --- | --- | --- |
| Source startup and dependencies | Shared Python 3.10/PySide6 app; source helper installs real engine dependencies. | CI pending for each CPU; first visible startup, restart and close are physical deferred. |
| Projects and all eight Setup steps | Shared root discovery, create/open/save, drafts, templates and validation; same persisted schemas. | Native dialogs, long paths, cancel/permission errors, 1120x820 bounds and both themes. |
| Experiment categories | Shared FPVS Oddball, Cognitive Load FPVS and supported letter-stream Attentional-Blink authoring/compiler/runtime. Standard FPVS remains unavailable on all hosts; retired image-pair AB remains unsupported. | Representative native local tests for every supported category; no category is qualified merely by being listed. |
| Timing, session order and fixation | Shared frame compiler, display-rate constraints, randomization domains, saved/partial condition blocks, fixation counts/timing rules and seeded realization. | Same-target cross-OS schedule comparisons; physical refresh, Retina geometry and onset checks. Different refresh targets need compatible authored timing, not assumed identical frames. |
| Images and words | Shared import, inspection, variants, normalization, resizing, image/character geometry and word content. Portable intake guards and Finder-metadata tests are non-Qt. | Native source selection, case-sensitive volumes, Unicode filenames, previews and resizer flows. |
| Tasks and modifiers | Shared instructions, study/choice/questionnaire/key/feedback steps, backward counting, image memory, masking scenes, questions, branches and scoring. | Native task rendering/input, explicit/exact geometry, abort/recovery and result comparison. |
| Local presentation | Existing PsychoPy session/runtime reused; Mac launch/display/process adapters preserve explicit local testing and project settings. | CI imports/adapters do not open a presentation window; fullscreen render, main-thread lifecycle, keyboard response and cleanup remain physical deferred. |
| Display, file/folder actions and secure credentials | Mac native mode provider, Finder/Trash operations and Keychain seam; fake-backed regression coverage. | Native CI probes are pending; physical display accuracy, Finder presentation, locked Keychain and interactive recovery remain deferred. |
| Library and project version updates | Shared catalog, enrollment, independent imports and reviewed same-folder update services; credentials remain machine-local. | Authorized native login/enrollment, restart, disconnect/revocation, download/update/cancel and network failure flows. No live service action is claimed by this change. |
| Sharing, comparisons and support | Shared results/consent/outbox, comparisons, manual bug reports and crash reporting through existing service contracts. | Native authorized end-to-end checks, opt-out, offline/retry and secure-store recovery; no automatic permission to contact services. |
| Templates and presets | Shared factory/app-owned condition templates, modifier presets, import/export and project category boundaries. | Native dialogs and paths; unchanged source/preset behavior after relocation and restart. |
| Exports and reports | Shared configs, run/session artifacts, CSV/XLSX summaries, accuracy/masking/AB reports and completed Toolbox handoff generation. Bundles carry editable design/assets, not run history. | Native file dialogs, local-test export/reopen and semantic comparisons; external Toolbox execution is not included. |
| Maintainer tools and access control | Shared publishing/review tooling remains behind existing authorization/capability checks; ordinary users gain no maintainer access. | Authorized native checks only; service permissions and publication requirements remain unchanged. |
| Menus, shortcuts, fonts and accessibility | Shared Qt UI; Save/Find use standard bindings and native shortcut text. Open Sans task font is bundled; authored font choices remain explicit. | Command-key/menu behavior, Tab/arrow navigation, focus, VoiceOver, glyph coverage, Arial/font resolution and scientific text geometry. |
| Source updates and version display | Explicit Git/dependency update workflow; source version remains visible. Windows package installation is outside Mac Phase 1. | Native source-version/update messaging and dependency refresh/restart. |

## Automated Mac evidence

[macos-source.yml](../.github/workflows/macos-source.yml) defines native Python 3.10
lanes for `macos-15`/arm64 and `macos-15-intel`/x86_64. These are qualification
candidates, not an advertised support matrix until their runs pass. The workflow
records OS/interpreter/dependency versions and JUnit results for the exact commit.
A dependency or runner failure is a visible gap, not a reason to bypass constraints.

The handoff jobs exchange an actual synthetic artifact: Windows creates a bundle and
baseline, each Mac lane imports/compiles/re-exports it, then Windows checks each
returned bundle. The fixture contains images, Unicode/space filenames, inline words,
grayscale derivatives, bound task media, saved partial condition blocks, independent
seeds, fixation schedules and a Windows recording declaration. It moves its synthetic
source before the first import and compares semantic state, payload SHA256 and the
full compiled 60 Hz session plan at every stage. It does not open a GUI or presentation
window. The [handoff CLI](../tests/integration/macos_bundle_handoff.py) supports `create`
and `roundtrip`; each output holds `project.fpvsbundle`, unchanged `baseline.json`
and host-specific `evidence.json`. Successful local reuse on one OS is not a cross-OS
pass; retain the actual CI artifact chain for that claim.

`bash scripts/macos-source.sh verify` runs the safe `macos` focused scope. Native
checks require `FPVS_MACOS_NATIVE_CHECKS=1`; CI enables it explicitly. Those checks
import native bindings and PsychoPy without opening a window, probe available display
information, and use unique synthetic Keychain/Trash items with cleanup. The hosted-only
Keychain check creates an unlocked temporary store and restores the runner's previous
default/search list afterward; it does not unlock or change access controls on the login
Keychain. A real child-process IPC check rejects acquisition settings before any engine
or hardware is created. These checks do not contact EEG devices, use real projects or
establish physical display timing. Neutral
core imports must remain independent of Qt/PsychoPy/hardware. Qt execution requires
the approved visible-environment policy in [Environment](ENVIRONMENT.md#gui-test-environment).

Record successful run links and the resolved matrix before marking **CI pending**
items qualified. Hosted display diagnostics can explain an unavailable mode without
claiming a connected research monitor was verified.

## Bundle transfer and portability

Use **Export > Project Bundle...** for a full editable transfer and **Import > Project
Bundle...** on the receiving computer. `.fpvsconfig` is a setup/handoff export and
intentionally omits ordinary image pools; it is not a substitute for `.fpvsbundle`.

Bundles preserve project/manifest JSON and owned stimulus, word, task and scene media
with payload hashes. Run history, logs, cache, credentials and local enrollment/test
preferences are excluded. Receiving imports stage and validate before creating a
unique project folder. A failed or cancelled operation preserves existing projects
and cleans only its own staging; export preserves the previous destination.

Portable guards reject absolute/drive/UNC/traversal paths, conflicting case or
canonical-Unicode aliases, Windows-reserved/invalid names, trailing dots/spaces and
filename components beyond 255 UTF-8 bytes or 255 UTF-16 units. Archive links/special
files are rejected; export rejects source links/junctions before descending into them.
Stored references must match archive spelling. Export retains authored Unicode
spelling when the source filesystem presents a canonically equivalent name, without
renaming source files or normalizing word content. Ambiguous references fail with an
actionable error.

Image intake, owned folder discovery and bundle export omit only signature-recognized,
unreferenced Finder metadata (`.DS_Store`/AppleDouble). Ordinary authored `._*` images
remain included in the same sorted order. Explicit manifest/task image references are
never silently removed: a reference to recognized metadata fails validation and must
be replaced with an actual image. Original files and manifest membership are unchanged.
Checksums, active-payload rules, resource limits and compile validation still apply.
See [Experiment Library](EXPERIMENT_LIBRARY.md) for stricter publication inventory.

On import, **Open with Imported Values** preserves authored lab calibration;
**Apply & Open Project** is an explicit edit. Review the actual receiving display
and Windows recording setup before acquisition. Mac null output/test state must
never become a saved Windows hardware override.

## Native acceptance to complete later

Use task-owned synthetic projects and record OS/CPU, Studio commit, dependency
versions, display mode/scaling and results. Do not run these steps against real
participant data or publish/contact external services without authorization.

- [ ] Clean source install, first launch, preferences/restart and clean shutdown on
  each claimed target; record the actual dependency matrix.
- [ ] All eight Setup steps at 1120x820 in both themes, long values, dialogs,
  validation/busy/error states, shortcuts, focus and accessibility.
- [ ] Native Keychain, Trash/Finder, locked/unavailable-store and permission/cancel
  recovery; use only synthetic credentials and files.
- [ ] Local fullscreen Test/Pilot for every supported category and representative
  image/word/task/modifier design; confirm no hardware construction or marker writes,
  native/observed refresh agreement, geometry, timing QC and stable abort/close/recovery.
- [ ] Save/open/re-export without unintended changes to lab display/recording values,
  seeds, order, fixation rules, word text, media or participant/test eligibility.
- [ ] Windows -> Mac -> Windows and Mac -> Windows -> Mac bundles, including Unicode,
  spaces, case-sensitive destinations and task/scene media. Relocate/delete synthetic
  external sources, compare payload hashes and semantic design state, and allow only
  deliberate collision-ID remapping. Same-target seeded schedules must match.
- [ ] Reports/configs/Toolbox handoff generation and authorized Library/sharing/support/
  maintainer flows, with unchanged consent and access checks.
- [ ] Windows lab import and normal production preflight with explicit lab hardware;
  acquisition/physical marker qualification remains Phase 2.
