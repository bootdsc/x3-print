#!/bin/sh
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    python3 -m venv --system-site-packages .venv
    .venv/bin/python -m pip install --quiet pyserial pywebview
fi
exec .venv/bin/python -B -m x3print "$@"
