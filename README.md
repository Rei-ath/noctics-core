# Noctics Central Core

Local, privacy-first chat orchestration with helper-aware streaming and session logging. Ships with a thin CLI (`central/cli.py`) and an importable core (`central/core.py`). No external runtime dependencies.

**Current version:** `v0` (`0.0.0`)

## Quick Start

- Bootstrap everything (creates `.venv`, installs deps, seeds config):
  - `python scripts/bootstrap.py`
- Prefer manual setup? Create env (Python 3.13 recommended):
  - `python -m venv jenv && source jenv/bin/activate`
- Configure `.env` (optional; auto-loaded):
  - Create `.env` and adjust values (`scripts/bootstrap.py` seeds defaults)
- Run the CLI:
  - `python main.py`
- Check the bundled version:
  - `python main.py --version`

## Configuration

Central loads `.env` automatically from both the package folder and the current working directory. Existing environment variables are not overwritten. You can also provide a JSON config via `CENTRAL_CONFIG` or `config/central.json`; see `config/central.example.json` for the schema (currently helper automation toggle and custom helper roster).

- `CENTRAL_LLM_URL` (default local Ollama: `http://127.0.0.1:11434/api/generate`)
- `CENTRAL_LLM_MODEL` (set for your endpoint; defaults to `centi-noctics:latest` in this repo)
- `CENTRAL_LLM_API_KEY` or `OPENAI_API_KEY` (optional)
- `CENTRAL_NOX_SCALE` (optional): force the persona to `nano`, `micro`, `milli`, or `centi` regardless of the model string.
- `CENTRAL_PERSONA_FILE` (optional): path to a JSON overrides file for persona names, taglines, strengths, and limits. See `core/AGENTS.md` for the schema.
- `CENTRAL_PERSONA_*` environment variables provide ad-hoc overrides (e.g. `CENTRAL_PERSONA_TAGLINE`, `CENTRAL_PERSONA_STRENGTHS`, with optional `_CENTI` suffix).
- `CENTRAL_HELPER_ANON` (default `1`): show sanitized helper queries for safe sharing
- `CENTRAL_REDACT_NAMES` (optional): comma-separated names to redact in helper queries
- `CENTRAL_HELPERS` (optional): comma-separated helper names to present when choosing a helper
- `CENTRAL_DEV_NAME` (optional): if set, used as your prompt label and appended as identity context (e.g., "The user 'Rei' is the developer of Noctics.")
- `NOCTICS_PROJECT_NAME` (optional, default `Noctics`): used in the identity context above
- `CENTRAL_HELPER_AUTOMATION` (optional): set to `1/true/on` when a router is available and you want automatic helper dispatching.

Example `.env`:

```
CENTRAL_LLM_URL=http://127.0.0.1:11434/api/generate
CENTRAL_LLM_MODEL=centi-noctics:latest
# CENTRAL_LLM_API_KEY=sk-...
# CENTRAL_DEV_NAME=Rei
# NOCTICS_PROJECT_NAME=Noctics
```

## Personalise Central

Give Nox your own voice in three quick steps:

1. **Tell Central which scale to bias toward** (Optional)  
   ```bash
   export CENTRAL_NOX_SCALE=micro  # nano|micro|milli|centi
   ```
2. **Drop a persona override file** with your wording. Start from the template below and save it as `config/persona.overrides.json`:
   ```json
   {
     "global": {
       "tagline": "Always-on studio co-pilot",
       "strengths": "Keeps private briefs in sync|Checks every command before running it"
     },
     "scales": {
       "micro": {
         "central_name": "spark-nox",
         "limits": "Prefers focused prompts over sprawling brainstorms"
       }
     }
   }
   ```
3. **Reload overrides** (`python -c "from central.persona import reload_persona_overrides; reload_persona_overrides()"`) and start the CLI (`python main.py`). The startup HUD should now display your custom name, tagline, strengths, and limits.

