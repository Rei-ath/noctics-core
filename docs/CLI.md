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
- `--sessions-ls`: List saved sessions (with titles) and exit
- `--sessions-load` ID_OR_PATH: Load a saved session as the starting context
- `--sessions-rename` ID_OR_PATH "NEW TITLE": Rename a saved session’s title and exit

## Interactive Commands

- `/helper NAME`: Set helper label; `/helper` clears it
- `/result` (aliases: `/helper-result`, `/paste-helper`, `/hr`): Paste helper result to stitch
- `/sessions` or `/ls`: List saved sessions and titles
- `/load ID`: Load a session by id (e.g., `session-20250914-011955`)
- `/title NAME`: Set the current session title
- `/rename ID NAME`: Rename any saved session’s title
- `/reset`: Reset context to just the system message
- `exit` / `quit`: Exit the session

## Helper Flow

- Central asks for a helper (emits `[HELPER QUERY]` or fallback) → CLI prompts `Helper [NAME]: (paste streaming lines; type END ...)`.
- Paste multi-line content; each line echoes immediately. Finish by typing `END`.
- CLI wraps paste as `[HELPER RESULT]...[/HELPER RESULT]`, sends to Central, and streams stitched output when `--stream` is enabled.

## Sessions

- Files live under `memory/sessions/YYYY-MM-DD/`:
  - `session-*.jsonl`: turn-by-turn JSONL
  - `session-*.meta.json`: metadata sidecar (id, path, title, turns, created/updated)
- Auto-title on exit if no custom title.
- List using `--sessions-ls` or `/sessions`.
- Rename using `--sessions-rename` or `/rename`.
- Load using `--sessions-load` or `/load`.

## Examples

- Stream with helper stitching: `python main.py --stream`
- Manual assistant everywhere: `python main.py --manual`
- Name a helper: `python main.py --stream --helper claude`
- List sessions: `python main.py --sessions-ls`
- Rename a session: `python main.py --sessions-rename session-20250914-010016 "My Project"`
- Load a session: `python main.py --sessions-load session-20250913-234409`

## Tab Completion

When running interactively, the CLI enables Tab completion (readline-based) for:
- Commands: type `/` then press Tab to see options
- `/helper NAME`: completes helper names (from `CENTRAL_HELPERS` env or common defaults)
- `/load` and `/rename`: complete session indices (1..N) and session ids from the latest list

You’ll see a hint at startup: `[Tab completion enabled: type '/' then press Tab]`.
