#!/usr/bin/env bash
# Single, foolproof entry point for producing a signed-ready iOS archive.
#
# `flet build ipa` regenerates build/flutter/ios/ from its stock template on
# (most) runs -- including wiping the two hand-patches
# scripts/patch_ios_build_workarounds.py applies (iOS deployment target
# 13.0 -> 15.0 -- 14.0 was enough for the flet-health plugin's own `pod
# install` requirement, but App Store Connect's upload validation separately
# floors new submissions at 15.0; and ENABLE_USER_SCRIPT_SANDBOXING).
# Relying on a human to remember "build,
# patch, build again, then check" every single time is exactly how a
# pre-submission build can silently ship with the wrong deployment target
# (the health plugin crashing in App Review, or a "linking with dylib built
# for newer version" warning at best). This script always does the full
# patch-and-rebuild cycle and refuses to exit 0 unless the final archive is
# actually correctly patched -- there is no path to a silently-wrong build.
#
# Usage:
#   ./scripts/build_ios.sh
set -euo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate

echo "==> Building iOS archive (pass 1)..."
flet build ipa || echo "    (non-zero exit expected here if build/flutter/ios/ was just regenerated from scratch -- continuing to patch + rebuild)"

echo "==> Applying iOS build workarounds (deployment target, sandboxing)..."
python3 scripts/patch_ios_build_workarounds.py

echo "==> Building iOS archive (pass 2, with workarounds applied)..."
flet build ipa

echo "==> Verifying the final archive actually has the patched deployment target..."
PBXPROJ="build/flutter/ios/Runner.xcodeproj/project.pbxproj"
for bad_version in "13.0" "14.0"; do
    if grep -q "IPHONEOS_DEPLOYMENT_TARGET = ${bad_version};" "$PBXPROJ"; then
        echo "FAILED: $PBXPROJ still has IPHONEOS_DEPLOYMENT_TARGET = ${bad_version} after patching + rebuilding." >&2
        echo "        Do not archive/submit this build -- investigate before proceeding." >&2
        exit 1
    fi
done
if ! grep -q "IPHONEOS_DEPLOYMENT_TARGET = 15.0;" "$PBXPROJ"; then
    echo "FAILED: $PBXPROJ doesn't show IPHONEOS_DEPLOYMENT_TARGET = 15.0 either -- unexpected state, investigate." >&2
    exit 1
fi

if [ ! -d "build/ipa/Runner.xcarchive" ]; then
    echo "FAILED: build/ipa/Runner.xcarchive wasn't produced." >&2
    exit 1
fi

echo "==> OK: build/ipa/Runner.xcarchive is ready, deployment target confirmed at 15.0."
echo "==> Next: open -a Xcode build/ipa/Runner.xcarchive, then Organizer -> Distribute App."
