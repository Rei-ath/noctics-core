"""
Tiny .env loader with no external dependencies.

Loads key=value pairs from one or more .env files without overwriting
existing environment variables. Intended for local/dev usage.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def load_dotenv_files(paths: Iterable[Path]) -> None:
    for p in paths:
        try:
            if not p.exists():
                continue
            for line in p.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
        except Exception:
            # Best-effort: ignore malformed lines/files
            continue


def load_local_dotenv(here: Path | None = None) -> None:
    """Load .env from the package folder and current working directory.

    Does not overwrite existing environment variables.
    """
    if here is None:
        here = Path(__file__).resolve().parent
    load_dotenv_files([here / ".env", Path.cwd() / ".env"]) 

