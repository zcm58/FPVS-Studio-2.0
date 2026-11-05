# Studio 2.7.1 release

Status: Active

Date: 2026-11-05

## Scope and authorization

The user requested bundling and publishing all recent Studio changes on GitHub.
The latest published release is the immutable stable v2.7.0. This patch release
includes USB TriggerBox discovery cancellation, cleanup and plain-language error
guidance; Test Mode starting off each app launch; and requirements installation
including the PsychoPy engine and sounddevice. Parallel-port work remains secondary.

## Execution and verification

1. Commit version 2.7.1 and build from an isolated, clean checkout. Preserve the
   user's untracked files and the existing qualified dependency environment.
2. Run packaging focused and safe repository precommit checks. Build Studio,
   the independent updater, the full Windows installer, update JSON and checksums.
3. Verify exact source, bundled metadata, ownership hashes, native dependencies
   and extracted installer bytes. Run bounded visible packaged checks only with
   the safe visible-session approval required by the repository.
4. Push the exact source/tag, stage a GitHub draft, verify all uploaded assets,
   publish latest/stable and check public downloads, attestations and updater selection.

Use label `release-2.7.1`, with private evidence in
`build/release-2.7.1-evidence/`. Mac remains source-only. Production installation,
upgrade/uninstall, real EEG and physical timing checks remain separate; TriggerBox
hardware testing is deferred at the user's request.

## Progress

- Confirmed local master and remote match at `573b867`; v2.7.0 is latest/stable.
- Existing Python 3.10 environment passes dependency consistency checks.
- Release validation and artifact preparation are in progress.
