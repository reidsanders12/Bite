#!/usr/bin/env python3
"""
Workaround for an upstream bug in flet==0.28.3's websocket receive loop
(flet_web/fastapi/flet_app.py): `receive_text()` unconditionally indexes
message["text"], which raises a bare KeyError('text') on any non-text
frame or disconnect-event shape it doesn't expect. That KeyError isn't a
WebSocketDisconnect, so it falls into the `logger.warning("Receive loop
error: ...")` branch and tears the whole session down -- the client then
immediately reconnects and repeats, forever ("Receive loop error: 'text'"
spamming the terminal). Not specific to this app -- see flet-dev/flet
issues #5603 and #5972 (both open, unresolved, as of flet 0.28.3).

Run this after any fresh `pip install` that reinstalls flet-web (a new
venv, `pip install --force-reinstall`, etc.) -- pip installs overwrite the
patched file with the original, buggy one. Safe to run repeatedly: it
detects whether the patch is already applied and skips it if so.

Usage:
    python3 scripts/patch_flet_receive_loop.py
"""
import importlib.util
import sys
from pathlib import Path

OLD_LINE = "                await self.__on_message(await self.__websocket.receive_text())"

NEW_BLOCK = '''                # Patched -- see scripts/patch_flet_receive_loop.py
                message = await self.__websocket.receive()
                if message["type"] == "websocket.disconnect":
                    raise WebSocketDisconnect(message.get("code", 1000))
                text = message.get("text")
                if text is None:
                    continue
                await self.__on_message(text)'''

# Marker used to detect an already-patched file regardless of exactly which
# comment text was used when it was applied (e.g. by hand, the first time).
ALREADY_PATCHED_MARKER = 'if message["type"] == "websocket.disconnect":'


def find_target() -> Path:
    spec = importlib.util.find_spec("flet_web.fastapi.flet_app")
    if spec is None or spec.origin is None:
        print("flet_web.fastapi.flet_app not found -- is flet-web installed in this environment?", file=sys.stderr)
        sys.exit(1)
    return Path(spec.origin)


def main() -> None:
    target = find_target()
    src = target.read_text()

    if ALREADY_PATCHED_MARKER in src:
        print(f"Already patched: {target}")
        return

    if OLD_LINE not in src:
        print(
            f"Couldn't find the expected unpatched __receive_loop line in {target} -- "
            "flet-web's source may have changed. Skipping (manual check needed).",
            file=sys.stderr,
        )
        sys.exit(1)

    target.write_text(src.replace(OLD_LINE, NEW_BLOCK))
    print(f"Patched: {target}")


if __name__ == "__main__":
    main()
