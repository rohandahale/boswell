# Boswell

Local, bot-free meeting notetaker for macOS (Apple Silicon). Captures your
mic + the other party's audio, transcribes on-device with MLX Whisper,
and hands the transcript to interactive Claude Code for summarization
and optional filing to Notion via MCP.

Nothing leaves your machine unless you choose to file a summary to Notion.

## Requirements

- Apple Silicon Mac (M-series), macOS 14+
- [micromamba](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html)
  (or any conda/mamba variant)
- Homebrew (for BlackHole + Python)
- [Claude Code CLI](https://docs.claude.com/claude-code) (for summarization)

## Install

```bash
git clone <repo-url> boswell && cd boswell
./install.sh --autostart
```

`install.sh` is idempotent. It:

- Installs BlackHole 2ch via Homebrew if missing (needs your sudo password)
- Creates a `boswell` micromamba env (Python 3.12) and installs all deps
- Pre-pulls the Whisper model (~1.5 GB) so the first recording is fast
- Copies `meetings-CLAUDE.md` → `~/Meetings/CLAUDE.md` (standing context
  for the summarizer)
- Installs slash commands into `~/.claude/commands/`
- With `--autostart`: installs a LaunchAgent so the menu bar app starts
  on login

After install, verify:

```bash
micromamba run -n boswell boswell doctor
```

### Manual one-time steps (macOS won't let these be scripted)

1. **Audio MIDI Setup → Create Aggregate Device**
   - Check your mic first, then BlackHole 2ch
   - Clock source = your mic; enable Drift Correction on BlackHole
   - **Rename the device so its name contains "Boswell"** (required for
     auto-detection)
2. **Audio MIDI Setup → Create Multi-Output Device**
   - Check your speakers + BlackHole 2ch
   - In Zoom → Settings → Audio, set this as the Speaker
3. **On first recording**, accept the macOS microphone permission prompt

Run `boswell doctor` after each step — it tells you what's still missing.

## Usage

If you installed with `--autostart`, the menu bar is already running. Otherwise:

```bash
micromamba run -n boswell boswell
```

- Click **Start Recording…** — meeting folder is auto-named from the
  current day + time
- Click **Stop Recording** — transcription runs in a detached subprocess;
  you'll get a notification when `transcript.md` is ready

Each recording lives at `~/Meetings/YYYY-MM-DD-HHMM-<slug>/` with:

| File | Content |
|---|---|
| `audio.wav` | Stereo 48 kHz PCM — mic on L, BlackHole on R |
| `transcript.md` | Per-channel Whisper output, sorted by timestamp |
| `metadata.json` | Recording + transcription stats |
| `transcribe.log` | Subprocess log |

## Summarization (Phase 2)

Fill in the TODOs in `~/Meetings/CLAUDE.md` — your bio, collaborators, and
(once set up) the URL of your Notion Meetings database. This is the
standing context the summarizer uses to make summaries useful instead of
generic.

Then, inside any meeting folder:

```bash
cd ~/Meetings/2026-04-20-1422-team-standup
claude
```

In the `claude` session, run one of:

- `/summarize-1on1` — for 1:1 meetings
- `/summarize-working-group` — for multi-person working groups
- `/summarize-seminar` — for talks and lectures
- `/summarize-generic` — when the type is ambiguous (auto-classifies)

Each writes `summary.md` locally and, if the Notion MCP is configured,
adds a new row to your Meetings database with the summary in the page
body and the full transcript inside a collapsible "Full transcript"
toggle.

### Notion MCP (optional)

```bash
claude mcp add --transport http --scope user notion https://mcp.notion.com/mcp
```

Then inside any `claude` session, run `/mcp`, select Notion, and complete
the OAuth flow. Create a "Meetings" database in Notion with properties:

| Property | Type |
|---|---|
| Name | Title |
| Date | Date |
| Type | Select: 1on1, working-group, seminar, interview, other |
| Attendees | Multi-select |
| Action Items | Text |

Paste the database URL into the `## Notion Meetings database` section of
`~/Meetings/CLAUDE.md`. Grant the Claude connection access to the
database (top-right `···` → Connections).

## Configuration (env vars)

| Variable | Default | Purpose |
|---|---|---|
| `BOSWELL_MEETINGS_ROOT` | `~/Meetings` | Where meeting folders are created |
| `BOSWELL_INPUT_DEVICE` | `Boswell` (fallback `Notetaker`) | Substring matched against input device names |
| `BOSWELL_WHISPER_MODEL` | `mlx-community/whisper-large-v3-turbo` | HF repo for the MLX Whisper model |
| `BOSWELL_WHISPER_LANGUAGE` | auto | Force a language code (e.g. `en`) |
| `BOSWELL_ENV_NAME` | `boswell` | micromamba env name (for install + autostart) |

## Architecture

```
[Menu bar (rumps)] ──Start──▶ [Recorder] ──WAV──▶ [Meeting folder]
                                                        │
                                                        ▼
                                               [Transcriber (mlx-whisper)]
                                                        │
                                                        ▼
                                             transcript.md + metadata.json
                                                        │
                                                        ▼
                                   [Interactive Claude Code / Max plan]
                                   cd folder → claude → /summarize-*
                                   → (optional) Notion MCP page
```

- Recording runs in a background thread with a 5 s fsync cadence so a
  crash loses ≤ 5 s of audio
- Transcription is a detached subprocess kicked off on Stop so the menu
  bar stays responsive
- Stereo channel split ("Me"/"Them") falls back to a generic "Speaker"
  label when the BlackHole channel is silent (in-person meetings)

## Troubleshooting

`boswell doctor` diagnoses the common breakages. If it can't help:

- **No input device matching 'Boswell'** — your Aggregate Device isn't
  named correctly. Rename it in Audio MIDI Setup so the name contains
  "Boswell". (Or set `BOSWELL_INPUT_DEVICE` to any substring of your
  preferred device name.)
- **Menu bar icon missing on MacBook Pro** — notch overflow. Hold ⌘ and
  drag icons left/right, or quit another menu bar app to make room.
- **Whisper emits "Thank you"/"test test test…" loops** — near-silent
  audio. Check mic level; we raise the hallucination threshold but very
  quiet channels still slip through.
- **BlackHole doesn't show up after install** — run `sudo killall coreaudiod`
  or reboot (Homebrew installer says the same).

## Development

```bash
micromamba run -n boswell pytest
```

CI runs `pytest` on macOS 14 and 15 for every push and PR. See
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## License

MIT. See [LICENSE](LICENSE).
