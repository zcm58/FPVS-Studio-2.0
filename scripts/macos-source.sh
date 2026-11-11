#!/bin/bash
# Secondary Mac source adapter; Windows setup and application behavior stay shared.
set -euo pipefail

usage() {
  echo "Usage: bash scripts/macos-source.sh {setup|run|pycharm|verify} [arguments]"
  echo "setup prepares Python and dependencies; run opens Studio; pycharm opens the IDE."
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
tools_root="$repo_root/.fpvs-macos"
native_arch="$(uname -m)"
if [ "$(sysctl -n hw.optional.arm64 2>/dev/null || true)" = 1 ]; then
  native_arch=arm64
fi
case "$native_arch" in
  arm64|x86_64) ;;
  *) echo "Unsupported Mac CPU: $native_arch" >&2; exit 2 ;;
esac
venv_python="$repo_root/.venv3.10/bin/python"
if [ ! -e "$repo_root/.venv3.10" ] && [ ! -L "$repo_root/.venv3.10" ] &&
   { [ -e "$repo_root/.venv" ] || [ -L "$repo_root/.venv" ]; }; then
  venv_python="$repo_root/.venv/bin/python"
fi

require_python310() {
  "$1" -c 'import platform, sys
assert sys.version_info[:2] == (3, 10), "FPVS Studio requires Python 3.10"
assert platform.machine() == sys.argv[1], "Python must match the native Mac CPU"' "$native_arch"
}

require_environment() {
  if [ ! -x "$venv_python" ]; then
    echo "Double-click Setup Mac.command first (or run bash scripts/macos-source.sh setup)." >&2
    exit 2
  fi
  require_python310 "$venv_python"
}

download() {
  curl --fail --location --retry 3 --connect-timeout 20 --output "$2" "$1"
}

install_python() {
  # uv is used only to obtain Python, not to replace the repository's pip workflow.
  uv_version=0.13.7
  case "$native_arch" in
    arm64)
      uv_target=uv-aarch64-apple-darwin
      uv_sha=81b811b57e4624df7ed3aac148e0359100d9962f3d9dce00aec533dc2e086731
      ;;
    x86_64)
      uv_target=uv-x86_64-apple-darwin
      uv_sha=20c47e4c1f630b8abaff8c291fa9b9aa300fef92c4fbff95adf198b55287cda7
      ;;
  esac
  uv_bin="$tools_root/uv-$uv_version/uv"
  if [ ! -x "$uv_bin" ]; then
    echo "Downloading the native Python installer (uv $uv_version)..."
    download_tmp="$(mktemp -d "$tools_root/.uv.XXXXXX")"
    archive="$download_tmp/uv.tar.gz"
    download "https://github.com/astral-sh/uv/releases/download/$uv_version/$uv_target.tar.gz" "$archive"
    actual_sha="$(shasum -a 256 "$archive" | awk '{print $1}')"
    if [ "$actual_sha" != "$uv_sha" ]; then
      echo "Python installer checksum failed. Nothing from this download was executed." >&2
      exit 1
    fi
    tar -xzf "$archive" -C "$download_tmp" "$uv_target/uv"
    mkdir -p "$(dirname -- "$uv_bin")"
    install -m 755 "$download_tmp/$uv_target/uv" "$uv_bin"
    rm -rf -- "$download_tmp"
    download_tmp=""
  fi
  export UV_PYTHON_INSTALL_DIR="$tools_root/python"
  export UV_CACHE_DIR="$tools_root/cache"
  echo "Installing a native, project-contained Python 3.10..."
  "$uv_bin" python install --no-bin 3.10
  python_bin="$("$uv_bin" python find --managed-python --system 3.10)"
}

prepare_intel_build_tools() {
  if [ "$native_arch" != x86_64 ]; then return; fi
  echo "Checking Intel build tools for dependencies without Intel wheels..."
  if ! xcode-select -p >/dev/null 2>&1; then
    xcode-select --install || true
    echo "Complete Apple's Command Line Tools installer, then double-click Setup Mac.command again." >&2
    exit 2
  fi
  if [ -n "${OPENSSL_DIR:-}" ] && [ ! -f "$OPENSSL_DIR/include/openssl/opensslv.h" ]; then
    echo "OPENSSL_DIR does not contain OpenSSL headers: $OPENSSL_DIR" >&2
    exit 2
  fi
  rust_ready=false
  if command -v rustc >/dev/null 2>&1 && rustc --version | awk '
      { split($2, v, "."); exit !(v[1] > 1 || (v[1] == 1 && v[2] >= 83)) }'; then
    rust_ready=true
  fi
  if [ "$rust_ready" = true ] && [ -n "${OPENSSL_DIR:-}" ]; then return; fi
  brew_bin="$(command -v brew || true)"
  if [ -z "$brew_bin" ] && [ -x /usr/local/bin/brew ]; then brew_bin=/usr/local/bin/brew; fi
  if [ -z "$brew_bin" ]; then
    if [ ! -t 0 ]; then
      echo "Intel setup needs Homebrew for Rust/OpenSSL. Run Setup Mac.command in Terminal." >&2
      exit 2
    fi
    echo "Installing Homebrew for Intel build tools. macOS may request your administrator password."
    download_tmp="$(mktemp -d "$tools_root/.brew.XXXXXX")"
    download https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh "$download_tmp/install.sh"
    /bin/bash "$download_tmp/install.sh"
    rm -rf -- "$download_tmp"
    download_tmp=""
    brew_bin=/usr/local/bin/brew
  fi
  if [ -z "${OPENSSL_DIR:-}" ]; then
    openssl_prefix="$("$brew_bin" --prefix openssl@3 2>/dev/null || true)"
    if [ ! -f "$openssl_prefix/include/openssl/opensslv.h" ]; then
      "$brew_bin" install openssl@3
    fi
    export OPENSSL_DIR="$("$brew_bin" --prefix openssl@3)"
  fi
  if [ "$rust_ready" != true ]; then "$brew_bin" install rust; fi
  export PATH="$("$brew_bin" --prefix)/bin:$PATH"
}

