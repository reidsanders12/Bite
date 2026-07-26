"""
Central logging setup for Bite.

Console output stays at INFO so a dev running `flet run` sees the same
signal the old print() statements gave; a rotating file at DEBUG level is
added on top so a user's own logs are still available to inspect after the
fact (a shipped desktop/mobile build has no visible console) -- e.g. when
asking a user who hit a bug to send their log file.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.expanduser("~"), ".bite", "logs")
LOG_FILE = os.path.join(LOG_DIR, "bite.log")

_configured = False


def configure_logging() -> None:
    """Idempotent -- safe to call more than once (e.g. from tests)."""
    global _configured
    if _configured:
        return
    _configured = True

    os.makedirs(LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console_handler)
    root.addHandler(file_handler)
