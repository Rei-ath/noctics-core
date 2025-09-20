"""Importable session helpers and CLI utilities for the Noxl toolkit."""

from __future__ import annotations

import json
import argparse
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

from .sessions import (
    ARCHIVE_ROOT,
    SESSION_ROOT,
    archive_early_sessions,
    compute_title_from_messages,
    list_sessions,
    load_session_messages,
    merge_sessions_paths,
    resolve_session,
    set_session_title_for,
)
from interfaces.session_logger import format_session_display_name


def load_meta(log_path: Path) -> Dict[str, Any]:
    """Load meta sidecar data or synthesize a minimal metadata dict."""
    meta_path = log_path.with_name(log_path.stem + ".meta.json")
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "id": log_path.stem,
        "path": str(log_path),
        "display_name": format_session_display_name(log_path.stem),
        "turns": _count_lines(log_path),
    }


def list_session_infos(root: Path = SESSION_ROOT) -> List[Dict[str, Any]]:
    """Return session metadata dictionaries sorted newest first."""
    return list_sessions(root)


def iter_sessions(
    search: Optional[str] = None, *, root: Path = SESSION_ROOT
) -> Iterator[Dict[str, Any]]:
    """Yield session dictionaries from ``root``, optionally filtered by content."""
    needle = (search or "").strip().lower()
    for info in list_sessions(root):
        if not needle:
            yield info
            continue
        if any(
            needle in str(info.get(key, "")).lower()
            for key in ("id", "title", "display_name")
        ):
            yield info
            continue
        path_str = info.get("path")
        if not path_str:
            continue
        try:
            with Path(path_str).open("r", encoding="utf-8") as handle:
                for line in handle:
                    if needle in line.lower():
                        yield info
                        break
        except FileNotFoundError:
            continue


def print_session_table(
    items: Iterable[Dict[str, Any]], *, limit: Optional[int] = None
) -> None:
    """Pretty-print a compact table of session metadata."""
    count = 0
    for idx, info in enumerate(items, 1):
        if limit is not None and count >= limit:
            break
        count += 1
        ident = info.get("id", "?")
        display = info.get("display_name") or format_session_display_name(str(ident))
        turns = info.get("turns", "?")
        title = info.get("title") or "(untitled)"
        updated = info.get("updated") or "?"
        print(f"{idx:>3}. {display}  turns:{turns:<3}  updated:{updated}  title:{title}")
    if count == 0:
        print("No sessions found.")


def print_latest_session(info: Dict[str, Any]) -> None:
    """Print a summary of the latest session entry."""
    display = info.get("display_name") or format_session_display_name(str(info.get("id")))
    title = info.get("title") or "(untitled)"
    updated = info.get("updated") or "?"
    turns = info.get("turns") or "?"
    print(f"Most recent session: {display}")
    print(f"  id: {info.get('id')}")
    print(f"  title: {title}")
    print(f"  turns: {turns}")
    print(f"  updated: {updated}")
    print(f"  path: {info.get('path')}")


def show_session(
    ident: str, *, raw: bool = False, root: Path = SESSION_ROOT
) -> int:
    """Display a session conversation resolved within ``root``."""
    path = resolve_session(ident, root)
    if path is None:
        print(f"No session matches '{ident}'.")
        return 1
    messages = load_session_messages(path)
    if not messages:
        print(f"Session '{path.stem}' is empty or unreadable.")
        return 0
    meta = load_meta(path)
    print(f"== {meta.get('display_name', path.stem)} ==")
    if meta.get("title"):
        print(f"Title: {meta['title']}")
    print(f"Model: {meta.get('model', '?')}  Turns: {meta.get('turns', len(messages)//2)}")
    print("-")
    if raw:
        for msg in messages:
            print(json.dumps(msg, ensure_ascii=False))
        return 0
    for msg in messages:
        role = msg.get("role", "?").upper()
        content = str(msg.get("content", "")).rstrip()
        header = f"{role:>10}:"
        print(header, content)
        print()
    return 0


def _count_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for _ in handle)
    except FileNotFoundError:
        return 0


__all__ = [
    "ARCHIVE_ROOT",
    "SESSION_ROOT",
    "archive_early_sessions",
    "compute_title_from_messages",
    "iter_sessions",
    "list_session_infos",
    "list_sessions",
    "load_meta",
    "load_session_messages",
    "merge_sessions_paths",
    "cli_build_parser",
    "cli_main",
    "cli_parse_args",
    "print_latest_session",
    "print_session_table",
    "resolve_session",
    "set_session_title_for",
    "show_session",
]


def cli_build_parser(prog: str = "noxl") -> argparse.ArgumentParser:
    """Return the argparse parser used by the Noxl CLI."""

    from .cli import build_parser as _build_parser

    return _build_parser(prog=prog)


def cli_parse_args(argv: Optional[List[str]] = None, *, prog: str = "noxl") -> argparse.Namespace:
    """Parse command-line arguments using the CLI parser."""

    from .cli import parse_args as _parse_args

    return _parse_args(argv, prog=prog)


def cli_main(argv: Optional[List[str]] = None) -> int:
    """Run the Noxl CLI programmatically."""

    from .cli import main as _main

    return _main(argv)
