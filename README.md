# Nox Core (the public brain)

Nox Core is the public, stdlib-only package that powers the ChatClient, runtime
server, persona system, and memory tooling. If the private wrapper package is
installed, `python main.py` will hand off to the full multitool CLI; otherwise it
runs the lightweight core CLI.

## Quick start
- `python -m venv .venv && source .venv/bin/activate`
- `python -m pip install -U pip`
- `python scripts/bootstrap.py`
- `export NOX_LLM_URL=http://127.0.0.1:11434/api/chat`
- `export NOX_LLM_MODEL=nox`
- `python main.py --stream`

`noctics-central` is the core CLI entrypoint. `noxl` is the memory browser.

## Config cheat sheet
- `.env` is auto-loaded from the package dir, CWD, and up to 3 parent dirs.
  Set `NOCTICS_SKIP_DOTENV=1` to disable.
- Required for ChatClient:
  - `NOX_LLM_URL` (example: `http://127.0.0.1:11434/api/chat` or `/api/generate`)
  - `NOX_LLM_MODEL` (persona scale or model alias)
- Optional:
  - `NOX_LLM_API_KEY` or `OPENAI_API_KEY` for hosted providers
  - `NOX_TARGET_MODEL` / `NOX_OPENAI_MODEL` for OpenAI endpoint mapping
  - `NOX_SCALE` and `NOX_PERSONA_*` for persona overrides (see `docs/PERSONA.md`)
  - `NOX_CONFIG` or `NOCTICS_CONFIG_HOME` for config file discovery
  - `NOCTICS_DATA_ROOT` or `NOCTICS_MEMORY_HOME` for session storage

Example `config/central.json`:
```json
{
  "instrument": {
    "automation": false,
    "roster": ["claude", "gpt-4o"]
  }
}
```

## Runtime server (`/api/chat`)
- `python -m central.runtime --host 127.0.0.1 --port 11437`
- Uses the same ChatClient stack as the CLI (no streaming for HTTP calls).
- Flags/env: `--default-url` (`NOX_RUNTIME_URL`), `--default-model`
  (`NOX_RUNTIME_MODEL`), `--no-strip-reasoning`, `--log-sessions`,
  `NOX_RUNTIME_ALLOW_ORIGIN`.

Request shape:
```json
{
  "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
  "model": "nox",
  "url": "http://127.0.0.1:11434/api/chat",
  "temperature": 0.7,
  "max_tokens": -1,
  "sanitize": false
}
```

## Inference runtime
- Core inference plumbing lives in `central/core/payloads.py` and
  `central/transport.py`.
- `scripts/nox.run` boots a local Ollama binary at `inference/ollama` and
  ensures models are available.
- See `docs/INFERENCE.md` for endpoint behavior, tuning env vars, and the full
  bootstrap flow.

## Sessions and memory
- The core CLI logs sessions by default.
- Default root: `~/.local/share/noctics/memory` (or `XDG_DATA_HOME`).
- Override with `NOCTICS_DATA_ROOT` or `NOCTICS_MEMORY_HOME`.
- If the preferred root is not writable, the repo `memory/` directory is used.
- Use `noxl` to browse, rename, merge, and archive sessions (see
  `docs/SESSIONS.md`).

## Persona remix
- Overrides live in `config/persona.overrides.json` or `NOX_PERSONA_FILE`.
- Env overrides (`NOX_PERSONA_*`) win over JSON.
- See `docs/PERSONA.md` for fields and template tokens.

## Instruments
- The core ships the hooks (`ChatClient.wants_instrument`,
  `ChatClient.process_instrument_result`) but not the router.
- If the optional `instruments` package is installed, ChatClient will attempt to
  call it automatically.
- See `docs/INSTRUMENTS.md` for the wiring details.

## What ships here
- `central/core/` - ChatClient, payload builders, reasoning cleanup
- `central/cli/` - lightweight CLI entrypoint
- `central/runtime/` - tiny HTTP server for `/api/chat`
- `inference/` - local Ollama binary used by `scripts/nox.run`
- `interfaces/` - dotenv loader, PII scrubber, session logger
- `noxl/` - memory explorer CLI + utilities
- `scripts/` - bootstrapper and local inference helper
- `tests/` - pytest suite; keep it green

Docs live in `docs/` for CLI, persona, instruments, inference, and sessions.
