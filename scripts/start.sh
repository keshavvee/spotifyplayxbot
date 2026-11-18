#!/usr/bin/env bash
set -e
python scripts/health.py &
exec python -m ShrutixMusic
