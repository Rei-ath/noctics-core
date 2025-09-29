"""Noctics Central core package."""

from .cli import main, parse_args  # noqa: F401
from .version import __version__  # noqa: F401

__all__ = ["main", "parse_args", "__version__"]
