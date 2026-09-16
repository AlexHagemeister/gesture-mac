#!/bin/zsh
# Build ~/Applications/gesture-mac.app: a thin launcher around `uv run
# gesture-mac` so the app runs without a terminal and can be a login item.
# The bundle is what macOS asks camera and Accessibility permission for,
# so the grants attach to "gesture-mac" rather than to Terminal or uv.
# Needs a C compiler (Xcode Command Line Tools).
# Re-run after moving the repo or uv. Output goes to ~/Library/Logs/gesture-mac.log.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
UV="$(command -v uv)"
APP="${1:-$HOME/Applications/gesture-mac.app}"

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>gesture-mac</string>
  <key>CFBundleDisplayName</key><string>gesture-mac</string>
  <key>CFBundleIdentifier</key><string>com.alexhagemeister.gesture-mac</string>
  <key>CFBundleVersion</key><string>0.1.0</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>gesture-mac</string>
  <key>LSUIElement</key><true/>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSCameraUsageDescription</key><string>gesture-mac reads your webcam to recognize hand gestures.</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

# A compiled launcher, not a script: macOS attributes the child's camera
# and Accessibility requests to the bundle only when the bundle's main
# executable is a real binary inside it. Repo and uv paths are baked in.
cc -O2 -Wall -DREPO="\"$REPO\"" -DUV="\"$UV\"" -o "$APP/Contents/MacOS/gesture-mac" "$REPO/scripts/launcher.c"

# Ad hoc signature: gives the bundle a stable identity for the permission
# database, so re-running this script does not reset the grants.
codesign --force --sign - "$APP" >/dev/null 2>&1 || true

echo "built $APP"
echo "repo:  $REPO"
echo "uv:    $UV"
echo "log:   $HOME/Library/Logs/gesture-mac.log"
