"""Audio recorder: sounddevice callback -> queue -> soundfile writer thread.

Writes a single WAV at `output_path`. Stereo by default: left=mic,
right=BlackHole (assumes the caller points at an Aggregate Device wired that
way). Flushes every 5 s so an unclean shutdown loses at most a few seconds.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd
import soundfile as sf

from .devices import InputDevice

log = logging.getLogger(__name__)

_FLUSH_INTERVAL_SECONDS = 5.0
_WRITER_POLL_SECONDS = 0.2
_WRITER_JOIN_TIMEOUT = 10.0


class RecorderError(RuntimeError):
    pass


class Recorder:
    def __init__(
        self,
        device: InputDevice,
        output_path: Path,
        sample_rate: int = 48000,
        channels: int = 2,
    ) -> None:
        if channels < 1:
            raise ValueError("channels must be >= 1")
        self.device = device
        self.output_path = Path(output_path)
        self.sample_rate = sample_rate
        self.channels = channels
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: sd.InputStream | None = None
        self._writer_thread: threading.Thread | None = None
        self._writer_stop = threading.Event()
        self._started_at: float | None = None
        self._stopped_at: float | None = None
        self._frames_written = 0
        self._write_error: BaseException | None = None

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: Any,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            log.warning("Audio callback status: %s", status)
        # sounddevice reuses the buffer; copy before handing off.
        self._queue.put(indata.copy())

    def _writer(self) -> None:
        try:
            with sf.SoundFile(
                str(self.output_path),
                mode="w",
                samplerate=self.sample_rate,
                channels=self.channels,
                subtype="PCM_16",
            ) as f:
                last_flush = time.monotonic()
                while not self._writer_stop.is_set() or not self._queue.empty():
                    try:
                        chunk = self._queue.get(timeout=_WRITER_POLL_SECONDS)
                    except queue.Empty:
                        continue
                    f.write(chunk)
                    self._frames_written += len(chunk)
                    if time.monotonic() - last_flush > _FLUSH_INTERVAL_SECONDS:
                        f.flush()
                        last_flush = time.monotonic()
        except BaseException as e:  # noqa: BLE001 — propagate via _write_error
            self._write_error = e
            log.exception("Writer thread failed")

    def start(self) -> None:
        if self._stream is not None:
            raise RecorderError("Already recording")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._writer_stop.clear()
        self._writer_thread = threading.Thread(target=self._writer, daemon=True)
        self._writer_thread.start()
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                device=self.device.index,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
        except Exception:
            self._writer_stop.set()
            if self._writer_thread:
                self._writer_thread.join(timeout=_WRITER_JOIN_TIMEOUT)
            raise
        self._started_at = time.time()
        log.info(
            "Recording started: %s (device=%s, %d Hz, %d ch)",
            self.output_path,
            self.device.name,
            self.sample_rate,
            self.channels,
        )

    def stop(self) -> dict[str, Any]:
        if self._stream is None:
            raise RecorderError("Not recording")
        self._stream.stop()
        self._stream.close()
        self._stream = None
        self._stopped_at = time.time()
        self._writer_stop.set()
        if self._writer_thread:
            self._writer_thread.join(timeout=_WRITER_JOIN_TIMEOUT)
        if self._write_error is not None:
            raise RecorderError(f"Writer thread failed: {self._write_error!r}") from self._write_error
        duration = (self._stopped_at or 0.0) - (self._started_at or 0.0)
        log.info(
            "Recording stopped: %s (%.1fs, %d frames)",
            self.output_path,
            duration,
            self._frames_written,
        )
        return {
            "start_ts": self._started_at,
            "end_ts": self._stopped_at,
            "duration_seconds": duration,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "device_name": self.device.name,
            "device_index": self.device.index,
            "frames_written": self._frames_written,
            "output_path": str(self.output_path),
        }

    def is_running(self) -> bool:
        return self._stream is not None

    def elapsed_seconds(self) -> float:
        if self._started_at is None:
            return 0.0
        end = self._stopped_at or time.time()
        return end - self._started_at
