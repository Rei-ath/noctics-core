"""Lightweight CLI entrypoints bundled with the public core package."""

from __future__ import annotations

from .simple import build_parser, main, parse_args

__all__ = ["build_parser", "main", "parse_args"]
