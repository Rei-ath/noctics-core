# Noctics Agents Guide

## Setup Checklist
- Clone the repo and create a virtualenv: `python -m venv jenv && source jenv/bin/activate`.
- Install tooling: `pip install -r requirements.txt` (keep runtime stdlib-only).
- Prefer the bootstrap script: run `scripts/nox.run` to spin up the bundled Ollama binary, pull/build the model, and launch Central with the right URL/model exports.
- Export overrides when needed: `CENTRAL_MODEL`, `CENTRAL_LLM_URL_OVERRIDE`, `CENTRAL_LLM_MODEL_OVERRIDE`, `OLLAMA_HOST`, `OLLAMA_REPO_URL`.

## Submodules & Repository Sync
- The root project now vendors the `noctics-core` git repo as a submodule at `core/`. After cloning the top-level repo run `git submodule update --init --recursive` to pull the core sources.
- Day-to-day core work still happens inside `core/`; commit and push there first (`git -C core status`, `git -C core commit …`, `git -C core push origin main`).
- Once `noctics-core` is pushed, update the superproject pointer from the repo root with `git add core && git commit -m "chore: bump core"` (or bundle other top-level changes). Push the superproject afterwards.
- Configure `git config push.recurseSubmodules on-demand` in the superproject so a single `git push` can cascade core commits when needed.
- Never rewrite the submodule from the parent via `git add core/…` file paths—stage the submodule pointer only.

## Repository Layout
- `central/`
  - `cli/`: argument parsing, interactive shell, dev tooling, startup status HUD.
  - `commands/`: helper/session command handlers used by the CLI.
  - `core/`: `ChatClient`, helper prompt loader, payload builders, reasoning filters.
  - `config.py`: loads JSON config overrides and environment toggles.
  - `connector.py`: transport wiring layer—swap this if Central needs a different backend.
  - `system_info.py`, `runtime_identity.py`, `version.py`, `colors.py`: shared utilities.
- `interfaces/`: adapters for dotenv loading, session logging, PII sanitisation.
- `noxl/`: programmatic access to session utilities plus an alternate CLI.
- `memory/`: `system_prompt.txt`, per-session logs (`memory/sessions/...`), day aggregates.
- `models/`: `ModelFile` templates or manual `.gguf` drops; the bootstrap script reads from here when it cannot `ollama pull`.
- `inference/`: houses the cached `ollama` binary (or `ollama-mini` clone).
- `scripts/`: automation (`nox.run`, self-play/self-improve harnesses).
- `tests/`: pytest suite covering CLI, helper flow, transport, logging, titles.
- `docs/`: task guides (CLI usage, helpers, sessions) – keep them in sync with behavior.
- `instruments/`: SDK-backed provider integrations. `OpenAIInstrument` is the first implementation; additional vendors drop in here and register through `instruments.__init__`.

## Development Workflow
- Activate the env (`source jenv/bin/activate`) before linting or testing.
- Run tests: `pytest -q` or targeted selections (`pytest -k helper -q`).
- Lint/format: `ruff check .`, `black .`, `isort .` as needed (match CI expectations).
- Use `scripts/nox.run` for manual testing; it prints the endpoint/model and will pull/build `CENTRAL_MODEL` automatically if Ollama lacks it.
- Central auto-detects SDK instruments (e.g., OpenAI) via `instruments/`; ensure required SDKs (`pip install openai>=1.0`) and API keys (`OPENAI_API_KEY`/`CENTRAL_LLM_API_KEY`) are present when targeting remote providers. Streaming falls back to raw HTTP if an instrument is unavailable.
- When developing helper automation, simulate helper queries via the CLI; Central emits `[HELPER QUERY]` when its self-score ≤ 5 and expects the router to respond.
- Keep commits clean (Conventional Commits) and avoid reintroducing large binaries—if one slips in, rewrite history with `git filter-repo` before pushing.

## Runtime & Helper Behaviour
- Central self-scores responses; at ≤ 5 it prepares a helper query. If no router is integrated it tells the user helpers are unavailable.
- Helper roster awareness lives in `memory/system_prompt.txt`; adjust when adding or removing helpers.
- Dev mode (gated by passphrase) unlocks shell bridging and shows developer diagnostics; keep it hidden in user mode.
- Sanitisation removes `<think>` traces before streaming replies; `--show-think` toggles the explicit thinking loader animation.

## Sessions & Memory
- Each run writes JSONL logs under `memory/sessions/<YYYY-MM-DD>/session-*.jsonl` with `.meta.json` sidecars.
- `noxl.sessions` APIs support listing, loading past turns, merging, and archival (`python -m noxl --help`).
- Session titles can be set by Central mid-chat via `[SET TITLE]Name[/SET TITLE]`; CLI stores the latest title and updates metadata.

## Security & Operations
- Never commit secrets or API keys; rely on local `.env` (gitignored) if you need overrides.
- Keep `inference/ollama` executable up to date by rerunning `scripts/nox.run` (it will refresh from `OLLAMA_REPO_URL`).
- Validate external inputs at module boundaries and guard helper responses before storing them.
- When bundling releases, use `noctics_bundle.spec` / PyInstaller and include the `inference/ollama` binary plus required model assets.
