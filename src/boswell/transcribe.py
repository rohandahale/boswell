"""Whisper transcription via mlx-whisper, with stereo channel separation.

Stereo layout assumed: left = mic (Me), right = BlackHole (Them). Each
channel is transcribed independently, then segments are merged in
chronological order and labeled by speaker. For mono input, a single pass
labels everything "Speaker".
"""

from __future__ import annotations

import gc
import logging
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

log = logging.getLogger(__name__)

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
_SILENCE_ENERGY_THRESHOLD = 1e-5  # mean |amplitude| below this -> skip channel
_WHISPER_SR = 16000  # Whisper expects 16 kHz; resample before handoff.


def _resample_to_16k(audio: np.ndarray, sr: int) -> np.ndarray:
    if sr == _WHISPER_SR:
        return audio.astype("float32", copy=False)
    # Prefer scipy.signal.resample_poly (polyphase FIR, no aliasing). Fall
    # back to linear interp if scipy isn't installed — Whisper tolerates
    # it for speech, just with slightly worse high-frequency response.
    try:
        from math import gcd

        from scipy.signal import resample_poly  # type: ignore[import-not-found]

        g = gcd(sr, _WHISPER_SR)
        up = _WHISPER_SR // g
        down = sr // g
        return resample_poly(audio, up, down).astype("float32")
    except ImportError:
        log.warning("scipy not installed; using linear-interp resampler (slight aliasing).")
        n_in = audio.shape[0]
        n_out = int(round(n_in * _WHISPER_SR / sr))
        x_in = np.linspace(0.0, 1.0, n_in, endpoint=False, dtype=np.float64)
        x_out = np.linspace(0.0, 1.0, n_out, endpoint=False, dtype=np.float64)
        return np.interp(x_out, x_in, audio).astype("float32")


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: str


def _load_channels(wav_path: Path) -> tuple[np.ndarray, np.ndarray | None, int]:
    data, sr = sf.read(str(wav_path), dtype="float32")
    if data.ndim == 1:
        return data, None, sr
    left = np.ascontiguousarray(data[:, 0])
    right = np.ascontiguousarray(data[:, 1]) if data.shape[1] >= 2 else None
    return left, right, sr


def _mean_energy(x: np.ndarray) -> float:
    return float(np.abs(x).mean()) if x.size else 0.0


def transcribe(
    wav_path: Path,
    model: str = DEFAULT_MODEL,
    language: str | None = None,
) -> list[Segment]:
    import mlx_whisper  # imported lazily; loading MLX is heavy

    left, right, sr = _load_channels(Path(wav_path))
    log.info(
        "Loaded audio: %s (%.1fs, sr=%d, stereo=%s)",
        wav_path,
        left.size / sr if sr else 0,
        sr,
        right is not None,
    )

    # Suppress common Whisper hallucinations on silence/near-silence:
    # - no_speech_threshold: skip segments Whisper itself thinks are non-speech
    # - condition_on_previous_text=False: stop it looping the same phrase
    # - compression_ratio_threshold: drop runs of repeated tokens ("or or or…")
    kwargs: dict[str, Any] = {
        "path_or_hf_repo": model,
        "word_timestamps": False,
        "no_speech_threshold": 0.6,
        "condition_on_previous_text": False,
        "compression_ratio_threshold": 2.0,
    }
    if language:
        kwargs["language"] = language

    # In-person mode: if the BlackHole channel is empty, the mic channel is
    # a mixed-speaker recording, not just "Me". Relabel generically so the
    # transcript doesn't misattribute. Proper diarization is Phase 3.
    right_silent = right is None or _mean_energy(right) < _SILENCE_ENERGY_THRESHOLD
    me_label = "Speaker" if right_silent else "Me"

    segments: list[Segment] = []

    def _run(audio: np.ndarray, speaker: str) -> None:
        if _mean_energy(audio) < _SILENCE_ENERGY_THRESHOLD:
            log.info("Skipping %s channel: silence", speaker)
            return
        log.info("Transcribing %s channel (%.1fs)…", speaker, audio.size / sr)
        audio_16k = _resample_to_16k(audio, sr)
        result = mlx_whisper.transcribe(audio_16k, **kwargs)
        del audio_16k
        for seg in result.get("segments", []):
            text = str(seg["text"]).strip()
            if not text:
                continue
            segments.append(
                Segment(
                    start=float(seg["start"]),
                    end=float(seg["end"]),
                    text=text,
                    speaker=speaker,
                )
            )

    # An hour of stereo float32 is ~1.4 GB; release each channel right after
    # transcribing it so peak RSS isn't both channels + the MLX model.
    _run(left, me_label)
    del left
    gc.collect()

    if right is not None and not right_silent:
        _run(right, "Them")
    del right
    gc.collect()

    segments.sort(key=lambda s: s.start)
    return segments


def format_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_duration(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    total_minutes = int(seconds // 60)
    s = int(seconds % 60)
    if seconds >= 3600:
        h = total_minutes // 60
        m = total_minutes % 60
        return f"{h}h {m}m {s}s"
    return f"{total_minutes}m {s}s"


def render_transcript_md(
    segments: list[Segment],
    *,
    title: str,
    date: _date,
    duration_seconds: float,
) -> str:
    lines = [
        f"# Transcript — {title}",
        "",
        f"**Date:** {date.isoformat()}",
        f"**Duration:** {format_duration(duration_seconds)}",
        "",
        "---",
        "",
    ]
    prev_speaker: str | None = None
    for seg in segments:
        if not seg.text:
            continue
        if prev_speaker is not None and seg.speaker != prev_speaker:
            lines.append("")
        lines.append(f"[{format_timestamp(seg.start)}] {seg.speaker}: {seg.text}")
        prev_speaker = seg.speaker
    return "\n".join(lines) + "\n"


def write_transcript(
    segments: list[Segment],
    output_path: Path,
    *,
    title: str,
    date: _date,
    duration_seconds: float,
) -> None:
    content = render_transcript_md(
        segments, title=title, date=date, duration_seconds=duration_seconds
    )
    output_path.write_text(content, encoding="utf-8")
