from __future__ import annotations

from typing import Callable, List, Optional
import os
import re

from central.colors import color
from central.core import ChatClient
from interfaces.pii import sanitize as pii_sanitize


def manual_helper_stream(helper_name: Optional[str]) -> str:
    """Collect helper output interactively, echoing as a stream.

    User types/pastes lines; each line is echoed immediately. Typing
    a single END line finishes input. Returns the concatenated text.
    """
    helper_label = f" [{helper_name}]" if helper_name else ""
    print(color(f"Helper{helper_label}:", fg="blue", bold=True) + " ", end="", flush=True)
    print(
        color(
            "(paste streaming lines; type END on its own line to finish)",
            fg="yellow",
        )
    )
    collected: List[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        # Echo the line as part of the stream
        print(line)
        collected.append(line)
    return "\n".join(collected).strip()


def process_helper_result(
    *,
    client: ChatClient,
    helper_text: str,
    stream: bool,
    on_delta: Callable[[str], None],
) -> Optional[str]:
    if not helper_text:
        return None
    if stream:
        print("\n" + color("Noctics Central (processing helper):", fg="#ffefff", bold=True) + " ", end="", flush=True)
        reply = client.process_helper_result(helper_text, on_delta=on_delta)
        print()
        return reply
    else:
        reply = client.process_helper_result(helper_text)
        if reply is not None:
            print(reply)
        return reply


def manual_central_stream(helper_name: Optional[str] = None) -> str:
    """Let the operator act as Central: paste the final stitched response.

    Returns the concatenated text, collected line-by-line until END.
    """
    label = "Act as Central"
    if helper_name:
        label += f" (helper: {helper_name})"
    print(color(f"{label}:", fg="#ffefff", bold=True))
    print(color("(paste final response; type END on its own line to finish)", fg="yellow"))
    buf: List[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        print(line)
        buf.append(line)
    return "\n".join(buf).strip()


# -----------------------------
# Helper query anonymization
# -----------------------------

_HELPER_QUERY_RE = re.compile(r"\[HELPER\s+QUERY\](.*?)\[/HELPER\s+QUERY\]", re.IGNORECASE | re.DOTALL)


def extract_helper_query(text: str) -> Optional[str]:
    """Extract the content of a [HELPER QUERY]...[/HELPER QUERY] block.

    Returns None if no block is present.
    """
    if not text:
        return None
    m = _HELPER_QUERY_RE.search(text)
    if not m:
        return None
    return m.group(1).strip()


def anonymize_for_helper(text: str, *, user_name: Optional[str] = None) -> str:
    """Sanitize a helper query to avoid leaking user identity.

    - Applies PII redaction (emails, phones, cards via Luhn-like, IPv4).
    - Optionally redacts configured names from env `CENTRAL_REDACT_NAMES` (comma-separated).
    - Optionally redacts the interactive prompt label if provided via `user_name`.
    """
    # Base PII sanitization
    out = pii_sanitize(text)

    # Redact interactive label (avoid over-redacting the generic "You")
    label = (user_name or "").strip()
    if label and label.lower() not in {"you", "user"}:
        out = re.sub(re.escape(label), "[REDACTED:NAME]", out, flags=re.IGNORECASE)

    # Redact additional names from env
    extra = os.getenv("CENTRAL_REDACT_NAMES", "")
    for raw in [s.strip() for s in extra.split(",") if s.strip()]:
        out = re.sub(re.escape(raw), "[REDACTED:NAME]", out, flags=re.IGNORECASE)

    return out


def print_sanitized_helper_query(block: str, *, user_name: Optional[str]) -> None:
    """Utility to print a sanitized helper query block for copy/paste."""
    print()
    print(color("Helper Query (sanitized):", fg="blue", bold=True))
    print(color("(copy this to your external helper)", fg="yellow"))
    print(anonymize_for_helper(block, user_name=user_name))


# -----------------------------
# Helper selection utilities
# -----------------------------

def get_helper_candidates() -> List[str]:
    """Return a list of helper names from env or defaults.

    Uses CENTRAL_HELPERS="a,b,c" if set, otherwise a small default list.
    """
    env_helpers = [s.strip() for s in (os.getenv("CENTRAL_HELPERS") or "").split(",") if s.strip()]
    default_helpers = ["claude", "o3", "gpt-4o", "sonnet", "llama", "mistral"]
    return env_helpers or default_helpers


def choose_helper_interactively(current: Optional[str] = None) -> Optional[str]:
    """Prompt the user to choose a helper if none is set.

    - Returns the chosen helper name (or None if skipped).
    - Accepts a number (index) or a free-form name.
    - If stdin is not interactive, returns current unchanged.
    """
    try:
        import sys

        if not sys.stdin.isatty():
            return current
    except Exception:
        return current

    candidates = get_helper_candidates()
    print(color("Choose a helper:", fg="yellow", bold=True))
    print(color("(press Enter to skip; type a number or name)", fg="yellow"))
    for i, h in enumerate(candidates, 1):
        print(f"  {i}. {h}")
    print(color("helper>", fg="blue", bold=True) + " ", end="", flush=True)
    try:
        choice = input().strip()
    except EOFError:
        return current
    if not choice:
        return current
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(candidates):
            return candidates[idx - 1]
        return current
    return choice
