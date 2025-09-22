# Noctics Central Core

Local, privacy-first chat orchestration with optional manual helper flow, streaming, and session logging. Ships with a thin CLI (`central/cli.py`) and an importable core (`central/core.py`). No external runtime dependencies.

## Quick Start

- Create env (Python 3.13 recommended):
  - `python -m venv jenv && source jenv/bin/activate`
- Configure `.env` (optional; auto-loaded):
  - Copy `.env.example` to `.env` and adjust values
- Run the CLI:
  - `python main.py`

## .env Support

Central loads `.env` automatically from both the package folder and the current working directory. Existing environment variables are not overwritten.

- `CENTRAL_LLM_URL` (default `http://localhost:1234/v1/chat/completions`)
- `CENTRAL_LLM_MODEL` (default `qwen/qwen3-1.7b`)
- `CENTRAL_LLM_API_KEY` or `OPENAI_API_KEY` (optional)
- `CENTRAL_HELPER_ANON` (default `1`): show sanitized helper queries for safe sharing
- `CENTRAL_REDACT_NAMES` (optional): comma-separated names to redact in helper queries
- `CENTRAL_HELPERS` (optional): comma-separated helper names to present when choosing a helper
- `CENTRAL_DEV_NAME` (optional): if set, used as your prompt label and appended as identity context (e.g., "The user 'Rei' is the developer of Noctics.")
- `NOCTICS_PROJECT_NAME` (optional, default `Noctics`): used in the identity context above

Example `.env`:

```
CENTRAL_LLM_URL=http://localhost:1234/v1/chat/completions
CENTRAL_LLM_MODEL=qwen/qwen3-4b-thinking-2507
# CENTRAL_LLM_API_KEY=sk-...
# CENTRAL_DEV_NAME=Rei
# NOCTICS_PROJECT_NAME=Noctics
```

## Core Concepts

- ChatClient (importable): stateful conversation + streaming + helper stitching + logging
- CLI: interactive wrapper over ChatClient
- Sessions: JSONL logs with `.meta.json` sidecar including a human title
- Helper flow: when Central requests a helper, you paste the helper output (line-by-line stream) and Central stitches the result

## CLI Usage (highlights)

- Normal streaming:
  - `python main.py --stream`
- Manual assistant replies for every turn (no API):
  - `python main.py --manual`
- When Central is unreachable and you are in an interactive shell, the CLI auto-switches to manual mode so you can paste replies.
- Show the model's raw `<think>` reasoning (hidden by default):
  - `python main.py --show-think`
- Name a helper (implies manual paste prompt when needed):
  - `python main.py --helper claude`
- List saved sessions and titles:
  - `python main.py --sessions-ls`
- Rename a saved session title:
  - `python main.py --sessions-rename session-20250914-010016 "My Title"`
- Load a saved session before chatting:
  - `python main.py --sessions-load session-20250913-234409`

See `docs/CLI.md` for all flags and interactive commands.

## Helper Flow (manual paste)

- Central outputs a `[HELPER QUERY]...[/HELPER QUERY]` or fallback message → CLI prompts:
  - `Helper [NAME]: (paste streaming lines; type END on its own line to finish)`
- Paste the helper output line-by-line; each line echoes instantly (simulated stream)
- Type `END` to finish; CLI wraps it as `[HELPER RESULT]...[/HELPER RESULT]` and sends to Central
- With `--stream`, Central’s stitched response streams live back to you

You can also trigger the stitch manually anytime with `/result` (aliases: `/helper-result`, `/paste-helper`, `/hr`).

Privacy: When Central asks for a helper and emits a `[HELPER QUERY]` block, the CLI prints a sanitized version by default for safe copy/paste (redacts emails/phones/cards/IPs and optional names). Toggle with `--anon-helper` / `--no-anon-helper` or `/anon`.

Selecting a helper: If you haven’t set `--helper`, the CLI will ask you to choose one when needed (from `CENTRAL_HELPERS` or a default list). You can type a number or a custom name.

Built-in helper names (override with `CENTRAL_HELPERS`):
- claude (Anthropic)
- gpt-4o / gpt-4 (OpenAI)
- grok (xAI)
- gemini (Google)
- llama (Meta)
- mistral (Mistral AI)
- cohere (Cohere)
- deepseek (DeepSeek)

