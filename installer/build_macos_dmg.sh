#!/usr/bin/env bash
# Packages dist/LiminalVibes.app into a distributable .dmg with no prerequisites
# for the end user (they just open the dmg and drag the app to Applications).
#
# Expects dist/LiminalVibes.app to already exist (built via:
#   pyinstaller --noconfirm --clean LiminalVibes.spec
# run from the repository root).
#
# Usage:
#   installer/build_macos_dmg.sh
#
# Output: dist/LiminalVibes.dmg

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
APP_PATH="$DIST_DIR/LiminalVibes.app"
DMG_PATH="$DIST_DIR/LiminalVibes.dmg"
STAGING_DIR="$(mktemp -d)"

if [[ ! -d "$APP_PATH" ]]; then
  echo "error: $APP_PATH not found. Build it first with:" >&2
  echo "  pyinstaller --noconfirm --clean LiminalVibes.spec" >&2
  exit 1
fi

cleanup() {
  rm -rf "$STAGING_DIR"
}
trap cleanup EXIT

rm -f "$DMG_PATH"

cp -R "$APP_PATH" "$STAGING_DIR/LiminalVibes.app"
ln -s /Applications "$STAGING_DIR/Applications"

hdiutil create \
  -volname "Liminal Vibes" \
  -srcfolder "$STAGING_DIR" \
  -ov -format UDZO \
  "$DMG_PATH"

echo "Created $DMG_PATH"
