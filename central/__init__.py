"""
Noctics Central package.

Exports the CLI entry `main` for use by `main.py` and compatibility wrappers.
"""

from .cli import main, parse_args  # noqa: F401

__all__ = ["main", "parse_args"]

