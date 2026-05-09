import logging

import pytest
import yaml
from pathlib import Path

from custom_components.voiceforge.character_manager import CharacterCard, CharacterManager


VALID_CARD = {
    "schema_version": "1.0",
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
    },
    "examples": [{"user": "Hello.", "character": "Hello, Dave."}],
    "memory": {
        "enabled": True,
        "summarize_after_turns": 5,
        "max_memory_entries": 50,
    },
    "message_board": {"enabled": True},
    "guardrail_response": {
        "style": "ARIA declines precisely.",
        "examples": [],
    },
}


def _write_yaml(path: Path, data: dict) -> Path:
    path.write_text(yaml.dump(data), encoding="utf-8")
    return path


def test_load_valid_card_returns_character_card(tmp_path):
    card_path = _write_yaml(tmp_path / "aria.yaml", VALID_CARD)
    manager = CharacterManager(str(tmp_path))
    card = manager.load_card(str(card_path))
    assert isinstance(card, CharacterCard)
    assert card.id == "aria"
    assert card.name == "ARIA"


def test_load_card_missing_required_field_returns_none_and_logs(tmp_path, caplog):
    bad = {k: v for k, v in VALID_CARD.items() if k != "name"}
    card_path = _write_yaml(tmp_path / "bad.yaml", bad)
    manager = CharacterManager(str(tmp_path))
    with caplog.at_level(logging.ERROR):
        card = manager.load_card(str(card_path))
    assert card is None
    assert "name" in caplog.text.lower() or "required" in caplog.text.lower()


def test_load_card_missing_guardrail_uses_default_fallback(tmp_path):
    no_guardrail = {k: v for k, v in VALID_CARD.items() if k != "guardrail_response"}
    card_path = _write_yaml(tmp_path / "aria.yaml", no_guardrail)
    manager = CharacterManager(str(tmp_path))
    card = manager.load_card(str(card_path))
    assert card is not None
    assert "cannot help with that" in card.guardrail_response_text.lower()


def test_switch_character_updates_active_character(tmp_path):
    aria_data = {**VALID_CARD, "id": "aria", "name": "ARIA"}
    sera_data = {**VALID_CARD, "id": "sera", "name": "SERA"}
    _write_yaml(tmp_path / "aria.yaml", aria_data)
    _write_yaml(tmp_path / "sera.yaml", sera_data)

    manager = CharacterManager(str(tmp_path))
    manager.load_all()

    manager.switch_character("aria")
    assert manager.get_active_character().id == "aria"

    manager.switch_character("sera")
    assert manager.get_active_character().id == "sera"


def test_get_all_characters_returns_loaded_library(tmp_path):
    """get_all_characters() returns every card loaded by load_all()."""
    aria_data = {**VALID_CARD, "id": "aria", "name": "ARIA"}
    sera_data = {**VALID_CARD, "id": "sera", "name": "SERA"}
    _write_yaml(tmp_path / "aria.yaml", aria_data)
    _write_yaml(tmp_path / "sera.yaml", sera_data)

    manager = CharacterManager(str(tmp_path))
    manager.load_all()

    cards = manager.get_all_characters()
    assert len(cards) == 2
    ids = {c.id for c in cards}
    assert ids == {"aria", "sera"}
