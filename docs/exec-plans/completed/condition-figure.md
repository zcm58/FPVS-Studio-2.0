# Condition Figure

Status: Completed

## Workflow

Open **Tools > Condition Figure** in an active project and select a condition
with a configured periodic Base/Oddball stream. Automatic selection fills four
base slots and one oddball slot from the condition's configured pools. Manual
selection exposes the same pools. Choose a destination for the 600-DPI PNG.

Adapt Toolbox's Sequence Figure layout for one Studio condition. Use the effective
condition frequency and configured cadence. Show four base and one oddball example
even for other cadences, with a separate, correctly spaced timing schematic when
the sample strip does not correspond to one cycle. The figure describes authored
timing and representative stimuli. Specialized AB and Masking layouts use separate
presentation contracts.

## Implementation and verification

Use the existing compiler asset resolver and configured variants without compiling
or running an experiment. Resolve sources from the active project and use a Studio
utility renderer backed by Pillow. Keep stimulus assets read-only and replace the
selected export file atomically after successful rendering. Resolve and render off
the GUI thread. Provide actionable empty, busy, failure, and success states.

Verify the emitted PNG's DPI and geometry, authored frequency and cadence, source
pool selection, alternate variants and words, export failures, and project path
containment. Register dialog coverage at `860x520` and `920x560`, plus the Tools action.
Run GUI-focused verification and safe precommit. Record visible acceptance separately.

Synthetic image and word figures were rendered and inspected at the configured
cadences of five and fifteen, with 600-DPI metadata verified. The
[visible smoke path](../../GUI_WORKFLOW.md#condition-figure) covers the Studio dialog.
