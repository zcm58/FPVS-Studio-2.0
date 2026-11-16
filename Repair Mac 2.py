"""Run the shared Mac repair and automatically report its final outcome."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    helper = Path(__file__).resolve().with_name("Repair Mac.py")
    sys.argv = [str(helper), "--automatic-report", *sys.argv[1:]]
    runpy.run_path(str(helper), run_name="__main__")
