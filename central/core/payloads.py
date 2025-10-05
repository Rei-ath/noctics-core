"""Payload helpers shared by the chat client."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

__all__ = ["build_payload"]


def _messages_to_prompt(messages: List[Dict[str, Any]]) -> str:
    system_parts: List[str] = []
    conversation_parts: List[str] = []

    dialogue: List[Dict[str, Any]] = [
        msg for msg in messages if (msg.get("role") or "").lower() in {"user", "assistant"}
    ]
    # keep the last three user/assistant exchanges (max six entries)
    max_items = 6
    if len(dialogue) > max_items:
        dialogue = dialogue[-max_items:]

    for msg in messages:
        role = (msg.get("role") or "").lower()
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            system_parts.append(content)

    for msg in dialogue:
        role = (msg.get("role") or "").lower()
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            conversation_parts.append(f"<|user|>{content}")
        elif role == "assistant":
            conversation_parts.append(f"<|assistant|>{content}")

    conversation = "\n".join(conversation_parts).strip()
    if conversation and not conversation.endswith("<|assistant|>"):
        conversation = f"{conversation}\n<|assistant|>"
    elif not conversation:
        conversation = "<|assistant|>"

    return "\n\n".join(filter(None, ["\n".join(system_parts).strip(), conversation]))


def _system_and_prompt(messages: List[Dict[str, Any]]) -> Tuple[str, str]:
    system_texts: List[str] = []
    for msg in messages:
        if (msg.get("role") or "").lower() == "system":
            content = str(msg.get("content") or "").strip()
            if content:
                system_texts.append(content)
    system_text = "\n\n".join(system_texts)

    prompt = _messages_to_prompt(messages)
    return system_text, prompt


def build_payload(
    *,
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float,
    max_tokens: int,
    stream: bool,
) -> Dict[str, Any]:
    """Return a payload compatible with Ollama's chat/generate APIs."""

    options: Dict[str, Any] = {"temperature": temperature}
    if max_tokens and max_tokens > 0:
        options["num_predict"] = max_tokens

    system_text, prompt = _system_and_prompt(messages)
    # print(prompt)
    payload: Dict[str, Any] = {
        "model": model,
        "stream": stream,
        # "options": options,
    }

    # if prompt:
    #     payload["prompt"] = prompt
    # if system_text:
    #     payload["system"] = system_text

    # include chat-style messages for endpoints that support them
    if messages:
        payload["messages"] = messages
    # print(payload)
    return payload
