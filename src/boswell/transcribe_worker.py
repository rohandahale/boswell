"""Subprocess entrypoint for post-recording transcription.

Reads audio.wav + metadata.json from a meeting folder, runs mlx-whisper,
writes transcript.md, and updates metadata.json with transcription stats.
Logs to <meeting_dir>/transcribe.log.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date as _date
from datetime import datetime
from pathlib import Path

from . import paths
from .transcribe import DEFAULT_MODEL, transcribe, write_transcript

log = logging.getLogger(__name__)


def _parse_date(meta: dict, fallback_dir: Path) -> _date:
    iso = meta.get("start_iso")
    if isinstance(iso, str):
        try:
            return datetime.fromisoformat(iso).date()
        except ValueError:
            pass
    # Fallback: parse from directory name "YYYY-MM-DD-HHMM-slug"
    parts = fallback_dir.name.split("-", 3)
    if len(parts) >= 3:
        try:
            return _date(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            pass
    return datetime.now().date()


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1:
        print("Usage: python -m boswell.transcribe_worker <meeting_dir>", file=sys.stderr)
        return 2

    meeting_dir = Path(argv[0]).expanduser().resolve()
    if not meeting_dir.is_dir():
        print(f"Not a directory: {meeting_dir}", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        filename=str(meeting_dir / "transcribe.log"),
    )

    meta_path = paths.metadata_path(meeting_dir)
    meta: dict = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except json.JSONDecodeError:
            log.warning("metadata.json is malformed; continuing with empty meta")

    audio = paths.audio_path(meeting_dir)
    if not audio.exists():
        log.error("audio.wav not found at %s", audio)
        return 3

    model = os.environ.get("BOSWELL_WHISPER_MODEL", DEFAULT_MODEL)
    language = os.environ.get("BOSWELL_WHISPER_LANGUAGE") or None

    t0 = datetime.now()
    log.info("Transcription start: model=%s language=%s", model, language or "auto")
    segments = transcribe(audio, model=model, language=language)
    dt = (datetime.now() - t0).total_seconds()
    log.info("Transcribed %d segments in %.1fs", len(segments), dt)

    duration = float(meta.get("duration_seconds") or 0.0)
    title = str(meta.get("title") or meeting_dir.name)
    d = _parse_date(meta, meeting_dir)

    write_transcript(
        segments,
        paths.transcript_path(meeting_dir),
        title=title,
        date=d,
        duration_seconds=duration,
    )

    meta.update(
        {
            "transcribed_at": datetime.now().isoformat(),
            "transcription_seconds": dt,
            "segment_count": len(segments),
            "model": model,
        }
    )
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    log.info("Wrote %s", paths.transcript_path(meeting_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