First prompt: When you send the very first message, the CLI proposes a short session title based on your request, offers a chance to add clarifying details, and lets you accept or override the title before the request goes to Central.

## Sessions

- Storage: `memory/sessions/YYYY-MM-DD/`
  - Turns: `session-*.jsonl` (JSON Lines turn records; legacy `.json` files still load)
  - Day aggregate: `day.json` (auto-appended when sessions close; deduped)
  - Meta: `session-*.meta.json` (title, turns, created/updated, etc.)
- Titles:
  - Set in-session: `/title My Topic`
  - Rename any saved session: `/rename session-YYYYMMDD-HHMMSS New Title` or `--sessions-rename ...`
  - Auto-title: on exit, Central derives a concise title from the first meaningful user message if you didn’t set one
- Listing:
  - Non-interactive: `--sessions-ls` (full list), `--sessions-latest` (show most recent), or `--sessions-archive-early` (merge everything except latest into `memory/early-archives/`)
  - Interactive: `/sessions` or `/ls`; quick summary: `/last`; browse menu: `/browse`; pretty-print: `/show ID`; archive: `/archive`
- Loading:
  - `--sessions-load ID_OR_PATH` or in chat `/load ID`

### Memory explorer (`noxl`)

- Quick list: `python -m noxl` (lists most recent sessions; `--limit N` to adjust)
- Filter by text: `python -m noxl --search "error"`
- Inspect a session: `python -m noxl --show session-YYYYMMDD-HHMMSS`
- Show latest summary: `python -m noxl --latest`
- Raw JSON dump: `python -m noxl --show <id> --raw`
- Browse alternate roots: `python -m noxl list --root memory/early-archives`
- Rename a session: `python -m noxl rename session-YYYYMMDD-HHMMSS "New Title"`
- Merge sessions: `python -m noxl merge session-A session-B --title "Merged"`
- Archive early sessions: `python -m noxl archive`
- Show stored metadata: `python -m noxl meta session-YYYYMMDD-HHMMSS`
- Count matches: `python -m noxl count --search helper`
- Programmatic helpers: `from noxl import list_sessions, load_session_messages`

Most commands accept `--root PATH` so you can target alternate directories (like `memory/early-archives`).

More details: `docs/SESSIONS.md`.

## Programmatic Use

```python
from central.core import ChatClient

client = ChatClient(stream=True, sanitize=True)
client.reset_messages(system=open("memory/system_prompt.txt").read().strip())

# Stream output
assistant = client.one_turn("Explain X", on_delta=lambda s: print(s, end=""))

if ChatClient.wants_helper(assistant):
    # Paste helper text from elsewhere
    helper_text = "..."
    client.process_helper_result(helper_text, on_delta=lambda s: print(s, end=""))

# Access current session log path
print("log:", client.log_path())
```

## Interactive Commands (CLI)

- `/helper NAME`: set helper label; `/helper` clears
- `/result` (aliases: `/helper-result`, `/paste-helper`, `/hr`): paste helper result
- `/iam-dev NAME`: mark yourself as the developer for this session (injects identity context)
- `/sessions` or `/ls`: list saved sessions + titles
- `/last`: show the most recently updated session
- `/browse`: interactively list and view saved sessions
- `/show ID`: pretty-print a saved session without loading it
- `/archive`: merge all but the latest session into `memory/early-archives/`
- `/load ID`: load a session by id
- `/title NAME`: set current session title
- `/rename ID NAME`: rename a saved session title
- `/reset`: reset context to just the system message
- `exit` / `quit`: leave

## Dev Tips

- Formatting/checks: `ruff check .`, `black .`, `isort .`
- Tests: `pytest -q` (if you set up a test env)
- No secrets in repo; rely on `.env` or environment variables

## Notes

- Manual streaming is line-based. Type `END` to finish the paste.
- PII redaction: enable with `--sanitize` to redact common PII in user input before sending.
- The CLI prints the session log path on start and confirms a saved title on exit.

***

Questions or improvements you want next? I can add a `--helper-result-file` flag for non-interactive stitching, or subcommands like `sessions ls|load|rename`.
