# Nox Persona Customization Guide

Noctics Central ships with four scale-aware profiles (`nano-nox`, `micro-nox`, `milli-nox`, `centi-nox`) plus a fallback (`prime-nox`). Each profile controls how Central introduces itself, what strengths it highlights, and which limitations it makes explicit.

This guide shows how to:

1. Understand the built-in scales.
2. Override names/taglines/strengths/limits to match your own style.
3. Confirm the CLI has picked up your changes.

---

## 1. Scale Cheat Sheet

| Scale | Central Name | Variant Alias | Model Target | Best For |
|-------|---------------|---------------|--------------|----------|
| nano  | `nano-nox`    | `nano-noctics`   | `qwen3:0.6b` | Instant answers, terminal helpers, ultra-low resource devices. |
| micro | `micro-nox`   | `micro-noctics`  | `qwen3:1.7b` | Daily driver, small refactors, tutoring with quick feedback loops. |
| milli | `milli-nox`   | `milli-noctics`  | `qwen3:4b`   | Architecture discussions, structured planning, iterative drafting. |
| centi | `centi-nox`   | `centi-noctics`  | `qwen3:8b`   | Long-form analysis, research synthesis, multi-branch reasoning. |

When Central can’t infer the scale from the configured model, it falls back to `prime-nox` (adaptive defaults).

---

## 2. Override Options

Central merges overrides in this order:

1. **Global overrides** (apply to all scales).
2. **Scale-specific overrides** (override the global values for one scale).
3. **Environment variables** (individual tweaks without editing files).

### Fields You Can Override

- `central_name` – Display name (e.g. `"spark-nox"`).
- `variant_name` – How the variant is announced (e.g. `"studio-noctics"`).
- `model_target` – Canonical model string to mention.
- `parameter_label` – Friendly description of the model size.
- `tagline` – One-line summary the CLI shows in the status HUD.
- `strengths` – Bullet points describing the persona’s sweet spots.
- `limits` – Bullet points highlighting trade-offs.

When you provide a string for `strengths` or `limits`, Central splits it on commas, pipes (`|`), or newlines so you can write compact overrides.

---

## 3. Configure via JSON

Create `config/persona.overrides.json` (or point `CENTRAL_PERSONA_FILE` at any path) with the following structure:

```json
{
  "global": {
    "tagline": "Always-on studio co-pilot",
    "strengths": [
      "Keeps private briefs in sync",
      "Checks every command before running it"
    ]
  },
  "scales": {
    "micro": {
      "central_name": "spark-nox",
      "variant_name": "spark-noctics",
      "parameter_label": "1.7B tuned for dev loops",
      "limits": "Prefers focused prompts over sprawling brainstorms"
    },
    "centi": {
      "tagline": "Chief of staff for big-picture planning"
    }
  }
}
```

Any scale keys (`"nano"`, `"micro"`, `"milli"`, `"centi"`) are case-insensitive.

After saving, reload overrides without restarting Python:

```python
from central.persona import reload_persona_overrides
reload_persona_overrides()
```

---

## 4. Quick Tweaks via Environment Variables

Use these for experiments or CI:

```bash
export CENTRAL_NOX_SCALE=micro            # force a scale when model name is ambiguous
export CENTRAL_PERSONA_TAGLINE="Studio co-pilot"
export CENTRAL_PERSONA_STRENGTHS="Knows Rei's configs|Keeps dev shells tidy"
export CENTRAL_PERSONA_LIMITS_MICRO="Avoids long research binges"
```

Environment variables accept either a single value or a pipe/comma/newline separated list for the bullet fields. Scale-specific overrides add `_<SCALE>` (e.g. `CENTRAL_PERSONA_TAGLINE_CENTI`).

---

## 5. Verify in the CLI

1. Reload overrides (see above) or restart the CLI.
2. Run `python main.py` (or `./noctics chat`).
3. On startup you should see:
   - The status HUD showing the updated persona name, variant, and tagline.
   - A system preamble entry that reads `Central persona: …`.
4. If you still see the default branding, double-check:
   - The JSON path in `CENTRAL_PERSONA_FILE`.
   - That your JSON fields are spelled correctly.
   - That `reload_persona_overrides()` was invoked after changes.

---

## 6. Troubleshooting

- **“My overrides apply to all scales”** → Place them under the `"global"` block so every scale shares them.
- **“Only one bullet shows up”** → Separate bullet strings with commas, pipes, or newlines, or provide a JSON array.
- **“I want the original defaults back”** → Remove your override file/environment variables and call `reload_persona_overrides()`; Central reverts to the built-in catalog.

---

Need more control? Ping the core team and we can expand the schema (e.g., custom onboarding messages or per-scale system prompt fragments).
