"""Chat client implementation for Noctics Central."""

from __future__ import annotations

import os
import socket
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional
from urllib.error import URLError
from urllib.parse import urlparse

from interfaces.dotenv import load_local_dotenv
from interfaces.pii import sanitize as pii_sanitize
from interfaces.session_logger import SessionLogger
from noxl import (
    append_session_to_day_log as noxl_append_session_to_day_log,
    compute_title_from_messages,
    delete_session_if_empty as noxl_delete_session_if_empty,
)

from ..transport import LLMTransport
from ..connector import CentralConnector, build_connector
from .helper_prompt import load_helper_prompt
from .payloads import build_payload
from .reasoning import clean_public_reply, extract_public_segments, strip_chain_of_thought

try:  # instruments package lives in the superproject
    from instruments import build_instrument as _build_instrument
except Exception:  # pragma: no cover - optional dependency
    _build_instrument = None

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from instruments.base import BaseInstrument

DEFAULT_URL = "http://127.0.0.1:11434/api/generate"


class ChatClient:
    """Stateful chat client used by the CLI and external consumers."""

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
        connector: Optional[CentralConnector] = None,
    ) -> None:
        try:
            load_local_dotenv(Path(__file__).resolve().parent)
        except Exception:
            pass

        resolved_url = url or os.getenv("CENTRAL_LLM_URL", DEFAULT_URL)
        resolved_api_key = api_key or (os.getenv("CENTRAL_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"))

        connector = connector or build_connector(url=resolved_url, api_key=resolved_api_key)
        self.connector = connector

        if transport is None:
            transport = connector.connect()

        self.transport = transport
        resolved_url = getattr(transport, "url", resolved_url)
        resolved_api_key = getattr(transport, "api_key", resolved_api_key)

        self.url = resolved_url
        self.model = model
        self.api_key = resolved_api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.stream = stream
        self.sanitize = sanitize
        self.messages: List[Dict[str, Any]] = list(messages or [])
        self.strip_reasoning = strip_reasoning

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

        self.instrument: Optional["BaseInstrument"] = None
        self.instrument_warning: Optional[str] = None
        if _build_instrument is not None:
            try:
                instrument, warning = _build_instrument(
                    url=self.url,
                    model=self.model,
                    api_key=self.api_key,
                )
            except Exception:  # pragma: no cover - defensive fallback
                instrument, warning = None, None
            self.instrument = instrument
            self.instrument_warning = warning

    # -----------------
    # Payload adapters
    # -----------------
    def _prepare_payload(self, payload: Dict[str, Any], *, stream: bool) -> Dict[str, Any]:
        """Normalize payload details for specific providers."""

        if self.instrument is not None:
            return payload

        target_url = (self.url or "").lower()
        if "openai.com" not in target_url:
            return payload

        adjusted: Dict[str, Any] = dict(payload)

        messages = adjusted.get("messages")
        if isinstance(messages, list):
            converted: List[Dict[str, Any]] = []
            for message in messages:
                if not isinstance(message, dict):
                    continue
                rewritten = dict(message)
                content = rewritten.get("content")
                if isinstance(content, str):
                    rewritten["content"] = [{"type": "text", "text": content}]
                elif isinstance(content, list):
                    rewritten["content"] = deepcopy(content)
                elif content is not None:
                    rewritten["content"] = [{"type": "text", "text": str(content)}]
                converted.append(rewritten)
            adjusted["messages"] = converted

        if self.temperature is not None:
            adjusted.setdefault("temperature", self.temperature)

        if self.max_tokens and self.max_tokens > 0:
            adjusted.setdefault("max_tokens", self.max_tokens)

        if stream:
            adjusted["stream"] = True

        return adjusted

    # ---------------------
    # Connectivity / health
    # ---------------------
    def check_connectivity(self, *, timeout: float = 1.0) -> None:
        """Raise ``URLError`` if the configured endpoint is unreachable."""

        parsed = urlparse(self.url)
        host = parsed.hostname
        if not host:
            raise URLError(f"Invalid CENTRAL_LLM_URL (no host): {self.url}")

        port = parsed.port or (443 if (parsed.scheme or "http").lower() == "https" else 80)
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return
        except Exception as exc:  # pragma: no cover - requires network issues
            message = f"Unable to connect to Central at {host}:{port} ({type(exc).__name__}: {exc})."
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
        """Ensure a session title exists; compute and set one if absent."""

        if not self.logger:
            return None
        meta = self.logger.get_meta()
        if meta.get("title") and meta.get("custom"):
            return meta.get("title")

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
        lowered = text.lower()
        return "[helper query]" in lowered or (
            "requires a helper" in lowered and "paste a helper response" in lowered
        )

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
        stream_callback = on_delta
        public_state: Dict[str, Any] = {}
        if self.stream:
            if self.strip_reasoning and on_delta:
                public_state = {"buffer": "", "public": ""}

                def sanitized_delta(piece: str) -> None:
                    state = public_state
                    buffer = state["buffer"] + piece
                    public, remainder = extract_public_segments(buffer)
                    state["buffer"] = remainder
                    previous = state["public"]
                    if len(public) > len(previous):
                        on_delta(public[len(previous):])
                        state["public"] = public

                stream_callback = sanitized_delta

        assistant: Optional[str] = None

        if self.instrument is not None:
            instrument_response = self.instrument.send_chat(
                turn_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens if self.max_tokens and self.max_tokens > 0 else None,
                stream=bool(self.stream),
                on_chunk=stream_callback,
            )
            assistant = instrument_response.text
        else:
            payload = build_payload(
                model=self.model,
                messages=turn_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=bool(self.stream),
            )
            payload = self._prepare_payload(payload, stream=bool(self.stream))

            if self.stream:
                assistant, _ = self.transport.send(
                    payload,
                    stream=True,
                    on_chunk=stream_callback,
                )
            else:
                assistant, _ = self.transport.send(payload, stream=False)

        if assistant is not None:
            if self.strip_reasoning:
                assistant = strip_chain_of_thought(assistant)
                if self.stream and on_delta and public_state:
                    public_text = public_state.get("public", "")
                    if len(assistant) > len(public_text):
                        on_delta(assistant[len(public_text):])
            assistant = clean_public_reply(assistant) or ""
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
        """Record an assistant response without calling the API."""

        to_send_user = pii_sanitize(user_text) if self.sanitize else user_text
        if self.strip_reasoning:
            assistant_text = strip_chain_of_thought(assistant_text)
        assistant_text = clean_public_reply(assistant_text) or ""
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
        helper_wrapped = f"[INSTRUMENT RESULT]\n{helper_text}\n[/INSTRUMENT RESULT]"
        helper_messages = list(self.messages)
        helper_messages.append({"role": "system", "content": load_helper_prompt()})
        helper_messages.append({"role": "user", "content": helper_wrapped})
        reply: Optional[str]
        if self.instrument is not None:
            instrument_response = self.instrument.send_chat(
                helper_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens if self.max_tokens and self.max_tokens > 0 else None,
                stream=bool(self.stream),
                on_chunk=on_delta,
            )
            reply = instrument_response.text
        else:
            payload = build_payload(
                model=self.model,
                messages=helper_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=bool(self.stream),
            )
            payload = self._prepare_payload(payload, stream=bool(self.stream))

            if self.stream:
                reply, _ = self.transport.send(payload, stream=True, on_chunk=on_delta)
            else:
                reply, _ = self.transport.send(payload, stream=False)

        if reply is not None:
            if self.strip_reasoning:
                reply = strip_chain_of_thought(reply)
            reply = clean_public_reply(reply) or ""
            self.messages.append({"role": "user", "content": helper_wrapped})
            self.messages.append({"role": "assistant", "content": reply})
            if self.logger:
                sys_msgs = [m for m in self.messages if m.get("role") == "system"]
                to_log = (sys_msgs[-1:] if sys_msgs else []) + [
                    {"role": "user", "content": helper_wrapped},
                    {"role": "assistant", "content": reply},
                ]
                self.logger.log_turn(to_log)
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
            "instrument": getattr(self.instrument, "name", None),
            "instrument_warning": self.instrument_warning,
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


__all__ = ["ChatClient", "DEFAULT_URL"]
