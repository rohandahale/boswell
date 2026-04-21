"""rumps menu bar app: Start / Stop / Open Meetings Folder."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path

import rumps

from . import devices, notify, paths
from .recorder import Recorder, RecorderError

APP_NAME = "Boswell"

log = logging.getLogger(__name__)

_POLL_SECONDS = 2
# How long the input callback can be silent before we treat the device as
# lost. CoreAudio normally fires every ~10 ms; >5 s of nothing means the
# device was unplugged or the OS reclaimed it.
_DEVICE_SILENCE_THRESHOLD_SECONDS = 5.0


class State(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"


class BoswellApp(rumps.App):
    def __init__(self) -> None:
        # quit_button=None so we can intercept Quit while transcription runs.
        super().__init__(APP_NAME, title=f"{APP_NAME} · Idle", quit_button=None)
        self.state: State = State.IDLE
        self.recorder: Recorder | None = None
        self.meeting_dir: Path | None = None
        self.transcribe_proc: subprocess.Popen[bytes] | None = None
        self._device_lost_notified = False

        self.start_item = rumps.MenuItem("Start Recording…", callback=self.on_start)
        self.stop_item = rumps.MenuItem("Stop Recording", callback=self.on_stop)
        self.stop_item.set_callback(None)  # disabled while idle
        self.menu = [
            self.start_item,
            self.stop_item,
            None,
            rumps.MenuItem("Open Meetings Folder", callback=self.on_open_folder),
            None,
            rumps.MenuItem("Quit", callback=self.on_quit),
        ]

        self._poll_timer = rumps.Timer(self._poll, _POLL_SECONDS)
        self._poll_timer.start()

    def _set_title(self, text: str) -> None:
        self.title = f"{APP_NAME} · {text}"

    def on_start(self, _sender: rumps.MenuItem) -> None:
        if self.state is not State.IDLE:
            return
        # rumps.Window is unreliable on recent macOS (blocks main thread
        # without rendering). Auto-name from the weekday — the date+time
        # already prefix the folder, so don't re-encode them in the slug.
        title = datetime.now().strftime("%A").lower()

        try:
            dev = devices.find_input_device()
        except devices.DeviceError as e:
            notify.notify(f"{APP_NAME}: input device error", str(e))
            log.error("Device lookup failed: %s", e)
            return

        # Use the device's actual sample rate. Hardcoding 48000 fails when
        # the user's Aggregate Device is configured at 44.1 kHz, with a
        # confusing PortAudioError. The transcriber resamples to 16 kHz
        # anyway, so any source rate is fine.
        sample_rate = int(dev.default_samplerate) or 48000

        try:
            self.meeting_dir = paths.new_meeting_dir(title)
            self.recorder = Recorder(
                dev, paths.audio_path(self.meeting_dir), sample_rate=sample_rate
            )
            self.recorder.start()
        except Exception as e:  # noqa: BLE001
            log.exception("Failed to start recording")
            notify.notify(f"{APP_NAME}: start failed", str(e))
            self.recorder = None
            self.meeting_dir = None
            return

        self._device_lost_notified = False
        self.state = State.RECORDING
        self._set_title("Recording 00:00")
        self.start_item.set_callback(None)
        self.stop_item.set_callback(self.on_stop)

    def on_stop(self, _sender: rumps.MenuItem) -> None:
        if self.state is not State.RECORDING or self.recorder is None or self.meeting_dir is None:
            return
        try:
            meta = self.recorder.stop()
        except RecorderError as e:
            log.exception("Recorder stop failed")
            notify.notify(f"{APP_NAME}: stop failed", str(e))
            self._reset_to_idle()
            return

        meta_full = {
            **meta,
            "start_iso": _iso_or_none(meta.get("start_ts")),
            "end_iso": _iso_or_none(meta.get("end_ts")),
            "title": self.meeting_dir.name,
        }
        paths.metadata_path(self.meeting_dir).write_text(
            json.dumps(meta_full, indent=2, default=str), encoding="utf-8"
        )

        # transcribe_worker writes its own log file inside the meeting
        # folder; redirect stdio to DEVNULL so we don't hold the menu bar's
        # fds open or pipe into a closed launchd stream.
        self.transcribe_proc = subprocess.Popen(
            [sys.executable, "-m", "boswell.transcribe_worker", str(self.meeting_dir)],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        self.state = State.TRANSCRIBING
        self._set_title("Transcribing…")
        self.stop_item.set_callback(None)
        notify.notify(f"{APP_NAME}: recording stopped", f"Transcribing {self.meeting_dir.name}")

    def on_open_folder(self, _sender: rumps.MenuItem) -> None:
        root = paths.meetings_root()
        root.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["open", str(root)])

    def _poll(self, _timer: rumps.Timer) -> None:
        if self.state is State.RECORDING and self.recorder is not None:
            err = self.recorder.write_error()
            if err is not None:
                log.error("Recorder writer thread died: %r", err)
                notify.notify(
                    f"{APP_NAME}: write error",
                    f"Recording stopped — {err}",
                )
                self._abandon_recording()
                return

            silence = self.recorder.callback_silence_seconds()
            if silence > _DEVICE_SILENCE_THRESHOLD_SECONDS and not self._device_lost_notified:
                # Notify once; don't auto-stop in case the device comes back.
                # The user can decide whether to Stop and check the device.
                log.warning("Input callback silent for %.1fs", silence)
                notify.notify(
                    f"{APP_NAME}: input device silent",
                    f"No audio for {int(silence)}s — device unplugged?",
                )
                self._device_lost_notified = True

            secs = int(self.recorder.elapsed_seconds())
            m, s = divmod(secs, 60)
            self._set_title(f"Recording {m:02d}:{s:02d}")
            return

        if self.state is State.TRANSCRIBING and self.transcribe_proc is not None:
            ret = self.transcribe_proc.poll()
            if ret is None:
                return
            name = self.meeting_dir.name if self.meeting_dir else ""
            if ret == 0:
                notify.notify(f"{APP_NAME}: transcription complete", name)
            else:
                notify.notify(f"{APP_NAME}: transcription failed", f"{name} (exit {ret})")
            self._reset_to_idle()

    def _abandon_recording(self) -> None:
        """Recorder writer thread died (disk full, etc.). Tear down without
        re-raising the writer error — we already notified the user."""
        if self.recorder is not None:
            try:
                self.recorder.stop()
            except RecorderError:
                pass
        self._reset_to_idle()

    def on_quit(self, _sender: rumps.MenuItem) -> None:
        # Block silent quit during recording or transcription. Detached
        # transcription would survive the parent (start_new_session=True)
        # but the user would lose the completion notification.
        if self.state is State.RECORDING:
            resp = rumps.alert(
                title=f"{APP_NAME}: recording in progress",
                message="Stop and save the recording before quitting?",
                ok="Stop & Quit",
                cancel="Cancel",
            )
            if not resp:
                return
            self.on_stop(None)  # type: ignore[arg-type]

        if self.state is State.TRANSCRIBING:
            resp = rumps.alert(
                title=f"{APP_NAME}: transcription in progress",
                message=(
                    "Quitting now will detach the transcription. The "
                    "transcript will still be written, but you won't get "
                    "the completion notification."
                ),
                ok="Quit Anyway",
                cancel="Cancel",
            )
            if not resp:
                return

        rumps.quit_application()

    def _reset_to_idle(self) -> None:
        self.state = State.IDLE
        self._set_title("Idle")
        self.start_item.set_callback(self.on_start)
        self.stop_item.set_callback(None)
        self.recorder = None
        self.meeting_dir = None
        self.transcribe_proc = None


def _iso_or_none(ts: object) -> str | None:
    if not isinstance(ts, (int, float)):
        return None
    return datetime.fromtimestamp(ts).isoformat()


def main() -> None:
    BoswellApp().run()
