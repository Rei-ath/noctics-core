# CLI Reference

The Central CLI is a thin wrapper over `central.core.ChatClient`. It supports streaming, session management, and .env loading.

## Flags

- `--url` string: Endpoint URL (env `CENTRAL_LLM_URL`)
- `--model` string: Model name (env `CENTRAL_LLM_MODEL`)
- `--system` string: System message (defaults to `memory/system_prompt*.txt` if present)
- `--user` string: Optional initial user message
- `--messages` path: JSON file with an initial messages array
- `--temperature` float: Sampling temperature (default 0.7)
- `--max-tokens` int: Max tokens (-1 for unlimited if supported)
- `--stream`: Enable SSE streaming (skips the interactive prompt)
- `--no-stream`: Disable SSE streaming without a prompt
- `--sanitize`: Redact common PII from user text before sending
- `--raw`: In non-streaming, print raw JSON response
- `--api-key` string: API key (env `CENTRAL_LLM_API_KEY` or `OPENAI_API_KEY`)
- `--helper` string: Set a helper label for display when helpers are mentioned
- `--anon-helper` / `--no-anon-helper`: Reserved sanitization toggle for future helper integration (default respects `CENTRAL_HELPER_ANON`).
- `--show-think`: Include the assistant’s `<think>` reasoning blocks in output/logs (hidden by default).
- `--sessions-ls`: List saved sessions (with titles) and exit
- `--sessions-latest`: Show the most recently updated session and exit
- `--sessions-archive-early`: Merge all but the latest session into `memory/early-archives/` and exit
- `--sessions-show` ID_OR_PATH: Pretty-print the contents of a saved session and exit
- `--sessions-browse`: Interactively browse sessions and view their contents
- `--sessions-load` ID_OR_PATH: Load a saved session as the starting context
- `--sessions-rename` ID_OR_PATH "NEW TITLE": Rename a saved session’s title and exit
- `--sessions-merge` ID_OR_INDEX [...]: Merge sessions into a new combined session and exit
- `--user-name` NAME: Set the input prompt label (default "You"; env `CENTRAL_USER_NAME`)
- `--version`: Print the Central version and exit

## Interactive Commands

- `/helper NAME`: Set helper label; `/helper` clears it
- `/sessions` or `/ls`: List saved sessions and titles
- `/last` (alias `/latest`, `/recent`): Show the most recently updated session
- `/archive` (alias `/archive-early`, `/archive-old`): Merge all but the latest session into `memory/early-archives/`
- `/show ID|INDEX`: Pretty-print a saved session without loading it into the conversation
- `/browse`: Interactively browse sessions and view one with a quick selection
- `/load`: without arguments, opens an interactive picker; `/load ID` still works for direct loading
- `/load ID|INDEX`: Load a session by id or list index
- `/title NAME`: Set the current session title
- `/rename ID NAME`: Rename any saved session’s title
- `/merge A B ...`: Merge sessions by ids or indices
- `/name NAME`: Set your input prompt label for this session
- `/anon` (or `/anon-helper`): Reserved helper-query anonymization toggle (no effect until helper automation ships)
- `/shell CMD`: Run a local shell command (developer mode only); output is logged into the session
- `/reset`: Reset context to just the system message
- `exit` / `quit`: Exit the session

## Helper Flow

Central tries to answer locally first. If it needs an external helper it:

1. Confirms which helper label to use (from env/config/defaults).
2. Emits a sanitized `[HELPER QUERY]…[/HELPER QUERY]` and tells you it is waiting for an external reply.
3. If automation is disabled (default for the standalone core), it reminds you to paste the helper output with `/result` and notes that the full Noctics suite + router enables automatic routing.
4. The current standalone build does not forward helper requests; Central will acknowledge the limitation. When automation is available (router service), `ChatClient.process_helper_result` stitches the returned `[HELPER RESULT]` into the conversation automatically.

