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
    _meta_file: Optional[Path] = None
    _turn: int = 0
    _title: Optional[str] = None
    _title_custom: bool = False

    def start(self) -> None:
        # Create a date-based subfolder (UTC) for sessions, e.g.,
        # memory/sessions/2025-09-13/session-20250913-123456.jsonl
        base = self.dirpath
        date_folder = datetime.utcnow().date().isoformat()  # YYYY-MM-DD
        dated_dir = base / date_folder
        dated_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        self._file = dated_dir / f"session-{ts}.jsonl"
        # Touch the file so the session is visible immediately even before first turn
        self._file.touch(exist_ok=True)
        # Create/initialize sidecar meta file
        self._meta_file = self._file.with_name(self._file.stem + ".meta.json")
        self._write_meta(initial=True)

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
        self._write_meta()

    # -----------------
    # Meta sidecar utils
    # -----------------
    def _write_meta(self, initial: bool = False) -> None:
        if self._file is None:
            return
        if self._meta_file is None:
            self._meta_file = self._file.with_name(self._file.stem + ".meta.json")
        created_iso: Optional[str] = None
        if self._meta_file.exists() and not initial:
            try:
                data = json.loads(self._meta_file.read_text(encoding="utf-8"))
                created_iso = data.get("created")
                # Preserve title/custom if already set
                if self._title is None:
                    self._title = data.get("title")
                self._title_custom = bool(data.get("custom", False))
            except Exception:
                created_iso = None
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        meta = {
            "id": self._file.stem,
            "path": str(self._file),
            "model": self.model,
            "sanitized": bool(self.sanitized),
            "turns": self._turn,
            "created": created_iso or now,
            "updated": now,
            "title": self._title,
            "custom": bool(self._title_custom),
        }
        self._meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def set_title(self, title: str, *, custom: bool = True) -> None:
        self._title = title.strip() if title else None
        self._title_custom = bool(custom)
        self._write_meta()

    def get_title(self) -> Optional[str]:
        return self._title

    def get_meta(self) -> Dict[str, Any]:
        if self._meta_file and self._meta_file.exists():
            try:
                return json.loads(self._meta_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        # Fallback
        return {
            "id": self._file.stem if self._file else None,
            "path": str(self._file) if self._file else None,
            "model": self.model,
            "sanitized": bool(self.sanitized),
            "turns": self._turn,
            "title": self._title,
            "custom": bool(self._title_custom),
        }

    def meta_path(self) -> Optional[Path]:
        return self._meta_file
    
    def log_path(self) -> Optional[Path]:
        return self._file