Need the full schema, more examples, or environment variable shortcuts? See `core/docs/PERSONA.md`.

### Bundled Model Cheatsheet

| Scale  | Alias to use in configs | Upstream Model |
|--------|-------------------------|----------------|
| nano   | `nano-noctics:latest`   | `qwen3:0.6b`   |
| micro  | `micro-noctics:latest`  | `qwen3:1.7b`   |
| milli  | `milli-noctics:latest`  | `qwen3:4b`     |
| centi  | `centi-noctics:latest`  | `qwen3:8b`     |

The default release (`scripts/build_release.sh`) ships with the centi build (Qwen3 8B). Use the scale-specific scripts if you want a lighter bundle.

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

### Embedding the core inside the top-level Noctics repo

When you maintain the parent distribution (for bundling helpers, router, `ollama.cpp`, etc.) add this repository as a submodule under `core/`:

```bash
git submodule add git@github.com:<you>/noctics-core.git core
```

Whenever you push new changes to `noctics-core`, update the parent checkout with:

```bash
./scripts/update_core_submodule.sh
```

The helper script runs `git submodule update --init --remote core` and prints the resulting status so you can review the commit pointer before committing the bump.

## CLI Usage (highlights)

- Normal streaming:
  - `python main.py --stream`
- Show the model's raw `<think>` reasoning (hidden by default):
  - `python main.py --show-think`
- Name an instrument label for external calls (alias: `--helper`):
  - `python main.py --instrument claude`
- List saved sessions and titles:
  - `python main.py --sessions-ls`
- Rename a saved session title:
  - `python main.py --sessions-rename session-20250914-010016 "My Title"`
- Load a saved session before chatting:
  - `python main.py --sessions-load session-20250913-234409`

See `docs/CLI.md` for all flags and interactive commands.

## Instrument Flow

Central first tries to answer locally. If it needs an external instrument, it confirms which instrument to use, emits a sanitized `[INSTRUMENT QUERY]…[/INSTRUMENT QUERY]`, and—when automation is unavailable—explains that the request could not be sent. When paired with the Noctics router, the instrument response arrives automatically and is stitched into the conversation as `[INSTRUMENT RESULT]`.

Privacy: Instrument requests are always sanitized (PII redaction + optional name masking). Automation is disabled by default; toggle it with `CENTRAL_HELPER_AUTOMATION` (compat alias) or the JSON config once you wire in the router.

Selecting an instrument: If you haven’t set `--instrument`, the CLI asks you to choose one when the request happens (from `CENTRAL_HELPERS` roster, config roster, or defaults). You can type a number or a custom name.

Common instrument labels (override via env/config):
- claude, gpt-4o, grok, gemini, llama, mistral, cohere, deepseek

First prompt: When you start the CLI it asks for your username (unless `--dev` is supplied) and whether you want streaming enabled. On the first message, it proposes a short title and lets you accept or override it. A `Hardware context: …` line is injected into the system prompt so the assistant knows where it’s running.

## Sessions

- Storage: `~/.local/share/noctics/memory/sessions/YYYY-MM-DD/` by default (override with `NOCTICS_MEMORY_HOME`; legacy `memory/` folders are migrated automatically).
  - Turns: `session-*.jsonl` (JSON Lines turn records; legacy `.json` files still load)
  - Day aggregate: `day.json` (auto-appended when sessions close; deduped)
  - Meta: `session-*.meta.json` (title, turns, created/updated, etc.)
- Titles:
  - Set in-session: `/title My Topic`
  - Rename any saved session: `/rename session-YYYYMMDD-HHMMSS New Title` or `--sessions-rename ...`
  - Auto-title: on exit, Central derives a concise title from the first meaningful user message if you didn’t set one
- Listing:
  - Non-interactive: `--sessions-ls` (full list), `--sessions-latest` (show most recent), or `--sessions-archive-early` (merge everything except latest into `~/.local/share/noctics/memory/early-archives/`)
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
