"""
Interactive CLI to talk to a local OpenAI-like chat completions endpoint.

Defaults mirror the provided curl and post to http://localhost:1234/v1/chat/completions.
Supports both non-streaming and streaming (SSE) responses via --stream.
No external dependencies (stdlib only).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from interfaces.pii import sanitize as pii_sanitize
from interfaces.session_logger import SessionLogger
from urllib.request import Request, urlopen
from .colors import color


DEFAULT_URL = "http://localhost:1234/v1/chat/completions"


def build_payload(
    *,
    model: str,
    system_msg: Optional[str],
    user_msg: Optional[str],
    messages_override: Optional[List[Dict[str, Any]]],
    temperature: float,
    max_tokens: int,
    stream: bool,
) -> Dict[str, Any]:
    """Build an OpenAI-style chat.completions payload.

    If messages_override is provided, it takes precedence over system/user.
    """
    if messages_override is not None:
        messages = messages_override
    else:
        messages: List[Dict[str, str]] = []
        if system_msg:
            messages.append({"role": "system", "content": system_msg})
        if user_msg:
            messages.append({"role": "user", "content": user_msg})
    return {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }


def _print_non_streaming(req: Request) -> None:
    with urlopen(req) as resp:  # nosec - local/dev usage
        charset = resp.headers.get_content_charset() or "utf-8"
        body = resp.read().decode(charset)

    obj = json.loads(body)
    try:
        content = obj["choices"][0]["message"].get("content")
    except Exception:
        content = None

    if content:
        print(content)
    else:
        print(json.dumps(obj, indent=2))


def _request_non_streaming(req: Request) -> Tuple[Optional[str], Dict[str, Any]]:
    """Perform a non-streaming request and return (assistant_text, raw_json)."""
    with urlopen(req) as resp:  # nosec - local/dev usage
        charset = resp.headers.get_content_charset() or "utf-8"
        body = resp.read().decode(charset)
    obj = json.loads(body)
    try:
        text = obj["choices"][0]["message"].get("content")
    except Exception:
        text = None
    return text, obj


def _stream_sse(req: Request) -> str:
    """Stream Server-Sent Events and print incremental content.

    Handles both chat.delta (choices[].delta.content) and final message content.
    """
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
                # End of one SSE event; process accumulated data lines
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
                    # If not JSON, just echo raw
                    print(data_str, end="", flush=True)
                    acc.append(data_str)
                    continue

                try:
                    choice = (evt.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}
                    piece = delta.get("content")
                    if piece is None:
                        # Some servers might send full message during stream end
                        piece = (choice.get("message") or {}).get("content")
                    if piece is None:
                        # Fallback: text key used by some implementations
                        piece = choice.get("text")
                except Exception:
                    piece = None

                if piece:
                    print(piece, end="", flush=True)
                    acc.append(piece)
                continue

            # Accumulate data lines; ignore comments/other fields
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                buffer.append(line[len("data:"):].lstrip())
                continue
            # Ignore other SSE fields (event:, id:, retry:)
            continue

    # Ensure trailing newline after stream completes
    print()
    return "".join(acc)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive Chat Completions CLI")
    parser.add_argument(
        "--url",
        default=os.getenv("CENTRAL_LLM_URL", DEFAULT_URL),
        help="Endpoint URL (env CENTRAL_LLM_URL)",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("CENTRAL_LLM_MODEL", "liquid/lfm2-1.2b"),
        help="Model name (env CENTRAL_LLM_MODEL)",
    )
    parser.add_argument(
        "--system",
        default=None,
        help="System message (defaults to memory/system_prompt.txt; ignored if --messages is used)",
    )
    parser.add_argument("--user", default=None, help="Optional initial user message")
    parser.add_argument(
        "--messages",
        dest="messages_file",
        default=None,
        help="Path to JSON file containing a messages array to send",
    )
    parser.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature")
    parser.add_argument(
        "--max-tokens",
        dest="max_tokens",
        type=int,
        default=-1,
        help="Max tokens (-1 for unlimited if supported)",
    )
    parser.add_argument("--stream", action="store_true", help="Enable streaming (SSE)")
    parser.add_argument(
        "--sanitize",
        action="store_true",
        help="Redact common PII from user text before sending",
    )
    parser.add_argument("--raw", action="store_true", help="Also print raw JSON in non-streaming mode")
    parser.add_argument(
        "--api-key",
        default=(os.getenv("CENTRAL_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")),
        help="Optional API key for Authorization header (env CENTRAL_LLM_API_KEY | OPENAI_API_KEY)",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    # Load environment from a local .env file if present (no external deps)
    def _load_dotenv() -> None:
        def load_file(p: Path) -> None:
            if not p.exists():
                return
            for line in p.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v

        here = Path(__file__).resolve().parent
        load_file(here / ".env")
        load_file(Path.cwd() / ".env")

    _load_dotenv()

    args = parse_args(argv)

    # Load default system prompt from file if not provided
    if args.system is None and not args.messages_file:
        local_path = Path("memory/system_prompt.local.txt")
        default_path = Path("memory/system_prompt.txt")
        if local_path.exists():
            args.system = local_path.read_text(encoding="utf-8").strip()
        elif default_path.exists():
            args.system = default_path.read_text(encoding="utf-8").strip()

    # Initialize conversation messages
    messages: List[Dict[str, Any]]
    if args.messages_file:
        with open(args.messages_file, "r", encoding="utf-8") as f:
            messages = json.load(f)
            if not isinstance(messages, list):
                raise SystemExit("--messages must point to a JSON array of messages")
    else:
        messages = []
        if args.system:
            messages.append({"role": "system", "content": args.system})

    # Session logger (for later fine-tuning)
    logger = SessionLogger(model=args.model, sanitized=bool(args.sanitize))
    logger.start()

    # Helper to perform a single turn given a user prompt
    def one_turn(user_text: str) -> Optional[str]:
        to_send_user = pii_sanitize(user_text) if args.sanitize else user_text
        turn_messages = messages + [{"role": "user", "content": to_send_user}]
        payload = {
            "model": args.model,
            "messages": turn_messages,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "stream": bool(args.stream),
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if args.api_key:
            headers["Authorization"] = f"Bearer {args.api_key}"
        req = Request(args.url, data=data, headers=headers, method="POST")

        if args.stream:
            assistant = _stream_sse(req)
            if assistant:
                messages.append({"role": "user", "content": to_send_user})
                messages.append({"role": "assistant", "content": assistant})
                # Log compact SFT-style example: system (if any), user, assistant
                sys_msgs = [m for m in messages if m.get("role") == "system"]
                to_log = (sys_msgs[-1:] if sys_msgs else []) + [
                    {"role": "user", "content": to_send_user},
                    {"role": "assistant", "content": assistant},
                ]
                logger.log_turn(to_log)
            return assistant
        else:
            text, obj = _request_non_streaming(req)
            # Print either the text or full JSON depending on --raw
            if args.raw:
                print(json.dumps(obj, indent=2))
            else:
                if text:
                    print(text)
                else:
                    print(json.dumps(obj, indent=2))
            if text is not None:
                messages.append({"role": "user", "content": to_send_user})
                messages.append({"role": "assistant", "content": text})
                sys_msgs = [m for m in messages if m.get("role") == "system"]
                to_log = (sys_msgs[-1:] if sys_msgs else []) + [
                    {"role": "user", "content": to_send_user},
                    {"role": "assistant", "content": text},
                ]
                logger.log_turn(to_log)
            return text

    # Non-interactive one-shot if stdin is piped and no --user provided
    if args.user is None and not sys.stdin.isatty():
        initial = sys.stdin.read().strip()
        if initial:
            one_turn(initial)
        return 0

    # Optional initial user message via flag
    if args.user:
        one_turn(args.user)

    # Interactive loop
    print(color("Type 'exit' or 'quit' to end. Use /reset to clear context.", fg="yellow"))
    try:
        while True:
            try:
                prompt = input(color("You:", fg="cyan", bold=True) + " ").strip()
            except EOFError:
                break
            if not prompt:
                continue
            if prompt.lower() in {"exit", "quit"}:
                break
            if prompt.strip() == "/reset":
                # Reset to just system message if present
                messages = []
                if args.system:
                    messages.append({"role": "system", "content": args.system})
                print(color("Context reset.", fg="yellow"))
                continue

            print("\n" + color("Noctics Central:", fg="green", bold=True) + " ", end="", flush=True)
            one_turn(prompt)
    except KeyboardInterrupt:
        print("\n" + color("Interrupted.", fg="yellow"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
