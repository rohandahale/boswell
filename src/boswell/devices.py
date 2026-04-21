"""Audio input device discovery.

Resolves the recording input device for Boswell. Expects an Aggregate
Device created in Audio MIDI Setup that combines the user's mic and
BlackHole, with mic on channel 1 and BlackHole on channels 2-3 (stereo).

The device is selected by the `BOSWELL_INPUT_DEVICE` env var (substring
match against the device name) or, if unset, by looking for a device whose
name contains "Boswell" (or the legacy "Notetaker" for backward compat).
Fails loud with a clear error if no match.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import sounddevice as sd

log = logging.getLogger(__name__)

_DEVICE_ENV = "BOSWELL_INPUT_DEVICE"
_DEFAULT_HINTS = ("Boswell", "Notetaker")  # first match wins; legacy accepted.


class DeviceError(RuntimeError):
    pass


@dataclass
class InputDevice:
    index: int
    name: str
    max_input_channels: int
    default_samplerate: float


def list_input_devices() -> list[InputDevice]:
    devices = sd.query_devices()
    out: list[InputDevice] = []
    for i, d in enumerate(devices):
        if d.get("max_input_channels", 0) > 0:
            out.append(
                InputDevice(
                    index=i,
                    name=d["name"],
                    max_input_channels=int(d["max_input_channels"]),
                    default_samplerate=float(d.get("default_samplerate") or 0.0),
                )
            )
    return out


def find_input_device(name_hint: str | None = None) -> InputDevice:
    override = name_hint or os.environ.get(_DEVICE_ENV)
    hints: tuple[str, ...] = (override,) if override else _DEFAULT_HINTS
    all_devices = list_input_devices()
    for hint in hints:
        matches = [d for d in all_devices if hint.lower() in d.name.lower()]
        if matches:
            if len(matches) > 1:
                log.warning(
                    "Multiple input devices match %r; using the first: %s",
                    hint,
                    [m.name for m in matches],
                )
            dev = matches[0]
            if dev.max_input_channels < 2:
                raise DeviceError(
                    f"Device {dev.name!r} has {dev.max_input_channels} input channel(s); "
                    "need >= 2 for stereo (mic on L, BlackHole on R)."
                )
            return dev
    available = "\n  ".join(f"[{d.index}] {d.name}" for d in all_devices)
    raise DeviceError(
        f"No input device matching {hints!r} found. Set "
        f"{_DEVICE_ENV}=<substring> to override. Available inputs:\n  {available}"
    )
