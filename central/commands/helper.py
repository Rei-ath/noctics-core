from __future__ import annotations

import os
import re
from typing import List, Optional

from central.colors import color
from central.config import get_runtime_config
from interfaces.pii import sanitize as pii_sanitize

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
    """Utility to display a sanitized helper query block."""
    print()
    print(color("Helper Query (sanitized):", fg="blue", bold=True))
    print(anonymize_for_helper(block, user_name=user_name))


# -----------------------------
# Helper selection utilities
# -----------------------------

def get_helper_candidates() -> List[str]:
    """Return a list of helper names from env, config, or defaults."""

    env_helpers = [s.strip() for s in (os.getenv("CENTRAL_HELPERS") or "").split(",") if s.strip()]
    if env_helpers:
        return env_helpers

    config_helpers = get_runtime_config().helper.roster
    if config_helpers:
        return config_helpers

    # Popular LLM/provider names as convenient defaults; override via env/config
    return [
        "claude",      # Anthropic
        "gpt-4o",      # OpenAI
        "gpt-4",       # OpenAI
        "grok",        # xAI
        "gemini",      # Google
        "llama",       # Meta
        "mistral",     # Mistral AI
        "cohere",      # Cohere
        "deepseek",    # DeepSeek
    ]


def helper_automation_enabled() -> bool:
    """Return True if automatic helper stitching is available."""

    value = os.getenv("CENTRAL_HELPER_AUTOMATION", "").strip()
    if value:
        return value.lower() in {"1", "true", "on", "yes"}
    return get_runtime_config().helper.automation


def describe_helper_status() -> str:
    """Return a concise description of helper availability."""

    helpers = get_helper_candidates()
    roster = ", ".join(helpers) if helpers else "none configured"
    if helper_automation_enabled():
        return f"Automation enabled. Available helpers: {roster}."
    return (
        "Automation disabled. Available helper labels: "
        f"{roster}. Install the full Noctics suite (with the router service) to enable automatic helper routing."
    )


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
