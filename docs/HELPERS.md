# Instrument Workflow

Central detects when an external instrument is needed, sanitises the payload, and clearly states whether the request could be sent. Automatic routing is handled by the Noctics router, but you can already customise the roster and automation toggle via environment variables or `config/central.json`.

## Instrument labels

- Set a label with `--instrument NAME` (alias: `--helper`) or `/instrument NAME` (alias: `/helper`); clear with `/instrument` (or `/helper`).
- If no label is set, the CLI prompts you to choose one when the instrument request happens (env roster, JSON config roster, or defaults).
- You can define a roster in config: `config/central.json` → `{ "helper": { "roster": ["claude", "gpt-4o"] } }`. Environment `CENTRAL_HELPERS` overrides both config and defaults.

## Sanitized instrument queries

PII redaction (`--sanitize`) runs first. `CENTRAL_REDACT_NAMES` masks additional names. Instrument requests are wrapped in `[INSTRUMENT QUERY]…[/INSTRUMENT QUERY]`. `--anon-instrument` (alias: `--anon-helper`) remains reserved for when router automation ships.

## What happens today?

1. Central emits a human-friendly explanation plus `[INSTRUMENT QUERY]`.
2. If automation is disabled, Central notes that the request could not be sent and offers alternative local steps.
3. When deployed with the router, set `CENTRAL_HELPER_AUTOMATION=1` (compat alias) so the router performs the instrument call automatically and returns `[INSTRUMENT RESULT]` for stitching.
