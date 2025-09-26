# Helper Workflow

Central v0 keeps helpers manual by design. It detects when the assistant wants outside help, sanitises the payload, and guides you through the copy/paste loop. Automatic routing is reserved for the upcoming Noctics router service, but you can already customise the roster and automation toggle via environment variables or `config/central.json`.

## Helper labels

- Set a label with `--helper NAME` or `/helper NAME`; clear it with `/helper`.
- If no label is set, the CLI prompts you to choose one when the helper request happens (env roster, JSON config roster, or defaults).
- You can define a roster in config: `config/central.json` → `{ "helper": { "roster": ["claude", "gpt-4o"] } }`. Environment `CENTRAL_HELPERS` overrides both config and defaults.

## Sanitized helper queries

PII redaction (`--sanitize`) still runs first. `CENTRAL_REDACT_NAMES` masks additional names, and the helper block is always wrapped in `[HELPER QUERY]…[/HELPER QUERY]` / `[HELPER RESULT]…[/HELPER RESULT]`. `--anon-helper` remains reserved for when router automation ships.

## What happens today?

1. Central emits a human-friendly explanation plus the `[HELPER QUERY]` block.
2. If automation is disabled, the CLI tells you to consult the chosen helper and paste the result using `/result` (ending input with a single `.` line).
3. `ChatClient.process_helper_result` consumes the pasted text and logs it as part of the conversation.
4. If you deploy Central within the full Noctics suite, set `CENTRAL_HELPER_AUTOMATION=1` (or turn it on in `config/central.json`) so the router can perform the helper call automatically.
