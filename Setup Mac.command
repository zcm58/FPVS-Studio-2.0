#!/bin/bash
# Finder opens this in Terminal; keep the result visible for non-programmers.
cd -- "$(dirname -- "${BASH_SOURCE[0]}")" || exit 1
bash scripts/macos-source.sh setup
result=$?
if [ -t 0 ]; then
  echo
  read -r -p "Press Return to close this window. "
fi
exit "$result"
