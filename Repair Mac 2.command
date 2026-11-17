#!/bin/bash
# Finder opens the repair and its final outcome in Terminal.
cd -- "$(dirname -- "${BASH_SOURCE[0]}")" || exit 1
bash scripts/macos-source.sh repair "$@"
result=$?
if [ -t 0 ]; then
  echo
  read -r -p "Press Return to close this window. "
fi
exit "$result"
