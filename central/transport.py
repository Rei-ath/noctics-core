"""Network transport utilities for Central's ChatClient."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMTransport:
    """Thin wrapper around HTTP requests to the configured LLM endpoint."""

    def __init__(self, url: str, api_key: Optional[str] = None) -> None:
        self.url = url
        self.api_key = api_key

    def send(
        self,
        payload: Dict[str, Any],
        *,
        stream: bool = False,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        send_payload = dict(payload)
        if "/api/generate" in self.url:
            send_payload.pop("messages", None)
        data = json.dumps(send_payload).encode("utf-8")
        headers = self._headers(stream=stream)
        req = Request(self.url, data=data, headers=headers, method="POST")
        if "/api/generate" in self.url:
            if stream:
                text = self._stream_generate(req, on_chunk)
                return text, None
            return self._request_generate(req)
        if stream:
            text = self._stream_sse(req, on_chunk)
            return text, None
        return self._request_json(req)

    # -----------------
    # Internal helpers
    # -----------------
    def _headers(self, *, stream: bool = False) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if stream:
            headers.setdefault("Accept", "text/event-stream")
        return headers

    def _request_json(self, req: Request) -> Tuple[Optional[str], Dict[str, Any]]:
        try:
            with urlopen(req) as resp:  # nosec - local/dev usage
                charset = resp.headers.get_content_charset() or "utf-8"
                body = resp.read().decode(charset)
        except HTTPError as he:  # pragma: no cover - network specific
            body = _extract_error_body(he)
            message = _http_error_message(he, suffix=body)
            raise HTTPError(req.full_url, he.code, message, he.headers, he.fp)
        except URLError as ue:  # pragma: no cover - network specific
            raise URLError(f"Failed to reach Central at {self.url}: {ue.reason}")
        except OSError as oe:  # pragma: no cover - network specific
            raise URLError(f"Network error talking to Central at {self.url}: {oe}")

        try:
            obj = json.loads(body)
        except Exception as exc:
            raise URLError(
                f"Central returned non-JSON response: {exc}\nBody: {body[:512]}"
            ) from exc  # pragma: no cover

        message: Optional[str]
        try:
            message = obj["choices"][0]["message"].get("content")
        except Exception:
            message = None
        return message, obj

    def _request_generate(self, req: Request) -> Tuple[Optional[str], Dict[str, Any]]:
        try:
            with urlopen(req) as resp:  # nosec - local/dev usage
                charset = resp.headers.get_content_charset() or "utf-8"
                body = resp.read().decode(charset)
        except HTTPError as he:
            body = _extract_error_body(he)
            message = _http_error_message(he, suffix=body)
            raise HTTPError(req.full_url, he.code, message, he.headers, he.fp)
        except URLError as ue:
            raise URLError(f"Failed to reach Central at {self.url}: {ue.reason}")
        except OSError as oe:
            raise URLError(f"Network error talking to Central at {self.url}: {oe}")

        lines = [line for line in body.splitlines() if line.strip()]
        responses: list[str] = []
        payloads: list[Dict[str, Any]] = []
        for line in lines:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            payloads.append(data)
            if data.get("error"):
                raise URLError(str(data["error"]))
            text = data.get("response") or ""
            if text:
                responses.append(text)
        return ("".join(responses) if responses else None, {"responses": payloads})

    def _stream_sse(
        self,
        req: Request,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> str:
        try:
            with urlopen(req) as resp:  # nosec - local/dev usage
                charset = resp.headers.get_content_charset() or "utf-8"
                buffer: list[str] = []
                acc: list[str] = []
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
                        piece = _extract_sse_piece(data_str)
                        if piece:
                            if on_chunk:
                                on_chunk(piece)
                            acc.append(piece)
                        continue

                    if line.startswith(":"):
                        continue
                    if line.startswith("data:"):
                        buffer.append(line[len("data:"):].lstrip())
                        continue
                    buffer.clear()
        except HTTPError as he:  # pragma: no cover - network specific
            message = _http_error_message(he)
            raise HTTPError(req.full_url, he.code, message, he.headers, he.fp)
        except URLError as ue:  # pragma: no cover - network specific
            raise URLError(f"Failed to reach Central at {self.url}: {ue.reason}")
        except OSError as oe:  # pragma: no cover - network specific
            raise URLError(f"Network error talking to Central at {self.url}: {oe}")

        return "".join(acc)

    def _stream_generate(
        self,
        req: Request,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> str:
        try:
            with urlopen(req) as resp:  # nosec - local/dev usage
                charset = resp.headers.get_content_charset() or "utf-8"
                acc: list[str] = []
                while True:
                    line_bytes = resp.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode(charset, errors="replace").strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("error"):
                        raise URLError(str(data["error"]))
                    text = data.get("response")
                    if text:
                        acc.append(text)
                        if on_chunk:
                            on_chunk(text)
                    if data.get("done"):
                        break
        except HTTPError as he:
            message = _http_error_message(he)
            raise HTTPError(req.full_url, he.code, message, he.headers, he.fp)
        except URLError as ue:
            raise URLError(f"Failed to reach Central at {self.url}: {ue.reason}")
        except OSError as oe:
            raise URLError(f"Network error talking to Central at {self.url}: {oe}")

        return "".join(acc)


def _extract_error_body(error: HTTPError) -> str:
    try:
        return error.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _http_error_message(error: HTTPError, *, suffix: str = "") -> str:
    status = getattr(error, "code", None)
    reason = getattr(error, "reason", "HTTP error")
    message = f"HTTP {status or ''} {reason} from Central endpoint"
    if status == 401:
        message += ": unauthorized (set CENTRAL_LLM_API_KEY or OPENAI_API_KEY?)"
    elif status == 404:
        message += ": endpoint not found (URL path invalid?)"
    if suffix:
        message = f"{message}\n{suffix}"
    return message


def _extract_sse_piece(data_str: str) -> Optional[str]:
    try:
        event = json.loads(data_str)
    except Exception:
        if not data_str.strip().startswith("{"):
            return data_str
        return None

    choice = (event.get("choices") or [{}])[0]
    delta = choice.get("delta") or {}
    piece = delta.get("content")
    if piece is None:
        piece = (choice.get("message") or {}).get("content")
    if piece is None:
        piece = choice.get("text")
    return piece
