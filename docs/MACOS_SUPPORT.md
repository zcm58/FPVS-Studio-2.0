# macOS source support

Phase 1 targets the Windows source application's non-hardware authoring and local
experiment-testing workflows on macOS. Source implementation and automated source,
native-service and bundle-transfer checks are complete on the recorded CI matrix.
Physical Mac GUI/display/service acceptance was explicitly
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
| Windows regressions | Repo precommit: 4,974 passed, 14 symlink-permission skips; Ruff, full source mypy, compilation and audits passed. Final focused bundle/fixture run: 197 passed, 5 native-only skips. Counts overlap. |
| Windows environment/test-adapter repair | Native Windows precommit on `185471b` in [run 41571020291](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/41571020291): 5,033 passed, four POSIX-only skips, 24 subtests; both type passes and transfer fixture passed. |
| Local Mac repair | Python 3.10.20/arm64 `.venv` passes `pip check`; repo precommit: 4,973 passed, 64 platform/filesystem skips, 24 subtests. Focused visible Mac/Welcome/Library/worker/popup coverage: 100 passed. Original intermittent crash stability remains open. |
| Mac clone bootstrap | Clean managed Python 3.10.22/arm64 install in a spaced path passed full engine requirements, dependency/import checks and nine approved visible Qt cases. Existing `.venv` reuse and scoped PyCharm setup verified; final focused checks: 1,397 passed/15 skips; repo precommit: 4,993 passed/64 skips/24 subtests. See [setup record](exec-plans/completed/mac-clone-bootstrap.md). |
| Refresh recovery | [Run 41583072217](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/41583072217), source `79756a4`: all six jobs passed; Windows 5,051 tests/15 skips/24 subtests; each Mac CPU 1,411 checks/10 skips; both bundle-transfer chains passed. Local 58 visible fake-only Qt checks passed. The physical fullscreen freeze was not rerun; see the [repair record](exec-plans/completed/macos-refresh-recovery.md). |
| Visible Windows checks | 18 focused GUI cases passed across calibration, source updates, test availability, shortcuts and Save. Mac-only policy was faked; these are not native Mac GUI results. |
| Mac CI | [Run 41554238134](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/41554238134), source commit `f6b6721`: all six jobs passed. Each Mac CPU lane passed 1,358 checks with 10 platform-specific skips. Native private-Keychain roundtrip, Trash, display metadata and real child IPC passed. |
| Mac CI after the compatibility repair | Both arm64 and Intel source jobs on `185471b` in [run 41571020291](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/41571020291) passed 1,382 checks with ten platform skips, adapter mypy and native probes using the new dependency selection. |
| Cross-OS bundles | Windows -> Mac -> Windows and Mac -> Windows -> Mac passed on both CPUs. Each transfer matched semantic settings, all 14 asset hashes and complete 7-run plans/fixation schedules, preserving recording settings and seeds. |
| Windows acquisition policy | Separate offline checks of four real Mac exports resolved normal launch flags to Brain Products TriggerBox, never null; missing amplifier/sampling-rate setup correctly blocked readiness. No saved Test/Pilot flags or project-byte changes; no hardware was probed. |
| Physical Mac software | Focused visible Qt checks are recorded above; full GUI/PsychoPy/display, interactive secure-store/service, filesystem and failure/recovery acceptance remain separate. |
| EEG/hardware | Phase 2; not implemented or qualified here. |

Keep the active plan open for the deferred physical and interactive acceptance gates.
The matrix below qualifies installation, shared software checks and selected native
APIs on hosted Macs; it does not establish physical presentation or full GUI parity.

## Install, run and update from source

Use the same Studio version or commit on the Mac and Windows computers. Download
or clone the **whole repository**, not just `src/`: setup needs `pyproject.toml`,
the requirements files and `scripts/`. Keep it in a local folder.

1. In Finder, double-click **Setup Mac.command**. A Terminal window shows progress.
   Wait for **Setup complete**. No preinstalled Python or PyCharm is required.
2. Double-click **Run Mac.command** to open Studio. Select an FPVS Studio Root Folder
   on first launch, as on Windows.
3. To work in PyCharm, install PyCharm separately and double-click **Open in PyCharm
   Mac.command**. Choose **FPVS Studio (Mac)** in the Run menu and click Run. Fully
   quit PyCharm before using this launcher so its interpreter setting is read; the
   shortcut explains this if PyCharm is already running and preserves your open work.

