import json
from pathlib import Path

from central.persona import reload_persona_overrides, render_system_prompt, resolve_persona


def test_resolve_persona_known_alias():
    persona = resolve_persona("qwen3:0.6b")
    assert persona.central_name == "nano-nox"
    assert persona.scale == "nano"


def test_resolve_persona_env_override(monkeypatch):
    monkeypatch.setenv("CENTRAL_NOX_SCALE", "micro")
    persona = resolve_persona("unknown-model")
    assert persona.central_name == "micro-nox"
    assert persona.scale == "micro"


def test_render_system_prompt_is_idempotent():
    persona = resolve_persona("centi-nox")
    template = "Name {{CENTRAL_NAME}}\n{{NOX_PERSONA_STRENGTHS}}\n{{NOX_PERSONA_EMOJI}}"
    rendered = render_system_prompt(template, persona)
    assert "{{" not in rendered
    assert persona.central_name in rendered
    assert "- " in rendered
    assert "{{NOX_PERSONA_EMOJI}}" not in rendered
    assert "  " not in rendered  # no double spaces left behind
    assert render_system_prompt(rendered, persona) == rendered


def test_persona_override_file(monkeypatch, tmp_path: Path):
    override_path = tmp_path / "persona.override.json"
    override_path.write_text(
        json.dumps(
            {
                "global": {"tagline": "Custom signal"},
                "scales": {
                    "nano": {
                        "central_name": "spark-nox",
                        "strengths": ["Knows Rei's shortcuts"],
                        "limits": "Prefers tiny prompts",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CENTRAL_PERSONA_FILE", str(override_path))
    reload_persona_overrides()
    persona = resolve_persona("qwen3:0.6b")
    assert persona.central_name == "spark-nox"
    assert persona.tagline == "Custom signal"
    assert persona.strengths == ("Knows Rei's shortcuts",)
    assert persona.limits == ("Prefers tiny prompts",)
    reload_persona_overrides()


def test_persona_environment_overrides(monkeypatch):
    monkeypatch.delenv("CENTRAL_PERSONA_FILE", raising=False)
    monkeypatch.setenv("CENTRAL_NOX_SCALE", "milli")
    monkeypatch.setenv("CENTRAL_PERSONA_TAGLINE_MILLI", "Hand-crafted by Rei")
    monkeypatch.setenv("CENTRAL_PERSONA_STRENGTHS", "Dev-mode wizardry|Design feedback")
    reload_persona_overrides()
    persona = resolve_persona("ignored")
    assert persona.central_name == "milli-nox"
    assert persona.scale == "milli"
    assert persona.tagline == "Hand-crafted by Rei"
    assert persona.strengths == ("Dev-mode wizardry", "Design feedback")
    reload_persona_overrides()
