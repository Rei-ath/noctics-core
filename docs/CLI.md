# Nox Core CLI

This is the lightweight CLI that ships with `noctics-core`. If the full
`noctics_cli` package is installed, `python main.py` will dispatch to it.
The `noctics-central` entrypoint always uses the core CLI described here.

## Flags

| Flag | What it does |
|------|--------------|
| `--url` | Target inference endpoint URL (defaults to `NOX_LLM_URL`). |
| `--model` | Model alias or persona scale (defaults to `NOX_LLM_MODEL`). |
| `--system` | Override system prompt text (literal string, not a file path). |
| `--temperature` | Sampling temperature (default 0.7). |
| `--max-tokens` | Max response tokens (`-1` for backend default). |
| `--stream` | Enable streaming responses (prints deltas). |
| `--no-stream` | Disable streaming (default). |
| `--sanitize` | Apply built-in PII scrubbing to user text before sending. |
| `--user` | Send a single user prompt and exit. |
| `--show-config` | Print the resolved runtime configuration before chatting. |
| `--list-models` | List installed Noctics model aliases and exit. |

Notes:
- If `--system` is not provided, the CLI searches for prompt files in this order:
  `memory/system_prompt.local.md`, `memory/system_prompt.local.txt`,
  `memory/system_prompt.md`, `memory/system_prompt.txt`.
- System prompt templates can include persona tokens like `{{NOX_NAME}}` and
  `{{NOX_PERSONA_TAGLINE}}` (see `docs/PERSONA.md`).
- `--list-models` shells out to `ollama` using `OLLAMA_BIN`, `ollama` in `PATH`,
  or `assets/ollama/bin/ollama`.

## Interactive slash commands

| Command | Action |
|---------|--------|
| `/help` | Show CLI help. |
| `/config` | Print the resolved runtime configuration. |
| `/models` | List installed Noctics model aliases. |
| `/reset` | Clear conversation history (keeps the system prompt). |
| `/exit` or `/quit` | Exit the CLI. |

## Input modes
- Interactive prompt (default when stdin is a TTY).
- One-shot via `--user "..."`.
- Non-interactive stdin (pipe text into the CLI).

## Sessions
The core CLI does not ship session-management commands. Use `noxl` to browse,
rename, merge, or archive sessions (see `docs/SESSIONS.md`).

## Inference details
See `docs/INFERENCE.md` for endpoint behavior, payload options, and the local
Ollama bootstrap flow.