Setup reuses `.venv3.10`, then `.venv`, when present and compatible. Otherwise it
creates `.venv3.10`. Missing native Python 3.10 is downloaded through a pinned,
checksum-verified [uv release](https://github.com/astral-sh/uv/releases/tag/0.13.7),
using uv's [managed Python installation](https://docs.astral.sh/uv/guides/install-python/).
The installer and Python live in ignored `.fpvs-macos/`; keep that folder alongside
the environment because it can contain the environment's base interpreter. Setup
does not change system Python or shell startup files. An existing environment with
the wrong Python version/CPU or an incomplete interpreter is reported and preserved.

`pyproject.toml` remains the only dependency version list. `requirements-macos.txt`
includes its `dev,engine` extras; the primary Windows `requirements.txt` keeps `dev`.
Setup installs with pip, runs `pip check`, checks GUI imports without opening an app,
and verifies engine metadata. Successful installation does not guarantee every GUI,
presentation or service workflow is bug-free; those acceptance gates remain above.

Intel dependencies can require compilation. Setup checks Apple's Command Line Tools,
Rust 1.83+ and OpenSSL 3. If Apple's tools are missing, complete the macOS installer
that setup requests, then run Setup again. Missing Rust/OpenSSL are installed through
[Homebrew](https://docs.brew.sh/Installation); installing Homebrew itself can require
an administrator password in Terminal. These OS/admin prompts cannot be completed
unattended on a new Mac. Existing build tools are reused. A preconfigured OpenSSL
installation can be selected with `OPENSSL_DIR`; Apple's system SSL is insufficient.
See [cryptography's build requirements](https://cryptography.io/en/50.0.2/installation/#building-cryptography-on-macos).

The PyCharm helper prepares `.idea/runConfigurations/FPVS_Studio_Mac.xml`, with the
active venv and `src/fpvs_studio/app/main.py`. It refuses to overwrite a custom file
with that name. With the IDE closed, its optional launcher registers/reuses one SDK
in the selected app's standard Mac settings profile and binds this project's SDK.
Existing SDKs, other project components and run configurations are preserved;
changed XML is backed up under `.fpvs-macos/pycharm-backups/`. This avoids the
process-wide [interpreter startup variable](https://www.jetbrains.com/help/pycharm/configure-an-interpreter-using-command-line.html),
which can change defaults for other unconfigured projects opened in that IDE process.
PyCharm is optional; Run Mac.command launches the shared application directly.
For a nonstandard IDE install, set
`FPVS_PYCHARM_APP` to its `.app` path when invoking the shell helper.

Terminal alternatives, from the checkout:

```bash
bash scripts/macos-source.sh setup
bash scripts/macos-source.sh verify
bash scripts/macos-source.sh run
```

`FPVS_PYTHON=/absolute/path/to/python3.10` selects an existing interpreter;
`FPVS_MANAGED_PYTHON=1` exercises managed Python acquisition on a fresh checkout
even if Python 3.10 is already on PATH. Existing environments are always preserved
and reused first. Install the declared requirements without `--no-deps` or mixing
Intel and Apple Silicon environments. No guarantee follows for an untested OS/CPU.

If setup fails, its window keeps the error visible. The complete log is
`.fpvs-macos/setup.log`; correct the reported issue and rerun Setup. Network failures,
invalid interpreter versions/architectures and failed packages stop setup. A damaged
environment may be renamed before retrying; do not delete its Python base directory.

Mac dependencies currently select PySide6 6.11.3 and the engine's PyQt6 6.11 line.
The PySide selection is a compatibility mitigation following an observed PySide6
6.12.0 native wrapper/event-filter crash during Library bundle review; the original
crash has not been deterministically reproduced or established as an upstream bug.
The PyQt constraint avoids invalid syntax in 6.12.0's published type stubs.
Windows and Linux keep their previous dependency ranges and shared application code.
The hosted 6.12.0 matrix recorded below predates these constraints; it is historical
evidence, not qualification of the newly selected dependency set.

In a Studio environment previously using 6.12.0, `pip check` may also identify its
orphaned `PySide6_Pdf` and `PySide6_WebEngine` split packages. Remove those 6.12-only
packages, then reinstall the selected complete Qt family to restore overlapping files:

```bash
.venv/bin/python -m pip uninstall PySide6_Pdf PySide6_WebEngine
.venv/bin/python -m pip install --force-reinstall 'PySide6==6.11.3'
.venv/bin/python -m pip check
```

Use `.venv3.10/bin/python` in these commands if that is the environment being refreshed.

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

Mac refresh checks now have a 30-second deadline. Setup's progress dialog also offers
Cancel and responds to application shutdown; a stopped check leaves the refresh rate
unverified and can be retried. Automatic preflight uses the same protected probe,
and playback skips PsychoPy's duplicate constructor measurement. See the
[runtime contract](RUNTIME_EXECUTION.md#session-flow) for lifetime
and validation rules. The reported physical fullscreen freeze has not been rerun;
software timeout/cancellation coverage does not establish GPU-driver recovery.

## Evidence levels and software inventory

- **Shared:** the same models, services, GUI/runtime routes or contracts exist on both
  hosts. Existing safe tests support their logic; this does not establish native GUI,
  service-account or physical presentation success on macOS.
- **Adapter:** a Mac-specific seam behind shared contracts; its fake-backed and native
  evidence are distinguished below.
- **CI passed:** recorded host, CPU, dependencies and commit passed the stated
  automated checks. Physical presentation is not inferred.
- **Physical deferred:** requires an approved visible Mac session or two computers;
  hosted adapter tests cannot replace it.

| Software area | Current implementation/evidence | Remaining Mac evidence |
| --- | --- | --- |
| Source startup and dependencies | Clean engine installs, dependency checks and windowless source imports passed both CPU lanes. | First visible startup, restart and close are physical deferred. |
| Projects and all eight Setup steps | Shared root discovery, create/open/save, drafts, templates and validation; same persisted schemas. | Native dialogs, long paths, cancel/permission errors, 1120x820 bounds and both themes. |
| Experiment categories | Shared FPVS Oddball, Cognitive Load FPVS and supported letter-stream Attentional-Blink authoring/compiler/runtime. Standard FPVS remains unavailable on all hosts; retired image-pair AB remains unsupported. | Representative native local tests for every supported category; no category is qualified merely by being listed. |
| Timing, session order and fixation | Shared frame compiler, display-rate constraints, randomization domains, saved/partial condition blocks, fixation rules and seeded realization; same-target cross-OS schedule comparisons passed. | Physical refresh, Retina geometry and onset checks. Different refresh targets need compatible authored timing, not assumed identical frames. |
| Images and words | Shared import, inspection, variants, normalization, resizing, image/character geometry and word content. Portable intake guards and Finder-metadata tests are non-Qt. | Native source selection, case-sensitive volumes, Unicode filenames, previews and resizer flows. |
| Tasks and modifiers | Shared instructions, study/choice/questionnaire/key/feedback steps, backward counting, image memory, masking scenes, questions, branches and scoring. | Native task rendering/input, explicit/exact geometry, abort/recovery and result comparison. |
| Local presentation | Existing PsychoPy session/runtime reused; Mac launch/display/process adapters preserve explicit local testing and project settings. | CI imports/adapters do not open a presentation window; fullscreen render, main-thread lifecycle, keyboard response and cleanup remain physical deferred. |
| Display, file/folder actions and secure credentials | Native display queries, Trash and private-Keychain roundtrips passed CI; shared Qt folder opening and fake-backed failure coverage retained. | Physical display accuracy, Finder presentation, real login/locked Keychain and interactive recovery remain deferred. |
| Library and project version updates | Shared catalog, enrollment, independent imports and reviewed same-folder update services; credentials remain machine-local. | Authorized native login/enrollment, restart, disconnect/revocation, download/update/cancel and network failure flows. No live service action is claimed by this change. |
| Sharing, comparisons and support | Shared results/consent/outbox, comparisons, manual bug reports and crash reporting through existing service contracts. | Native authorized end-to-end checks, opt-out, offline/retry and secure-store recovery; no automatic permission to contact services. |
| Templates and presets | Shared factory/app-owned condition templates, modifier presets, import/export and project category boundaries. | Native dialogs and paths; unchanged source/preset behavior after relocation and restart. |
| Exports and reports | Shared configs, run/session artifacts, CSV/XLSX summaries, accuracy/masking/AB reports and completed Toolbox handoff generation. Bundles carry editable design/assets, not run history. | Native file dialogs, local-test export/reopen and semantic comparisons; external Toolbox execution is not included. |
| Maintainer tools and access control | Shared publishing/review tooling remains behind existing authorization/capability checks; ordinary users gain no maintainer access. | Authorized native checks only; service permissions and publication requirements remain unchanged. |
| Menus, shortcuts, fonts and accessibility | Shared Qt UI; Save/Find use standard bindings and native shortcut text. Open Sans task font is bundled; authored font choices remain explicit. | Command-key/menu behavior, Tab/arrow navigation, focus, VoiceOver, glyph coverage, Arial/font resolution and scientific text geometry. |
| Source updates and version display | Explicit Git/dependency update workflow; source version remains visible. Windows package installation is outside Mac Phase 1. | Native source-version/update messaging and dependency refresh/restart. |

## Automated Mac evidence

[macos-source.yml](../.github/workflows/macos-source.yml) defines native Python 3.10
lanes for `macos-15`/arm64 and `macos-15-intel`/x86_64. Successful
[run 41554238134](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/41554238134)
records this source-environment matrix for `f6b6721`:

| CPU | macOS | CPython | PySide6 | PsychoPy | Source checks |
| --- | --- | --- | --- | --- | --- |
| Apple Silicon / arm64 | 15.8.2 (24H232) | 3.10.11 | 6.12.0 | 2026.2.5 | 1,358 passed; 10 platform skips |
| Intel / x86_64 | 15.7.9 (24G830) | 3.10.21 | 6.12.0 | 2026.2.5 | 1,358 passed; 10 platform skips |

Both resolved pyglet 1.5.27, PyObjC/Cocoa/Security 12.2.2, cryptography 50.0.2,
keyring 25.7.0, NumPy 2.2.6 and Pillow 11.3.0. Full dependency freezes, host data,
JUnit and handoff evidence are workflow artifacts. Toolchain inventories are
[ARM image 20261028.0489.1](https://github.com/actions/runner-images/blob/macos-15-arm64/20261028.0489/images/macos/macos-15-arm64-Readme.md)
and [Intel image 20260824.0482.1](https://github.com/actions/runner-images/blob/macos-15/20260824.0482/images/macos/macos-15-Readme.md).
Later dependency/OS combinations require another run before qualification.
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

`bash scripts/macos-source.sh verify` runs the safe `macos` focused scope.
The helper prefers `.venv3.10` and reuses `.venv` if present instead of creating
another environment. Tests select the primary Windows or secondary Mac contract at
module-owned seams without changing the process-wide host. Repo verification checks
all source types for Windows, then the Mac adapter owners for Darwin; the Mac focused
route includes the latter pass. Full repo precommit also requires PowerShell (`pwsh`)
for the existing audits; see [test verification](ENVIRONMENT.md#test-performance).
The source workflow runs Windows repo precommit before starting the secondary Mac
jobs, so Mac source changes also retain a native Windows regression gate.

Native checks require `FPVS_MACOS_NATIVE_CHECKS=1`; CI enables it explicitly. Those checks
import native bindings and PsychoPy without opening a window, probe available display
information, and use unique synthetic Keychain/Trash items with cleanup. The hosted-only
Keychain check creates an unlocked temporary store and restores the runner's previous
default/search list afterward; it does not unlock or change access controls on the login
Keychain. A real child-process IPC check rejects acquisition settings before any engine
or hardware is created. These checks do not contact EEG devices, use real projects or
establish physical display timing. Neutral
core imports must remain independent of Qt/PsychoPy/hardware. Qt execution requires
the approved visible-environment policy in [Environment](ENVIRONMENT.md#gui-test-environment).

Both private credential probes recorded `result="roundtrip"`, `domain=0`,
`default_status=0`, `keychain_flags=7`; neither used the interactive-write skip.
Hosted displays reported configured 60 Hz at 1024x768 with
`physical_display_qualified=false`. No PsychoPy presentation window was opened.

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

- [x] Clean dependency installation, windowless source imports and native-service
  checks on both recorded hosted targets.
- [ ] Visible first source launch, preferences/restart and clean shutdown on each
  physical target.
- [ ] All eight Setup steps at 1120x820 in both themes, long values, dialogs,
  validation/busy/error states, shortcuts, focus and accessibility.
- [ ] Native Keychain, Trash/Finder, locked/unavailable-store and permission/cancel
  recovery; use only synthetic credentials and files.
- [ ] Local fullscreen Test/Pilot for every supported category and representative
  image/word/task/modifier design; confirm no hardware construction or marker writes,
  native/observed refresh agreement, geometry, timing QC and stable abort/close/recovery.
- [ ] Save/open/re-export without unintended changes to lab display/recording values,
  seeds, order, fixation rules, word text, media or participant/test eligibility.
- [x] Both native CI transfer directions with Unicode, spaces, images/words, derivatives,
  task media, relocated source and exact same-target plans/hashes.
- [ ] Physical import/export dialogs, case-sensitive volumes and broader scene/media
  workflows; preserve only deliberate collision-ID remapping.
- [ ] Reports/configs/Toolbox handoff generation and authorized Library/sharing/support/
  maintainer flows, with unchanged consent and access checks.
- [ ] Windows lab import and normal production preflight with explicit lab hardware;
  acquisition/physical marker qualification remains Phase 2.
