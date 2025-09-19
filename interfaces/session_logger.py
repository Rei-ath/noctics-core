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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def format_session_display_name(session_id: str) -> str:
    """Return a human-friendly label for a session file stem.

    Examples:
        session-20250913-123456 -> "Session 2025-09-13 12:34:56 UTC"
        session-merged-20250913-123456 -> "Merged session 2025-09-13 12:34:56 UTC"
    Fallback: replace dashes with spaces and title-case the id.
    """
    base = session_id or ""
    prefixes = [
        ("session-merged-", "Merged session"),
        ("session-", "Session"),
    ]
    for prefix, label in prefixes:
        if base.startswith(prefix):
            suffix = base[len(prefix):]
            try:
                dt = datetime.strptime(suffix, "%Y%m%d-%H%M%S")
            except ValueError:
                break
            return f"{label} {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC"
    # Fallback formatting
    pretty = base.replace("-", " ").strip()
    return pretty.title() if pretty else "Session"


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
    _display_name: Optional[str] = None
    _records: List[Dict[str, Any]] = field(default_factory=list, init=False)

    def start(self) -> None:
        # Create a date-based subfolder (UTC) for sessions, e.g.,
        # memory/sessions/2025-09-13/session-20250913-123456.json
        base = self.dirpath
        now_utc = datetime.now(timezone.utc)
        date_folder = now_utc.date().isoformat()  # YYYY-MM-DD
        dated_dir = base / date_folder
        dated_dir.mkdir(parents=True, exist_ok=True)

        ts = now_utc.strftime("%Y%m%d-%H%M%S")
        self._file = dated_dir / f"session-{ts}.json"
        self._display_name = format_session_display_name(self._file.stem)
        self._records = []
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._records = data
            except Exception:
                self._records = []
        else:
            self._file.write_text("[]", encoding="utf-8")

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
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "file_name": self._file.name if self._file else None,
                "display_name": self._display_name,
            },
        }
        self._records.append(rec)
        if self._file is not None:
            self._file.write_text(
                json.dumps(self._records, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
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
                existing_title = data.get("title")
                existing_custom = bool(data.get("custom", False))
                if self._title is None:
                    self._title = existing_title
                    self._title_custom = existing_custom
                elif not self._title_custom and self._title == existing_title:
                    self._title_custom = existing_custom
                if self._display_name is None:
                    self._display_name = data.get("display_name")
            except Exception:
                created_iso = None
        now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
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
            "file_name": self._file.name if self._file else None,
            "display_name": self._display_name or format_session_display_name(self._file.stem),
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
            "file_name": self._file.name if self._file else None,
            "display_name": self._display_name if self._display_name else (format_session_display_name(self._file.stem) if self._file else None),
        }

    def meta_path(self) -> Optional[Path]:
        return self._meta_file

    def log_path(self) -> Optional[Path]:
        return self._file
