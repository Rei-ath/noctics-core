"""Minimal CLI facade retained for backwards compatibility."""

from __future__ import annotations

from .simple import build_parser, main, parse_args

__all__ = ["build_parser", "main", "parse_args"]
