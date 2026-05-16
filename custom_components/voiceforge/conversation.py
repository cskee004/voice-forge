"""VoiceForge conversation agent — wires all modules into the HA pipeline."""

from __future__ import annotations

import logging
import re
import time

from homeassistant.components.conversation import (
    ConversationEntity,
    ConversationInput,
    ConversationResult,
)
from homeassistant.const import MATCH_ALL
from homeassistant.helpers import intent as ha_intent

from .character_manager import CharacterCard, CharacterManager
from .const import DOMAIN, EMERGENCY_RESPONSE, SESSION_IDLE_TTL
from .llm_client import LLMClient
from .safety_classifier import check_emergency
from .template_engine import TemplateEngine

_LOGGER = logging.getLogger(__name__)

_MARKDOWN_RE = re.compile(
    r"\*\*|\*|#{1,6}\s?|`{1,3}|!?\[.*?\]\(.*?\)|\(https?://\S+\)"
)
_URL_RE = re.compile(r"https?://\S+")
_LIST_PREFIX_RE = re.compile(r"^\s*[-•]\s+|^\s*\d+\.\s+", re.MULTILINE)
_MAX_TTS_CHARS = 400


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """HA conversation platform entry point — registers the agent entity."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    agent = VoiceForgeConversationAgent(
        hass=hass,
        entry_id=config_entry.entry_id,
        character_manager=data["character_manager"],
        llm_client=data["llm_client"],
        template_engine=data["template_engine"],
        memory_manager=data["memory_manager"],
    )
    async_add_entities([agent])


class VoiceForgeConversationAgent(ConversationEntity):
    _attr_should_poll = False

    def __init__(
        self,
        hass,
        entry_id: str,
        character_manager: CharacterManager,
        llm_client: LLMClient,
        template_engine: TemplateEngine,
        memory_manager=None,
    ) -> None:
        self._hass = hass
        self._entry_id = entry_id
        self._character_manager = character_manager
        self._llm_client = llm_client
        self._template_engine = template_engine
        self._memory_manager = memory_manager
        self._histories: dict[str, list] = {}
        self._history_timestamps: dict[str, float] = {}

    @property
    def unique_id(self) -> str:
        return self._entry_id

    @property
    def name(self) -> str:
        return "VoiceForge"

    @property
    def supported_languages(self) -> list[str] | str:
        return MATCH_ALL

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        self._prune_idle_sessions()

        lang = getattr(user_input, "language", "en")

        if check_emergency(user_input.text):
            _LOGGER.warning("Emergency classifier fired on: %s", user_input.text)
            return self._make_result(EMERGENCY_RESPONSE, lang)

        character = self._character_manager.get_active_character()
        system_prompt = self._template_engine.render(character, self._hass)

        conv_id = user_input.conversation_id or "default"
        self._history_timestamps[conv_id] = time.time()
        history = self._histories.setdefault(conv_id, [])
        history.append({"role": "user", "content": user_input.text})

        messages = [{"role": "system", "content": system_prompt}] + history

        response = await self._llm_client.complete(messages)
        clean_response = self._clean_for_tts(response)

        history.append({"role": "assistant", "content": clean_response})

        if len(history) > 20:
            self._histories[conv_id] = history[-20:]

        if self._memory_manager:
            self._hass.async_create_task(
                self._memory_manager.async_extract(character, messages)
            )

        return self._make_result(clean_response, lang, conv_id)

    def _make_result(
        self, speech: str, language: str, conversation_id: str | None = None
    ) -> ConversationResult:
        intent_response = ha_intent.IntentResponse(language=language)
        intent_response.async_set_speech(speech)
        return ConversationResult(
            response=intent_response,
            conversation_id=conversation_id,
        )

    def _prune_idle_sessions(self) -> None:
        cutoff = time.time() - SESSION_IDLE_TTL
        stale = [k for k, ts in self._history_timestamps.items() if ts < cutoff]
        for key in stale:
            self._histories.pop(key, None)
            self._history_timestamps.pop(key, None)

    def _clean_for_tts(self, text: str) -> str:
        text = _URL_RE.sub("", text)
        text = _MARKDOWN_RE.sub("", text)
        text = _LIST_PREFIX_RE.sub("", text)
        text = text.replace("—", ",").replace("\n", " ")
        text = re.sub(r"\s{2,}", " ", text).strip()
        if len(text) > _MAX_TTS_CHARS:
            trimmed = text[:_MAX_TTS_CHARS]
            last_stop = max(trimmed.rfind("."), trimmed.rfind("?"), trimmed.rfind("!"))
            text = trimmed[: last_stop + 1] if last_stop > 0 else trimmed
        return text
