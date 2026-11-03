# Simple Mac source setup

Status: Completed

## Outcome and boundaries

Make a fresh clone usable by a non-programmer through Mac double-click setup/run
shortcuts. Windows stays primary; no runtime, compiler, persisted experiment or
Windows dependency change is in scope. Reuse the existing Mac source adapter.

`pyproject.toml` remains the dependency source of truth. Add a Mac requirements
entry point including the engine, automatic native Python 3.10 acquisition when
needed, explicit Intel build-tool setup, installation checks and a dedicated
PyCharm run configuration. Keep working environments and other IDE settings intact.
Register one SDK in the selected PyCharm app's standard Mac profile while the IDE
is closed, then bind only this project; preserve other SDKs and back up changed XML.
Avoid PyCharm's process-wide interpreter variable, which can affect unrelated
unconfigured projects. Download a pinned, checksum-verified official uv binary only as a
Python installer; retain pip/venv and the existing package architecture.

## Acceptance

- [x] Finder setup/run shortcuts and optional PyCharm launcher work from paths
  containing spaces, without needing Python or an activated environment first.
- [x] Existing compatible environments are reused; invalid/foreign environments,
  download failures and install failures produce actionable messages without deletion.
- [x] Intel tool requirements are handled explicitly; unavoidable Apple/admin
  prompts and supported-source limits are explained.
- [x] Pure tests cover bootstrap dispatch and IDE configuration preservation;
  actual clean Mac installs exercise managed Python and declared requirements.
- [x] Windows-first CI retains its gate; both Mac CPU lanes exercise the bootstrap.
- [x] Focused checks, applicable precommit, docs and install evidence are recorded;
  changes are committed/pushed with remote conflicts resolved.

## Sources and verification

- [uv Python installation](https://docs.astral.sh/uv/guides/install-python/)
- [uv release 0.13.7](https://github.com/astral-sh/uv/releases/tag/0.13.7)
- [Homebrew prerequisites](https://docs.brew.sh/Installation)
- [PyCharm interpreter launch](https://www.jetbrains.com/help/pycharm/configure-an-interpreter-using-command-line.html)

Use the safe `macos` and repo verification routes. Native GUI execution remains
visible and opt-in. Test generated IDE files in temporary projects; preserve the
user's normal Studio settings, projects, working `.venv` and standalone Python base.

## Recorded acceptance (2026-11-02)

- A separate local clone in a path containing spaces downloaded the verified uv
  installer and native managed Python 3.10.22, created `.venv3.10`, installed
  `requirements-macos.txt` including PsychoPy 2026.2.5, and passed `pip check` and
  authoring imports. No preinstalled interpreter was used for that environment.
- The existing working `.venv` was reused and refreshed after integrating the
  concurrent Studio 2.6.0 release commits. Its standalone Python base and Toolbox's
  separate environment were preserved. The temporary clone/environment and SDK
  registration were removed after testing.
- Finder's PyCharm shortcut opened the temporary clone with the correct dedicated
  SDK and run configuration. The main checkout was then restored/verified with its
  existing `.venv` SDK. The generated Run action selected `.venv/bin/python` and
  `src/fpvs_studio/app/main.py`; full interactive application acceptance remains in
  the separate Mac Phase 1 plan.
- Nine approved native visible Qt checks passed from the fresh environment,
  covering Welcome, local-test policy/calibration and the reported Library worker
  lifetime path. The original intermittent Library crash is not claimed resolved.
- Final focused Mac verification: 1,397 passed, 15 native/platform/filesystem skips.
  Repo precommit: 4,993 passed, 64 platform/filesystem skips, 24 subtests. Ruff,
  compilation, Windows-targeted mypy (266 files), Darwin adapter mypy (six files),
  repository audits and verification configuration passed. Counts overlap.
- Windows dependency selection and application source were unchanged. The Windows
  CI precommit gate remains first; both Mac CPU lanes now force managed Python
  acquisition. Intel tool installation is covered through adapter tests and the
  configured native CI lane; no physical Intel Mac was available locally.

Physical fullscreen timing, EEG hardware, broad interactive/service acceptance and
an unconditional bug-free guarantee remain outside this bootstrap task. The source
support plan retains those open gates. Publication uses the integrated remote base;
new workflow results are separate evidence from the completed local checks.
