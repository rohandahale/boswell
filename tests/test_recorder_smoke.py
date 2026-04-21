"""Recorder smoke test: feeds a fake sounddevice stream and verifies the WAV."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

from boswell.devices import InputDevice
from boswell.recorder import Recorder


class _FakeStream:
    """Drop-in for sd.InputStream that synthesizes stereo sine frames."""

    def __init__(self, samplerate: int, channels: int, device: int, dtype: str, callback) -> None:
        self.sr = samplerate
        self.ch = channels
        self.cb = callback
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        block = 1024
        t = 0
        while not self._stop.is_set():
            n = np.arange(t, t + block)
            left = 0.1 * np.sin(2 * np.pi * 440 * n / self.sr).astype("float32")
            right = 0.1 * np.sin(2 * np.pi * 880 * n / self.sr).astype("float32")
            frame = np.stack([left, right], axis=1) if self.ch == 2 else left[:, None]
            self.cb(frame, block, None, 0)
            t += block
            time.sleep(block / self.sr)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def close(self) -> None:
        pass


def test_recorder_writes_stereo_wav(tmp_path: Path) -> None:
    dev = InputDevice(index=0, name="FakeAggregate", max_input_channels=2, default_samplerate=48000)
    out = tmp_path / "audio.wav"
    rec = Recorder(dev, out, sample_rate=48000, channels=2)

    with patch("boswell.recorder.sd.InputStream", _FakeStream):
        rec.start()
        time.sleep(0.5)
        meta = rec.stop()

    assert out.exists() and out.stat().st_size > 1000
    data, sr = sf.read(str(out), dtype="float32")
    assert sr == 48000
    assert data.ndim == 2 and data.shape[1] == 2
    assert data.shape[0] > 0
    assert meta["channels"] == 2
    assert meta["sample_rate"] == 48000
    assert meta["duration_seconds"] > 0
