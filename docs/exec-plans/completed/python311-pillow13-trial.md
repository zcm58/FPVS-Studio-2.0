# Python 3.11 and Pillow 13 compatibility trial

Status: Completed

This Windows source trial starts at `f325278` and uses synthetic study files in
separate virtual environments. The production bootstrap and installer still
target Python 3.10. The trial does not use a recording device.

## Environments

| Environment | Purpose |
| --- | --- |
| Current Windows Studio environment | CPython 3.10.11, Pillow 11.3.0, NumPy 2.2.6 and PySide6 6.11.2 supply the reference outputs. |
| Python-only control | CPython 3.11.18 with the same Pillow and NumPy versions isolates the interpreter change. |
| Candidate base and developer install | CPython 3.11.18, Pillow 13.0.0 and the Windows base and developer dependencies exercise authoring, data handling and GUI workflows. |
| Candidate engine install | The same interpreter and Pillow version, PsychoPy 2026.2.5 and a pinned upstream MoviePy revision exercise the native presentation path. |

For a fresh Windows source checkout, use the following commands with a Python
3.11.18 interpreter. The control reads Studio directly from `src` and uses the
imaging and validation libraries installed in the reference environment.

```powershell
python -m venv .venv
& .venv/Scripts/python.exe -m pip install -e '.[dev]' 'Pillow==13.0.0' 'numpy==2.4.6' 'pydantic==2.14.4' 'PySide6==6.12.0'
python -m venv .tmp/trial/control-311
$control = '.tmp/trial/control-311/Scripts/python.exe'
& $control -m pip install 'pillow==11.3.0' 'numpy==2.2.6' 'pydantic==2.12.5' 'openpyxl==3.1.5' 'PySide6==6.11.2' 'scipy==1.17.1' 'pytest==9.2.0' 'pytest-qt==4.5.0' 'pytest-timeout==2.4.0' 'pytest-xdist==3.8.0' 'cryptography==50.0.2' 'packaging==25.0' 'pyserial==3.5' 'websockets==16.0' 'PyYAML==6.0.4'
```

