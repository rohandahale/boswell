"""Boswell CLI entrypoint.

Dispatches to subcommands. With no args (or `run`), launches the menu bar.
Other subcommands:
  - doctor: diagnose setup (BlackHole, Aggregate device, mic perms, model).
  - version: print version.
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__


def _run_menubar() -> int:
    from .menubar import main as menubar_main

    menubar_main()
    return 0


def _run_doctor() -> int:
    from .doctor import run_doctor

    return run_doctor()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="boswell",
        description="Local meeting notetaker for macOS.",
    )
    parser.add_argument("--version", action="version", version=f"boswell {__version__}")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("run", help="Launch the menu bar app (default).")
    sub.add_parser("doctor", help="Diagnose setup: BlackHole, Aggregate device, mic perms, model.")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cmd = args.cmd or "run"
    if cmd == "run":
        sys.exit(_run_menubar())
    if cmd == "doctor":
        sys.exit(_run_doctor())
    parser.error(f"unknown subcommand: {cmd}")
