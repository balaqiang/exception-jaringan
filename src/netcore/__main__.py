"""CLI entry point: ``python -m netcore``."""

from __future__ import annotations

import argparse
import sys

from netcore import __version__
from netcore.bootstrap import build_container
from netcore.tui.app import RichLiveApp, render_to_text


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(prog="netcore", description="NetCore TUI")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    parser.add_argument("--db", default=None, help="SQLite database path")
    parser.add_argument(
        "--seed",
        choices=("two-router", "spine-leaf", "none"),
        default="two-router",
        help="sample lab to seed when the database is empty",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="render one frame to stdout and exit (headless)",
    )
    parser.add_argument("--width", type=int, default=120)
    parser.add_argument("--height", type=int, default=36)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the application."""
    args = build_parser().parse_args(argv)
    if args.version:
        print(f"netcore {__version__}")
        return 0
    container = build_container(
        args.db, seed_lab=None if args.seed == "none" else args.seed
    )
    app = RichLiveApp(container.services, container.watcher, container.reader)
    try:
        if args.render or not sys.stdin.isatty():
            render_to_text(app, args.width, args.height)
            return 0
        app.run()
        return 0
    finally:
        closer = getattr(container.reader, "close", None)
        if closer is not None:
            closer()


if __name__ == "__main__":
    raise SystemExit(main())
