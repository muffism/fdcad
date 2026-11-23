#!/usr/bin/env bash
# make_dmg.sh - turn the PyInstaller output into a signed Apple Silicon DMG.
# Usage: bash packaging/macos/make_dmg.sh VERSION
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: make_dmg.sh VERSION" >&2
  exit 2
fi
VERSION="$1"

cd "$(dirname "$0")/../.."

APP="dist/FDCAD.app"
if [ ! -d "$APP" ]; then
  echo "missing $APP: run pyinstaller first" >&2
  exit 1
fi

xattr -cr "$APP"
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

STAGING="dist/dmg-staging"
rm -rf "$STAGING"
mkdir -p "$STAGING"
ditto "$APP" "$STAGING/FDCAD.app"
ln -s /Applications "$STAGING/Applications"
# Show the license, the notices and the source offer beside the app (D2867). The spec
# puts them in FDCAD.app/Contents/Resources; stop if one is missing.
for NAME in LICENSE THIRD_PARTY_NOTICES.txt SOURCE_OFFER.md; do
  if [ ! -f "$APP/Contents/Resources/$NAME" ]; then
    echo "missing $APP/Contents/Resources/$NAME: build with packaging/fdcad.spec" >&2
    exit 1
  fi
  cp "$APP/Contents/Resources/$NAME" "$STAGING/$NAME"
done

DMG="dist/FDCAD-${VERSION}-macos-arm64.dmg"
rm -f "$DMG"
hdiutil create -volname "FDCAD ${VERSION}" -srcfolder "$STAGING" -ov -format UDZO "$DMG"

rm -rf "$STAGING"
echo "built $DMG"