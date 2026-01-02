# Instrument Flow (core)

The public core ships the hooks for instrument routing, but not the router
itself. If the optional `instruments` package is installed (in the full
Noctics suite), `ChatClient` will attempt to call it automatically.

## When instruments are used
- `ChatClient.wants_instrument(text)` detects `[INSTRUMENT QUERY]` blocks.
- If an instrument backend is available, `ChatClient.one_turn(...)` tries it
  before falling back to the local transport.
- To stitch a manual result back in, call `ChatClient.process_instrument_result(...)`.

## Parsing and sanitizing queries
Use the helper utilities in `central.commands.instrument`:
- `extract_instrument_query(text)` pulls the block contents.
- `anonymize_for_instrument(text, user_name=...)` redacts common PII and names.
- `print_sanitized_instrument_query(...)` prints a friendly, sanitized preview.

Example flow:
```python
from central.core import ChatClient
from central.commands.instrument import extract_instrument_query, anonymize_for_instrument

client = ChatClient(url="http://127.0.0.1:11434/api/chat", model="nox")
reply = client.one_turn("Handle the request and call an instrument if needed.")
query = extract_instrument_query(reply or "")
if query:
    safe_query = anonymize_for_instrument(query, user_name="Rei")
    # send safe_query to your provider, then stitch the result:
    client.process_instrument_result("<provider response>")
```

## Instrument roster + automation config
These settings are consumed by the full Noctics CLI (and available to your own
routers):
- `NOX_INSTRUMENTS` - comma-separated labels (ex: `"claude,gpt-4o"`).
- `NOX_INSTRUMENT_AUTOMATION` - `1/true/on` to enable automation.
- `NOX_REDACT_NAMES` - extra names to redact in queries.

Config file (`config/central.json` or `NOX_CONFIG`) example:
```json
{
  "instrument": {
    "automation": false,
    "roster": ["claude", "gpt-4o"]
  }
}
```

## Instrument result prompt
`ChatClient.process_instrument_result(...)` prepends an instrument follow-up
prompt. Override it by creating:
`central/memory/instrument_result_prompt.txt`
Otherwise the built-in default prompt is used.

## Safety note
Always sanitize and validate external instrument responses before logging or
replaying them. The core logger stores whatever you provide.
