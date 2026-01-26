#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

pyinstaller \
  --onefile \
  --windowed \
  --name LogTool \
  App.py