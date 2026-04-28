---
name: legacy-boundary-review
description: Use before refactors that may cross protected legacy folders such as Main_App/Legacy_App/** or Tools/SourceLocalization/**, or when checking whether new code should use legacy public APIs, adapters, or black-box boundaries only.
---

# Legacy Boundary Review

## Workflow

1. Read `AGENTS.md` and `ARCHITECTURE.md`.
2. Check whether protected legacy folders exist in the current checkout.
3. Inspect the proposed change scope before editing.
4. Treat protected legacy modules as black boxes unless the user explicitly asks to edit
   them after the risk is explained.
5. Prefer existing public APIs, stable file formats, or thin adapters outside protected
   folders.
6. If the desired behavior requires a protected-module edit, stop and report why.
7. Confirm the final diff does not include protected paths unless explicitly authorized.

## Review Questions

- Which legacy paths are involved, if any?
- Which public API or adapter can satisfy the task?
- What behavior, processing order, or data format must remain untouched?
- What verification proves the boundary stayed intact?

## Output Checklist

- List protected paths checked.
- State whether protected files were untouched.
- Name any adapter or public API used.
- Report verification commands and results.
