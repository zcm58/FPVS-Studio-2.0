# Studio and Toolbox handoff edge cases

Status: Completed

Exercise the paths from condition editing and completed Studio export through
Toolbox project creation, cohort revision and native marker comparison. Use
synthetic data and the production readers and writers for both applications.

- Reproduce ambiguous condition codes or labels, contradictory run evidence,
  changed recording identities and timing across acquisition pauses.
- Fix each failure at the boundary that owns it and retain regression cases for
  historical inputs and ordinary study exports.
- Run the focused and precommit gates, record the outcomes and verify both main
  branches. Physical timing and electrical receipt require a lab recording.

The corresponding Toolbox work follows its [Studio import contract](https://github.com/zcm58/FPVS-Toolbox/blob/main/docs/agent/architecture/project-io.md#studio-config-handoff).

## Results

On Windows, fresh two-condition, two-block Studio projects produced setup,
completed-session and whole-study exports for 17 recorder and cap combinations.
All 51 exports followed the expected Toolbox processing or marker-only path.
The 15 processing cohorts each retained all four runs through initial review,
commit and reimport. Source recording hashes remained unchanged.

A separate saved project exercised four condition codes and oddball code 201.
Its two blocks retained all 32 markers through each export. Seven visible Qt
editor tests covered Add and Duplicate. Native CNT and MFF comparisons across
three conditions and two blocks exercised 144 recording/run combinations.
Matching marker words alone could not distinguish repeated runs of the same
condition. Such runs still need independent acquisition records for attribution.
