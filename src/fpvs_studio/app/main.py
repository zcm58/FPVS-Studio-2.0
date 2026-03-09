"""Application entry point that lazily hands off to the PySide6 GUI."""

from __future__ import annotations

from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the packaged FPVS Studio GUI entry point."""

    from fpvs_studio.gui.application import run_gui_app

    return run_gui_app(list(argv) if argv is not None else None)


if __name__ == "__main__":
    raise SystemExit(main())
