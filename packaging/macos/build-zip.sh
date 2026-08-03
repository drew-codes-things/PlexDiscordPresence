#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="$(cat "$ROOT/VERSION")"

pyinstaller --onefile --name PlexDiscordPresence \
  --distpath "$ROOT/dist" --workpath "$ROOT/build" --specpath "$ROOT/build" \
  "$ROOT/main.py"

cd "$ROOT/dist"
ZIP_NAME="PlexDiscordPresence-${VERSION}-macos-x86_64.zip"
zip -q "$ZIP_NAME" PlexDiscordPresence
echo "Built: $ROOT/dist/$ZIP_NAME"
