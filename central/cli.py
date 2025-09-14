"""
Interactive CLI to talk to a local OpenAI-like chat completions endpoint.

Defaults mirror the provided curl and post to http://localhost:1234/v1/chat/completions.
Supports both non-streaming and streaming (SSE) responses via --stream.
Optionally supports a manual "helper" workflow where, instead of calling
an API, you select a helper and paste the helper's response.

No external dependencies (stdlib only).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, Any, List, Optional, Tuple
import shlex
try:
    import readline  # type: ignore
except Exception:  # pragma: no cover - platform without readline
    readline = None  # type: ignore
from pathlib import Path
# No direct HTTP in the CLI; core handles requests
from .colors import color
from .core import (
    ChatClient,
    list_sessions,
    resolve_session,
    load_session_messages,
    set_session_title_for,
    merge_sessions_paths,
)
from interfaces.dotenv import load_local_dotenv


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


def _printer():
    def emit(piece: str) -> None:
        print(piece, end="", flush=True)
    return emit


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive Chat Completions CLI")
    parser.add_argument(
        "--url",
        default=os.getenv("CENTRAL_LLM_URL", DEFAULT_URL),
        help="Endpoint URL (env CENTRAL_LLM_URL)",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("CENTRAL_LLM_MODEL", "qwen/qwen3-1.7b"),
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
    parser.add_argument(
        "--helper",
        default=None,
        help=(
            "Optional helper name. When set, API calls are skipped and you will be "
            "prompted to paste the external helper's response manually."
        ),
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help=(
            "Manual response mode. Skip API calls and prompt to paste the assistant/" 
            "helper response each turn. If --helper is provided, it implies --manual."
        ),
    )
    parser.add_argument(
        "--sessions-ls",
        "--sessions",
        "--list-sessions",
        "--ls",
        "--seeessions-ls",  # friendly alias for common typo
        dest="sessions_ls",
        action="store_true",
        help="List saved sessions with titles and exit",
    )
    parser.add_argument(
        "--sessions-load",
        metavar="ID_OR_PATH",
        default=None,
        help="Load a session's messages before starting chat (by id or path)",
    )
    parser.add_argument(
        "--sessions-rename",
        nargs=2,
        metavar=("ID_OR_PATH", "NEW_TITLE"),
        default=None,
        help="Rename (retitle) a saved session and exit",
    )
    parser.add_argument(
        "--sessions-merge",
        nargs="+",
        metavar="ID_OR_INDEX",
        default=None,
        help="Merge sessions (ids or indices) into a new merged folder and exit",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    # Load environment from a local .env file by default
    load_local_dotenv(Path(__file__).resolve().parent)

    args = parse_args(argv)

    # Session management commands (non-interactive)
    if args.sessions_ls:
        items = list_sessions()
        if not items:
            print("No sessions found.")
            return 0
        # Print compact list: index, id, turns, title
        for i, it in enumerate(items, 1):
            ident = it.get("id")
            turns = it.get("turns")
            title = it.get("title") or "(untitled)"
            print(f"{i:>2}. {ident}  [turns:{turns}]  {title}")
        print("\nTip: load by index with --sessions-load N")
        return 0

    if args.sessions_rename is not None:
        ident, new_title = args.sessions_rename
        # Allow numeric index from latest list ordering
        path = None
        if ident.isdigit():
            items = list_sessions()
            idx = int(ident)
            if 1 <= idx <= len(items):
                path = Path(items[idx - 1]["path"])  # type: ignore[index]
        if path is None:
            path = resolve_session(ident)
        if not path:
            print(f"Could not find session for: {ident}")
            return 1
        set_session_title_for(path, new_title, custom=True)
        print(f"Renamed session {path.stem} -> '{new_title}'")
        return 0

    if args.sessions_merge is not None:
        # Accept indices and ids; allow comma-separated in args
        raw_tokens: List[str] = []
        for tok in args.sessions_merge:
            raw_tokens.extend([t for t in tok.split(",") if t])
        if not raw_tokens:
            print("No sessions specified to merge.")
            return 1
        items = list_sessions()
        paths: List[Path] = []
        for ident in raw_tokens:
            p: Optional[Path] = None
            if ident.isdigit():
                idx = int(ident)
                if 1 <= idx <= len(items):
                    p = Path(items[idx - 1]["path"])  # type: ignore[index]
            if p is None:
                p = resolve_session(ident)
            if not p:
                print(f"Skipping unknown session: {ident}")
                continue
            paths.append(p)
        if len(paths) < 2:
            print("Need at least two sessions to merge.")
            return 1
        out = merge_sessions_paths(paths)
        print(f"Merged into: {out}")
        return 0

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

    # Optionally load a saved session as starting context
    if args.sessions_load:
        # Allow numeric index from latest list ordering
        path = None
        if str(args.sessions_load).isdigit():
            items = list_sessions()
            idx = int(args.sessions_load)
            if 1 <= idx <= len(items):
                path = Path(items[idx - 1]["path"])  # type: ignore[index]
        if path is None:
            path = resolve_session(args.sessions_load)
        if not path:
            raise SystemExit(f"--sessions-load: not found: {args.sessions_load}")
        loaded = load_session_messages(path)
        if loaded:
            messages = loaded
            # Reset system prompt text to what's in loaded messages (for display)
            sys_msgs = [m for m in messages if m.get("role") == "system"]
            if sys_msgs:
                args.system = sys_msgs[0].get("content")
        print(color(f"Loaded session: {path.stem}", fg="yellow"))

    # Determine and display system prompt at startup (colored)
    sys_prompt_text: Optional[str] = None
    if args.messages_file:
        # Take the last system message if present
        sys_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "system"]
        if sys_msgs:
            sys_prompt_text = str(sys_msgs[-1].get("content", "")).strip() or None
    else:
        sys_prompt_text = args.system

    if sys_prompt_text:
        print(color("System Prompt:", fg="magenta", bold=True))
        print(color(sys_prompt_text, fg="magenta"))
        print()

    # Core client: importable functions live in central.core
    client = ChatClient(
        url=args.url,
        model=args.model,
        api_key=args.api_key,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        stream=bool(args.stream),
        sanitize=bool(args.sanitize),
        messages=messages,
        enable_logging=True,
    )

    # ----------
    # Tab completion (interactive only)
    # ----------
    def _setup_completions() -> None:
        if not sys.stdin.isatty() or readline is None:
            return

        commands = [
            "/help",
            "/reset",
            "/sessions",
            "/ls",
            "/result",
            "/helper",
            "/load",
            "/title",
            "/rename",
            "/merge",
        ]

        # Helpers list from env var CENTRAL_HELPERS=comma,separated
        env_helpers = [s.strip() for s in (os.getenv("CENTRAL_HELPERS") or "").split(",") if s.strip()]
        default_helpers = ["claude", "o3", "gpt-4o", "sonnet", "llama", "mistral"]
        helper_candidates = env_helpers or default_helpers

        def complete(text: str, state: int) -> Optional[str]:
            try:
                line = readline.get_line_buffer()  # type: ignore[attr-defined]
                beg = readline.get_begidx()  # type: ignore[attr-defined]
            except Exception:
                line, beg = "", 0

            # Default: suggest commands starting with text when starting with '/'
            if not line or line.startswith("/") and (" " not in line[:beg]):
                matches = [c for c in commands if c.startswith(text or "")]
                return matches[state] if state < len(matches) else None

            # Parse the command and args region
            head = line.split(" ", 1)[0]
            arg_region = line[len(head):]
            arg_text = arg_region.lstrip()
            arg_index = 0 if not arg_text or arg_text.endswith(" ") else len(arg_text.split()) - 1

            # /helper <NAME>
            if head == "/helper":
                if beg >= len(head) + 1:  # in argument region
                    matches = [h for h in helper_candidates if h.startswith(text or "")]
                    return matches[state] if state < len(matches) else None
                return None

            # Build session-based suggestions (indexes and ids)
            def session_suggestions() -> List[str]:
                items = list_sessions()
                out: List[str] = []
                # 1-based indices
                out.extend([str(i) for i in range(1, len(items) + 1)])
                # ids (stems)
                out.extend([it.get("id") for it in items if it.get("id")])
                return [s for s in out if s]

            if head in {"/load", "/rename", "/merge"}:
                # Only complete first argument (identifier); title is free-form for /rename
                if beg >= len(head) + 1 and arg_index == 0:
                    candidates = session_suggestions()
                    matches = [c for c in candidates if c.startswith(text or "")]
                    return matches[state] if state < len(matches) else None
                return None

            # For other commands, no special completion
            return None

        try:
            readline.parse_and_bind("tab: complete")  # type: ignore[attr-defined]
            # Make '/' a word break trigger
            if hasattr(readline, "set_completer_delims"):
                delims = readline.get_completer_delims()  # type: ignore[attr-defined]
                # Keep default delims
                readline.set_completer_delims(delims)
            readline.set_completer(complete)  # type: ignore[attr-defined]
        except Exception:
            pass

    _setup_completions()

    def _manual_helper_stream(helper_name: Optional[str]) -> str:
        """Collect helper output interactively, echoing as a stream.

        User types/pastes lines; each line is echoed immediately. Typing
        a single END line finishes input. Returns the concatenated text.
        """
        helper_label = f" [{helper_name}]" if helper_name else ""
        print(color(f"Helper{helper_label}:", fg="blue", bold=True) + " ", end="", flush=True)
        print(
            color(
                "(paste streaming lines; type END on its own line to finish)",
                fg="yellow",
            )
        )
        collected: List[str] = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == "END":
                break
            # Echo the line as part of the stream
            print(line)
            collected.append(line)
        return "\n".join(collected).strip()

    def _process_helper_result(helper_text: str) -> Optional[str]:
        if not helper_text:
            return None
        if args.stream:
            print("\n" + color("Noctics Central (processing helper):", fg="green", bold=True) + " ", end="", flush=True)
            reply = client.process_helper_result(helper_text, on_delta=_printer())
            print()
            return reply
        else:
            reply = client.process_helper_result(helper_text)
            if reply is not None:
                print(reply)
            return reply

    # Helper to perform a single turn given a user prompt
    def one_turn(user_text: str) -> Optional[str]:
        # Determine if we're in manual paste mode
        manual_mode = bool(args.manual or args.helper)

        if manual_mode:
            helper_label = f" [{args.helper}]" if args.helper else ""
            print()
            print(
                color(
                    f"Manual mode{helper_label}: paste external response, then type END on its own line.",
                    fg="yellow",
                )
            )
            pasted_lines: List[str] = []
            while True:
                try:
                    line = input()
                except EOFError:
                    break
                if line.strip() == "END":
                    break
                pasted_lines.append(line)
            text = "\n".join(pasted_lines).strip()
            if text:
                print(text)
                client.record_turn(user_text, text)
            return text or None

        # Normal API mode via core client
        if args.stream:
            assistant = client.one_turn(user_text, on_delta=_printer())
            print()
            if assistant is not None and ChatClient.wants_helper(assistant):
                helper_text = _manual_helper_stream(args.helper)
                final_assistant = _process_helper_result(helper_text)
                if final_assistant is not None:
                    return final_assistant
            return assistant
        else:
            assistant = client.one_turn(user_text)
            if assistant is not None:
                print(assistant)
                if ChatClient.wants_helper(assistant):
                    helper_text = _manual_helper_stream(args.helper)
                    final_text = _process_helper_result(helper_text)
                    if final_text is not None:
                        return final_text
            return assistant

    # Non-interactive one-shot if stdin is piped and no --user provided
    if args.user is None and not sys.stdin.isatty():
        initial = sys.stdin.read().strip()
        if initial:
            one_turn(initial)
        # Auto title for non-interactive runs
        try:
            title = client.ensure_auto_title()
            if title:
                print(color(f"Saved session title: {title}", fg="yellow"))
        except Exception:
            pass
        return 0

    # Optional initial user message via flag
    if args.user:
        one_turn(args.user)

    # Interactive loop
    def _print_help() -> None:
        print(color("Type 'exit' or 'quit' to end. Use /reset to clear context.", fg="yellow"))
        lp = client.log_path()
        if lp:
            print(color(f"Logging session to: {lp}", fg="yellow"))
        print(color("Commands:", fg="yellow"))
        print(color("  /help          show this help", fg="yellow"))
        print(color("  /helper NAME   set helper label & enable paste", fg="yellow"))
        print(color("  /helper        clear helper label", fg="yellow"))
        print(color("  /result        paste a Helper Result to stitch", fg="yellow"))
        print(color("  /sessions      list saved sessions with titles", fg="yellow"))
        print(color("  /load ID       load a session by id", fg="yellow"))
        print(color("  /title NAME    set current session title", fg="yellow"))
        print(color("  /rename ID T   rename a saved session's title", fg="yellow"))
        print(color("  /merge A B..   merge sessions by ids or indices", fg="yellow"))
        print(color("  /reset         reset context to just the system message", fg="yellow"))
        print(color("Docs: README.md, docs/CLI.md, docs/SESSIONS.md, docs/HELPERS.md", fg="yellow"))
        print(color("Tip: run with --help to see all CLI flags.", fg="yellow"))

    _print_help()
    if sys.stdin.isatty() and readline is not None:
        print(color("[Tab completion enabled: type '/' then press Tab]", fg="yellow"))
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
            if prompt.lower() in {"/help", "help", "/?", "/h"}:
                _print_help()
                continue
            if prompt.strip() == "/reset":
                # Reset to just system message if present
                client.reset_messages(system=args.system)
                print(color("Context reset.", fg="yellow"))
                continue
            if prompt.startswith("/helper"):
                parts = prompt.split(maxsplit=1)
                if len(parts) == 1:
                    # Clear helper and disable manual if it was only implied by helper
                    args.helper = None
                    print(color("Helper cleared. API mode restored (unless --manual).", fg="yellow"))
                else:
                    args.helper = parts[1].strip()
                    print(color(f"Helper set to '{args.helper}'. Manual paste mode enabled.", fg="yellow"))
                continue

            if prompt.strip() in {"/sessions", "/ls", "/sessions-ls", "/list", "/list-sessions"}:
                items = list_sessions()
                if not items:
                    print(color("No sessions found.", fg="yellow"))
                else:
                    for i, it in enumerate(items, 1):
                        ident = it.get("id")
                        turns = it.get("turns")
                        title = it.get("title") or "(untitled)"
                        print(f"{i:>2}. {ident}  [turns:{turns}]  {title}")
                    print(color("Tip: load by index: /load N", fg="yellow"))
                continue

            if prompt.startswith("/load "):
                ident = prompt.split(maxsplit=1)[1].strip()
                # Numeric index support relative to latest ordering
                path = None
                if ident.isdigit():
                    items = list_sessions()
                    idx = int(ident)
                    if 1 <= idx <= len(items):
                        path = Path(items[idx - 1]["path"])  # type: ignore[index]
                if path is None:
                    path = resolve_session(ident)
                if not path:
                    print(color(f"No session found for: {ident}", fg="red"))
                    continue
                loaded = load_session_messages(path)
                if not loaded:
                    print(color("Session is empty or unreadable.", fg="red"))
                    continue
                messages = loaded
                client.set_messages(messages)
                sys_msgs = [m for m in messages if m.get("role") == "system"]
                args.system = sys_msgs[0].get("content") if sys_msgs else None
                print(color(f"Loaded session: {path.stem}", fg="yellow"))
                continue

            if prompt.startswith("/merge "):
                rest = prompt.split(maxsplit=1)[1].strip()
                if not rest:
                    print(color("Usage: /merge ID [ID ...] (supports indices)", fg="yellow"))
                    continue
                tokens = [t for part in rest.split() for t in part.split(",") if t]
                items = list_sessions()
                paths: List[Path] = []
                for ident in tokens:
                    p: Optional[Path] = None
                    if ident.isdigit():
                        idx = int(ident)
                        if 1 <= idx <= len(items):
                            p = Path(items[idx - 1]["path"])  # type: ignore[index]
                    if p is None:
                        p = resolve_session(ident)
                    if not p:
                        print(color(f"Skipping unknown session: {ident}", fg="red"))
                        continue
                    paths.append(p)
                if len(paths) < 2:
                    print(color("Need at least two sessions to merge.", fg="yellow"))
                    continue
                out = merge_sessions_paths(paths)
                print(color(f"Merged into: {out}", fg="yellow"))
                continue
            if prompt.startswith("/title "):
                title = prompt.split(maxsplit=1)[1].strip()
                # Set title on the current active session
                if title:
                    # Use ChatClient to persist on current logger
                    # Note: this names the active session, not a past one
                    try:
                        client.set_session_title(title, custom=True)
                        print(color(f"Session titled: {title}", fg="yellow"))
                    except Exception:
                        print(color("Failed to set session title.", fg="red"))
                continue

            if prompt.startswith("/rename "):
                rest = prompt.split(maxsplit=1)[1]
                ident, sep, new_title = rest.partition(" ")
                if not sep or not new_title.strip():
                    print(color("Usage: /rename ID New Title", fg="yellow"))
                    continue
                # Numeric index support relative to latest ordering
                path = None
                if ident.isdigit():
                    items = list_sessions()
                    idx = int(ident)
                    if 1 <= idx <= len(items):
                        path = Path(items[idx - 1]["path"])  # type: ignore[index]
                if path is None:
                    path = resolve_session(ident)
                if not path:
                    print(color(f"No session found for: {ident}", fg="red"))
                    continue
                set_session_title_for(path, new_title.strip(), custom=True)
                print(color(f"Renamed session {path.stem} -> '{new_title.strip()}'", fg="yellow"))
                continue

            if prompt in {"/result", "/helper-result", "/paste-helper", "/hr"}:
                # Explicitly paste a helper response and send it for stitching
                helper_text = _manual_helper_stream(args.helper)
                _process_helper_result(helper_text)
                continue

            helper_suffix = f" [{args.helper}]" if args.helper else ""
            print("\n" + color(f"Noctics Central{helper_suffix}:", fg="green", bold=True) + " ", end="", flush=True)
            one_turn(prompt)
    except KeyboardInterrupt:
        print("\n" + color("Interrupted.", fg="yellow"))
    finally:
        # Auto-generate a session title if not user-provided
        try:
            title = client.ensure_auto_title()
            if title:
                print(color(f"Saved session title: {title}", fg="yellow"))
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
