# Windows source setup

Status: Completed

The checkout launcher prepares 64-bit Python 3.10, installs the Windows source
requirements, activates the virtual environment in its console, and prepares a
PyCharm run configuration for `src/fpvs_studio/app/main.py`.

Use `requirements.txt` as the package installation entry point and retain existing
incompatible environments. Scope IDE changes to the Studio project and one SDK in
the selected PyCharm profile. The launcher should also work before PyCharm is installed.

Windows smoke verification covered a fresh checkout in a path with spaces, Python
selection in a path with Unicode characters, shell activation on Python 3.10.22,
requirements consistency, and SDK/run configuration
generation and reuse in an isolated PyCharm profile. Interpreter selection preserved
an existing Python 3.14 `.venv` and created `.venv3.10`. A pip dry run under 3.14
rejected the project. The engine uses PyQt6 6.11 on Windows because 6.12.0 ships
invalid type stubs.

For a visible smoke check, close PyCharm, double-click `Setup Windows.cmd`, and
open the checkout again in PyCharm. Select **FPVS Studio (Windows)** and confirm
that `main.py` opens the Studio window. This visible check was deferred.
