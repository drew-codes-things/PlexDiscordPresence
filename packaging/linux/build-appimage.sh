#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="$(cat "$ROOT/VERSION")"
ARCH="${ARCH:-x86_64}"
APPDIR="$ROOT/build/AppDir"
APPIMAGETOOL="$ROOT/build/appimagetool-${ARCH}.AppImage"

if [ ! -x "$APPIMAGETOOL" ]; then
  mkdir -p "$ROOT/build"
  curl -fsSL -o "$APPIMAGETOOL" \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
  chmod +x "$APPIMAGETOOL"
fi

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"

cp "$ROOT/dist/PlexDiscordPresence" "$APPDIR/usr/bin/plexdiscordpresence"
chmod 755 "$APPDIR/usr/bin/plexdiscordpresence"
cp "$ROOT/packaging/linux/assets/icon.png" "$APPDIR/plexdiscordpresence.png"

cat > "$APPDIR/plexdiscordpresence.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=PlexDiscordPresence
Exec=plexdiscordpresence
Icon=plexdiscordpresence
Categories=Network;
Terminal=true
EOF

ln -sf usr/bin/plexdiscordpresence "$APPDIR/AppRun"

mkdir -p "$ROOT/dist"
export APPIMAGE_EXTRACT_AND_RUN=1
ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" \
  "$ROOT/dist/PlexDiscordPresence-${VERSION}-${ARCH}.AppImage"
echo "Built: $ROOT/dist/PlexDiscordPresence-${VERSION}-${ARCH}.AppImage"
