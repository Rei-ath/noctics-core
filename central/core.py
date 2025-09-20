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
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse
import socket

from interfaces.pii import sanitize as pii_sanitize
from interfaces.session_logger import SessionLogger
from interfaces.dotenv import load_local_dotenv
from noxl import compute_title_from_messages


DEFAULT_URL = "http://localhost:1234/v1/chat/completions"


_HELPER_PROMPT_CACHE: Optional[str] = None


def _load_helper_prompt() -> str:
    global _HELPER_PROMPT_CACHE
    if _HELPER_PROMPT_CACHE is not None:
        return _HELPER_PROMPT_CACHE

    default = (
        "You are **Central**, acting as a structured explainer and code provider.\n"
        "You always work with a JSON object where each key contains two fields:\n"
        "- \"point\" → human explanation (not copyable)\n"
        "- \"copy\" → Python code snippet (safe for user to copy-paste)\n\n"
        "Behavior Rules:\n"
        "1. If the user asks for an explanation, return the \"point\".\n"
        "   - Prefix with: **\"Explanation:\"**\n"
        "2. If the user asks for a code snippet, return the \"copy\".\n"
        "   - Prefix with: **\"Code (copy-paste):\"**\n"
        "3. If the user asks for a full runnable script, concatenate all \"copy\" fields in the correct order, and output as a single Python file.\n"
        "   - Prefix with: **\"Full Script:\"**\n"
        "4. Never mix modes:\n"
        "   - Do **not** show \"point\" if code is requested.\n"
        "   - Do **not** show \"copy\" unless clearly labeled as copyable.\n"
        "5. If user intent is unclear, explicitly ask:\n"
        "   - “Do you want the explanation (point), snippet (copy), or full script?”\n"
    )

    prompt_path = Path(__file__).resolve().parents[1] / "memory" / "helper_result_prompt.txt"
    try:
        text = prompt_path.read_text(encoding="utf-8").strip()
        if text:
            _HELPER_PROMPT_CACHE = text
            return text
    except FileNotFoundError:
        pass
    _HELPER_PROMPT_CACHE = default
    return default


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
    # Connectivity / health
    # ---------------------
    def check_connectivity(self, *, timeout: float = 1.0) -> None:
        """Quickly verify the target endpoint host:port is reachable.

        Raises URLError on failure with a helpful message. Callers can catch
        this to provide friendly CLI guidance.
        """
        parsed = urlparse(self.url)
        host = parsed.hostname
        if not host:
            raise URLError(f"Invalid CENTRAL_LLM_URL (no host): {self.url}")
        port: int
        if parsed.port:
            port = int(parsed.port)
        else:
            port = 443 if (parsed.scheme or "http").lower() == "https" else 80
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return
        except Exception as e:  # pragma: no cover - requires network unavailability
            message = f"Unable to connect to Central at {host}:{port} ({type(e).__name__}: {e})."
            raise URLError(message)

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
        try:
            with urlopen(req) as resp:  # nosec - local/dev usage
                charset = resp.headers.get_content_charset() or "utf-8"
                body = resp.read().decode(charset)
        except HTTPError as he:  # pragma: no cover - network specific
            # Read body for diagnostics if available
            try:
                body = he.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            status = getattr(he, "code", None)
            reason = getattr(he, "reason", "HTTP error")
            msg = f"HTTP {status or ''} {reason} from Central endpoint"
            if status == 401:
                msg += ": unauthorized (set CENTRAL_LLM_API_KEY or OPENAI_API_KEY?)"
            elif status == 404:
                msg += ": endpoint not found (URL path invalid?)"
            raise HTTPError(req.full_url, he.code, msg + (f"\n{body}" if body else ""), he.headers, he.fp)
        except URLError as ue:  # pragma: no cover - network specific
            raise URLError(f"Failed to reach Central at {self.url}: {ue.reason}")
        except OSError as oe:  # pragma: no cover - network specific
            raise URLError(f"Network error talking to Central at {self.url}: {oe}")

        try:
            obj = json.loads(body)
        except Exception as je:
            raise URLError(f"Central returned non-JSON response: {je}\nBody: {body[:512]}")  # pragma: no cover
        try:
            text = obj["choices"][0]["message"].get("content")
        except Exception:
            text = None
        return text, obj

    def _stream_sse(self, req: Request, on_delta: Optional[Callable[[str], None]] = None) -> str:
        try:
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
        except HTTPError as he:  # pragma: no cover - network specific
            status = getattr(he, "code", None)
            reason = getattr(he, "reason", "HTTP error")
            msg = f"HTTP {status or ''} {reason} during stream from Central"
            if status == 401:
                msg += ": unauthorized (set CENTRAL_LLM_API_KEY or OPENAI_API_KEY?)"
            elif status == 404:
                msg += ": endpoint not found (URL path invalid?)"
            raise HTTPError(req.full_url, he.code, msg, he.headers, he.fp)
        except URLError as ue:  # pragma: no cover - network specific
            raise URLError(f"Failed to reach Central at {self.url}: {ue.reason}")
        except OSError as oe:  # pragma: no cover - network specific
            raise URLError(f"Network error talking to Central at {self.url}: {oe}")

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
        helper_messages = list(self.messages)
        helper_messages.append({"role": "system", "content": _load_helper_prompt()})
        helper_messages.append({"role": "user", "content": helper_wrapped})
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

    def adopt_session_log(self, log_path: Path) -> None:
        if not self.logger:
            return
        self.logger.load_existing(log_path)


# ------------------------------
# Session management utilities
# ------------------------------
