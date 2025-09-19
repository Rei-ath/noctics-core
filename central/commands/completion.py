from __future__ import annotations

import os
from typing import List, Optional

try:
    import readline  # type: ignore
except Exception:  # pragma: no cover
    readline = None  # type: ignore

from central.core import list_sessions


def setup_completions() -> None:
    if readline is None:
        return
    try:
        import sys

        if not sys.stdin.isatty():
            return
    except Exception:
        return

    commands = [
        "/help",
        "/reset",
        "/sessions",
        "/ls",
        "/last",
        "/result",
        "/helper",
        "/anon",
        "/anon-helper",
        "/load",
        "/title",
        "/rename",
        "/merge",
        "/name",
    ]

    env_helpers = [s.strip() for s in (os.getenv("CENTRAL_HELPERS") or "").split(",") if s.strip()]
    default_helpers = ["claude", "o3", "gpt-4o", "sonnet", "llama", "mistral"]
    helper_candidates = env_helpers or default_helpers

    def session_suggestions() -> List[str]:
        items = list_sessions()
        out: List[str] = []
        out.extend([str(i) for i in range(1, len(items) + 1)])
        out.extend([it.get("id") for it in items if it.get("id")])
        return [s for s in out if s]

    def complete(text: str, state: int) -> Optional[str]:
        try:
            line = readline.get_line_buffer()  # type: ignore[attr-defined]
            beg = readline.get_begidx()  # type: ignore[attr-defined]
        except Exception:
            line, beg = "", 0

        if not line or line.startswith("/") and (" " not in line[:beg]):
            matches = [c for c in commands if c.startswith(text or "")]
            return matches[state] if state < len(matches) else None

        head = line.split(" ", 1)[0]
        arg_region = line[len(head):]
        arg_text = arg_region.lstrip()
        arg_index = 0 if not arg_text or arg_text.endswith(" ") else len(arg_text.split()) - 1

        if head == "/helper":
            if beg >= len(head) + 1:
                matches = [h for h in helper_candidates if h.startswith(text or "")]
                return matches[state] if state < len(matches) else None
            return None

        if head in {"/load", "/rename", "/merge"}:
            if beg >= len(head) + 1 and arg_index == 0:
                candidates = session_suggestions()
                matches = [c for c in candidates if c.startswith(text or "")]
                return matches[state] if state < len(matches) else None
            return None

        return None

    try:
        readline.parse_and_bind("tab: complete")  # type: ignore[attr-defined]
        readline.set_completer(complete)  # type: ignore[attr-defined]
    except Exception:
        pass