finish_setup() {
  result=$?
  if [ -n "${download_tmp:-}" ]; then rm -rf -- "$download_tmp"; fi
  if [ "$result" -ne 0 ]; then
    echo
    echo "Setup did not finish. Fix the error above, then run Setup Mac.command again."
    echo "Setup log: $tools_root/setup.log"
  fi
}

case "$command_name" in
  setup)
    if [ "$#" -ne 0 ]; then usage >&2; exit 2; fi
    if [ -L "$tools_root" ]; then echo "Setup tools directory must not be a symlink." >&2; exit 2; fi
    mkdir -p "$tools_root"
    exec > >(tee -a "$tools_root/setup.log") 2>&1
    trap finish_setup EXIT
    echo "FPVS Studio Mac setup ($native_arch)"
    if [ -e "$(dirname -- "$(dirname -- "$venv_python")")" ] && [ ! -x "$venv_python" ]; then
      echo "The existing environment is incomplete: $venv_python" >&2
      echo "Rename the obsolete environment folder, then run Setup Mac.command again." >&2
      exit 2
    fi
    if [ -x "$venv_python" ]; then
      require_python310 "$venv_python"
      echo "Reusing $venv_python"
    else
      python_bin="${FPVS_PYTHON:-}"
      if [ -n "$python_bin" ] && [ "${FPVS_MANAGED_PYTHON:-0}" = 1 ]; then
        echo "Use either FPVS_PYTHON or FPVS_MANAGED_PYTHON, not both." >&2
        exit 2
      fi
      if [ -z "$python_bin" ] && [ "${FPVS_MANAGED_PYTHON:-0}" != 1 ]; then
        python_bin="$(command -v python3.10 || true)"
        if [ -n "$python_bin" ] && ! require_python310 "$python_bin" >/dev/null 2>&1; then
          echo "Python on PATH is not native Python 3.10; installing a compatible interpreter."
          python_bin=""
        fi
      fi
      if [ -z "$python_bin" ]; then install_python; fi
      require_python310 "$python_bin"
      "$python_bin" -m venv "$repo_root/.venv3.10"
    fi
    require_python310 "$venv_python"
    prepare_intel_build_tools
    echo "Installing Studio, the presentation engine and verification tools..."
    "$venv_python" -m pip install --upgrade 'pip>=25,<27'
    "$venv_python" -m pip install --requirement requirements-macos.txt
    "$venv_python" -m pip check
    "$venv_python" -c 'from packaging.version import Version
from fpvs_studio.gui import application
from importlib.metadata import version
import logging
assert Version(version("psychopy"))
logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("fpvs_studio.setup").info("Studio imports and engine installation verified.")'
    if [ "${FPVS_SKIP_PYCHARM_CONFIG:-0}" != 1 ]; then
      "$venv_python" scripts/macos_pycharm.py "$repo_root" "$venv_python"
    fi
    echo
    echo "Setup complete. Double-click Run Mac.command to open Studio."
    echo "Optional: quit PyCharm, then use Open in PyCharm Mac.command to open this project."
    ;;
  run)
    require_environment
    exec "$venv_python" -m fpvs_studio.app "$@"
    ;;
  pycharm)
    if [ "$#" -ne 0 ]; then usage >&2; exit 2; fi
    require_environment
    if pgrep -x pycharm >/dev/null 2>&1; then
      echo "Save your work and fully quit PyCharm (Command-Q), then run this shortcut again." >&2
      echo "The IDE must be closed while its SDK is registered. Run Mac.command needs no IDE." >&2
      exit 2
    fi
    "$venv_python" scripts/macos_pycharm.py "$repo_root" "$venv_python" --launch "${FPVS_PYCHARM_APP:-PyCharm.app}"
    ;;
  verify)
    require_environment
    exec "$venv_python" .agents/scripts/verify.py --scope macos --tier focused "$@"
    ;;
  *) usage >&2; exit 2 ;;
esac
