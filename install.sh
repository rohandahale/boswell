#!/usr/bin/env bash
# Boswell installer. Idempotent — safe to re-run.
#
# Does:
#   - Detects (and offers to install) BlackHole 2ch via Homebrew.
#   - Detects micromamba, creates a `boswell` env if missing.
#   - Installs the boswell package (editable) + deps into that env.
#   - Pre-pulls the Whisper model so first Stop isn't a 5-min surprise.
#   - Copies ~/Meetings/CLAUDE.md (preserves any existing file).
#   - Installs slash commands into ~/.claude/commands/.
#   - Optionally installs the launchd agent (`--autostart`).
#
# Does NOT:
#   - Create the Aggregate Device / Multi-Output Device in Audio MIDI Setup
#     (no stable macOS API). Prints instructions instead.
#   - Grant microphone permission (TCC requires user consent).
#   - Install micromamba itself (prints instructions).
#
# Usage:
#   ./install.sh             # install everything except autostart
#   ./install.sh --autostart # also install the LaunchAgent
#   ./install.sh --uninstall # remove autostart + symlinks (env untouched)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="${BOSWELL_ENV_NAME:-boswell}"
PYTHON_VERSION="3.12"
MEETINGS_DIR="${BOSWELL_MEETINGS_ROOT:-$HOME/Meetings}"
CLAUDE_COMMANDS_DIR="$HOME/.claude/commands"
MODEL="${BOSWELL_WHISPER_MODEL:-mlx-community/whisper-large-v3-turbo}"

# Flags
DO_AUTOSTART=0
DO_UNINSTALL=0
for arg in "$@"; do
  case "$arg" in
    --autostart) DO_AUTOSTART=1 ;;
    --uninstall) DO_UNINSTALL=1 ;;
    --help|-h)
      grep '^# ' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log()   { printf "\033[1;34m[install]\033[0m %s\n" "$*"; }
ok()    { printf "\033[1;32m[install]\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[install]\033[0m %s\n" "$*" >&2; }
fail()  { printf "\033[1;31m[install]\033[0m %s\n" "$*" >&2; exit 1; }

# ── Uninstall path (partial — env left intact) ─────────────────────────────
if [[ "$DO_UNINSTALL" -eq 1 ]]; then
  "$REPO_DIR/autostart.sh" uninstall 2>/dev/null || true
  rm -f "$CLAUDE_COMMANDS_DIR"/summarize-{1on1,working-group,seminar,generic}.md
  ok "Removed slash commands and LaunchAgent. The micromamba env '$ENV_NAME' is untouched; remove manually with 'micromamba env remove -n $ENV_NAME'."
  exit 0
fi

# ── 1. BlackHole 2ch ───────────────────────────────────────────────────────
if system_profiler SPAudioDataType 2>/dev/null | grep -qi "BlackHole 2ch"; then
  ok "BlackHole 2ch already installed."
elif command -v brew >/dev/null 2>&1; then
  log "BlackHole 2ch not detected. Installing via Homebrew (requires sudo for audio-driver install)…"
  brew install --cask blackhole-2ch
  warn "You may need to reboot OR run 'sudo killall coreaudiod' before BlackHole appears."
else
  warn "BlackHole 2ch not found and Homebrew not installed. Install manually:
  brew install --cask blackhole-2ch
or download from https://existential.audio/blackhole/"
fi

# ── 2. micromamba detection ────────────────────────────────────────────────
MICROMAMBA=""
if [[ -n "${MAMBA_EXE:-}" && -x "$MAMBA_EXE" ]]; then
  MICROMAMBA="$MAMBA_EXE"
elif [[ -x "$HOME/.local/bin/micromamba" ]]; then
  MICROMAMBA="$HOME/.local/bin/micromamba"
elif [[ -n "${MAMBA_ROOT_PREFIX:-}" && -x "$MAMBA_ROOT_PREFIX/bin/micromamba" ]]; then
  MICROMAMBA="$MAMBA_ROOT_PREFIX/bin/micromamba"
