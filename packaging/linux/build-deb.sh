#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="$(cat "$ROOT/VERSION")"
ARCH="${ARCH:-amd64}"
PKG_DIR="$ROOT/build/deb/plexdiscordpresence"

rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/DEBIAN" "$PKG_DIR/usr/bin"

cp "$ROOT/dist/PlexDiscordPresence" "$PKG_DIR/usr/bin/plexdiscordpresence"
chmod 755 "$PKG_DIR/usr/bin/plexdiscordpresence"

cat > "$PKG_DIR/DEBIAN/control" <<EOF
Package: plexdiscordpresence
Version: $VERSION
Section: net
Priority: optional
Architecture: $ARCH
Maintainer: drew-codes-things
Description: Shows current Plex playback as Discord Rich Presence
 Watches your Plex account's playback over Plex's websocket notification
 feed and displays it as Discord Rich Presence (poster, title, progress
 bar). Works for shared/non-owner Plex accounts, not just server owners.
EOF

mkdir -p "$ROOT/dist"
dpkg-deb --build --root-owner-group "$PKG_DIR" "$ROOT/dist/plexdiscordpresence_${VERSION}_${ARCH}.deb"
echo "Built: $ROOT/dist/plexdiscordpresence_${VERSION}_${ARCH}.deb"
