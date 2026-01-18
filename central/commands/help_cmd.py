from __future__ import annotations

from central.colors import color
from central.core import ChatClient


def print_help(client: ChatClient, *, user_name: str = "You") -> None:
    print(color("Type 'exit' or 'quit' to end. Use /reset to clear context.", fg="yellow"))
    lp = client.log_path()
    if lp:
        print(color(f"Logging session to: {lp}", fg="yellow"))
    print(color("Commands:", fg="yellow"))
    print(color("  /help          show this help", fg="yellow"))
    print(color("  /shell CMD     run a local shell command (developer mode only)", fg="yellow"))
    print(color("  /iam NAME      mark yourself as the developer for this session", fg="yellow"))
    print(color("  /ls            list saved sessions with titles", fg="yellow"))
    print(color("  /last          show the most recently updated session", fg="yellow"))
    print(color("  /archive       merge all but latest session into early archives", fg="yellow"))
    print(color("  /browse        interactively browse & view sessions", fg="yellow"))
    print(color("  /load ID       load a session by id", fg="yellow"))
    print(color("  /title NAME    set current session title", fg="yellow"))
    print(color("  /rename ID T   rename a saved session's title", fg="yellow"))
    print(color("  /merge A B..   merge sessions by ids or indices", fg="yellow"))
    print(color("  /reset         reset context to just the system message", fg="yellow"))
    print(color("  /name NAME     set the input prompt label (default: You)", fg="yellow"))
    print(color("  @codex MSG     send a prompt to the Codex CLI (NoxdEx)", fg="yellow"))
    print(color("  [run] ...      execute structured command blocks (auto-run)", fg="yellow"))
    print(color("  [cmd] ...      run shell commands (auto-run)", fg="yellow"))
    print(color("  [py]  ...      run python snippets (auto-run)", fg="yellow"))
    print(color("Docs: README.md, docs/CLI.md, docs/SESSIONS.md", fg="yellow"))
    print(color("Tip: run with --help to see all CLI flags.", fg="yellow"))
    print()
    print(color("Examples:", fg="yellow", bold=True))
    print(color("  python main.py --stream", fg="yellow"))
    print(color("  /ls                (list saved sessions)", fg="yellow"))
    print(color("  /load 1            (load most recent by index)", fg="yellow"))