elif command -v micromamba >/dev/null 2>&1; then
  MICROMAMBA="$(command -v micromamba)"
fi

if [[ -z "$MICROMAMBA" ]]; then
  fail "micromamba binary not found. Install it first:
  'brew install micromamba'  (Homebrew), or
  curl -Ls https://micro.mamba.pm/api/micromamba/osx-arm64/latest | tar -xvj bin/micromamba
then re-run ./install.sh"
fi
log "Using micromamba: $MICROMAMBA"

# ── 3. environment ─────────────────────────────────────────────────────────
if "$MICROMAMBA" env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  log "micromamba env '$ENV_NAME' already exists."
else
  log "Creating micromamba env '$ENV_NAME' (python=$PYTHON_VERSION)…"
  "$MICROMAMBA" create -y -n "$ENV_NAME" -c conda-forge "python=$PYTHON_VERSION" "pip"
fi

MM_RUN=("$MICROMAMBA" run -n "$ENV_NAME")

# ── 4. install package + deps ──────────────────────────────────────────────
log "Installing boswell (editable) and dependencies…"
"${MM_RUN[@]}" pip install --upgrade pip >/dev/null
"${MM_RUN[@]}" pip install -e "$REPO_DIR[dev]"

# ── 5. pre-pull Whisper model ──────────────────────────────────────────────
log "Pre-pulling Whisper model: $MODEL"
if ! "${MM_RUN[@]}" python -c "
import sys
try:
    from huggingface_hub import snapshot_download
except ImportError:
    sys.exit(0)
snapshot_download('$MODEL')
print('ok')
"; then
  warn "Model prefetch failed; it will download on first transcription."
fi

# ── 6. meetings folder + CLAUDE.md ─────────────────────────────────────────
mkdir -p "$MEETINGS_DIR"
if [[ -f "$MEETINGS_DIR/CLAUDE.md" ]]; then
  log "$MEETINGS_DIR/CLAUDE.md already exists — leaving in place."
else
  cp "$REPO_DIR/meetings-CLAUDE.md" "$MEETINGS_DIR/CLAUDE.md"
  ok "Wrote $MEETINGS_DIR/CLAUDE.md (fill in the TODOs before your next meeting)."
fi

# ── 7. slash commands ──────────────────────────────────────────────────────
mkdir -p "$CLAUDE_COMMANDS_DIR"
for f in "$REPO_DIR"/claude-commands/*.md; do
  base="$(basename "$f")"
  dest="$CLAUDE_COMMANDS_DIR/$base"
  if [[ -f "$dest" ]] && ! cmp -s "$f" "$dest"; then
    warn "$dest exists and differs — leaving in place. Diff manually if you want the update."
    continue
  fi
  cp "$f" "$dest"
  ok "Installed slash command: /$(basename "$base" .md)"
done

# ── 8. optional autostart ─────────────────────────────────────────────────
if [[ "$DO_AUTOSTART" -eq 1 ]]; then
  log "Installing LaunchAgent (auto-start at login)…"
  "$REPO_DIR/autostart.sh" install
fi

# ── 9. final instructions ─────────────────────────────────────────────────
cat <<EOF

$(printf "\033[1;32m[install] Done.\033[0m")

Remaining manual steps (macOS can't automate these):
  1. Open Audio MIDI Setup → create an Aggregate Device combining your mic
     and BlackHole 2ch. Rename it so the name contains "Boswell".
  2. Create a Multi-Output Device (speakers + BlackHole). Set Zoom's
     speaker output to it so call audio routes through BlackHole.
  3. On first recording, grant microphone permission when prompted.

Verify the setup:
  $MICROMAMBA run -n $ENV_NAME boswell doctor

Launch the menu bar app:
  $MICROMAMBA run -n $ENV_NAME boswell
EOF
