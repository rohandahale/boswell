"""macOS notifications. Tries pync first, falls back to osascript."""

from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)


def notify(title: str, message: str) -> None:
    try:
        import pync  # type: ignore[import-not-found]

        pync.notify(message, title=title)
        return
    except Exception:
        pass
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{_esc(message)}" with title "{_esc(title)}"',
            ],
            check=False,
            timeout=5,
        )
    except Exception:
        log.exception("Notification failed: %s — %s", title, message)


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')
