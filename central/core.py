"""
Core chat client utilities for Noctics Central.

This module exposes importable functionality without CLI-specific I/O.
It provides a ChatClient that manages messages, performs API calls,
handles streaming via a callback, detects helper requests, and logs
turns using interfaces.session_logger.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from interfaces.pii import sanitize as pii_sanitize
from interfaces.session_logger import SessionLogger, format_session_display_name
from interfaces.dotenv import load_local_dotenv


DEFAULT_URL = "http://localhost:1234/v1/chat/completions"


def build_payload(
    *,
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float,
    max_tokens: int,
    stream: bool,
) -> Dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }


class ChatClient:
    """Stateful chat client for Central.

    - Manages message history.
    - Performs streaming and non-streaming API requests.
    - Detects helper requests emitted by Central.
    - Logs turns for fine-tuning.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        model: str = os.getenv("CENTRAL_LLM_MODEL", "qwen/qwen3-1.7b"),
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = -1,
        stream: bool = False,
        sanitize: bool = False,
        messages: Optional[List[Dict[str, Any]]] = None,
        enable_logging: bool = True,
    ) -> None:
        # Ensure .env is loaded when core is used as a library
        try:
            load_local_dotenv(Path(__file__).resolve().parent)
        except Exception:
            pass
        self.url = url or os.getenv("CENTRAL_LLM_URL", DEFAULT_URL)
        self.model = model
        self.api_key = api_key or (os.getenv("CENTRAL_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"))
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.stream = stream
        self.sanitize = sanitize
        self.messages: List[Dict[str, Any]] = list(messages or [])
        self.logger = SessionLogger(model=self.model, sanitized=bool(self.sanitize)) if enable_logging else None
        if self.logger:
            self.logger.start()

    # ---------------------
    # Message/state helpers
    # ---------------------
    def reset_messages(self, system: Optional[str] = None) -> None:
        self.messages = []
        if system:
            self.messages.append({"role": "system", "content": system})

    def set_messages(self, messages: List[Dict[str, Any]]) -> None:
        self.messages = list(messages)

    # ---------------------
    # Session title helpers
    # ---------------------
    def get_session_title(self) -> Optional[str]:
        if not self.logger:
            return None
        meta = self.logger.get_meta()
        return meta.get("title")

    def set_session_title(self, title: str, *, custom: bool = True) -> None:
        if not self.logger:
            return
        self.logger.set_title(title, custom=custom)

    def ensure_auto_title(self) -> Optional[str]:
        """Ensure a session title exists; compute and set one if absent.

        Returns the resulting title or None if not available.
        """
        if not self.logger:
            return None
        meta = self.logger.get_meta()
        if meta.get("title") and meta.get("custom"):
            return meta.get("title")
        # Compute from messages (first non-helper user content)
        title = compute_title_from_messages(self.messages) or meta.get("title")
        if title:
            self.logger.set_title(title, custom=False)
        return title

    # ----------------------
    # Helper-related helpers
    # ----------------------
    @staticmethod
    def wants_helper(text: Optional[str]) -> bool:
        if not text:
            return False
        s = text.lower()
        if "[helper query]" in s:
            return True
        if "requires a helper" in s and "paste a helper response" in s:
            return True
        return False

    # --------------------
    # Network interactions
    # --------------------
    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _request_non_streaming(self, req: Request) -> Tuple[Optional[str], Dict[str, Any]]:
        with urlopen(req) as resp:  # nosec - local/dev usage
            charset = resp.headers.get_content_charset() or "utf-8"
            body = resp.read().decode(charset)
        obj = json.loads(body)
        try:
            text = obj["choices"][0]["message"].get("content")
        except Exception:
            text = None
        return text, obj

    def _stream_sse(self, req: Request, on_delta: Optional[Callable[[str], None]] = None) -> str:
        with urlopen(req) as resp:  # nosec - local/dev usage
            charset = resp.headers.get_content_charset() or "utf-8"
            buffer: List[str] = []
            acc: List[str] = []
            while True:
                line_bytes = resp.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode(charset, errors="replace").rstrip("\r\n")

                if not line:
                    if not buffer:
                        continue
                    data_str = "\n".join(buffer).strip()
                    buffer.clear()
                    if not data_str:
                        continue
                    if data_str == "[DONE]":
                        break
                    try:
                        evt = json.loads(data_str)
                    except Exception:
                        piece = data_str
                    else:
                        try:
                            choice = (evt.get("choices") or [{}])[0]
                            delta = choice.get("delta") or {}
                            piece = delta.get("content")
                            if piece is None:
                                piece = (choice.get("message") or {}).get("content")
                            if piece is None:
                                piece = choice.get("text")
                        except Exception:
                            piece = None

                    if piece:
                        if on_delta:
                            on_delta(piece)
                        acc.append(piece)
                    continue

                if line.startswith(":"):
                    continue
                if line.startswith("data:"):
                    buffer.append(line[len("data:"):].lstrip())
                    continue
                continue

        return "".join(acc)

    # -------------
    # Public API
    # -------------
    def one_turn(
        self,
        user_text: str,
        *,
        on_delta: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        to_send_user = pii_sanitize(user_text) if self.sanitize else user_text
        turn_messages = self.messages + [{"role": "user", "content": to_send_user}]
        payload = build_payload(
            model=self.model,
            messages=turn_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=bool(self.stream),
        )
        data = json.dumps(payload).encode("utf-8")
        req = Request(self.url, data=data, headers=self._headers(), method="POST")

        if self.stream:
            assistant = self._stream_sse(req, on_delta)
        else:
            assistant, _ = self._request_non_streaming(req)

        # Output/log and retain state
        if assistant is not None:
            self.messages.append({"role": "user", "content": to_send_user})
            self.messages.append({"role": "assistant", "content": assistant})
            if self.logger:
                sys_msgs = [m for m in self.messages if m.get("role") == "system"]
                to_log = (sys_msgs[-1:] if sys_msgs else []) + [
                    {"role": "user", "content": to_send_user},
                    {"role": "assistant", "content": assistant},
                ]
                self.logger.log_turn(to_log)
        return assistant

    def record_turn(self, user_text: str, assistant_text: str) -> None:
        """Record a manual assistant response without calling the API."""
        to_send_user = pii_sanitize(user_text) if self.sanitize else user_text
        self.messages.append({"role": "user", "content": to_send_user})
        self.messages.append({"role": "assistant", "content": assistant_text})
        if self.logger:
            sys_msgs = [m for m in self.messages if m.get("role") == "system"]
            to_log = (sys_msgs[-1:] if sys_msgs else []) + [
                {"role": "user", "content": to_send_user},
                {"role": "assistant", "content": assistant_text},
            ]
            self.logger.log_turn(to_log)

    def process_helper_result(
        self,
        helper_text: str,
        *,
        on_delta: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        if not helper_text:
            return None
        helper_wrapped = f"[HELPER RESULT]\n{helper_text}\n[/HELPER RESULT]"
        helper_messages = self.messages + [{"role": "user", "content": helper_wrapped}]
        payload = build_payload(
            model=self.model,
            messages=helper_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=bool(self.stream),
        )
        data = json.dumps(payload).encode("utf-8")
        req = Request(self.url, data=data, headers=self._headers(), method="POST")

        if self.stream:
            reply = self._stream_sse(req, on_delta)
        else:
            reply, _ = self._request_non_streaming(req)

        if reply is not None:
            self.messages.append({"role": "user", "content": helper_wrapped})
            self.messages.append({"role": "assistant", "content": reply})
            if self.logger:
                sys_msgs = [m for m in self.messages if m.get("role") == "system"]
                to_log2 = (sys_msgs[-1:] if sys_msgs else []) + [
                    {"role": "user", "content": helper_wrapped},
                    {"role": "assistant", "content": reply},
                ]
                self.logger.log_turn(to_log2)
        return reply

    # -----------------
    # Diagnostics / info
    # -----------------
    def log_path(self) -> Optional[Path]:
        """Return the current session log file path, if logging is enabled."""
        if not self.logger:
            return None
        return self.logger._file

    def maybe_delete_empty_session(self) -> bool:
        if not self.logger:
            return False
        path = self.logger.log_path()
        if not path or not path.exists():
            return False
        meta_path = self.logger.meta_path()
        try:
            if meta_path and meta_path.exists():
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                if data.get("turns"):
                    return False
            if path.suffix == ".json":
                try:
                    records = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    records = []
                for obj in records or []:
                    msgs = obj.get("messages") if isinstance(obj, dict) else None
                    if not msgs:
                        continue
                    has_user = any(m.get("role") == "user" for m in msgs)
                    has_asst = any(m.get("role") == "assistant" for m in msgs)
                    if has_user or has_asst:
                        return False
            else:
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except Exception:
                            obj = None
                        if obj and obj.get("messages"):
                            msgs = obj["messages"]
                            has_user = any(m.get("role") == "user" for m in msgs)
                            has_asst = any(m.get("role") == "assistant" for m in msgs)
                            if has_user or has_asst:
                                return False
        except FileNotFoundError:
            return False

        path.unlink(missing_ok=True)
        if meta_path:
            meta_path.unlink(missing_ok=True)
        try:
            parent = path.parent
            parent.rmdir()
        except OSError:
            pass
        return True

    def append_session_to_day_log(self) -> Optional[Path]:
        if not self.logger:
            return None
        log_path = self.logger.log_path()
        if not log_path or not log_path.exists():
            return None
        try:
            records = json.loads(log_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(records, list) or not records:
            return None

        meta = self.logger.get_meta()
        day_dir = log_path.parent
        day_log = day_dir / "day.json"
        try:
            if day_log.exists():
                day_data = json.loads(day_log.read_text(encoding="utf-8"))
                if not isinstance(day_data, list):
                    day_data = []
            else:
                day_data = []
        except Exception:
            day_data = []

        session_id = log_path.stem
        day_data = [entry for entry in day_data if entry.get("id") != session_id]
        day_data.append(
            {
                "id": session_id,
                "title": meta.get("title"),
                "custom": meta.get("custom"),
                "path": str(log_path),
                "records": records,
                "meta": meta,
            }
        )
        day_log.write_text(json.dumps(day_data, ensure_ascii=False, indent=2), encoding="utf-8")
        return day_log


# ------------------------------
# Session management utilities
# ------------------------------

def compute_title_from_messages(messages: List[Dict[str, Any]]) -> Optional[str]:
    """Derive a short session title from the first meaningful user message."""
    def normalize(s: str) -> str:
        s = (s or "").strip().replace("\n", " ")
        s = s.replace("  ", " ")
        return s

    first_user = None
    for m in messages:
        if m.get("role") == "user":
            content = str(m.get("content") or "")
            # Skip helper result wraps
            if content.strip().startswith("[HELPER RESULT]"):
                continue
            first_user = content
            break
    title_src = normalize(first_user or "")
    if not title_src:
        return None
    # Trim to ~8 words
    words = title_src.split()
    short = " ".join(words[:8])
    return short[:80]


def _meta_path_for(log_path: Path) -> Path:
    return log_path.with_name(log_path.stem + ".meta.json")


def _session_files_for_day(day_dir: Path) -> Dict[str, Path]:
    files: Dict[str, Path] = {}
    for pattern in ("session-*.jsonl", "session-*.json"):
        for log_path in sorted(day_dir.glob(pattern), reverse=True):
            if log_path.name.endswith(".meta.json"):
                continue
            files.setdefault(log_path.stem, log_path)
    return files


def list_sessions(root: Path = Path("memory/sessions")) -> List[Dict[str, Any]]:
    """Return a list of session infos sorted by updated desc.

    Each item: {id, path, title, custom, turns, created, updated, file_name, display_name}
    """
    items: List[Dict[str, Any]] = []
    if not root.exists():
        return items
    for day_dir in sorted(root.iterdir() if root.is_dir() else [], reverse=True):
        if not day_dir.is_dir():
            continue
        file_map = _session_files_for_day(day_dir)
        for log_path in file_map.values():
            meta_path = _meta_path_for(log_path)
            info: Dict[str, Any]
            if meta_path.exists():
                try:
                    info = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    info = {}
                info.setdefault("id", log_path.stem)
                info.setdefault("path", str(log_path))
                if log_path.suffix == ".json":
                    try:
                        data = json.loads(log_path.read_text(encoding="utf-8"))
                        info.setdefault("turns", len(data))
                    except Exception:
                        info.setdefault("turns", 0)
                else:
                    info.setdefault("turns", sum(1 for _ in log_path.open("r", encoding="utf-8")))
                info.setdefault("file_name", log_path.name)
                info.setdefault("display_name", format_session_display_name(log_path.stem))
            else:
                # Fallback without meta
                # Quick turn count (lines)
                turns = 0
                if log_path.suffix == ".json":
                    try:
                        turns = len(json.loads(log_path.read_text(encoding="utf-8")))
                    except Exception:
                        turns = 0
                else:
                    try:
                        with log_path.open("r", encoding="utf-8") as f:
                            for _ in f:
                                turns += 1
                    except Exception:
                        turns = 0
                # Title from first record's user
                title = None
                try:
                    if log_path.suffix == ".json":
                        data = json.loads(log_path.read_text(encoding="utf-8"))
                        first = data[0] if isinstance(data, list) and data else None
                        msgs = first.get("messages") if isinstance(first, dict) else []
                        title = compute_title_from_messages(msgs or [])
                    else:
                        first_line = log_path.open("r", encoding="utf-8").readline()
                        if first_line:
                            obj = json.loads(first_line)
                            msgs = obj.get("messages") or []
                            title = compute_title_from_messages(msgs)
                except Exception:
                    title = None
                stat = log_path.stat()
                info = {
                    "id": log_path.stem,
                    "path": str(log_path),
                    "turns": turns,
                    "title": title,
                    "custom": False,
                    "created": None,
                    "updated": None,
                    "file_name": log_path.name,
                    "display_name": format_session_display_name(log_path.stem),
                }
            items.append(info)
    # Sort by updated desc (fallback by path mtime)
    def _key(i: Dict[str, Any]) -> float:
        up = i.get("updated")
        if isinstance(up, str) and up:
            try:
                # Strip trailing 'Z' and parse
                ts = datetime.fromisoformat(up.rstrip("Z")).timestamp()
                return ts
            except Exception:
                pass
        try:
            return Path(i["path"]).stat().st_mtime
        except Exception:
            return 0.0
    items.sort(key=_key, reverse=True)
    return items


def resolve_session(identifier: str, root: Path = Path("memory/sessions")) -> Optional[Path]:
    """Resolve a session by path or id (stem)."""
    p = Path(identifier)
    if p.exists():
        return p
    # Search by stem across all day dirs
    for day_dir in root.iterdir() if root.exists() else []:
        if not day_dir.is_dir():
            continue
        for log_path in day_dir.glob("session-*.jsonl"):
            if log_path.stem == identifier or log_path.stem.endswith(identifier):
                return log_path
    return None


def load_session_messages(log_path: Path) -> List[Dict[str, Any]]:
    """Reconstruct a conversation message list from a session JSONL."""
    messages: List[Dict[str, Any]] = []
    system_set = False
    try:
        if log_path.suffix == ".json":
            try:
                data = json.loads(log_path.read_text(encoding="utf-8"))
            except Exception:
                return []
            records = data if isinstance(data, list) else []
        else:
            records = []
            with log_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    records.append(obj)

        for obj in records:
            turn_msgs = obj.get("messages") or []
            if not system_set:
                for m in turn_msgs:
                    if m.get("role") == "system":
                        messages.append(m)
                        system_set = True
                        break
            pair = [m for m in turn_msgs if m.get("role") in {"user", "assistant"}]
            if pair:
                messages.extend(pair)
    except FileNotFoundError:
        pass
    return messages


def _group_user_assistant_pairs(messages: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    pairs: List[List[Dict[str, Any]]] = []
    current_user: Optional[Dict[str, Any]] = None
    for m in messages:
        role = m.get("role")
        if role == "system":
            continue
        if role == "user":
            current_user = m
        elif role == "assistant" and current_user is not None:
            pairs.append([current_user, m])
            current_user = None
    return pairs


def merge_sessions_paths(paths: List[Path], *, title: Optional[str] = None, root: Path = Path("memory/sessions")) -> Path:
    """Merge multiple session logs into a new session JSONL under merged-<date>/.

    - Concatenates conversations in the provided order.
    - Writes a standard session JSONL (one record per user/assistant pair).
    - Adds a meta sidecar with merged title and counts.
    Returns the path to the merged JSONL file.
    """
    # Collect combined messages
    combined: List[Dict[str, Any]] = []
    system_set = False
    source_ids: List[str] = []
    for p in paths:
        source_ids.append(p.stem)
        msgs = load_session_messages(p)
        if not msgs:
            continue
        # Add the first system only once
        if not system_set:
            for m in msgs:
                if m.get("role") == "system":
                    combined.append(m)
                    system_set = True
                    break
        # Append user/assistant pairs from this session
        for m in msgs:
            if m.get("role") in {"user", "assistant"}:
                combined.append(m)

    # Prepare output directory and filenames
    now_utc = datetime.now(timezone.utc)
    date_dir = root / ("merged-" + now_utc.date().isoformat())
    date_dir.mkdir(parents=True, exist_ok=True)
    ts = now_utc.strftime("%Y%m%d-%H%M%S")
    out_log = date_dir / f"session-merged-{ts}.json"
    out_meta = out_log.with_name(out_log.stem + ".meta.json")

    # Build records (one per user/assistant pair)
    sys_msg = next((m for m in combined if m.get("role") == "system"), None)
    pairs = _group_user_assistant_pairs(combined)
    turns = 0
    records: List[Dict[str, Any]] = []
    for user_m, asst_m in pairs:
        rec_msgs = ([sys_msg] if sys_msg else []) + [user_m, asst_m]
        turns += 1
        rec = {
            "messages": rec_msgs,
            "meta": {
                "model": "merged",
                "sanitized": False,
                "turn": turns,
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "file_name": out_log.name,
                "display_name": format_session_display_name(out_log.stem),
            },
        }
        records.append(rec)
    out_log.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    # Compose title if not provided: concat first few source titles or ids
    if title is None:
        # Try to read titles from source meta
        parts: List[str] = []
        for p in paths:
            mp = _meta_path_for(p)
            t = None
            try:
                if mp.exists():
                    data = json.loads(mp.read_text(encoding="utf-8"))
                    t = data.get("title")
            except Exception:
                t = None
            parts.append(t or p.stem)
        base = " | ".join(parts[:3])  # limit
        title = f"Merged: {base}"

    # Write meta
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    meta = {
        "id": out_log.stem,
        "path": str(out_log),
        "model": "merged",
        "sanitized": False,
        "turns": turns,
        "created": now_iso,
        "updated": now_iso,
        "title": title,
        "custom": False,
        "sources": source_ids,
        "file_name": out_log.name,
        "display_name": format_session_display_name(out_log.stem),
    }
    out_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_log


def archive_early_sessions(
    *,
    root: Path = Path("memory/sessions"),
    archive_root: Path = Path("memory/early-archives"),
    delete_sources: bool = True,
) -> Optional[Path]:
    """Merge all but the latest session into a single archive file.

    Returns the path to the archived session log, or None if no archive was created.
    """
    infos = list_sessions(root)
    if len(infos) <= 1:
        return None

    latest = infos[0]
    archive_infos = infos[1:]
    paths: List[Path] = []
    for info in archive_infos:
        path_str = info.get("path")
        if not path_str:
            continue
        path = Path(path_str)
        if path.exists():
            paths.append(path)
    if not paths:
        return None

    latest_display = latest.get("display_name") or format_session_display_name(str(latest.get("id")))
    title = f"Early archive (before {latest_display})"
    merged_path = merge_sessions_paths(paths, title=title, root=archive_root)

    # Rename merged file to an early-archive specific stem
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive_stem = f"session-early-archive-{timestamp}"
    archive_log = merged_path.with_name(f"{archive_stem}.json")
    merged_path.rename(archive_log)

    merged_meta_path = merged_path.with_name(merged_path.stem + ".meta.json")
    archive_meta_path = archive_log.with_name(f"{archive_stem}.meta.json")
    if merged_meta_path.exists():
        merged_meta_path.rename(archive_meta_path)

    meta: Dict[str, Any] = {}
    if archive_meta_path.exists():
        try:
            meta = json.loads(archive_meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    meta.update(
        {
            "id": archive_stem,
            "path": str(archive_log),
            "file_name": archive_log.name,
            "display_name": format_session_display_name(archive_stem),
        }
    )
    meta["archive"] = {
        "type": "early",
        "latest_excluded_id": latest.get("id"),
        "latest_excluded_display_name": latest_display,
        "source_count": len(paths),
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }

    archive_meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if delete_sources:
        for p in paths:
            try:
                p.unlink(missing_ok=False)
            except FileNotFoundError:
                pass
            meta_p = p.with_name(p.stem + ".meta.json")
            meta_p.unlink(missing_ok=True)
            # Remove parent dir if it becomes empty and is under root
            try:
                if p.parent != archive_root and p.parent != root:
                    p.parent.rmdir()
            except OSError:
                pass
        # Clean up empty day directories under root
        try:
            for day_dir in root.iterdir():
                if day_dir.is_dir():
                    try:
                        next(day_dir.iterdir())
                    except StopIteration:
                        day_dir.rmdir()
        except FileNotFoundError:
            pass

    return archive_log


def set_session_title_for(log_path: Path, title: str, *, custom: bool = True) -> None:
    """Set or update the title for a given session log via its meta sidecar."""
    meta_path = _meta_path_for(log_path)
    # Build base info if missing
    meta: Dict[str, Any]
    try:
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        else:
            # Fallback: compute minimal meta
            # Count turns by lines
            turns = 0
            try:
                with log_path.open("r", encoding="utf-8") as f:
                    for _ in f:
                        turns += 1
            except Exception:
                turns = 0
            meta = {
                "id": log_path.stem,
                "path": str(log_path),
                "turns": turns,
                "model": None,
                "sanitized": None,
                "created": None,
                "updated": None,
                "file_name": log_path.name,
                "display_name": format_session_display_name(log_path.stem),
            }
    except Exception:
        meta = {
            "id": log_path.stem,
            "path": str(log_path),
            "file_name": log_path.name,
            "display_name": format_session_display_name(log_path.stem),
        }
    meta["title"] = title.strip() if title else None
    meta["custom"] = bool(custom)
    # Update updated time
    meta["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    meta.setdefault("file_name", log_path.name)
    meta.setdefault("display_name", format_session_display_name(log_path.stem))
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
