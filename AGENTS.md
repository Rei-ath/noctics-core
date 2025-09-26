# Repository Guidelines

## Project Structure & Module Organization
- `central/`: Core chat client, CLI, commands, and color helpers.
  - `central/core.py`: importable ChatClient + session utilities.
  - `central/cli.py`: interactive CLI (streams, helpers, sessions).
  - `central/commands/`: small CLI helpers (completion, sessions, helper flow).
- `interfaces/`: Integrations and adapters (e.g., `.env` loader, session logger, PII sanitizer).
- `memory/`: System prompt and session storage (`session-*.jsonl` per run, `day.json` aggregates).
- `tests/`: Pytest suite (e.g., `tests/test_core_title.py`, `tests/test_session_logger.py`).
- `main.py`: Local entry point.
- `requirements.txt`: Dev/test tools (runtime is stdlib-only).
- `jenv/`: Local Python virtualenv (ignored).

Import policy: prefer public functions across modules; avoid deep internals. Keep modules small and cohesive.

## Build, Test, and Development Commands
- Create env: `python -m venv jenv && source jenv/bin/activate` (Python 3.13).
- Install dev deps: `pip install -r requirements.txt` (runtime uses stdlib; tests need these).
- Run app: `python main.py`.
- Run tests: `source jenv/bin/activate && pytest -q` (subset example: `source jenv/bin/activate && pytest -k core -q`).
- Coverage: `pytest --cov=.` (requires `pytest-cov`).

## Coding Style & Naming Conventions
- Indentation: 4 spaces; follow PEP 8; use type hints.
- Naming: `snake_case` functions/vars, `PascalCase` classes, `lower_snake_case.py` modules.
- Docstrings: brief, task-focused summaries on public APIs.
- Tooling: `ruff check .`, `black .`, `isort .` (run before PRs).

## Testing Guidelines
- Framework: `pytest`; tests live under `tests/` and are named `test_*.py`.
- Seed tests: `compute_title_from_messages` and `SessionLogger` behaviors are covered; extend as you add features.
- Coverage: ≥ 80% for changed lines; include edge cases in `central/core.py` and `interfaces/session_logger.py`.
- Practices: one behavior per test; prefer fixtures; keep tests deterministic.

## CLI Usage Examples
- Stream responses: `python main.py --stream`
- Name a helper and stream: `python main.py --helper claude --stream`
- One-off user message: `python main.py --user "Explain X" --stream`
- Provide messages array: `python main.py --messages msgs.json --stream`
- Show version: `python main.py --version`
- Sessions list/load/rename:
  - `python main.py --sessions-ls`
  - `python main.py --sessions-browse`
  - `python main.py --sessions-load session-YYYYMMDD-HHMMSS` (or `/load` → interactive picker)
  - `python main.py --sessions-rename session-YYYYMMDD-HHMMSS "My Title"`
  - `python main.py --sessions-archive-early`

### Default helper roster
- claude (Anthropic)
- gpt-4o / gpt-4 (OpenAI)
- grok (xAI)
- gemini (Google)
- llama (Meta)
- mistral (Mistral AI)
- cohere (Cohere)
- deepseek (DeepSeek)

## Commit & Pull Request Guidelines
- Commits: Conventional Commits.
  - Examples: `feat(memory): add vector anchor lookup`, `fix(reasoning): guard null plan step`.
- PRs: clear description, linked issues, updated tests, and screenshots/logs if helpful; keep scope small.
- Checks: tests green; lint/format clean; no secrets or env-specific files.

## Security & Configuration Tips
- Never commit secrets or API keys; use environment variables or a local `.env` (gitignored).
- Keep `jenv/` untracked; recreate locally as needed.
- Validate inputs at module boundaries; prefer least-privilege defaults for external calls.

## Architecture Overview
- Central is a local-first chat orchestrator; the reusable client lives in `central/core.py` and the CLI wrapper in `central/cli.py`.
- Network access is isolated in `central/transport.py`, which handles JSON POST requests and SSE streaming.
- Persistence, helper flows, and utilities are split into `central/commands/`, `interfaces/`, and the `noxl/` toolkit.
- Runtime remains stdlib-only; optional tooling (pytest, ruff, black, etc.) is listed in `requirements.txt`.

## Core Runtime (`central/core.py`)
- `ChatClient` wires dotenv loading, message history, helper detection, and session logging.
- Streaming runs strip `<think>` sections before surfacing deltas; non-streaming calls sanitize replies on completion.
- Helper follow-ups wrap normalized `[HELPER RESULT]` payloads and add the helper system prompt fetched by `_load_helper_prompt()`.
- Session management helpers cover auto-titling, empty-session cleanup, and day-log aggregation via `noxl` utilities.

## CLI Workflow (`central/cli.py`)
- The CLI bootstraps environment variables, prompts the user to choose or create a profile (unless `--dev` is supplied), asks whether to enable streaming, and then instantiates `ChatClient`.
- It can preload saved sessions, inject identity context into the system prompt, and run in one-shot or interactive REPL modes.
- Slash commands support session browsing, renaming, merging, archiving, helper selection, and contextual toggles like `/anon`.
- On exit the CLI auto-generates a session title when possible, deletes empty logs, and appends summaries to the day aggregate.

## Helper Flow & Session Utilities
- The CLI prompts for a helper label when Central emits a `[HELPER QUERY]`. Automation is manual by default—users paste `[HELPER RESULT]` with `/result`. Install the full Noctics router and toggle `CENTRAL_HELPER_AUTOMATION` (or JSON config) to enable automatic dispatch.
- `central/commands/sessions.py` wraps `noxl` helpers for listing, loading, merging, and showing stored conversations with paired turn output.
- `noxl/__init__.py` exposes programmatic helpers (list, load, merge, archive) for scripts or the alternate `python -m noxl` CLI.

## Persistence & Identity
- `interfaces/session_logger.py` writes per-turn JSONL records alongside `.meta.json` sidecars, recording model, sanitized state, titles, and user info.
- When a `memory_user` is provided, logs are stored under `memory/users/<user>/sessions/` and the user profile is updated in `user.json`.
- Developer identity context is resolved via `interfaces/dev_identity.py`, falling back to env vars or stored metadata before using the default "Rei" profile.

## Testing & Coverage Notes
- Tests under `tests/` exercise title computation, CLI identity onboarding, helper prompting, reasoning stripping, session logging, transport SSE parsing, and archival flows.
- Streaming and helper behaviors are validated with stub transports (`tests/test_strip_reasoning.py`) and helper prompts (`tests/test_helper_prompt.py`).
- Session logging persistence and metadata integrity are guarded by `tests/test_session_logger.py`, while archival and day-log behavior is covered in `tests/test_archive_early.py` and `tests/test_day_aggregate.py`.
