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
import re
import subprocess
import sys
from typing import Dict, Any, List, Optional, Tuple
try:
    import readline  # type: ignore
except Exception:  # pragma: no cover - platform without readline
    readline = None  # type: ignore
from pathlib import Path
# No direct HTTP in the CLI; core handles requests
from .colors import color
from .core import ChatClient
from .runtime_identity import (
    RuntimeIdentity as _RuntimeIdentity,
    resolve_runtime_identity as _resolve_runtime_identity,
)
from noxl import compute_title_from_messages, load_session_messages
from .commands.completion import setup_completions
from .commands.helper import (
    choose_helper_interactively,
    describe_helper_status,
    helper_automation_enabled,
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
from .system_info import hardware_summary

RuntimeIdentity = _RuntimeIdentity
resolve_runtime_identity = _resolve_runtime_identity

__all__ = ["main", "parse_args", "RuntimeIdentity", "resolve_runtime_identity"]


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
            "  python main.py --helper claude --stream\n"
            "  python main.py --user 'Explain X' --stream\n"
            "  python main.py --messages msgs.json --stream\n"
            "  python main.py --sessions-ls\n"
            "  python main.py --sessions-load session-20250913-234409\n"
            "  python main.py --sessions-rename session-20250914-010016 'My Title'\n"
        ),
    )
    parser.add_argument(
        "-U", "--url",
        default=os.getenv("CENTRAL_LLM_URL", DEFAULT_URL),
        help="Endpoint URL (env CENTRAL_LLM_URL)",
    )
    parser.add_argument(
        "-M", "--model",
        default=os.getenv("CENTRAL_LLM_MODEL", "qwen/qwen3-1.7b"),
        help="Model name (env CENTRAL_LLM_MODEL)",
    )
    parser.add_argument(
        "-S", "--system",
        default=None,
        help="System message (defaults to memory/system_prompt.txt; ignored if --messages is used)",
    )
    parser.add_argument("-u", "--user", default=None, help="Optional initial user message")
    parser.add_argument(
        "-F", "--messages",
        dest="messages_file",
        default=None,
        help="Path to JSON file containing a messages array to send",
    )
    parser.add_argument("-t", "--temperature", type=float, default=0.7, help="Sampling temperature")
    parser.add_argument(
        "-T", "--max-tokens",
        dest="max_tokens",
        type=int,
        default=-1,
        help="Max tokens (-1 for unlimited if supported)",
    )
    parser.add_argument(
        "-s",
        "--stream",
        dest="stream",
        action="store_true",
        default=None,
        help="Enable streaming (SSE)",
    )
    parser.add_argument(
        "--no-stream",
        dest="stream",
        action="store_false",
        help="Disable streaming (skips the interactive prompt)",
    )
    parser.add_argument(
        "-z", "--sanitize",
        action="store_true",
        help="Redact common PII from user text before sending",
    )
    parser.add_argument("-r", "--raw", action="store_true", help="Also print raw JSON in non-streaming mode")
    parser.add_argument(
        "--show-think",
        action="store_true",
        help="Include assistant <think> blocks in console output and session logs.",
    )
    parser.add_argument(
        "-k", "--api-key",
        default=(os.getenv("CENTRAL_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")),
        help="Optional API key for Authorization header (env CENTRAL_LLM_API_KEY | OPENAI_API_KEY)",
    )
    parser.add_argument(
        "-H", "--helper",
        default=None,
        help=(
            "Optional helper name label used when Central requests a helper; "
            "does not skip API calls."
        ),
    )
    parser.add_argument(
        "-L", "--sessions-ls",
        dest="sessions_ls",
        action="store_true",
        help="List saved sessions with titles and exit",
    )
    parser.add_argument(
        "-D", "--sessions-load",
        metavar="ID_OR_PATH",
        default=None,
        help="Load a session's messages before starting chat (by id or path)",
    )
    parser.add_argument(
        "-R", "--sessions-rename",
        nargs=2,
        metavar=("ID_OR_PATH", "NEW_TITLE"),
        default=None,
        help="Rename (retitle) a saved session and exit",
    )
    parser.add_argument(
        "-G", "--sessions-merge",
        nargs="+",
        metavar="ID_OR_INDEX",
        default=None,
        help="Merge sessions (ids or indices) into a new merged folder and exit",
    )
    parser.add_argument(
        "-E", "--sessions-latest",
        dest="sessions_latest",
        action="store_true",
        help="Show the most recently updated session and exit",
    )
    parser.add_argument(
        "-A", "--sessions-archive-early",
        dest="sessions_archive_early",
        action="store_true",
        help="Merge all but the latest session into memory/early-archives and exit",
    )
    parser.add_argument(
        "-B", "--sessions-browse",
        dest="sessions_browse",
        action="store_true",
        help="Interactively browse saved sessions and view their contents",
    )
    parser.add_argument(
        "-P", "--sessions-show",
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
        "--dev",
        action="store_true",
        help="Run as the project developer (skip user onboarding and log as developer)",
    )
    # Helper anonymization toggle (default on unless CENTRAL_HELPER_ANON=0/false)
    default_anon = (os.getenv("CENTRAL_HELPER_ANON", "1").lower() not in {"0", "false", "off", "no"})
    parser.add_argument(
        "--anon-helper",
        dest="anon_helper",
        action="store_true",
        default=default_anon,
        help="Reserved sanitization toggle for future helper integration",
    )
    parser.add_argument(
        "--no-anon-helper",
        dest="anon_helper",
        action="store_false",
        help="Disable the reserved helper sanitization toggle",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the Central version and exit",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    # Load environment from a local .env file by default
    load_local_dotenv(Path(__file__).resolve().parent)

    args = parse_args(argv)

    if getattr(args, "version", False):
        from .version import __version__

        print(__version__)
        return 0

    interactive = sys.stdin.isatty()
    original_label = (args.user_name or "").strip()
    identity = resolve_runtime_identity(
        dev_mode=bool(getattr(args, "dev", False)),
        initial_label=original_label,
        interactive=interactive,
    )
    args.user_name = identity.display_name
    if interactive:
        if getattr(args, "dev", False):
            print(color("Running in developer mode as Rei.", fg="yellow"))
        else:
            if identity.created_user:
                print(
                    color(
                        f"Registered user '{identity.display_name}' (id: {identity.user_id}).",
                        fg="yellow",
                    )
                )
            else:
                print(
                    color(
                        f"Signed in as '{identity.display_name}' (id: {identity.user_id}).",
                        fg="yellow",
                    )
                )

    if interactive:
        print(color(f"Helpers: {describe_helper_status()}", fg="yellow"))
    hardware_line = f"Hardware context: {hardware_summary()}"

    if args.stream is None:
        if interactive:
            prompt = color("Enable streaming? [y/N]: ", fg="yellow")
            try:
                choice = input(prompt).strip().lower()
            except EOFError:
                choice = ""
            args.stream = choice in {"y", "yes"}
        else:
            args.stream = False
    else:
        args.stream = bool(args.stream)

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
    session_path_to_adopt: Optional[Path] = None
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
        session_path_to_adopt = path
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

    # Inject identity context if not already present
    identity_line = identity.context_line()
    if identity_line:
        already_tagged = False
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "system":
                content = str(msg.get("content") or "")
                if identity_line in content:
                    already_tagged = True
                    break
        if not already_tagged:
            inserted = False
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                if isinstance(msg, dict) and msg.get("role") == "system":
                    content = str(msg.get("content") or "").strip()
                    content = (content + ("\n\n" if content else "") + identity_line).strip()
                    messages[i]["content"] = content
                    inserted = True
                    break
            if not inserted:
                messages.insert(0, {"role": "system", "content": identity_line})
            if args.system:
                content = args.system.strip()
                if identity_line not in content:
                    args.system = (content + ("\n\n" if content else "") + identity_line).strip()
            else:
                args.system = identity_line

    hardware_inserted = False
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "system":
            content = str(msg.get("content") or "")
            if hardware_line in content:
                hardware_inserted = True
                break
    if not hardware_inserted:
        inserted = False
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if isinstance(msg, dict) and msg.get("role") == "system":
                content = str(msg.get("content") or "").strip()
                content = (content + ("\n\n" if content else "") + hardware_line).strip()
                messages[i]["content"] = content
                inserted = True
                break
        if not inserted:
            messages.insert(0, {"role": "system", "content": hardware_line})
        if args.system:
            content = args.system.strip()
            if hardware_line not in content:
                args.system = (content + ("\n\n" if content else "") + hardware_line).strip()
        else:
            args.system = hardware_line
    if interactive:
        print(color(hardware_line, fg="yellow"))

    if (sys_prompt_text or identity_line):
        # Recompute for display after any identity injection
        if args.messages_file:
            sys_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "system"]
            sys_prompt_text = str(sys_msgs[-1].get("content", "")).strip() if sys_msgs else None
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
        strip_reasoning=not bool(args.show_think),
        memory_user=identity.user_id,
        memory_user_display=identity.display_name,
    )

    # Early connectivity check unless in helper-only mode
    if not args.helper:
        try:
            client.check_connectivity()
        except Exception as e:  # network-specific; present friendly guidance
            print(color("Warning: cannot reach Noctics Central.", fg="red", bold=True))
            print(color(f"{e}", fg="red"))
            print(
                color(
                    "Start your local OpenAI-compatible server on the configured URL and try again.",
                    fg="yellow",
                )
            )
            return 2

    def adopt_session(path: Path) -> None:
        nonlocal title_confirmed, first_prompt_handled
        client.maybe_delete_empty_session()
        client.adopt_session_log(path)
        title_confirmed = bool(client.get_session_title())
        first_prompt_handled = True

    if session_path_to_adopt is not None:
        adopt_session(session_path_to_adopt)

    title_confirmed = bool(client.get_session_title())
    first_prompt_handled = any(m.get("role") == "user" for m in client.messages)
    if session_path_to_adopt is not None:
        first_prompt_handled = True

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

    # Helper to perform a single turn given a user prompt
    def prompt_for_helper_reply() -> Optional[str]:
        print(color("Paste the helper's reply. Enter a single '.' line to finish.", fg="yellow"))
        lines: List[str] = []
        while True:
            try:
                line = input(color("helper>", fg="blue", bold=True) + " ")
            except EOFError:
                return None
            if line.strip() == ".":
                break
            lines.append(line)
        helper_text = "\n".join(lines).strip()
        if not helper_text:
            print(color("No helper result captured.", fg="yellow"))
            return None
        return helper_text

    dev_shell_pattern = re.compile(r"\[DEV\s*SHELL\s*COMMAND\](.*?)\[/DEV\s*SHELL\s*COMMAND\]", re.IGNORECASE | re.DOTALL)

    def handle_dev_shell_commands(assistant_text: Optional[str]) -> None:
        if not assistant_text or not getattr(args, "dev", False):
            return
        matches = dev_shell_pattern.findall(assistant_text)
        if not matches:
            return
        for raw in matches:
            command = raw.strip()
            if not command:
                continue
            print(color(f"[dev shell] Running: {command}", fg="yellow"))
            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                output = (proc.stdout or "") + (proc.stderr or "")
            except Exception as exc:  # pragma: no cover - defensive
                output = f"Command failed: {exc}"
            output = output.strip() or "(no output)"
            print(color("[dev shell output]", fg="yellow", bold=True))
            print(output)

            result_text = (
                "[DEV SHELL RESULT]\n"
                f"{output}\n"
                "[/DEV SHELL RESULT]"
            )
            client.messages.append({"role": "assistant", "content": result_text})
            if client.logger:
                sys_msgs = [m for m in client.messages if m.get("role") == "system"]
                to_log = (sys_msgs[-1:] if sys_msgs else []) + [
                    {"role": "assistant", "content": result_text},
                ]
                client.logger.log_turn(to_log)

    def notify_helper_needed() -> None:
        status_line = describe_helper_status()
        message = f"Central requested an external helper. {status_line}"
        if helper_automation_enabled():
            message += " Central will attempt to call the configured helper automatically when available."
        else:
            if not args.helper and sys.stdin.isatty():
                chosen = choose_helper_interactively(args.helper)
                if chosen:
                    args.helper = chosen
            message += " Helper automation is unavailable in this build, so the request could not be sent."
        print(color(message, fg="yellow"))

    def one_turn(user_text: str) -> Optional[str]:
        # Normal API mode via core client
        if args.stream:
            try:
                assistant = client.one_turn(user_text, on_delta=_printer())
            except Exception as e:
                print()
                print(color("Request failed:", fg="red", bold=True))
                print(color(f"{e}", fg="red"))
                print(
                    color(
                        "Central could not process the request. Ensure the model endpoint is available and try again.",
                        fg="yellow",
                    )
                )
                return None
            print()
            if assistant is not None and ChatClient.wants_helper(assistant):
                notify_helper_needed()
            handle_dev_shell_commands(assistant)
            return assistant
        else:
            try:
                assistant = client.one_turn(user_text)
            except Exception as e:
                print(color("Request failed:", fg="red", bold=True))
                print(color(f"{e}", fg="red"))
                print(
                    color(
                        "Central could not process the request. Ensure the model endpoint is available and try again.",
                        fg="yellow",
                    )
                )
                return None
            if assistant is not None:
                print(assistant)
                if ChatClient.wants_helper(assistant):
                    notify_helper_needed()
                handle_dev_shell_commands(assistant)
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
            if prompt.lower() in {"/help"}:
                cmd_print_help(client, user_name=args.user_name)
                continue
            if prompt.strip() == "/reset":
                # Reset to just system message if present
                client.reset_messages(system=args.system)
                print(color("Context reset.", fg="yellow"))
                continue
            if prompt.startswith("/iam ") or prompt.strip() == "/iam":
                parts = prompt.split(maxsplit=1)
                new_name = parts[1].strip() if len(parts) > 1 else args.user_name
                if not new_name:
                    print(color("Usage: /iam NAME", fg="yellow"))
                    continue
                args.user_name = new_name
                # Update developer identity context and append as latest system message
                project = os.getenv("NOCTICS_PROJECT_NAME", "Noctics")
                ident = build_identity_context(new_name, project)
                client.messages.append({"role": "system", "content": ident})
                # Also reflect in args.system for future resets
                if args.system:
                    args.system = (args.system + "\n\n" + ident).strip()
                else:
                    args.system = ident
                print(color(f"Developer identity set: {new_name}", fg="yellow"))
                continue
            if prompt.startswith("/helper"):
                parts = prompt.split(maxsplit=1)
                if len(parts) == 1:
                    # Clear helper preference
                    args.helper = None
                    print(color("Helper cleared. API mode unchanged.", fg="yellow"))
                else:
                    args.helper = parts[1].strip()
                    print(color(f"Helper set to '{args.helper}'.", fg="yellow"))
                continue

            if prompt.startswith("/shell"):
                if not getattr(args, "dev", False):
                    print(color("/shell is only available in developer mode.", fg="red"))
                    continue
                parts = prompt.split(maxsplit=1)
                if len(parts) == 1 or not parts[1].strip():
                    print(color("Usage: /shell COMMAND", fg="yellow"))
                    continue
                command = parts[1].strip()
                try:
                    result = subprocess.run(
                        command,
                        shell=True,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    combined = (result.stdout or "") + (result.stderr or "")
                    combined = combined.strip()
                    if not combined:
                        combined = "(no output)"
                    print(color("[shell output]", fg="yellow", bold=True))
                    print(combined)
                except Exception as exc:  # pragma: no cover - defensive
                    combined = f"Command failed: {exc}"
                    print(color(combined, fg="red"))

                user_text = (
                    "[DEV SHELL COMMAND]\n"
                    f"{command}\n"
                    "[/DEV SHELL COMMAND]"
                )
                assistant_text = (
                    "[DEV SHELL RESULT]\n"
                    f"{combined}\n"
                    "[/DEV SHELL RESULT]"
                )
                client.record_turn(user_text, assistant_text)
                continue

            if prompt.startswith("/name "):
                new_name = prompt.split(maxsplit=1)[1].strip()
                if new_name:
                    args.user_name = new_name
                    print(color(f"Prompt label set to: {args.user_name}", fg="yellow"))
                continue

            if prompt.startswith("/anon"):
                tokens = prompt.split()
                if len(tokens) == 1:
                    args.anon_helper = not bool(args.anon_helper)
                else:
                    val = tokens[1].lower()
                    args.anon_helper = val in {"1", "true", "on", "yes"}
                state = "ON" if args.anon_helper else "OFF"
                print(color(f"Helper anonymization: {state}", fg="yellow"))
                continue

            if prompt.strip() == "/ls":
                items = cmd_list_sessions()
                cmd_print_sessions(items)
                print(color("Tip: load by index: /load N", fg="yellow"))
                continue

            if prompt.strip() == "/last":
                latest = cmd_latest_session()
                if not latest:
                    print(color("No sessions found.", fg="yellow"))
                else:
                    cmd_print_latest_session(latest)
                continue

            if prompt.strip() == "/archive":
                cmd_archive_early_sessions()
                continue

            if prompt.startswith("/show "):
                ident = prompt.split(maxsplit=1)[1].strip()
                if not cmd_show_session(ident):
                    continue
                continue

            if prompt.strip() == "/browse":
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
                path_for_adopt = p if p else (Path(ident) if Path(ident).exists() else None)
                if path_for_adopt is not None:
                    adopt_session(path_for_adopt)
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
                path_for_adopt = p if p else (Path(selection) if Path(selection).exists() else None)
                if path_for_adopt is not None:
                    adopt_session(path_for_adopt)
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
