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
- `memory/`: packaged prompts (`system_prompt.txt`, `system_prompt.dev.txt`, etc.). Live session data defaults to `~/.local/share/noctics/memory/` so it persists across repo updates (override with `NOCTICS_MEMORY_HOME`).
- `models/`: `ModelFile` templates or manual `.gguf` drops; the bootstrap script reads from here when it cannot `ollama pull`.
- `inference/`: houses the cached `ollama` binary (or `ollama-mini` clone).
- `scripts/`: automation (`nox.run`, self-play/self-improve harnesses).
- `tests/`: pytest suite covering CLI, helper flow, transport, logging, titles.
- `docs/`: task guides (CLI usage, helpers, sessions) – keep them in sync with behavior.
- `instruments/`: SDK-backed provider integrations. `OpenAIInstrument` is the first implementation; additional vendors drop in here and register through `instruments.__init__`.

### Build Targets
- `scripts/build_release.sh` → standard `dist/noctics-core/` bundle.
- `scripts/build_j_rei.sh` → optional personal bundle that mirrors your active `.env`.
- `scripts/build_edge.sh` → centi-nox (Qwen3 8B) bundle (`dist/centi-noctics/`).
- `scripts/build_ejer.sh` → micro-nox (Qwen3 1.7B) bundle (`dist/micro-noctics/`).
All builds package the shared prompts (`memory/system_prompt.txt` and `memory/system_prompt.dev.txt`) so the assistant identifies itself as the scale-aware `*-nox` persona (normal vs developer mode).

### Nox Scale Map

| Scale | Central Name | Variant Alias | Model Target | Personality Snapshot |
|-------|---------------|---------------|--------------|----------------------|
| nano  | nano-nox      | nano-nox  | qwen3:0.6b   | Lightning-fast heuristics and ultra-low resource footprint. |
| micro | micro-nox     | micro-nox | qwen3:1.7b   | Agile analyst balancing speed with deeper reasoning. |
| milli | milli-nox     | milli-nox | qwen3:4b     | Strategic planner for architecture and refactors. |
| centi | centi-nox     | centi-nox | qwen3:8b     | Flagship counselor with long-form reasoning stamina. |

### Persona Personalisation

Customise the assistant voice without touching source code:

1. Copy the template below into `config/persona.overrides.json`.
2. Adjust the name/tagline/strengths/limits per scale (keys are case-insensitive).
3. Run `python -c "from central.persona import reload_persona_overrides; reload_persona_overrides()"`.
4. Restart the CLI (`python main.py` or `./noctics chat`) and confirm the status HUD shows your phrasing.

```json
{
  "global": {
    "tagline": "Studio co-pilot for Rei",
    "strengths": "Knows local dotfiles|Remembers helper etiquette"
  },
  "scales": {
    "nano": {
      "central_name": "spark-nox",
      "limits": [
        "Prefers concise prompts",
        "Escalate big research to milli/centi"
      ]
    }
  }
}
```

You can also tweak individual fields on the fly:

```bash
export CENTRAL_NOX_SCALE=centi
export CENTRAL_PERSONA_TAGLINE_CENTI="Chief of staff for long-range planning"
export CENTRAL_PERSONA_STRENGTHS="Synthesises multi-day notes|Keeps action lists tight"
```

Central applies overrides in the following order (later entries win):

1. `config/persona.overrides.json` (or any path set in `CENTRAL_PERSONA_FILE`).
   ```json
   {
     "global": {"tagline": "Always-on studio co-pilot"},
     "scales": {
       "micro": {
         "central_name": "spark-nox",
         "strengths": ["Knows Rei's dotfiles", "Loves test benches"],
         "limits": "Prefers focused prompts"
       }
     }
   }
   ```
   Fields accept either strings or arrays; string lists are split on commas, pipes, or newlines.
2. Environment variables (global or scale-specific):
   - `CENTRAL_PERSONA_NAME`, `CENTRAL_PERSONA_VARIANT`, `CENTRAL_PERSONA_MODEL`, `CENTRAL_PERSONA_PARAMETERS`,
     `CENTRAL_PERSONA_TAGLINE`, `CENTRAL_PERSONA_STRENGTHS`, `CENTRAL_PERSONA_LIMITS`
   - Scale-specific overrides append `_<SCALE>` (e.g. `CENTRAL_PERSONA_TAGLINE_CENTI`).
3. `CENTRAL_NOX_SCALE` selects which scale persona to load when the model string is ambiguous.

For deeper examples (including troubleshooting tips), see `core/docs/PERSONA.md`.

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
- Instrument semantics live in `memory/system_prompt.txt`; adjust only if you change the external-calls workflow. Legacy “helper” aliases are maintained for compatibility.
- Dev mode (gated by passphrase) unlocks shell bridging and shows developer diagnostics; keep it hidden in user mode.
- Sanitisation removes `<think>` traces before streaming replies; `--show-think` toggles the explicit thinking loader animation.

## Sessions & Memory
- Each run writes JSONL logs under `~/.local/share/noctics/memory/sessions/<YYYY-MM-DD>/session-*.jsonl` with `.meta.json` sidecars (automatically migrated from the legacy `memory/` folder if present).
- `noxl.sessions` APIs support listing, loading past turns, merging, and archival (`python -m noxl --help`).
- Session titles can be set by Central mid-chat via `[SET TITLE]Name[/SET TITLE]`; CLI stores the latest title and updates metadata.

## Security & Operations
- Never commit secrets or API keys; rely on local `.env` (gitignored) if you need overrides.
- Keep `inference/ollama` executable up to date by rerunning `scripts/nox.run` (it will refresh from `OLLAMA_REPO_URL`).
- Validate external inputs at module boundaries and guard helper responses before storing them.
- When bundling releases, use `noctics_bundle.spec` / PyInstaller and include the `inference/ollama` binary plus required model assets.
