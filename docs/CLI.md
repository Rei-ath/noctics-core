# CLI Reference

The Central CLI is a thin wrapper over `central.core.ChatClient`. It supports streaming, manual helper pasting, session management, and .env loading.

## Flags

- `--url` string: Endpoint URL (env `CENTRAL_LLM_URL`)
- `--model` string: Model name (env `CENTRAL_LLM_MODEL`)
- `--system` string: System message (defaults to `memory/system_prompt*.txt` if present)
- `--user` string: Optional initial user message
- `--messages` path: JSON file with an initial messages array
- `--temperature` float: Sampling temperature (default 0.7)
- `--max-tokens` int: Max tokens (-1 for unlimited if supported)
- `--stream`: Enable SSE streaming
- `--sanitize`: Redact common PII from user text before sending
- `--raw`: In non-streaming, print raw JSON response
- `--api-key` string: API key (env `CENTRAL_LLM_API_KEY` or `OPENAI_API_KEY`)
- `--helper` string: Set a helper label; implies manual paste when needed
- `--manual`: Manual mode; paste assistant responses (skip API calls)
- `--bypass-helper`: Bypass helper stitching; you paste the final response (acts as Central)
- `--anon-helper` / `--no-anon-helper`: Show (or disable) a sanitized copy of the `[HELPER QUERY]` for safe sharing with helpers. Default ON (can be set via `CENTRAL_HELPER_ANON=0`).
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

## Interactive Commands

- `/helper NAME`: Set helper label; `/helper` clears it
- `/result` (aliases: `/helper-result`, `/paste-helper`, `/hr`): Paste helper result to stitch
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
- `/bypass-helper` (or `/bypass`, `/act-as-central`, `/iam-central`): Toggle bypass mode
- `/anon` (or `/anon-helper`): Toggle helper-query anonymization output
- `/reset`: Reset context to just the system message
- `exit` / `quit`: Exit the session

## Helper Flow

- Central asks for a helper (emits `[HELPER QUERY]` or fallback) → CLI prompts `Helper [NAME]: (paste streaming lines; type END ...)`.
- If no helper is set, the CLI asks you to choose one (from `CENTRAL_HELPERS` or defaults).
- Paste multi-line content; each line echoes immediately. Finish by typing `END`.
- CLI wraps paste as `[HELPER RESULT]...[/HELPER RESULT]`, sends to Central, and streams stitched output when `--stream` is enabled.
- Default helper names you can use: CodeSmith, DataDive, ResearchSleuth, UIWhisperer, OpsSentinel, LegalEagle. Override with `CENTRAL_HELPERS="Name1,Name2"` if you prefer your own roster.

## First Prompt Experience

- On the first user message of a new session, the CLI proposes a short session title derived from your request.
- You can add clarifying notes before the message is sent, accept the suggested title, or type a custom one (or press Enter to skip).
- After this first turn, the chat proceeds normally; you can still rename later with `/title` or `/rename`.

## Sessions

- Files live under `memory/sessions/YYYY-MM-DD/`:
- `session-*.json`: array of turn records
  - `session-*.meta.json`: metadata sidecar (id, path, title, turns, created/updated)
- Auto-title on exit if no custom title.
- List using `--sessions-ls` or `/sessions`.
- Rename using `--sessions-rename` or `/rename`.
- Load using `--sessions-load` or `/load`.

## Examples

- Stream with helper stitching: `python main.py --stream`
- Manual assistant everywhere: `python main.py --manual`
- If Central cannot be reached, the interactive CLI automatically falls back to manual mode so you can paste assistant replies.
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
