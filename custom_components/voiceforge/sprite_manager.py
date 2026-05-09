"""Emotion state machine and HA event firing for sprite display."""

from __future__ import annotations

import asyncio
import logging
from enum import IntEnum

_LOGGER = logging.getLogger(__name__)

_DEFAULT_IDLE_TIMEOUT = 60.0
_SPRITE_URL_TEMPLATE = "/local/voiceforge/sprites/{character_id}/{emotion}.gif"


class EmotionState(IntEnum):
    IDLE = 0
    PLEASED = 1
    LISTENING = 2
    SPEAKING = 3
    ALERT = 4
    WARNING = 5


class SpriteManager:
    def __init__(self, hass, idle_timeout: float = _DEFAULT_IDLE_TIMEOUT) -> None:
        self._hass = hass
        self._idle_timeout = idle_timeout
        self._states: dict[str, EmotionState] = {}
        self._timers: dict[str, asyncio.Task] = {}

    def get_state(self, character_id: str) -> EmotionState:
        return self._states.get(character_id, EmotionState.IDLE)

    def transition(self, character_id: str, emotion: EmotionState) -> bool:
        current = self.get_state(character_id)
        if emotion < current:
            return False

        self._states[character_id] = emotion
        self._fire_event(character_id, emotion)
        self._reset_timer(character_id)
        return True

    def _fire_event(self, character_id: str, emotion: EmotionState) -> None:
        self._hass.bus.async_fire(
            "voiceforge_emotion_change",
            {
                "character_id": character_id,
                "emotion": emotion.name.lower(),
                "sprite_url": _SPRITE_URL_TEMPLATE.format(
                    character_id=character_id,
                    emotion=emotion.name.lower(),
                ),
            },
        )

    def _reset_timer(self, character_id: str) -> None:
        existing = self._timers.get(character_id)
        if existing and not existing.done():
            existing.cancel()
        self._timers[character_id] = asyncio.get_event_loop().create_task(
            self._idle_after_timeout(character_id)
        )

    async def _idle_after_timeout(self, character_id: str) -> None:
        await asyncio.sleep(self._idle_timeout)
        self._states[character_id] = EmotionState.IDLE
        self._fire_event(character_id, EmotionState.IDLE)
