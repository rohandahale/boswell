"""`boswell doctor` — diagnose common setup issues and print a report."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .devices import list_input_devices
from .paths import meetings_root

GREEN = "\033[1;32m"
RED = "\033[1;31m"
YELLOW = "\033[1;33m"
DIM = "\033[2m"
END = "\033[0m"

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    hint: str = ""


def _ok(name: str, detail: str = "") -> Check:
    return Check(name, True, detail)


def _bad(name: str, detail: str, hint: str) -> Check:
    return Check(name, False, detail, hint)


def check_blackhole() -> Check:
    devices = list_input_devices()
    if any("blackhole" in d.name.lower() for d in devices):
        return _ok("BlackHole 2ch installed")
    return _bad(
        "BlackHole 2ch installed",
        "not found in input devices",
        "brew install --cask blackhole-2ch  (then `sudo killall coreaudiod` or reboot)",
    )


def check_aggregate() -> Check:
    hint = os.environ.get("BOSWELL_INPUT_DEVICE", "Boswell").lower()
    # Accept legacy "Notetaker" names for backward compat.
    accepted = {hint, "boswell", "notetaker"}
    matches = [
        d for d in list_input_devices()
        if any(tag in d.name.lower() for tag in accepted) and d.max_input_channels >= 2
    ]
    if matches:
        d = matches[0]
        return _ok(
            "Aggregate device found",
            f"{d.name!r} (index={d.index}, channels={d.max_input_channels})",
        )
    return _bad(
        "Aggregate device found",
        "no multi-channel device whose name contains 'Boswell' (or 'Notetaker')",
        "Audio MIDI Setup → + → Create Aggregate Device (mic + BlackHole). "
        "Rename it to contain 'Boswell'.",
    )


def check_mic_permission() -> Check:
    # macOS TCC doesn't expose mic permission programmatically without private
    # APIs; the honest signal is whether sounddevice can actually open a stream.
    # We don't do that here to avoid triggering the prompt outside a recording
    # context. Just instruct the user how to check.
    return Check(
        "Microphone permission",
        True,  # treat as advisory, not a hard failure
        "(check manually — System Settings → Privacy & Security → Microphone)",
    )


def check_whisper_model() -> Check:
    model = os.environ.get("BOSWELL_WHISPER_MODEL", DEFAULT_MODEL)
    # mlx-whisper uses huggingface_hub cache; any hit under the repo path counts.
    cache = Path.home() / ".cache" / "huggingface" / "hub"
    if not cache.exists():
        return _bad(
            "Whisper model cached",
            f"no HF cache at {cache}",
            f"./install.sh  (pre-pulls {model})",
        )
    repo_dir = "models--" + model.replace("/", "--")
    hit = cache / repo_dir
    if hit.exists():
        return _ok("Whisper model cached", f"{model}")
    return _bad(
        "Whisper model cached",
        f"{model} not in HF cache",
        "boswell will download on first transcription (~1.5 GB).",
    )


def check_notion_mcp() -> Check:
    cfg = Path.home() / ".claude.json"
    if not cfg.exists():
        return _bad(
            "Notion MCP configured",
            "~/.claude.json not found",
            "claude mcp add --transport http --scope user notion https://mcp.notion.com/mcp",
        )
    try:
        content = cfg.read_text()
    except OSError as e:
        return _bad("Notion MCP configured", f"{e}", "check ~/.claude.json perms")
    if '"notion"' in content and "mcp.notion.com" in content:
        return _ok("Notion MCP configured", "entry present in ~/.claude.json")
    return _bad(
        "Notion MCP configured",
        "no Notion entry in ~/.claude.json",
        "claude mcp add --transport http --scope user notion https://mcp.notion.com/mcp",
    )


def check_claude_md() -> Check:
    path = meetings_root() / "CLAUDE.md"
    if not path.exists():
        return _bad(
            "~/Meetings/CLAUDE.md present",
            "missing",
            "./install.sh  (copies the template)",
        )
    text = path.read_text()
    unfilled = text.count("TODO")
    url_ok = "Database URL: TODO" not in text
    if unfilled == 0 and url_ok:
        return _ok("~/Meetings/CLAUDE.md filled in", str(path))
    return Check(
        name="~/Meetings/CLAUDE.md filled in",
        ok=False,
        detail=f"{unfilled} TODOs remain" + ("" if url_ok else " (incl. Notion DB URL)"),
        hint=f"edit {path}",
    )


def check_slash_commands() -> Check:
    cmd_dir = Path.home() / ".claude" / "commands"
    expected = [f"summarize-{t}.md" for t in ("1on1", "working-group", "seminar", "generic")]
    missing = [name for name in expected if not (cmd_dir / name).exists()]
    if not missing:
        return _ok("Slash commands installed", f"{cmd_dir}")
    return _bad(
        "Slash commands installed",
        f"missing: {', '.join(missing)}",
        "./install.sh  (copies slash commands to ~/.claude/commands/)",
    )


def check_launch_agent() -> Check:
    label_candidates = [
        f"com.{os.environ.get('USER', 'user')}.boswell",
        "com.rdahale.notetaker",  # legacy
    ]
    for label in label_candidates:
        plist = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
        if plist.exists():
            return _ok("Auto-launch at login", f"{plist}")
    return Check(
        "Auto-launch at login",
        ok=False,
        detail="no LaunchAgent plist found",
        hint="./autostart.sh install  (optional)",
    )


def _claude_cli_available() -> Check:
    if shutil.which("claude"):
        return _ok("Claude Code CLI on PATH", "claude")
    return _bad(
        "Claude Code CLI on PATH",
        "`claude` not found",
        "install Claude Code from https://docs.claude.com/claude-code",
    )


def run_doctor() -> int:
    checks = [
        check_blackhole(),
        check_aggregate(),
        check_mic_permission(),
        check_whisper_model(),
        _claude_cli_available(),
        check_slash_commands(),
        check_claude_md(),
        check_notion_mcp(),
        check_launch_agent(),
    ]
    width = max(len(c.name) for c in checks) + 2
    fail = 0
    for c in checks:
        mark = f"{GREEN}✓{END}" if c.ok else f"{RED}✗{END}"
        detail = f" {DIM}{c.detail}{END}" if c.detail else ""
        print(f"  {mark} {c.name:<{width}}{detail}")
        if not c.ok:
            fail += 1
            if c.hint:
                print(f"     {YELLOW}→ {c.hint}{END}")
    print()
    if fail == 0:
        print(f"{GREEN}All checks passed.{END}")
        return 0
    print(f"{RED}{fail} issue(s) found.{END} Advisory checks don't block usage.")
    return 1 if any(not c.ok and c.hint for c in checks) else 0
