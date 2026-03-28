"""Top-level application bootstrap for the Phase 5 PySide6 shell.
It lazily hands process startup into the GUI application layer so imports stay lightweight until a desktop session is requested.
Project editing, compilation, preprocessing, and runtime orchestration remain in backend services beneath this handoff."""

from __future__ import annotations

from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the packaged FPVS Studio GUI entry point."""

    from fpvs_studio.gui.application import run_gui_app

    return run_gui_app(list(argv) if argv is not None else None)


if __name__ == "__main__":
    raise SystemExit(main())
