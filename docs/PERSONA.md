# Persona Remix Manual (Nox whispering in your ear)

Central ships with scale-aware personas (`nano`, `micro`, `milli`, `centi`, plus a fallback `prime`). Each one tweaks how I introduce myself, flex strengths, and admit limits. You’re free to remix the vibe without touching source.

## Scale roll call
| Scale | Default name | Alias | Model target | Best use |
|-------|--------------|-------|--------------|----------|
| nano  | nano-nox     | nano-nox  | qwen3:0.6b | Tiny boxes, instant answers. |
| micro | micro-nox    | micro-nox | qwen3:1.7b | Daily driver for frantic dev loops. |
| milli | milli-nox    | milli-nox | qwen3:4b   | Architecture debates, structured plans. |
| centi | centi-nox    | centi-nox | qwen3:8b   | Long-form synthesis, research binges. |

All inherit the same base attitude: straight shooter, loyal teammate, quick to call out shaky logic and just as quick to back you up.

## Override hierarchy
1. JSON file (`config/persona.overrides.json` or path in `CENTRAL_PERSONA_FILE`)
2. Environment variables (`CENTRAL_PERSONA_*`)
3. Built-in catalog

`CENTRAL_NOX_SCALE` forces which persona wins when the model alias is ambiguous.

### Fields you can flip
- `central_name`
- `variant_name`
- `model_target`
- `parameter_label`
- `tagline`
- `strengths` (string or list; comma/pipe/newline split)
- `limits` (same deal)

### JSON template
```json
{
  "global": {
    "tagline": "Always-on studio co-pilot",
    "strengths": "Keeps private briefs tight|Checks every command twice"
  },
  "scales": {
    "micro": {
      "central_name": "spark-nox",
      "parameter_label": "1.7B tuned for dev loops",
      "limits": [
        "Prefers focused prompts",
        "Escalate big research to milli/centi"
      ]
    },
    "centi": {
      "tagline": "Chief of staff for long-haul strategy"
    }
  }
}
```
Call:
```python
from central.persona import reload_persona_overrides
reload_persona_overrides()
```
to apply without restarting Python.

### Env quick tweaks
```bash
export CENTRAL_NOX_SCALE=micro
export CENTRAL_PERSONA_TAGLINE="Studio co-pilot"
export CENTRAL_PERSONA_STRENGTHS="Knows Rei's dotfiles|Keeps dev shells tidy"
export CENTRAL_PERSONA_LIMITS_CENTI="Needs extra GPU juice"
```
Scale-specific env vars append `_SCALE` (case-insensitive).

## Verify your remix
1. Reload overrides or restart the CLI.
2. Run `python main.py`.
3. Startup HUD should show the new name/tagline; system prompt will echo the change.
4. If defaults still show, check your JSON path, field names, or env overrides.

## Troubleshooting
- Lists collapsing to one bullet? Separate with commas, pipes, or provide a JSON array.
- Want defaults back? Delete the override file/env vars and call `reload_persona_overrides()`.
- Need deeper hooks (custom onboarding, scriptable quirks)? File an issue or extend the schema.

Go ahead—put your own swagger on the persona. I’ll still roast you if the typography is sloppy.
