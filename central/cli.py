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
from .core import ChatClient, compute_title_from_messages, load_session_messages
from .commands.completion import setup_completions
from .commands.helper import (
    manual_helper_stream,
    process_helper_result,
    manual_central_stream,
    extract_helper_query,
    print_sanitized_helper_query,
)
from .commands.sessions import (
    list_sessions as cmd_list_sessions,
    print_sessions as cmd_print_sessions,
    resolve_by_ident_or_index as cmd_resolve_by_ident_or_index,
    load_into_context as cmd_load_into_context,
    rename_session as cmd_rename_session,
    merge_sessions as cmd_merge_sessions,
    latest_session as cmd_latest_session,
    print_latest_session as cmd_print_latest_session,
    archive_early_sessions as cmd_archive_early_sessions,
    show_session as cmd_show_session,
    browse_sessions as cmd_browse_sessions,
)
from .commands.help_cmd import print_help as cmd_print_help
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
    parser = argparse.ArgumentParser(
        description="Interactive Chat Completions CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --stream\n"
            "  python main.py --manual\n"
            "  python main.py --helper claude --stream\n"
            "  python main.py --user 'Explain X' --stream\n"
            "  python main.py --messages msgs.json --stream\n"
            "  python main.py --sessions-ls\n"
            "  python main.py --sessions-load session-20250913-234409\n"
            "  python main.py --sessions-rename session-20250914-010016 'My Title'\n"
        ),
    )
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
    parser.add_argument(
        "--sessions-latest",
        dest="sessions_latest",
        action="store_true",
        help="Show the most recently updated session and exit",
    )
    parser.add_argument(
        "--sessions-archive-early",
        dest="sessions_archive_early",
        action="store_true",
        help="Merge all but the latest session into memory/early-archives and exit",
    )
    parser.add_argument(
        "--sessions-browse",
        dest="sessions_browse",
        action="store_true",
        help="Interactively browse saved sessions and view their contents",
    )
    parser.add_argument(
        "--sessions-show",
        metavar="ID_OR_PATH",
        dest="sessions_show",
        default=None,
        help="Pretty-print the contents of a saved session and exit",
    )
    parser.add_argument(
        "--user-name",
        dest="user_name",
        default=os.getenv("CENTRAL_USER_NAME", "You"),
        help="Name to display for your prompt label (env CENTRAL_USER_NAME)",
    )
    parser.add_argument(
        "--bypass-helper",
        dest="bypass_helper",
        action="store_true",
        help="Bypass Central->Helper stitching; you act as Central and paste the final reply",
    )
    # Helper anonymization toggle (default on unless CENTRAL_HELPER_ANON=0/false)
    default_anon = (os.getenv("CENTRAL_HELPER_ANON", "1").lower() not in {"0", "false", "off", "no"})
    parser.add_argument(
        "--anon-helper",
        dest="anon_helper",
        action="store_true",
        default=default_anon,
        help="Also show a sanitized [HELPER QUERY] block for copy/paste",
    )
    parser.add_argument(
        "--no-anon-helper",
        dest="anon_helper",
        action="store_false",
        help="Disable sanitized helper-query output",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    # Load environment from a local .env file by default
    load_local_dotenv(Path(__file__).resolve().parent)

    args = parse_args(argv)

    # Session management commands (non-interactive)
    if args.sessions_ls:
        items = cmd_list_sessions()
        if not items:
            print("No sessions found.")
            return 0
        cmd_print_sessions(items)
        print("\nTip: load by index with --sessions-load N")
        return 0

    if args.sessions_rename is not None:
        ident, new_title = args.sessions_rename
        ok = cmd_rename_session(ident, new_title)
        return 0 if ok else 1

    if args.sessions_merge is not None:
        # Accept indices and ids; allow comma-separated in args
        raw_tokens: List[str] = []
        for tok in args.sessions_merge:
            raw_tokens.extend([t for t in tok.split(",") if t])
        if not raw_tokens:
            print("No sessions specified to merge.")
            return 1
        out = cmd_merge_sessions(raw_tokens)
        if out is None:
            return 1
        return 0

    if args.sessions_latest:
        latest = cmd_latest_session()
        if not latest:
            print("No sessions found.")
            return 0
        cmd_print_latest_session(latest)
        return 0

    if args.sessions_archive_early:
        out = cmd_archive_early_sessions()
        return 0 if out else 1

    if args.sessions_show:
        ok = cmd_show_session(args.sessions_show, raw=bool(args.raw))
        return 0 if ok else 1

    if args.sessions_browse:
        cmd_browse_sessions()
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
        # Allow numeric index or explicit path
        path: Optional[Path] = None
        if str(args.sessions_load).isdigit():
            items = cmd_list_sessions()
            idx = int(args.sessions_load)
            if 1 <= idx <= len(items):
                path = Path(items[idx - 1]["path"])  # type: ignore[index]
        if path is None:
            candidate = Path(args.sessions_load)
            if candidate.exists():
                path = candidate
        if path is None:
            path = cmd_resolve_by_ident_or_index(str(args.sessions_load))
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

    title_confirmed = bool(client.get_session_title())
    first_prompt_handled = any(m.get("role") == "user" for m in client.messages)

    def prepare_first_prompt_text(user_text: str, *, allow_interactive: bool) -> str:
        nonlocal title_confirmed, first_prompt_handled
        if first_prompt_handled:
            return user_text

        proposed_title = compute_title_from_messages(client.messages + [{"role": "user", "content": user_text}])

        if not title_confirmed:
            if allow_interactive and sys.stdin.isatty():
                if proposed_title:
                    print(color(f"Proposed session title: {proposed_title}", fg="yellow"))
                else:
                    print(color("Proposed session title: (unable to summarize)", fg="yellow"))

                try:
                    extra = input(color("Add clarifications (optional, press Enter to skip): ", fg="yellow"))
                except EOFError:
                    extra = ""
                if extra.strip():
                    user_text = f"{user_text}\n\nClarification: {extra.strip()}"
                    proposed_title = compute_title_from_messages(
                        client.messages + [{"role": "user", "content": user_text}]
                    ) or proposed_title

                prompt = "Session title"
                if proposed_title:
                    prompt += f" [{proposed_title}]"
                prompt += ": "
                try:
                    resp = input(color(prompt, fg="yellow"))
                except EOFError:
                    resp = ""
                resp = resp.strip()
                if resp:
                    client.set_session_title(resp, custom=True)
                    print(color(f"Session titled: {resp}", fg="yellow"))
                    title_confirmed = True
                elif proposed_title:
                    client.set_session_title(proposed_title, custom=False)
                    print(color(f"Session title set: {proposed_title}", fg="yellow"))
                    title_confirmed = True
                else:
                    title_confirmed = True
            else:
                if proposed_title:
                    client.set_session_title(proposed_title, custom=False)
                    print(color(f"Session title set: {proposed_title}", fg="yellow"))
                    title_confirmed = True

        first_prompt_handled = True
        return user_text

    # ----------
    # Tab completion (interactive only)
    # ----------
    setup_completions()

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
            print("\n" + color("Noctics Central (processing helper):", fg="#ffefff", bold=True) + " ", end="", flush=True)
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
                if args.anon_helper:
                    q = extract_helper_query(assistant)
                    if q:
                        print_sanitized_helper_query(q, user_name=args.user_name)
                # Prompt to choose a helper if none set
                if not args.helper:
                    from .commands.helper import choose_helper_interactively

                    chosen = choose_helper_interactively(args.helper)
                    if chosen and chosen != args.helper:
                        args.helper = chosen
                        print(color(f"Helper set to '{args.helper}'.", fg="yellow"))
                helper_text = manual_helper_stream(args.helper)
                if args.bypass_helper:
                    central_reply = manual_central_stream(args.helper)
                    if central_reply:
                        wrapped = f"[HELPER RESULT]\n{helper_text}\n[/HELPER RESULT]"
                        client.record_turn(wrapped, central_reply)
                        print(central_reply)
                        return central_reply
                    return assistant
                final_assistant = process_helper_result(client=client, helper_text=helper_text, stream=bool(args.stream), on_delta=_printer())
                if final_assistant is not None:
                    return final_assistant
            return assistant
        else:
            assistant = client.one_turn(user_text)
            if assistant is not None:
                print(assistant)
                if ChatClient.wants_helper(assistant):
                    if args.anon_helper:
                        q = extract_helper_query(assistant)
                        if q:
                            print_sanitized_helper_query(q, user_name=args.user_name)
                    # Prompt to choose a helper if none set
                    if not args.helper:
                        from .commands.helper import choose_helper_interactively

                        chosen = choose_helper_interactively(args.helper)
                        if chosen and chosen != args.helper:
                            args.helper = chosen
                            print(color(f"Helper set to '{args.helper}'.", fg="yellow"))
                    helper_text = manual_helper_stream(args.helper)
                    if args.bypass_helper:
                        central_reply = manual_central_stream(args.helper)
                        if central_reply:
                            wrapped = f"[HELPER RESULT]\n{helper_text}\n[/HELPER RESULT]"
                            client.record_turn(wrapped, central_reply)
                            print(central_reply)
                            return central_reply
                        return assistant
                    final_text = process_helper_result(client=client, helper_text=helper_text, stream=bool(args.stream), on_delta=_printer())
                    if final_text is not None:
                        return final_text
            return assistant

    # Non-interactive one-shot if stdin is piped and no --user provided
    if args.user is None and not sys.stdin.isatty():
        initial = sys.stdin.read().strip()
        if initial:
            initial = prepare_first_prompt_text(initial, allow_interactive=False)
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
        initial_user = prepare_first_prompt_text(args.user, allow_interactive=False)
        one_turn(initial_user)

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
        print(color("  /name NAME     set the input prompt label (default: You)", fg="yellow"))
        print(color("Docs: README.md, docs/CLI.md, docs/SESSIONS.md, docs/HELPERS.md", fg="yellow"))
        print(color("Tip: run with --help to see all CLI flags.", fg="yellow"))

    cmd_print_help(client, user_name=args.user_name)
    if sys.stdin.isatty() and readline is not None:
        print(color("[Tab completion enabled: type '/' then press Tab]", fg="yellow"))
    try:
        while True:
            try:
                prompt = input(color(f"{args.user_name}:", fg="cyan", bold=True) + " ").strip()
            except EOFError:
                break
            if not prompt:
                continue
            if prompt.lower() in {"exit", "quit"}:
                break
            if prompt.lower() in {"/help", "help", "/?", "/h"}:
                cmd_print_help(client, user_name=args.user_name)
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

            if prompt.startswith("/bypass") or prompt.strip() in {"/bypass-helper", "/act-as-central", "/iam-central"}:
                tokens = prompt.split()
                if len(tokens) == 1:
                    args.bypass_helper = not bool(args.bypass_helper)
                else:
                    val = tokens[1].lower()
                    args.bypass_helper = val in {"1", "true", "on", "yes"}
                state = "ON" if args.bypass_helper else "OFF"
                print(color(f"Bypass helper stitching: {state}", fg="yellow"))
                continue

            if prompt.startswith("/name "):
                new_name = prompt.split(maxsplit=1)[1].strip()
                if new_name:
                    args.user_name = new_name
                    print(color(f"Prompt label set to: {args.user_name}", fg="yellow"))
                continue

            if prompt.startswith("/anon") or prompt.strip() in {"/anon-helper", "/anon"}:
                tokens = prompt.split()
                if len(tokens) == 1:
                    args.anon_helper = not bool(args.anon_helper)
                else:
                    val = tokens[1].lower()
                    args.anon_helper = val in {"1", "true", "on", "yes"}
                state = "ON" if args.anon_helper else "OFF"
                print(color(f"Helper anonymization: {state}", fg="yellow"))
                continue

            if prompt.strip() in {"/sessions", "/ls", "/sessions-ls", "/list", "/list-sessions"}:
                items = cmd_list_sessions()
                cmd_print_sessions(items)
                print(color("Tip: load by index: /load N", fg="yellow"))
                continue

            if prompt.strip() in {"/last", "/latest", "/recent"}:
                latest = cmd_latest_session()
                if not latest:
                    print(color("No sessions found.", fg="yellow"))
                else:
                    cmd_print_latest_session(latest)
                continue

            if prompt.strip() in {"/archive", "/archive-early", "/archive-old"}:
                cmd_archive_early_sessions()
                continue

            if prompt.startswith("/show "):
                ident = prompt.split(maxsplit=1)[1].strip()
                if not cmd_show_session(ident):
                    continue
                continue

            if prompt.strip() in {"/browse", "/sessions-browse"}:
                cmd_browse_sessions()
                continue

            if prompt.startswith("/load "):
                ident = prompt.split(maxsplit=1)[1].strip()
                loaded = cmd_load_into_context(ident, messages=messages)
                if not loaded:
                    continue
                messages = loaded
                client.set_messages(messages)
                sys_msgs = [m for m in messages if m.get("role") == "system"]
                args.system = sys_msgs[0].get("content") if sys_msgs else None
                # print name by resolving for display
                p = cmd_resolve_by_ident_or_index(ident)
                print(color(f"Loaded session: {p.stem if p else ident}", fg="yellow"))
                continue

            if prompt.strip() == "/load":
                items = cmd_list_sessions()
                if not items:
                    print(color("No sessions found.", fg="yellow"))
                    continue
                cmd_print_sessions(items)
                try:
                    selection = input(color("Select session number (Enter to cancel): ", fg="yellow")).strip()
                except EOFError:
                    print()
                    continue
                if not selection or selection.lower() in {"q", "quit", "exit"}:
                    continue
                loaded = cmd_load_into_context(selection, messages=messages)
                if not loaded:
                    continue
                messages = loaded
                client.set_messages(messages)
                sys_msgs = [m for m in messages if m.get("role") == "system"]
                args.system = sys_msgs[0].get("content") if sys_msgs else None
                p = cmd_resolve_by_ident_or_index(selection)
                display = p.stem if p else selection
                print(color(f"Loaded session: {display}", fg="yellow"))
                continue

            if prompt.startswith("/merge "):
                rest = prompt.split(maxsplit=1)[1].strip()
                if not rest:
                    print(color("Usage: /merge ID [ID ...] (supports indices)", fg="yellow"))
                    continue
                tokens = [t for part in rest.split() for t in part.split(",") if t]
                cmd_merge_sessions(tokens)
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
                if not cmd_rename_session(ident, new_title.strip()):
                    continue
                continue

            if prompt in {"/result", "/helper-result", "/paste-helper", "/hr"}:
                # Explicitly paste a helper response and send it for stitching
                helper_text = manual_helper_stream(args.helper)
                if args.bypass_helper:
                    central_reply = manual_central_stream(args.helper)
                    if central_reply:
                        wrapped = f"[HELPER RESULT]\n{helper_text}\n[/HELPER RESULT]"
                        client.record_turn(wrapped, central_reply)
                        print(central_reply)
                else:
                    process_helper_result(client=client, helper_text=helper_text, stream=bool(args.stream), on_delta=_printer())
                continue

            helper_suffix = f" [{args.helper}]" if args.helper else ""
            prompt_text = prepare_first_prompt_text(prompt, allow_interactive=True)
            print("\n" + color(f"Noctics Central{helper_suffix}:", fg="#ffefff", bold=True) + " ", end="", flush=True)
            one_turn(prompt_text)
    except KeyboardInterrupt:
        print("\n" + color("Interrupted.", fg="yellow"))
    finally:
        deleted = False
        # Auto-generate a session title if not user-provided
        try:
            title = client.ensure_auto_title()
            if title:
                print(color(f"Saved session title: {title}", fg="yellow"))
            else:
                if client.maybe_delete_empty_session():
                    print(color("Session empty; removed log.", fg="yellow"))
                    deleted = True
        except Exception:
            pass
        if not deleted:
            try:
                day_log = client.append_session_to_day_log()
                if day_log:
                    print(color(f"Appended session to {day_log}", fg="yellow"))
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