Sanitisation honours `CENTRAL_HELPER_ANON` and name redaction env vars. You can preconfigure helper rosters and automation flags via `central/config.py` (JSON) or environment variables.

### Configuration quick reference

- Primary overrides come from environment variables (`CENTRAL_*`).
- Optional JSON config: `config/central.json` (or a path supplied via `CENTRAL_CONFIG`) with structure:

```json
{
  "helper": {
    "automation": false,
    "roster": ["claude", "gpt-4o"]
  }
}
```

Environment variables take precedence over the JSON file.

### Developer mode shell automation

- When `--dev` is supplied, the model is encouraged (see `memory/system_prompt.txt`) to issue `[DEV SHELL COMMAND]…[/DEV SHELL COMMAND]` blocks for local diagnostics (for example “`ip addr show`”).
- The CLI executes those commands automatically, prints the output as `[DEV SHELL RESULT]`, and appends it to the session so follow-up answers can reference the data.
- You can still run commands manually via `/shell CMD`.

## First Prompt Experience

- At startup (unless `--dev` is supplied) the CLI lists any known users, lets you pick one or create a new profile, and asks whether you want streaming enabled. It also logs a `Hardware context: …` line to the system prompt so the assistant knows where it is running.
- The default developer identity is Rei, a 20-year-old solo creator of Central; the system prompt carries that context so replies stay personable. You can override with `--dev` or environment variables (`CENTRAL_DEV_NAME`, etc.). Developer mode also unlocks `/shell` for local command inspection.
- On the first user message of a new session, the CLI still proposes a short session title derived from your request.
- You can add clarifying notes before the message is sent, accept the suggested title, or type a custom one (or press Enter to skip).
- After this first turn, the chat proceeds normally; you can still rename later with `/title` or `/rename`.

## Sessions

- Files live under `memory/sessions/YYYY-MM-DD/`:
- `session-*.jsonl`: JSON Lines turn records (legacy `.json` files still supported)
  - `session-*.meta.json`: metadata sidecar (id, path, title, turns, created/updated)
- Auto-title on exit if no custom title.
- List using `--sessions-ls` or `/sessions`.
- Rename using `--sessions-rename` or `/rename`.
- Load using `--sessions-load` or `/load`.

## Examples

- Stream a conversation: `python main.py --stream`
- Name a helper and stream: `python main.py --helper claude --stream`
- One-off question with stream: `python main.py --user "Explain vector clocks" --stream`
- Provide messages array: `python main.py --messages msgs.json --stream`
- List sessions: `python main.py --sessions-ls`
- Load a session: `python main.py --sessions-load session-20250913-234409`
- Rename a session: `python main.py --sessions-rename session-20250914-010016 "My Project"`
- Merge two sessions by index: `python main.py --sessions-merge 1 3`

### Memory explorer (`noxl`)

- `python -m noxl` — list recent sessions (use `--limit` to refine)
- `python -m noxl --search TEXT` — filter by metadata or message content
- `python -m noxl list --root memory/early-archives` — inspect alternate session roots
- `python -m noxl --show <session>` — pretty-print a saved conversation (`--raw` for JSON)
- `python -m noxl --latest` — view the latest session summary
- `python -m noxl rename <session> "New Title"` — rename stored metadata
- `python -m noxl merge A B --title "Merged"` — create a combined log
- `python -m noxl archive` — move earlier sessions into `memory/early-archives/`
- `python -m noxl meta <session>` — print the metadata JSON
- `python -m noxl count --search TEXT` — count matching sessions

Most subcommands accept `--root PATH` to switch between `memory/sessions` and other directories (for example `memory/early-archives`).

## Tab Completion

When running interactively, the CLI enables Tab completion (readline-based) for:
- Commands: type `/` then press Tab to see options
- `/helper NAME`: completes helper names (from `CENTRAL_HELPERS` env or common defaults)
- `/load`, `/rename`, and `/merge`: complete session indices (1..N) and ids from the latest list

You’ll see a hint at startup: `[Tab completion enabled: type '/' then press Tab]`.
