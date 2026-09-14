#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p dist
uv run --with nuitka \
  --no-cache \
  nuitka --standalone --onefile \
    --include-package=textual \
    --include-package-data=textual \
    --include-package=httpx \
    --output-filename=dist/nasmanager-linux-x86_64 \
    src/nasmanager