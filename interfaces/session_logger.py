"""
Minimal session logger for fine-tuning data capture.

Writes one JSONL file per session under memory/sessions/ with
each turn captured as an example in the shape:

  {"messages": [{"role": "system"|"user"|"assistant", "content": "..."}, ...],
   "meta": {"model": "...", "sanitized": true/false, "turn": N, "ts": "ISO"}}

No external dependencies, append-only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SessionLogger:
    model: str
    sanitized: bool
    dirpath: Path = Path("memory/sessions")
    _file: Optional[Path] = None
    _turn: int = 0

    def start(self) -> None:
        # Create a date-based subfolder (UTC) for sessions, e.g.,
        # memory/sessions/2025-09-13/session-20250913-123456.jsonl
        base = self.dirpath
        date_folder = datetime.utcnow().date().isoformat()  # YYYY-MM-DD
        dated_dir = base / date_folder
        dated_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        self._file = dated_dir / f"session-{ts}.jsonl"

    def log_turn(self, messages: List[Dict[str, Any]]) -> None:
        if self._file is None:
            self.start()
        self._turn += 1
        rec = {
            "messages": messages,
            "meta": {
                "model": self.model,
                "sanitized": bool(self.sanitized),
                "turn": self._turn,
                "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            },
        }
        with self._file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
