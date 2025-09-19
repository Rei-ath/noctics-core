# Helper Workflow

Central supports a manual helper workflow when the model asks for external assistance.

## When does it trigger?

- Central emits a `[HELPER QUERY]...[/HELPER QUERY]` block, or
- Central falls back to a helper-required message.

The CLI detects this and prompts you to paste the helper output.

If no helper is set, the CLI asks you to choose a helper label first. It lists helpers from `CENTRAL_HELPERS` (comma‑separated) or a small default list. You can type a number or a custom name.

## How to paste helper output

- You’ll see: `Helper [NAME]: (paste streaming lines; type END on its own line to finish)`.
- Paste the helper output line-by-line; each line echoes immediately (simulated streaming).
- Type `END` on a new line to finish.

The CLI then wraps your paste as a `[HELPER RESULT]...[/HELPER RESULT]` message and sends it back to Central.

## Anonymizing helper queries

When Central asks for a helper and emits a `[HELPER QUERY]...[/HELPER QUERY]` block, the CLI also prints a sanitized version for safe copy/paste by default. It removes common PII (emails, phone numbers, credit cards, IPv4 addresses) and can redact names.

- Toggle with `--anon-helper` / `--no-anon-helper` or interactively with `/anon`.
- Configure extra names to redact with `CENTRAL_REDACT_NAMES="Alice,Bob,Acme"`.
- The interactive prompt label (from `--user-name`) is also redacted when it’s not the generic "You".

## Manually trigger a stitch

- Use `/result` (aliases: `/helper-result`, `/paste-helper`, `/hr`) to paste a helper result at any time.

## With streaming

- If `--stream` is enabled, Central’s stitched response is streamed back after you finish pasting.

## Labeling a helper

- Set a helper label via `--helper NAME` or `/helper NAME`. The label appears in the prompt and helps track which helper provided the result.
- If unset, you’ll be prompted to pick one when a helper is required.
