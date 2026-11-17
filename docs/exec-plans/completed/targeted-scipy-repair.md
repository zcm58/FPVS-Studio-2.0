# Targeted SciPy repair

Status: Completed (implementation)

Preserve working SciPy installations. Replace SciPy with 1.14.1 only after the
specific native loader failure, and test again. Keep other repair, IDE selection
and automatic reporting behavior. Consolidate the implementation in Repair Mac 2.py
and remove the obsolete entry point, migrating saved PyCharm paths.

Verification: focused Mac repair, dependency metadata and PyCharm tests; repository
precommit; no local Qt or claims of successful repair on the affected Mac.

Focused repair/metadata checks: 293 passed, 19 platform/permission skips. Final
repair/PyCharm regression rerun: 91 passed, 19 skips. Repository precommit had
6,454 passes, 41 skips, 24 passing subtests and two Windows access-denied errors
replacing temporary PyCharm XML files; both affected cases passed in the rerun.
Ruff, compilation, Windows/Darwin mypy, audits and verification configuration passed.
Native Mac acceptance remains under the existing macOS support workflow.
