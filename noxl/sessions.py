"""Session storage helpers for the Noxl memory toolkit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from interfaces.session_logger import format_session_display_name

SESSION_ROOT = Path("memory/sessions")
ARCHIVE_ROOT = Path("memory/early-archives")


def compute_title_from_messages(messages: List[Dict[str, Any]]) -> Optional[str]:
    """Derive a short session title from the first meaningful user message."""

    def normalize(text: str) -> str:
        text = (text or "").strip().replace("\n", " ")
        return text.replace("  ", " ")

    first_user = None
    for msg in messages:
        if msg.get("role") == "user":
            content = str(msg.get("content") or "")
            if content.strip().startswith("[HELPER RESULT]"):
                continue
            first_user = content
            break
    title_src = normalize(first_user or "")
    if not title_src:
        return None

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


def list_sessions(root: Path = SESSION_ROOT) -> List[Dict[str, Any]]:
    """Return session metadata dictionaries sorted newest first."""
    items: List[Dict[str, Any]] = []
    if not root.exists():
        return items

    for day_dir in sorted(root.iterdir() if root.is_dir() else [], reverse=True):
        if not day_dir.is_dir():
            continue
        file_map = _session_files_for_day(day_dir)
        for log_path in file_map.values():
            meta_path = _meta_path_for(log_path)
            if meta_path.exists():
                info = _read_info_with_meta(log_path, meta_path)
            else:
                info = _fallback_info_without_meta(log_path)
            items.append(info)

    items.sort(key=_info_sort_key, reverse=True)
    return items


def _read_info_with_meta(log_path: Path, meta_path: Path) -> Dict[str, Any]:
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
        info.setdefault("turns", _count_lines(log_path))
    info.setdefault("file_name", log_path.name)
    info.setdefault("display_name", format_session_display_name(log_path.stem))
    return info


def _fallback_info_without_meta(log_path: Path) -> Dict[str, Any]:
    turns: int
    if log_path.suffix == ".json":
        try:
            turns = len(json.loads(log_path.read_text(encoding="utf-8")))
        except Exception:
            turns = 0
    else:
        turns = _count_lines(log_path)

    title = None
    try:
        if log_path.suffix == ".json":
            data = json.loads(log_path.read_text(encoding="utf-8"))
            first = data[0] if isinstance(data, list) and data else None
            msgs = first.get("messages") if isinstance(first, dict) else []
            title = compute_title_from_messages(msgs or [])
        else:
            with log_path.open("r", encoding="utf-8") as handle:
                first_line = handle.readline()
            if first_line:
                obj = json.loads(first_line)
                msgs = obj.get("messages") or []
                title = compute_title_from_messages(msgs)
    except Exception:
        title = None

    return {
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


def _info_sort_key(info: Dict[str, Any]) -> float:
    updated = info.get("updated")
    if isinstance(updated, str) and updated:
        try:
            ts = datetime.fromisoformat(updated.rstrip("Z")).timestamp()
            return ts
        except Exception:
            pass
    try:
        return Path(info["path"]).stat().st_mtime
    except Exception:
        return 0.0


def _count_lines(log_path: Path) -> int:
    try:
        with log_path.open("r", encoding="utf-8") as handle:
            return sum(1 for _ in handle)
    except Exception:
        return 0


def resolve_session(identifier: str, root: Path = SESSION_ROOT) -> Optional[Path]:
    """Resolve a session JSON/JSONL path by stem or explicit filesystem path."""
    path_candidate = Path(identifier)
    if path_candidate.exists():
        return path_candidate

    for day_dir in root.iterdir() if root.exists() else []:
        if not day_dir.is_dir():
            continue
        for log_path in _session_files_for_day(day_dir).values():
            if log_path.stem == identifier or log_path.stem.endswith(identifier):
                return log_path
    return None


def load_session_messages(log_path: Path) -> List[Dict[str, Any]]:
    """Reconstruct an ordered message list from a session log."""
    messages: List[Dict[str, Any]] = []
    system_set = False
    try:
        records = _load_records(log_path)
        for obj in records:
            turn_msgs = obj.get("messages") or []
            if not system_set:
                for msg in turn_msgs:
                    if msg.get("role") == "system":
                        messages.append(msg)
                        system_set = True
                        break
            pair = [m for m in turn_msgs if m.get("role") in {"user", "assistant"}]
            if pair:
                messages.extend(pair)
    except FileNotFoundError:
        pass
    return messages


def _load_records(log_path: Path) -> List[Dict[str, Any]]:
    if log_path.suffix == ".json":
        try:
            data = json.loads(log_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return data if isinstance(data, list) else []

    records: List[Dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            records.append(obj)
    return records


def _group_user_assistant_pairs(messages: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    pairs: List[List[Dict[str, Any]]] = []
    current_user: Optional[Dict[str, Any]] = None
    for msg in messages:
        role = msg.get("role")
        if role == "system":
            continue
        if role == "user":
            current_user = msg
        elif role == "assistant" and current_user is not None:
            pairs.append([current_user, msg])
            current_user = None
    return pairs


def merge_sessions_paths(
    paths: Sequence[Path],
    *,
    title: Optional[str] = None,
    root: Path = SESSION_ROOT,
) -> Path:
    """Merge session logs into a single JSON archive under ``root``."""
    combined: List[Dict[str, Any]] = []
    system_set = False
    source_ids: List[str] = []

    for path in paths:
        source_ids.append(path.stem)
        msgs = load_session_messages(path)
        if not msgs:
            continue
        if not system_set:
            for msg in msgs:
                if msg.get("role") == "system":
                    combined.append(msg)
                    system_set = True
                    break
        for msg in msgs:
            if msg.get("role") in {"user", "assistant"}:
                combined.append(msg)

    now_utc = datetime.now(timezone.utc)
    date_dir = root / ("merged-" + now_utc.date().isoformat())
    date_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now_utc.strftime("%Y%m%d-%H%M%S")
    out_log = date_dir / f"session-merged-{timestamp}.json"
    out_meta = out_log.with_name(out_log.stem + ".meta.json")

    sys_msg = next((msg for msg in combined if msg.get("role") == "system"), None)
    pairs = _group_user_assistant_pairs(combined)
    turns = 0
    records: List[Dict[str, Any]] = []
    for user_msg, assistant_msg in pairs:
        rec_msgs = ([sys_msg] if sys_msg else []) + [user_msg, assistant_msg]
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

    if title is None:
        parts: List[str] = []
        for path in paths:
            meta_path = _meta_path_for(path)
            try:
                if meta_path.exists():
                    data = json.loads(meta_path.read_text(encoding="utf-8"))
                    part_title = data.get("title")
                else:
                    part_title = None
            except Exception:
                part_title = None
            parts.append(part_title or path.stem)
        base = " | ".join(parts[:3])
        title = f"Merged: {base}"

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
    root: Path = SESSION_ROOT,
    archive_root: Path = ARCHIVE_ROOT,
    delete_sources: bool = True,
) -> Optional[Path]:
    """Archive all but the latest session into a merged log."""
    infos = list_sessions(root)
    if len(infos) <= 1:
        return None

    latest = infos[0]
    archive_candidates = infos[1:]
    paths: List[Path] = []
    for info in archive_candidates:
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
    meta["sources"] = [path.stem for path in paths]

    archive_meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if delete_sources:
        _delete_source_sessions(paths, root, archive_root)

    return archive_log


def _delete_source_sessions(paths: Sequence[Path], root: Path, archive_root: Path) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=False)
        except FileNotFoundError:
            pass
        meta_path = path.with_name(path.stem + ".meta.json")
        meta_path.unlink(missing_ok=True)
        try:
            if path.parent not in {root, archive_root}:
                path.parent.rmdir()
        except OSError:
            pass

    try:
        for day_dir in root.iterdir():
            if day_dir.is_dir():
                try:
                    next(day_dir.iterdir())
                except StopIteration:
                    day_dir.rmdir()
    except FileNotFoundError:
        pass


def set_session_title_for(log_path: Path, title: str, *, custom: bool = True) -> None:
    """Update the session meta sidecar with a new title."""
    meta_path = _meta_path_for(log_path)
    try:
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        else:
            turns = _count_lines(log_path)
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
    meta["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    meta.setdefault("file_name", log_path.name)
    meta.setdefault("display_name", format_session_display_name(log_path.stem))
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = [
    "ARCHIVE_ROOT",
    "SESSION_ROOT",
    "archive_early_sessions",
    "compute_title_from_messages",
    "list_sessions",
    "load_session_messages",
    "merge_sessions_paths",
    "resolve_session",
    "set_session_title_for",
]
