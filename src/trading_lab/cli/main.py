"""Typer/CLI entrypoint (minimal Stage 1 harness)."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Construct the root CLI parser."""
    parser = argparse.ArgumentParser(prog="trading-lab")
    parser.add_argument("--version", action="version", version="trading-lab 0.1.0")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments."""
    parser = build_parser()
    parser.parse_args(argv)


if __name__ == "__main__":
    main()
