#!/bin/bash
# Source installation and launch only; never starts an installer or EEG backend.
set -euo pipefail

usage() {
  echo "Usage: bash scripts/macos-source.sh {setup|run|verify} [arguments]"
  echo "setup installs Python 3.10 dependencies; run opens Studio; verify runs safe Mac checks."
}

command_name="${1:-help}"
if [ "$command_name" = help ] || [ "$command_name" = --help ] || [ "$command_name" = -h ]; then
  usage
  exit 0
fi
shift
if [ "$(uname -s)" != Darwin ]; then
  echo "This helper requires macOS. Use the source instructions for your platform." >&2
  exit 2
fi
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$repo_root"
venv_python="$repo_root/.venv3.10/bin/python"
if [ ! -x "$venv_python" ] && [ -x "$repo_root/.venv/bin/python" ]; then
  venv_python="$repo_root/.venv/bin/python"
fi

require_python310() {
  "$1" -c 'import sys; assert sys.version_info[:2] == (3, 10), "FPVS Studio requires Python 3.10"'
}

case "$command_name" in
  setup)
    if [ "$#" -ne 0 ]; then usage >&2; exit 2; fi
    if [ ! -x "$venv_python" ]; then
      python_bin="${FPVS_PYTHON:-python3.10}"
      if ! command -v "$python_bin" >/dev/null 2>&1; then
        echo "Install Python 3.10, or set FPVS_PYTHON to its executable, then run setup again." >&2
        exit 2
      fi
      require_python310 "$python_bin"
      "$python_bin" -m venv "$repo_root/.venv3.10"
    fi
    require_python310 "$venv_python"
    "$venv_python" -m pip install --upgrade 'pip>=25,<27'
    "$venv_python" -m pip install --editable '.[dev,engine]'
    "$venv_python" -m pip check
    echo "Setup complete. Open Studio with: bash scripts/macos-source.sh run"
    ;;
  run)
    if [ ! -x "$venv_python" ]; then
      echo "Run bash scripts/macos-source.sh setup first." >&2
      exit 2
    fi
    require_python310 "$venv_python"
    exec "$venv_python" -m fpvs_studio.app "$@"
    ;;
  verify)
    if [ ! -x "$venv_python" ]; then
      echo "Run bash scripts/macos-source.sh setup first." >&2
      exit 2
    fi
    require_python310 "$venv_python"
    exec "$venv_python" .agents/scripts/verify.py --scope macos --tier focused "$@"
    ;;
  *) usage >&2; exit 2 ;;
esac
