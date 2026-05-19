#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  exec python3 install.py --quickstart --project-names
fi

exec python install.py --quickstart --project-names
