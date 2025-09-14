# Repository Guidelines

## Project Structure & Module Organization
- `interfaces/`: Integrations and orchestration adapters (e.g., `orchestrator_link.py`).
- `memory/`: Long-/short-term state, anchors, and helpers.
- `reasoning/`: Core reasoning utilities and algorithms.
- `tests/`: Pytest suite (e.g., `tests/test_memory.py`).
- `main.py`: Local entry point.
- `requirements.txt`: Runtime and dev dependencies.
- `jenv/`: Local Python virtualenv (ignored).

Import policy: prefer public functions across modules; avoid deep internals. Keep modules small and cohesive.

## Build, Test, and Development Commands
- Create env: `python -m venv jenv && source jenv/bin/activate` (Python 3.13).
- Install deps: `pip install -r requirements.txt`.
- Run app: `python main.py`.
- Run tests: `pytest -q` (subset: `pytest -k reasoning -q`).
- Coverage: `pytest --cov=.` (requires `pytest-cov`).

## Coding Style & Naming Conventions
- Indentation: 4 spaces; follow PEP 8; use type hints.
- Naming: `snake_case` functions/vars, `PascalCase` classes, `lower_snake_case.py` modules.
- Docstrings: brief, task-focused summaries on public APIs.
- Tooling: `ruff check .`, `black .`, `isort .` (run before PRs).

## Testing Guidelines
- Framework: `pytest`; tests live under `tests/` and are named `test_*.py`.
- Coverage: ≥ 80% for changed lines; include edge cases in `memory/anchors.py` and `reasoning/core.py`.
- Practices: one behavior per test; prefer fixtures; keep tests deterministic.

## Commit & Pull Request Guidelines
- Commits: Conventional Commits.
  - Examples: `feat(memory): add vector anchor lookup`, `fix(reasoning): guard null plan step`.
- PRs: clear description, linked issues, updated tests, and screenshots/logs if helpful; keep scope small.
- Checks: tests green; lint/format clean; no secrets or env-specific files.

## Security & Configuration Tips
- Never commit secrets or API keys; use environment variables or a local `.env` (gitignored).
- Keep `jenv/` untracked; recreate locally as needed.
- Validate inputs at module boundaries; prefer least-privilege defaults for external calls.
