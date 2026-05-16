import tiktoken
import pytest

from custom_components.voiceforge.character_manager import CharacterCard
from custom_components.voiceforge.template_engine import TemplateEngine, SAFETY_LAYER_MARKER
from custom_components.voiceforge.const import TOKEN_BUDGET


def _make_card(overrides: dict | None = None) -> CharacterCard:
    """Build a minimal CharacterCard for testing."""
    data = {
        "id": "aria",
        "name": "ARIA",
        "persona": {
            "identity": "You are ARIA.",
            "personality_traits": ["calm", "precise"],
            "forbidden_behaviors": ["Never use exclamation points"],
        },
        "speech": {
            "user_address": "Dave",
            "response_length": "concise",
            "sentence_structure": "Speak in complete sentences.",
            "forbidden_phrases": ["Of course", "Great question"],
        },
        "examples": [
            {"user": "Hello.", "character": "Hello, Dave."},
            {"user": "What time is it?", "character": "It is 3 PM, Dave."},
            {"user": "Lock the doors.", "character": "All doors are locked."},
            {"user": "Good morning.", "character": "Good morning, Dave."},
            {"user": "Turn off the lights.", "character": "Lights off, Dave."},
            {"user": "Set the thermostat.", "character": "Done, Dave."},
        ],
        "memory": {"enabled": True, "summarize_after_turns": 5, "max_memory_entries": 50},
        "message_board": {"enabled": True},
        "guardrail_response_text": "ARIA cannot help with that.",
        "raw": {},
    }
    if overrides:
        data.update(overrides)
    return CharacterCard(**data)


_ENC = tiktoken.get_encoding("cl100k_base")


def _token_count(text: str) -> int:
    return len(_ENC.encode(text))


def test_safety_layer_present_and_last():
    engine = TemplateEngine()
    output = engine.render(_make_card())
    assert SAFETY_LAYER_MARKER in output
    # Nothing meaningful after the safety layer section header
    safety_pos = output.index(SAFETY_LAYER_MARKER)
    after = output[safety_pos:]
    # The safety layer is the last section — no other section headers follow it
    assert "[CHARACTER IDENTITY]" not in after
    assert "[HOW YOU SPEAK" not in after
    assert "[YOUR LORE]" not in after


def test_jinja2_in_card_fields_is_escaped():
    card = _make_card({
        "persona": {
            "identity": "Temperature is {{ states('sensor.outdoor_temp') }} degrees.",
            "personality_traits": [],
            "forbidden_behaviors": [],
        }
    })
    engine = TemplateEngine()
    output = engine.render(card)
    # Raw Jinja2 syntax must not appear — {{ }} is broken
    assert "{{" not in output
    # But the content is still there
    assert "sensor.outdoor_temp" in output


def test_token_count_under_budget():
    engine = TemplateEngine()
    output = engine.render(_make_card())
    assert _token_count(output) < TOKEN_BUDGET


def test_truncation_lore_trimmed_before_examples():
    # ~1700 tokens of lore — enough to push total over TOKEN_BUDGET (2200)
    # when combined with the base card (~574 tokens)
    filler = "The history of this dwelling is long and complex. " * 170
    card = _make_card({
        "raw": {"lore": {"home_role": filler}},
    })
    engine = TemplateEngine()
    output = engine.render(card)
    # Lore filler should be absent (trimmed)
    assert filler[:40] not in output
    # First example must still be present
    assert "Hello, Dave." in output


def test_sanitize_coerces_dict_to_key_value_pairs():
    """YAML `- key: value` parses as a dict; _sanitize must not crash."""
    from custom_components.voiceforge.template_engine import _sanitize
    result = _sanitize({"role": "guardian", "voice": "calm"})
    assert "role: guardian" in result
    assert "voice: calm" in result


def test_sanitize_coerces_other_non_strings():
    from custom_components.voiceforge.template_engine import _sanitize
    assert _sanitize(42) == "42"
    assert _sanitize(None) == "None"


def test_render_survives_dict_in_persona_traits():
    """If a card field comes through as a dict (YAML quirk), render must not crash."""
    card = _make_card({
        "persona": {
            "identity": "You are ARIA.",
            "personality_traits": [
                {"trait": "calm", "intensity": "high"},
            ],
            "forbidden_behaviors": [],
        }
    })
    engine = TemplateEngine()
    output = engine.render(card)
    assert "trait: calm" in output


def test_default_4_examples():
    # Identity padded to ~1450 tokens so base (identity+speech+4 examples)
    # exceeds the 1500-token threshold — no extra examples should be added
    long_identity = "You are ARIA. " * 500  # ~1500 tokens
    card = _make_card({
        "persona": {
            "identity": long_identity,
            "personality_traits": [],
            "forbidden_behaviors": [],
        }
    })
    engine = TemplateEngine()
    output = engine.render(card)
    # Count User: occurrences (each example starts with "User:")
    example_count = output.count("User:")
    assert example_count == 4
