from __future__ import annotations

import types
from typing import Any, Dict, Iterable, List, Optional

import pytest

from central.core.client import ChatClient


class _StubInstrument:
    name = "openai-stub"

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def send_chat(
        self,
        messages: Iterable[Dict[str, Any]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        on_chunk: Optional[callable] = None,
    ) -> types.SimpleNamespace:
        serialised = [dict(message) for message in messages]
        self.calls.append(
            {
                "messages": serialised,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream,
            }
        )
        if stream and on_chunk:
            on_chunk("stub-stream")
        return types.SimpleNamespace(text="stub-response")


class _FakeTransport:
    def __init__(self, url: str) -> None:
        self.url = url
        self.api_key = "sk-test"
        self.sent: List[Dict[str, Any]] = []

    def send(
        self,
        payload: Dict[str, Any],
        *,
        stream: bool = False,
        on_chunk: Optional[callable] = None,
    ) -> tuple[str, Dict[str, Any]]:
        self.sent.append({"payload": payload, "stream": stream})
        if stream and on_chunk:
            on_chunk("transport-stream")
            return "transport-stream", {}
        return "transport-response", {}


@pytest.mark.parametrize("stream", [False, True])
def test_chatclient_prefers_instrument_for_openai(monkeypatch, stream: bool) -> None:
    instrument = _StubInstrument()
    transport = _FakeTransport("https://api.openai.com/v1/chat/completions")

    def fake_build_instrument(**_: Any) -> tuple[_StubInstrument, Optional[str]]:
        return instrument, None

    monkeypatch.setattr("central.core.client._build_instrument", fake_build_instrument)

    captured: List[str] = []
    client = ChatClient(
        url=transport.url,
        model="gpt-4o-mini",
        api_key="sk-test",
        transport=transport,
        stream=stream,
    )
    reply = client.one_turn("Hello instrument", on_delta=captured.append if stream else None)

    assert reply == "stub-response"
    assert instrument.calls, "Instrument should receive the chat request"
    assert transport.sent == [], "Transport should be bypassed when instrument is present"
    if stream:
        assert captured == ["stub-stream"], "Streaming chunks should flow from instrument"


def test_chatclient_openai_rest_payload(monkeypatch) -> None:
    transport = _FakeTransport("https://api.openai.com/v1/chat/completions")

    def fake_build_instrument(**_: Any) -> tuple[None, None]:
        return None, None

    monkeypatch.setattr("central.core.client._build_instrument", fake_build_instrument)

    captured: List[str] = []
    client = ChatClient(
        url=transport.url,
        model="gpt-4o-mini",
        api_key="sk-test",
        transport=transport,
        stream=True,
        max_tokens=77,
    )
    reply = client.one_turn("Hello REST", on_delta=captured.append)

    assert reply == "transport-stream"
    assert captured == ["transport-stream"]
    assert len(transport.sent) == 1
    payload = transport.sent[0]["payload"]
    assert "modalities" not in payload
    assert "response_format" not in payload
    assert "stream_options" not in payload
    assert payload.get("max_completion_tokens") is None
    assert payload.get("max_tokens") == 77
    messages = payload.get("messages")
    assert isinstance(messages, list) and messages
    assert messages[-1]["content"][0]["text"] == "Hello REST"


def test_chatclient_ollama_payload_passthrough(monkeypatch) -> None:
    transport = _FakeTransport("http://127.0.0.1:11434/api/generate")

    def fake_build_instrument(**_: Any) -> tuple[None, None]:
        return None, None

    monkeypatch.setattr("central.core.client._build_instrument", fake_build_instrument)

    client = ChatClient(
        url=transport.url,
        model="qwen/qwen3-1.7b",
        transport=transport,
        stream=False,
    )
    reply = client.one_turn("Hello Ollama")

    assert reply == "transport-response"
    assert len(transport.sent) == 1
    payload = transport.sent[0]["payload"]
    assert payload["model"] == "qwen/qwen3-1.7b"
    assert payload["stream"] is False
    messages = payload.get("messages")
    assert isinstance(messages, list) and messages[-1]["content"] == "Hello Ollama"
