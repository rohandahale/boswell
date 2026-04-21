# Changelog

All notable changes to Boswell are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [SemVer](https://semver.org/).

## [0.1.0] — 2026-04-20

Initial release.

### Added
- Menu bar app (rumps) with Start / Stop / Open Meetings Folder.
- Stereo Aggregate Device capture (mic on left, BlackHole on right).
- 16 kHz resample before Whisper to avoid chipmunk-noise hallucinations.
- MLX Whisper transcription via `mlx-community/whisper-large-v3-turbo`.
- Hallucination suppression: `no_speech_threshold`, `condition_on_previous_text=False`,
  `compression_ratio_threshold`.
- In-person vs remote auto-detect: if the BlackHole channel is silent,
  labels the mic channel `Speaker` instead of `Me` to avoid
  misattribution.
- Four Claude Code slash commands: `/summarize-1on1`, `/summarize-working-group`,
  `/summarize-seminar`, `/summarize-generic`. All auto-file to Notion
  (summary in page body, transcript in a collapsible toggle block).
- `boswell doctor` subcommand for setup diagnostics (BlackHole, Aggregate
  device, Whisper model cache, Claude CLI, slash commands, Notion MCP,
  LaunchAgent).
- Idempotent `install.sh` with `--autostart` and `--uninstall` flags.
- `autostart.sh` LaunchAgent installer (label derived from `$USER`).
- Tests for paths, transcript rendering, and recorder smoke (mocked
  sounddevice stream).

### Known limitations
- Aggregate Device / Multi-Output Device must be created manually in
  Audio MIDI Setup (no stable macOS API).
- Microphone TCC permission must be granted manually on first run.
- Group-call attribution on the BlackHole channel is a mix of all
  remote participants; diarization is deferred to a future release.
