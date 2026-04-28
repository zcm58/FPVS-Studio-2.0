"""Module-mode launcher for `python -m fpvs_studio.app`. It forwards directly to the GUI
bootstrap so command-line startup reaches the same Phase 5 authoring path as other
entrypoints. This shim owns invocation convenience only, not application state or
runtime behavior."""

from __future__ import annotations

from fpvs_studio.app.main import main

if __name__ == "__main__":
    raise SystemExit(main())