The published MoviePy 2.2.1 declares Pillow below 12. Without an explicit MoviePy
selection the resolver can choose 1.0.3. Its top-level API differs from the API
used by the current PsychoPy movie-export code. The engine trial uses an
unreleased upstream revision whose dependency declaration allows Pillow 13.
[MoviePy 2.2.1 metadata](https://pypi.org/pypi/moviepy/2.2.1/json)
· [Trial MoviePy source](https://github.com/Zulko/moviepy/tree/211e4b15f6ce4f34a6a9efbfff40590e43a68f77)

To recreate the experimental engine in a fresh Windows Python 3.11 environment,
run this from the trial checkout using that environment's interpreter.

```powershell
python -m pip install '.[dev,engine]' 'psychopy==2026.2.5' 'Pillow==13.0.0' 'moviepy @ https://github.com/Zulko/moviepy/archive/211e4b15f6ce4f34a6a9efbfff40590e43a68f77.zip'
python -m pip check
```

The tested engine environment passed package consistency checks across 124
installed distributions. MoviePy returned the exact pixel data for a synthetic
video frame. Its installed distribution identifies itself as 2.2.0. The source
revision above identifies the code actually tested.

## Test results

The first base and developer test run passed 6,621 tests and failed 16. Thirteen
failures came from the Mac repair probe importing a Python 3.10 backport. Two
checks enforced the production interpreter version, and a local Git fixture
inherited an incomplete environment setting. The trial uses the standard library
TOML reader on Python 3.11, recognizes the trial interpreter in the verification
scripts and isolates the Git environment for tests.

After those corrections, the installed-engine run passed all 6,643 executed
non-Qt unit tests and 24 subtests. Of the 40 skips, 22 require macOS or POSIX
and 18 require Windows file-symlink privileges. This run covered 192 unit-test
modules. The verification harness configuration and changed-file Ruff checks
also passed. With Python 3.11 as the type-checking target, mypy passed across
304 source files on the Windows target and nine Mac adapter files on the Darwin
target. Two local variable annotations accommodate the newer library stubs.
The affected image normalization and contrast suites passed all 50 tests.

The repository precommit run in the base and developer environment passed
6,637 tests and 24 subtests, with 46 skips. It also passed the repository audits
and both mypy targets. This environment omits the optional engine. The separate
installed-engine run above covers its additional cases.

The Windows trial built the Studio 3.1.5 Python wheel and installed it offline
in a fresh environment. Its 328 archive entries passed CRC verification. The
installed package passed dependency checks, loaded the `fpvs-studio` entry
point and imported the project model, GUI and lazy engine adapter from the
wheel. The Windows executable and installer require separate verification.

Both native PsychoPy integration tests passed on the visible Windows desktop.
One opened and closed a presentation window. The other played a synthetic
compiled condition with a null trigger backend and completed every planned
frame. The trial used a temporary monitor specification. These checks cover
functional playback. Physical refresh timing and EEG marker timing still need
instrumented acceptance.

Twenty-four seeded compiled contracts and all 54 decoded image comparisons matched
the Python 3.10 reference. Re-encoding nine PNGs under Pillow 13 changed their
compressed bytes. Four were selected study stimuli, which changed the Results
fingerprint and Library checksums. Reusing the original files preserved identity.
Pinning NumPy 2.2.6 reproduced the original equalization statistics.
[Scientific evidence and reproduction commands](../../references/python311-scientific-parity.md)

## Native Windows GUI

The initial visible GUI-scope run collected 2,716 cases. It stopped at 84%
during a native theme change after 2,173 pass, 128 failure, seven error and
three skip markers. The process produced no final pytest summary. Those
progress markers include teardown outcomes and do not count independent defects.

The visible trial exposed a participant-launch callback that attempted to use
deleted Qt objects when a nested save or confirmation outlived its window.
The source fix was applied to both branches. Thirteen focused checks passed on
each stack, covering seven window-disposal cases, ordinary asynchronous launch,
two shutdown outcomes, a failed condition-order save and retry, and refresh
measurement routed to the selected Windows display. The thirteenth check
verified that the participant history lookup ran off the GUI thread before
confirmation. It passed in a fresh process on each stack after stalling in a
group. These checks used local synthetic files and a simulated refresh measurement.

Six representative cases were compared on four configurations with the same
test code. All four recorded the same four passing assertions and the same two
failures. The Settings Close button measured 44 px in a 36 px container, and
the dark-card test expected a different stylesheet color token. Both also
occurred with the installed Python 3.10 and Qt 6.11.2. One Python 3.11 control
with the reference libraries stalled after its sixth case during native theme
restoration. The other three processes exited normally. Running the originally
timed-out Conditions cases in a fresh candidate process passed all eight.

Every one of the 411 remaining case IDs was subsequently exercised. Module runs
covered 410 cases and recorded four assertion failures and one teardown error.
The remaining confirmation case passed in a fresh process. The 144 Hz check
passed after its fake was corrected to accept the selected display. Other
failures involved clipped status text after a simulated Mac probe, a test that
expected eight Setup steps where nine are defined, and the Demographics editor's
scroll behavior. A close-prompt stub raised during teardown of the ready-project
case after its Return Home assertion passed. Two further Qt-registered document
modules passed all 58 cases. A bounded repeat of 45 cases across eight earlier
modules recorded eight failures and one teardown error. The overall GUI suite
did not pass, and matching
outcomes on the six-case controls do not establish the cause of every failure.

## Release decision

Keep the migration on this experimental branch. The interpreter-only control
preserved the measured outputs. Pillow 13 addresses upstream security issues on
supported image paths, including TIFF decoding, but regenerating intact-looking
images can change their identity across studies. A production upgrade under the
existing compatibility requirement needs a generation path that reproduces the
reference bytes or an explicitly accepted change in study identity. The engine
also needs a supported MoviePy dependency set. An installer built with the new
interpreter, macOS source setup and instrumented acquisition still require
qualification. The checked-in Windows and Mac bootstraps target Python 3.10.
[Pillow 13 security fixes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html#security)
