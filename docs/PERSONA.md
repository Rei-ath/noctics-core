# Persona Remix Manual (core)

Nox Core ships a single built-in persona (`nox`). You can override the
name/tagline/strengths/limits without touching source.

## Default persona
| Scale | Central name | Model target |
|-------|--------------|--------------|
| nox   | nox          | qwen2.5:0.5b |

## Selection and precedence
- Persona selection checks `NOX_SCALE`, then the model name, using aliases and
  substring matches (for example `nox`, `nox:latest`, `qwen2.5:0.5b`).
- Override order:
  1. Built-in catalog
  2. JSON overrides (global, then scale)
  3. Env overrides (`NOX_PERSONA_*`) which win

## Override file locations
- `NOX_PERSONA_FILE` (explicit path)
- `config/persona.overrides.json`
- `persona.override.json`
- `persona.overrides.json`

## Fields you can set
Canonical fields:
- `central_name`
- `variant_name`
- `model_target`
- `parameter_label`
- `tagline`
- `strengths` (string or list; comma/pipe/newline split)
- `limits` (string or list; comma/pipe/newline split)

Accepted JSON aliases:
- `name`, `variant`, `model`, `parameters`, `motto`, `summary`,
  `limitations`, `weaknesses`

## JSON template
```json
{
  "global": {
    "tagline": "Always-on studio co-pilot",
    "strengths": "Keeps private briefs tight|Checks every command twice"
  },
  "scales": {
    "nox": {
      "central_name": "spark-nox",
      "parameter_label": "0.5B tuned for dev loops",
      "limits": [
        "Prefers focused prompts",
        "Use a bigger/remote model for heavy research"
      ]
    }
  }
}
```

Reload without restarting:
```python
from central.persona import reload_persona_overrides
reload_persona_overrides()
```

## Env quick tweaks
```bash
export NOX_SCALE=nox
export NOX_PERSONA_TAGLINE="Studio co-pilot"
export NOX_PERSONA_STRENGTHS="Knows Rei's dotfiles|Keeps dev shells tidy"
export NOX_PERSONA_LIMITS="Needs extra GPU juice"
```

Scale-specific env vars append the uppercase scale, for example
`NOX_PERSONA_TAGLINE_NOX`.

## Template tokens
System prompt templates can include:
- `{{NOX_NAME}}`
- `{{NOX_VARIANT}}`
- `{{NOX_VARIANT_DISPLAY}}`
- `{{NOX_SCALE}}`
- `{{NOX_SCALE_LABEL}}`
- `{{NOX_MODEL_TARGET}}`
- `{{NOX_PERSONA_TAGLINE}}`
- `{{NOX_PERSONA_SUMMARY}}`
- `{{NOX_PERSONA_STRENGTHS}}`
- `{{NOX_PERSONA_LIMITS}}`

## Troubleshooting
- Lists collapsing to one bullet? Separate with commas, pipes, or JSON arrays.
- Defaults still showing? Check `NOX_PERSONA_FILE` path and field names.
- Need a clean slate? Remove overrides and call `reload_persona_overrides()`.
