"""Top-level application bootstrap for the Phase 5 PySide6 shell. It lazily hands process
startup into the GUI application layer so imports stay lightweight until a desktop
session is requested. Project editing, compilation, preprocessing, and runtime
orchestration remain in backend services beneath this handoff."""

from __future__ import annotations

import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the packaged FPVS Studio GUI entry point."""

    args = list(sys.argv[1:] if argv is None else argv)
    if "--packaged-smoke-output" in args:
        from fpvs_studio.app.packaged_smoke import run_packaged_smoke

        return run_packaged_smoke(args)

    from fpvs_studio.gui.application import run_gui_app

    return run_gui_app(args if argv is not None else None)


if __name__ == "__main__":
    raise SystemExit(main())
