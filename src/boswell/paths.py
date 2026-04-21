"""Meeting folder layout: ~/Meetings/YYYY-MM-DD-HHMM-<slug>/."""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

_MEETINGS_ROOT_ENV = "BOSWELL_MEETINGS_ROOT"
_SLUG_MAX_LEN = 40


def meetings_root() -> Path:
    override = os.environ.get(_MEETINGS_ROOT_ENV)
    return Path(override).expanduser() if override else Path.home() / "Meetings"


def make_slug(title: str) -> str:
    # Collapse anything non-alphanumeric to hyphens; trim; lowercase.
    s = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()
    if not s:
        s = "untitled"
    return s[:_SLUG_MAX_LEN].rstrip("-") or "untitled"


def meeting_dirname(title: str, now: datetime | None = None) -> str:
    now = now or datetime.now()
    return f"{now.strftime('%Y-%m-%d-%H%M')}-{make_slug(title)}"


def new_meeting_dir(title: str, now: datetime | None = None) -> Path:
    d = meetings_root() / meeting_dirname(title, now)
    d.mkdir(parents=True, exist_ok=False)
    return d


def audio_path(meeting_dir: Path) -> Path:
    return meeting_dir / "audio.wav"


def transcript_path(meeting_dir: Path) -> Path:
    return meeting_dir / "transcript.md"


def metadata_path(meeting_dir: Path) -> Path:
    return meeting_dir / "metadata.json"
