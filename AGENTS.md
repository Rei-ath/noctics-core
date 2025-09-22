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
- Run tests: `pytest -q` (subset example: `pytest -k core -q`).
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
- Manual mode (no API): `python main.py --manual`
- Name a helper and stream: `python main.py --helper claude --stream`
- One-off user message: `python main.py --user "Explain X" --stream`
- Provide messages array: `python main.py --messages msgs.json --stream`
- Sessions list/load/rename:
- `python main.py --sessions-ls`
- `python main.py --sessions-browse`
- `python main.py --sessions-load session-YYYYMMDD-HHMMSS` (or `/load` → interactive picker)
- `python main.py --sessions-rename session-YYYYMMDD-HHMMSS "My Title"`
- `python main.py --sessions-archive-early`

### Default helper roster
- **CodeSmith** – code, APIs, debugging, refactors
- **DataDive** – analytics, SQL/spreadsheets, KPIs
- **ResearchSleuth** – research synthesis, briefs, comparisons
- **UIWhisperer** – UX copy, product messaging, tone
- **OpsSentinel** – infrastructure, automation, runbooks
- **LegalEagle** – policy/compliance/contracts (guidance only)

## Commit & Pull Request Guidelines
- Commits: Conventional Commits.
  - Examples: `feat(memory): add vector anchor lookup`, `fix(reasoning): guard null plan step`.
- PRs: clear description, linked issues, updated tests, and screenshots/logs if helpful; keep scope small.
- Checks: tests green; lint/format clean; no secrets or env-specific files.

## Security & Configuration Tips
- Never commit secrets or API keys; use environment variables or a local `.env` (gitignored).
- Keep `jenv/` untracked; recreate locally as needed.
- Validate inputs at module boundaries; prefer least-privilege defaults for external calls.
