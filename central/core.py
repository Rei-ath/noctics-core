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
from urllib.error import URLError
from urllib.parse import urlparse
import socket
import re

from interfaces.pii import sanitize as pii_sanitize
from interfaces.session_logger import SessionLogger
from interfaces.dotenv import load_local_dotenv
from noxl import (
    append_session_to_day_log as noxl_append_session_to_day_log,
    compute_title_from_messages,
    delete_session_if_empty as noxl_delete_session_if_empty,
)
from .transport import LLMTransport


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


_THINK_PATTERN = re.compile(r"<think>.*?</think>\s*", re.IGNORECASE | re.DOTALL)


def strip_chain_of_thought(text: Optional[str]) -> Optional[str]:
    """Remove <think>...</think> segments while preserving public content."""

    if text is None:
        return None
    cleaned = _THINK_PATTERN.sub("", text)
    return cleaned.strip()


def _extract_public_segments(buffer: str) -> Tuple[str, str]:
    """Return (public_text, remainder) preserving incomplete <think> regions."""

    lower = buffer.lower()
    pos = 0
    public_parts: List[str] = []
    length = len(buffer)
    open_tag = "<think>"
    close_tag = "</think>"
    open_len = len(open_tag)
    close_len = len(close_tag)

    while pos < length:
        open_idx = lower.find(open_tag, pos)
        if open_idx == -1:
            # No more think segments; entire remainder is public
            public_parts.append(buffer[pos:])
            return "".join(public_parts), ""
        # Append text before the think block
        public_parts.append(buffer[pos:open_idx])
        close_search_start = open_idx + open_len
        close_idx = lower.find(close_tag, close_search_start)
        if close_idx == -1:
            # Incomplete think block; keep remainder for later
            return "".join(public_parts), buffer[open_idx:]
        pos = close_idx + close_len

    return "".join(public_parts), ""


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
        strip_reasoning: bool = True,
        memory_user: Optional[str] = None,
        memory_user_display: Optional[str] = None,
        transport: Optional[LLMTransport] = None,
    ) -> None:
        # Ensure .env is loaded when core is used as a library
        try:
            load_local_dotenv(Path(__file__).resolve().parent)
        except Exception:
            pass
        resolved_url = url or os.getenv("CENTRAL_LLM_URL", DEFAULT_URL)
        resolved_api_key = api_key or (os.getenv("CENTRAL_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"))
        if transport is None:
            self.transport = LLMTransport(resolved_url, resolved_api_key)
        else:
            self.transport = transport
            resolved_url = transport.url
            resolved_api_key = transport.api_key
        self.url = resolved_url
        self.model = model
        self.api_key = resolved_api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.stream = stream
        self.sanitize = sanitize
        self.messages: List[Dict[str, Any]] = list(messages or [])
        self.logger = (
            SessionLogger(
                model=self.model,
                sanitized=bool(self.sanitize),
                user_id=memory_user,
                user_display=memory_user_display,
            )
            if enable_logging
            else None
        )
        if self.logger:
            self.logger.start()
        self.strip_reasoning = strip_reasoning

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

        public_state: Dict[str, Any] = {}
        if self.stream:
            stream_callback = on_delta
            if self.strip_reasoning and on_delta:
                public_state = {"buffer": "", "public": ""}

                def sanitized_delta(piece: str) -> None:
                    state = public_state
                    state_buffer = state["buffer"] + piece
                    public, remainder = _extract_public_segments(state_buffer)
                    state["buffer"] = remainder
                    prev_public = state["public"]
                    if len(public) > len(prev_public):
                        on_delta(public[len(prev_public):])
                        state["public"] = public

                stream_callback = sanitized_delta

            assistant, _ = self.transport.send(payload, stream=True, on_chunk=stream_callback)
        else:
            assistant, _ = self.transport.send(payload, stream=False)

        # Output/log and retain state
        if assistant is not None:
            if self.strip_reasoning:
                assistant = strip_chain_of_thought(assistant)
                if self.stream and on_delta and public_state:
                    public_text = public_state.get("public", "")
                    if len(assistant) > len(public_text):
                        on_delta(assistant[len(public_text):])
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
        if self.strip_reasoning:
            assistant_text = strip_chain_of_thought(assistant_text)
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

        if self.stream:
            reply, _ = self.transport.send(payload, stream=True, on_chunk=on_delta)
        else:
            reply, _ = self.transport.send(payload, stream=False)

        if reply is not None:
            if self.strip_reasoning:
                reply = strip_chain_of_thought(reply)
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
    def describe_target(self) -> Dict[str, Any]:
        """Return a sanitized snapshot of the configured target LLM."""

        return {
            "url": self.url,
            "model": self.model,
            "stream": bool(self.stream),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "sanitize": bool(self.sanitize),
            "strip_reasoning": bool(self.strip_reasoning),
            "logging_enabled": self.logger is not None,
            "has_api_key": bool(self.api_key),
        }

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
        return noxl_delete_session_if_empty(path, meta_path=meta_path)

    def append_session_to_day_log(self) -> Optional[Path]:
        if not self.logger:
            return None
        log_path = self.logger.log_path()
        if not log_path or not log_path.exists():
            return None
        meta = self.logger.get_meta()
        return noxl_append_session_to_day_log(log_path, meta=meta)

    def adopt_session_log(self, log_path: Path) -> None:
        if not self.logger:
            return
        self.logger.load_existing(log_path)


# ------------------------------
# Session management utilities
# ------------------------------
