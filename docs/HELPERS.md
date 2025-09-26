# Helper Workflow

Central v0 detects when the assistant wants outside help, sanitises the payload, and clearly states whether the request could be sent. Automatic routing is reserved for the upcoming Noctics router service, but you can already customise the roster and automation toggle via environment variables or `config/central.json`.

## Helper labels

- Set a label with `--helper NAME` or `/helper NAME`; clear it with `/helper`.
- If no label is set, the CLI prompts you to choose one when the helper request happens (env roster, JSON config roster, or defaults).
- You can define a roster in config: `config/central.json` → `{ "helper": { "roster": ["claude", "gpt-4o"] } }`. Environment `CENTRAL_HELPERS` overrides both config and defaults.

## Sanitized helper queries

PII redaction (`--sanitize`) still runs first. `CENTRAL_REDACT_NAMES` masks additional names, and helper requests are always wrapped in `[HELPER QUERY]…[/HELPER QUERY]`. `--anon-helper` remains reserved for when router automation ships.

## What happens today?

1. Central emits a human-friendly explanation plus the `[HELPER QUERY]` block.
2. If automation is disabled, Central notes that the request could not be sent and offers alternative local steps.
3. When you deploy Central within the full Noctics suite, set `CENTRAL_HELPER_AUTOMATION=1` (or enable it in `config/central.json`) so the router performs the helper call automatically and returns `[HELPER RESULT]` for stitching.
