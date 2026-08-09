"""
Central logging setup for Bite!.

Console output stays at INFO so a dev running `flet run` sees the same
signal the old print() statements gave; a rotating file at DEBUG level is
added on top so a user's own logs are still available to inspect after the
fact (a shipped desktop/mobile build has no visible console) -- e.g. when
asking a user who hit a bug to send their log file.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def _log_dir() -> str:
    """Base directory for the rotating log file. iOS's sandbox only allows
    writes inside specific container subdirectories (Library, Documents,
    tmp) -- writing straight into the home directory root (fine on desktop
    and Android) raises PermissionError there. Library/Caches is the right
    category for a rotating debug log: non-essential and regenerable, so
    it's fine that iOS is allowed to purge it under storage pressure."""
    home = os.path.expanduser("~")
    if sys.platform in ("ios", "ipados"):
        return os.path.join(home, "Library", "Caches", "bite", "logs")
    return os.path.join(home, ".bite", "logs")


LOG_DIR = _log_dir()
LOG_FILE = os.path.join(LOG_DIR, "bite.log")

_configured = False


def configure_logging() -> None:
    """Idempotent -- safe to call more than once (e.g. from tests)."""
    global _configured
    if _configured:
        return
    _configured = True

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console_handler)

    # File logging is a nice-to-have (lets a user send their log file after
    # hitting a bug), not something app startup should ever die on -- an
    # unexpected sandbox restriction, read-only disk, or full disk here
    # should degrade to console-only logging, not crash the whole app
    # before it even renders a first screen (which is exactly what the
    # unguarded os.makedirs used to do on iOS).
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:
        root.warning("File logging disabled -- couldn't set up %s: %s", LOG_DIR, exc)
