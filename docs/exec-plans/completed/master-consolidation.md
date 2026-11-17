# Master consolidation

Status: Completed (integration)

Merge the ImageEqualizer branch and pending source/documentation into current
master, preserving the updater improvements and Repair Mac 2. Retain local tools
and generated scratch on disk, outside version control. Keep the appearance plan
planned; this consolidation does not implement it.

Verify both parent histories are included, repair files match the published repair
revision, focused non-Qt checks and repository precommit pass. Leave the primary
checkout on master and publish without rewriting remote history. GUI and physical
Mac acceptance remain separate from source verification.

Integrated current master `e1be34a` with ImageEqualizer and pending project work
captured in `5099a8a`. The only conflict was the plan index; both sets of entries
were retained. Updater implementations and Repair Mac 2 match the master parent.
The standalone contrast example needed comment/docstring wrapping only.

Verification: 158 focused tests passed. Repository precommit passed with 6,503
tests, 41 platform/permission skips and 24 passing subtests. Ruff, compilation,
Windows/Darwin mypy and repository audits passed. No local Qt session was run.
The appearance proposal remains planned, and local tool installations and retained
scratch output remain on disk outside Git.
