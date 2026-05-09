"""Character card loading, validation, and switching. No HA dependencies."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import voluptuous as vol
import yaml

_LOGGER = logging.getLogger(__name__)

DEFAULT_GUARDRAIL_TEMPLATE = "{name} cannot help with that."

_PERSONA_SCHEMA = vol.Schema(
    {
        vol.Required("identity"): str,
        vol.Optional("personality_traits"): list,
        vol.Optional("forbidden_behaviors"): list,
    }
)

_SPEECH_SCHEMA = vol.Schema(
    {
        vol.Required("user_address"): str,
        vol.Required("response_length"): vol.In(["concise", "moderate", "verbose"]),
        vol.Optional("tone_descriptors"): list,
        vol.Optional("sentence_structure"): str,
        vol.Optional("forbidden_phrases"): list,
        vol.Optional("device_control_style"): str,
    }
)

_MEMORY_SCHEMA = vol.Schema(
    {
        vol.Required("enabled"): bool,
        vol.Required("summarize_after_turns"): int,
        vol.Required("max_memory_entries"): int,
        vol.Optional("memory_categories"): list,
        vol.Optional("injection_style"): str,
    }
)

_MESSAGE_BOARD_SCHEMA = vol.Schema(
    {
        vol.Required("enabled"): bool,
        vol.Optional("message_style"): str,
        vol.Optional("voice_delivery"): dict,
        vol.Optional("triggers"): list,
    }
)

CARD_SCHEMA = vol.Schema(
    {
        vol.Required("id"): str,
        vol.Required("name"): str,
        vol.Required("persona"): _PERSONA_SCHEMA,
        vol.Required("speech"): _SPEECH_SCHEMA,
        vol.Required("examples"): [
            {vol.Required("user"): str, vol.Required("character"): str}
        ],
        vol.Required("memory"): _MEMORY_SCHEMA,
        vol.Required("message_board"): _MESSAGE_BOARD_SCHEMA,
        vol.Optional("schema_version"): str,
        vol.Optional("version"): str,
        vol.Optional("author"): str,
        vol.Optional("description"): str,
        vol.Optional("avatar_icon"): str,
        vol.Optional("tags"): list,
        vol.Optional("lore"): dict,
        vol.Optional("voice"): dict,
        vol.Optional("avatar"): dict,
        vol.Optional("guardrail_response"): dict,
    }
)


@dataclass
class CharacterCard:
    id: str
    name: str
    persona: dict
    speech: dict
    examples: list
    memory: dict
    message_board: dict
    guardrail_response_text: str
    raw: dict


class CharacterManager:
    def __init__(self, characters_dir: str) -> None:
        self._characters_dir = characters_dir
        self._library: dict[str, CharacterCard] = {}
        self._active_id: str | None = None

    def load_card(self, path: str) -> CharacterCard | None:
        """Load and validate a YAML character card. Returns None on failure."""
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            validated = CARD_SCHEMA(data)
        except vol.Invalid as exc:
            _LOGGER.error("Character card %s failed validation: %s", path, exc)
            return None
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Failed to load character card %s: %s", path, exc)
            return None

        guardrail_block = validated.get("guardrail_response")
        if guardrail_block and guardrail_block.get("style"):
            guardrail_text = guardrail_block["style"]
        else:
            if guardrail_block is None:
                _LOGGER.warning(
                    "Character card %s missing guardrail_response — using default",
                    path,
                )
            guardrail_text = DEFAULT_GUARDRAIL_TEMPLATE.format(
                name=validated["name"]
            )

        return CharacterCard(
            id=validated["id"],
            name=validated["name"],
            persona=validated["persona"],
            speech=validated["speech"],
            examples=validated["examples"],
            memory=validated["memory"],
            message_board=validated["message_board"],
            guardrail_response_text=guardrail_text,
            raw=validated,
        )

    def load_all(self) -> None:
        """Load all .yaml files from the characters directory."""
        for yaml_path in sorted(Path(self._characters_dir).glob("*.yaml")):
            card = self.load_card(str(yaml_path))
            if card:
                self._library[card.id] = card

    def get_all_characters(self) -> list[CharacterCard]:
        """Return all loaded character cards."""
        return list(self._library.values())

    def get_active_character(self) -> CharacterCard:
        """Return the active character, falling back to ARIA if needed."""
        if self._active_id and self._active_id in self._library:
            return self._library[self._active_id]
        if "aria" in self._library:
            return self._library["aria"]
        if self._library:
            return next(iter(self._library.values()))
        raise RuntimeError("No valid character cards loaded")

    def switch_character(self, character_id: str) -> None:
        """Set the active character by id."""
        if character_id in self._library:
            self._active_id = character_id
        else:
            _LOGGER.error(
                "Character '%s' not found in library; falling back to ARIA",
                character_id,
            )
            self._active_id = "aria"
