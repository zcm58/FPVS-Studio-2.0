#!/bin/bash
cd -- "$(dirname -- "${BASH_SOURCE[0]}")" || exit 1
bash scripts/macos-source.sh pycharm
result=$?
if [ "$result" -ne 0 ] && [ -t 0 ]; then
  read -r -p "Press Return to close this window. "
fi
exit "$result"
