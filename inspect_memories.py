"""CLI helper to explore stored conversation memories.

This script surfaces the sessions captured under ``memory/sessions`` so they
can be inspected without launching the full chat CLI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from central.core import (
    list_sessions,
    load_session_messages,
    resolve_session,
)
from interfaces.session_logger import format_session_display_name

SESSION_ROOT = Path("memory/sessions")


def load_meta(log_path: Path) -> Dict[str, Any]:
    """Load the sidecar meta file if present, otherwise derive minimal info."""
    meta_path = log_path.with_name(log_path.stem + ".meta.json")
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Fallback info
    return {
        "id": log_path.stem,
        "path": str(log_path),
        "display_name": format_session_display_name(log_path.stem),
        "turns": _count_lines(log_path),
    }


def iter_sessions(search: Optional[str] = None) -> Iterable[Dict[str, Any]]:
    """Yield session info, optionally filtering by a search string."""
    needle = (search or "").strip().lower()
    for info in list_sessions(SESSION_ROOT):
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


def print_session_table(items: Iterable[Dict[str, Any]], *, limit: Optional[int] = None) -> None:
    """Pretty print a compact session table."""
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


def show_session(ident: str, *, raw: bool = False) -> int:
    """Display the conversation stored in a session."""
    path = resolve_session(ident, SESSION_ROOT)
    if path is None:
        print(f"No session matches '{ident}'.", file=sys.stderr)
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


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect stored chat memories.")
    parser.add_argument(
        "--search",
        metavar="TEXT",
        help="Filter sessions whose metadata or content contains TEXT.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum sessions to list (default: 20).",
    )
    parser.add_argument(
        "--show",
        metavar="SESSION",
        help="Show the contents of a session by id, stem, or path.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Display only the most recently updated session summary and exit.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw JSON messages when used with --show.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.show:
        return show_session(args.show, raw=args.raw)
    if args.latest:
        latest_list = list_sessions(SESSION_ROOT)
        if not latest_list:
            print("No sessions found.")
            return 0
        print_latest_session(latest_list[0])
        return 0
    items = iter_sessions(args.search)
    print_session_table(items, limit=args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
