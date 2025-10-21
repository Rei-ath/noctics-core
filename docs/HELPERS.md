# Instrument Hustle (how Nox calls in backup)

Central knows when it’s outmatched and needs an external instrument—an LLM router,
another provider, whatever muscle you’ve got. Here’s how to control the flow.

## Label the helper
- CLI flags: `--instrument claude` (alias `--helper`)
- Slash command: `/helper claude` (or `/helper` alone to clear)
- No label set? You’ll get a picker with whatever roster we know about.

Rosters come from:
1. `CENTRAL_HELPERS` or `CENTRAL_INSTRUMENTS` env vars (`"claude,gpt-4o,grok"`)
2. `config/central.json`:
   ```json
   {
     "helper": {
       "roster": ["claude", "gpt-4o"],
       "automation": false
     }
   }
   ```
3. Built-in defaults if you’re too lazy to configure

## Sanitization + tags
- `--sanitize` (or env defaults) scrubs common PII.
- `CENTRAL_REDACT_NAMES="Alice,Bob"` masks extra tokens.
- Instrument requests show up as:
  ```
  [INSTRUMENT QUERY]
  ...
  [/INSTRUMENT QUERY]
  ```
- `--anon-instrument` (aliases respect `CENTRAL_INSTRUMENT_ANON`) keeps identifiers vague when logging.

## Built-in providers
- **OpenAI** – Models starting with `gpt`, `o1`, or URLs hitting `api.openai.com`.
- **Anthropic** – Any `claude-*`, `haiku`, or `sonnet` models, plus `api.anthropic.com`.
- More? Drop a plugin that imports `instruments.register_instrument` and call it with your class. Set
  `CENTRAL_INSTRUMENT_PLUGINS="your_module,another_module"` to auto-import on startup.

## Automation story
1. Central explains why an instrument is needed and prints the sanitized query.
2. Automation off (default): you get instructions to run it yourself.
3. Automation on: set `CENTRAL_HELPER_AUTOMATION=1` (compat alias). A router listens for the query, sends it out, and feeds `[INSTRUMENT RESULT]` back to Central.
4. `ChatClient.process_instrument_result(...)` handles the stitching so the conversation resumes smoothly.

## Custom routers
If you’re writing your own router:
- Watch session logs for `[INSTRUMENT QUERY]`.
- Parse the label (if any) and query text.
- Send the request to your provider, collect the response.
- Feed it back via the CLI prompt or `process_instrument_result`.

## Pro tips
- Keep helper names short and unique—makes tab-completion happier.
- Use env overrides per deployment (`CENTRAL_HELPERS="gpt-4o,claude"`) so you don’t leak internal rosters.
- Remember to sanitize helper outputs before you paste them back; Central logs everything by default.

That’s the playbook. Automate it, extend it, or ignore it and keep doing manual pastes—either way, I’m logging the receipts.
