# Noctics Central Core

Local, privacy-first chat orchestration with helper-aware streaming and session logging. Ships with a thin CLI (`central/cli.py`) and an importable core (`central/core.py`). No external runtime dependencies.

**Current version:** `v0` (`0.0.0`)

## Quick Start

- Create env (Python 3.13 recommended):
  - `python -m venv jenv && source jenv/bin/activate`
- Configure `.env` (optional; auto-loaded):
  - Copy `.env.example` to `.env` and adjust values
- Run the CLI:
  - `python main.py`
- Check the bundled version:
  - `python main.py --version`

## Configuration

Central loads `.env` automatically from both the package folder and the current working directory. Existing environment variables are not overwritten. You can also provide a JSON config via `CENTRAL_CONFIG` or `config/central.json`; see `config/central.example.json` for the schema (currently helper automation toggle and custom helper roster).

- `CENTRAL_LLM_URL` (default `http://localhost:1234/v1/chat/completions`)
- `CENTRAL_LLM_MODEL` (default `qwen/qwen3-1.7b`)
- `CENTRAL_LLM_API_KEY` or `OPENAI_API_KEY` (optional)
- `CENTRAL_HELPER_ANON` (default `1`): show sanitized helper queries for safe sharing
- `CENTRAL_REDACT_NAMES` (optional): comma-separated names to redact in helper queries
- `CENTRAL_HELPERS` (optional): comma-separated helper names to present when choosing a helper
- `CENTRAL_DEV_NAME` (optional): if set, used as your prompt label and appended as identity context (e.g., "The user 'Rei' is the developer of Noctics.")
- `NOCTICS_PROJECT_NAME` (optional, default `Noctics`): used in the identity context above
- `CENTRAL_HELPER_AUTOMATION` (optional): set to `1/true/on` when a router is available and you want automatic helper dispatching.

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
- Helper flow: Central may request a helper; the CLI informs you that automated helper integration is not available yet
- Developer identity: Central defaults to recognising Rei—a 20-year-old solo developer building this personal assistant—and weaves that context into the system prompt for rapport.
- Session picker: on launch, the CLI lists saved conversations (via the `noxl` helpers) so you can jump straight back into any prior session.
- Title management: on a fresh install Central names the first session automatically and can rename any session mid-conversation by emitting `[SET TITLE]New Name[/SET TITLE]`.
- Status HUD: startup prints a retro-styled "Central Status" block (version, developer, helper roster, session count) for quick situational awareness.
- Developer mode (`--dev`): exposes local shell access via `/shell CMD`, lets the assistant emit `[DEV SHELL COMMAND]…[/DEV SHELL COMMAND]` to run diagnostics automatically, prints hardware context, and bypasses the user-selection onboarding.

## CLI Usage (highlights)

- Normal streaming:
  - `python main.py --stream`
- Show the model's raw `<think>` reasoning (hidden by default):
  - `python main.py --show-think`
- Name a helper label for helper-related prompts:
  - `python main.py --helper claude`
- List saved sessions and titles:
  - `python main.py --sessions-ls`
- Rename a saved session title:
  - `python main.py --sessions-rename session-20250914-010016 "My Title"`
- Load a saved session before chatting:
  - `python main.py --sessions-load session-20250913-234409`

See `docs/CLI.md` for all flags and interactive commands.

## Helper Flow

Central first tries to answer locally. If it needs outside help, it confirms which helper should be used, emits a sanitized `[HELPER QUERY]…[/HELPER QUERY]`, and—when automation is unavailable—explains that the request could not be sent. Once Central is paired with the full Noctics router, the helper response will arrive automatically and be stitched into the conversation.

Privacy: Helper requests are always sanitized (PII redaction + optional name masking). Automation is disabled by default; toggle it with `CENTRAL_HELPER_AUTOMATION` or the JSON config once you wire in the router.

Selecting a helper: If you haven’t set `--helper`, the CLI asks you to choose one when the request happens (from `CENTRAL_HELPERS`, config roster, or defaults). You can type a number or a custom name.

Built-in helper names (override with `CENTRAL_HELPERS`):
- claude (Anthropic)
- gpt-4o / gpt-4 (OpenAI)
- grok (xAI)
- gemini (Google)
- llama (Meta)
- mistral (Mistral AI)
- cohere (Cohere)
- deepseek (DeepSeek)

First prompt: When you start the CLI it now asks for your username (unless `--dev` is supplied) and whether you want streaming enabled. On the very first message within a session, the CLI still proposes a short title based on your request and lets you accept or override it. A `Hardware context: …` line is also injected into the system prompt so the assistant knows which OS/CPU/memory it is running on.

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

- PII redaction: enable with `--sanitize` to redact common PII in user input before sending.
- The CLI prints the session log path on start and confirms a saved title on exit.

***

Questions or improvements you want next? I can add a `--helper-result-file` flag for non-interactive stitching, or subcommands like `sessions ls|load|rename`.
