#!/usr/bin/env python3
"""
Reapplies two hand-patches that `flet build ipa` / `flutter build ios`
silently wipe out whenever they regenerate build/flutter/ios/ (Podfile gets
rewritten on every "Upgrading Podfile" step; Runner.xcodeproj/project.pbxproj
gets rewritten on every "Upgrading project.pbxproj" step, or whenever Xcode
itself offers to "Update to recommended settings"):

1. iOS deployment target 13.0 -> 14.0 (Podfile `platform :ios` line, and
   IPHONEOS_DEPLOYMENT_TARGET in all three Xcode build configs). The `health`
   plugin (flet-health, Profile -> Connect Health App) requires iOS 14.0+;
   the flet 0.28.3 stock template's default of 13.0 makes `pod install` fail
   with "the plugin health requires a higher minimum iOS deployment version".
   There's no pyproject.toml hook for this in flet 0.28.3 (unlike Android's
   [tool.flet.android] min_sdk_version), so it has to be patched post-generation.

2. ENABLE_USER_SCRIPT_SANDBOXING YES -> NO, if present. Xcode 15+ defaults to
   sandboxing Run Script build phases, which blocks Flutter's own build
   scripts from reading/writing DerivedData (fails archiving with
   "Sandbox: rsync/dartvm(...) deny(1) file-read-data/file-write-create").
   flet 0.28.3's stock template doesn't set this key itself -- it only shows
   up if Xcode's project-upgrade flow adds it (e.g. building directly from
   Xcode after opening the generated project), so this step is a no-op when
   the key isn't there yet.

Safe to run repeatedly. Run this after any `flet build ipa`/`--clean`, or
any time build/flutter/ios/ gets regenerated from scratch and the app either
fails `pod install` over the health plugin, or fails archiving with a
Sandbox deny error.

Usage:
    python3 scripts/patch_ios_build_workarounds.py
"""
import sys
from pathlib import Path

IOS_DIR = Path(__file__).resolve().parent.parent / "build" / "flutter" / "ios"
PODFILE = IOS_DIR / "Podfile"
PBXPROJ = IOS_DIR / "Runner.xcodeproj" / "project.pbxproj"

MIN_IOS_VERSION = "14.0"


def patch_podfile() -> bool:
    if not PODFILE.exists():
        print(f"{PODFILE} doesn't exist yet -- run `flet build ipa` at least once first.")
        return False
    text = PODFILE.read_text()
    changed = False
    for old_version in ("11.0", "12.0", "13.0"):
        old = f"platform :ios, '{old_version}'"
        if old in text:
            text = text.replace(old, f"platform :ios, '{MIN_IOS_VERSION}'")
            changed = True
    if changed:
        PODFILE.write_text(text)
        print(f"Podfile: bumped platform :ios to {MIN_IOS_VERSION}")
    else:
        print("Podfile: already OK")
    return True


def patch_pbxproj() -> None:
    if not PBXPROJ.exists():
        print(f"{PBXPROJ} doesn't exist yet -- run `flet build ipa` at least once first.")
        return
    text = PBXPROJ.read_text()

    for old_version in ("11.0", "12.0", "13.0"):
        old = f"IPHONEOS_DEPLOYMENT_TARGET = {old_version};"
        new = f"IPHONEOS_DEPLOYMENT_TARGET = {MIN_IOS_VERSION};"
        if old in text:
            text = text.replace(old, new)

    sandbox_old = "ENABLE_USER_SCRIPT_SANDBOXING = YES;"
    sandbox_new = "ENABLE_USER_SCRIPT_SANDBOXING = NO;"
    if sandbox_old in text:
        text = text.replace(sandbox_old, sandbox_new)
        print("project.pbxproj: disabled ENABLE_USER_SCRIPT_SANDBOXING")
    else:
        print("project.pbxproj: ENABLE_USER_SCRIPT_SANDBOXING not set (OK, no-op)")

    PBXPROJ.write_text(text)
    print(f"project.pbxproj: IPHONEOS_DEPLOYMENT_TARGET is now {MIN_IOS_VERSION}")


def main() -> None:
    if not patch_podfile():
        sys.exit(1)
    patch_pbxproj()


if __name__ == "__main__":
    main()
