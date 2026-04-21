"""Integration tests for the transcribe pipeline.

We don't invoke mlx-whisper itself (too heavy + non-deterministic for unit
tests). Instead we mock it and verify:

- Stereo WAV gets loaded as two channels.
- Resampling to 16 kHz happens before the mlx-whisper call.
- Silence-detection skips the BlackHole channel entirely.
- Speaker labels flip between "Me"/"Them" (stereo with audio both sides)
  and "Speaker" (BlackHole silent = in-person mode).
- Empty-text segments are dropped.
- Segments end up time-sorted across channels.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import soundfile as sf

from boswell import transcribe


def _tone(freq: float, seconds: float, sr: int, amp: float = 0.15) -> np.ndarray:
    t = np.arange(int(seconds * sr)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype("float32")


def _write_wav(path: Path, left: np.ndarray, right: np.ndarray | None, sr: int) -> None:
    if right is None:
        sf.write(str(path), left, sr)
    else:
        sf.write(str(path), np.stack([left, right], axis=1), sr)


def _fake_mlx_module(return_segments: list[dict]) -> MagicMock:
    mod = MagicMock()
    mod.transcribe.return_value = {"segments": return_segments}
    return mod


def test_resampler_hits_16k_from_48k() -> None:
    audio_48k = _tone(440.0, 1.0, sr=48000)
    out = transcribe._resample_to_16k(audio_48k, 48000)
    # 1 s of 48 kHz → 1 s of 16 kHz (± rounding from resample_poly).
    assert abs(out.shape[0] - 16000) <= 2
    assert out.dtype == np.float32


def test_resampler_passthrough_when_already_16k() -> None:
    audio_16k = _tone(440.0, 0.5, sr=16000)
    out = transcribe._resample_to_16k(audio_16k, 16000)
    assert out.shape == audio_16k.shape
    assert out.dtype == np.float32


def test_load_channel_matches_full_load(tmp_path: Path) -> None:
    sr = 48000
    wav = tmp_path / "stereo.wav"
    left = _tone(300, 0.5, sr)
    right = _tone(600, 0.5, sr)
    _write_wav(wav, left=left, right=right, sr=sr)

    loaded_left, loaded_sr = transcribe._load_channel(wav, 0)
    loaded_right, _ = transcribe._load_channel(wav, 1)

    assert loaded_sr == sr
    # Exact match vs. the naive full-load-then-slice path.
    full = sf.read(str(wav), dtype="float32")[0]
    assert np.array_equal(loaded_left, full[:, 0])
    assert np.array_equal(loaded_right, full[:, 1])


def test_load_channel_rejects_out_of_range(tmp_path: Path) -> None:
    sr = 48000
    wav = tmp_path / "stereo.wav"
    _write_wav(wav, left=_tone(300, 0.1, sr), right=_tone(600, 0.1, sr), sr=sr)
    try:
        transcribe._load_channel(wav, 2)
    except ValueError:
        return
    raise AssertionError("expected ValueError for out-of-range channel")


def test_channel_mean_energy_matches_naive(tmp_path: Path) -> None:
    sr = 48000
    wav = tmp_path / "stereo.wav"
    left = _tone(300, 0.5, sr)
    right = np.zeros(len(left), dtype="float32")
    _write_wav(wav, left=left, right=right, sr=sr)

    streaming_left = transcribe._channel_mean_energy(wav, 0)
    streaming_right = transcribe._channel_mean_energy(wav, 1)
    expected_left = float(np.abs(left).mean())
    expected_right = 0.0

    # Chunked sum differs from single-pass only by float32 associativity;
    # tolerance matches the silence threshold the value actually feeds.
    assert abs(streaming_left - expected_left) < transcribe._SILENCE_ENERGY_THRESHOLD
    assert streaming_right == expected_right


def test_mean_energy_chunked_matches_naive() -> None:
    rng = np.random.default_rng(42)
    x = (rng.standard_normal(2_500_000).astype("float32") * 0.1)
    chunked = transcribe._mean_energy(x)
    naive = float(np.abs(x).mean())
    assert abs(chunked - naive) < transcribe._SILENCE_ENERGY_THRESHOLD


def test_mean_energy_empty_returns_zero() -> None:
    assert transcribe._mean_energy(np.array([], dtype="float32")) == 0.0


def test_stereo_both_channels_labeled_me_and_them(tmp_path: Path) -> None:
    sr = 48000
    wav = tmp_path / "both.wav"
    _write_wav(wav, left=_tone(300, 1.0, sr), right=_tone(600, 1.0, sr), sr=sr)

    mlx = _fake_mlx_module([{"start": 0.0, "end": 1.0, "text": "hello"}])
    with patch.dict("sys.modules", {"mlx_whisper": mlx}):
        segments = transcribe.transcribe(wav, model="fake")

    speakers = {s.speaker for s in segments}
    assert speakers == {"Me", "Them"}
    assert mlx.transcribe.call_count == 2
    # Resampled input should be 16 kHz length (~1 s).
    for call in mlx.transcribe.call_args_list:
        audio_arg = call.args[0]
        assert abs(audio_arg.shape[0] - 16000) <= 2


def test_stereo_silent_right_uses_speaker_label(tmp_path: Path) -> None:
    sr = 48000
    wav = tmp_path / "silent_right.wav"
    right = np.zeros(sr, dtype="float32")
    _write_wav(wav, left=_tone(300, 1.0, sr), right=right, sr=sr)

    mlx = _fake_mlx_module([{"start": 0.0, "end": 1.0, "text": "hi"}])
    with patch.dict("sys.modules", {"mlx_whisper": mlx}):
        segments = transcribe.transcribe(wav, model="fake")

    # In-person mode: only mic gets transcribed, labeled "Speaker".
    assert [s.speaker for s in segments] == ["Speaker"]
    assert mlx.transcribe.call_count == 1


def test_mono_wav_labeled_speaker(tmp_path: Path) -> None:
    sr = 48000
    wav = tmp_path / "mono.wav"
    _write_wav(wav, left=_tone(300, 0.5, sr), right=None, sr=sr)

    mlx = _fake_mlx_module([{"start": 0.0, "end": 0.5, "text": "only me"}])
    with patch.dict("sys.modules", {"mlx_whisper": mlx}):
        segments = transcribe.transcribe(wav, model="fake")

    assert [s.speaker for s in segments] == ["Speaker"]


def test_empty_text_segments_dropped(tmp_path: Path) -> None:
    sr = 48000
    wav = tmp_path / "with_empty.wav"
    _write_wav(wav, left=_tone(300, 1.0, sr), right=_tone(600, 1.0, sr), sr=sr)

    mlx = _fake_mlx_module(
        [
            {"start": 0.0, "end": 0.5, "text": "  "},
            {"start": 0.5, "end": 1.0, "text": "real"},
        ]
    )
    with patch.dict("sys.modules", {"mlx_whisper": mlx}):
        segments = transcribe.transcribe(wav, model="fake")

    texts = [s.text for s in segments]
    assert "real" in texts
    assert "" not in texts
    assert all(t.strip() for t in texts)


def test_segments_sorted_chronologically_across_channels(tmp_path: Path) -> None:
    sr = 48000
    wav = tmp_path / "interleaved.wav"
    _write_wav(wav, left=_tone(300, 1.0, sr), right=_tone(600, 1.0, sr), sr=sr)

    # Each mocked channel-call returns segments with different start times.
    # Mock flips return value per call.
    call_returns = [
        {"segments": [{"start": 0.2, "end": 0.5, "text": "first"}]},  # "Me"
        {"segments": [{"start": 0.6, "end": 0.9, "text": "second"}]},  # "Them"
    ]
    mlx = MagicMock()
    mlx.transcribe.side_effect = call_returns

    with patch.dict("sys.modules", {"mlx_whisper": mlx}):
        segments = transcribe.transcribe(wav, model="fake")

    assert [s.start for s in segments] == sorted(s.start for s in segments)
    assert segments[0].text == "first" and segments[0].speaker == "Me"
    assert segments[1].text == "second" and segments[1].speaker == "Them"
