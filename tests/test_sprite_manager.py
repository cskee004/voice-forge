"""
sprite_manager.py tests.

hass is always mocked. asyncio timer uses a tiny idle_timeout to avoid 60s waits.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.voiceforge.sprite_manager import SpriteManager, EmotionState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _manager(hass=None, idle_timeout: float = 0.05) -> SpriteManager:
    if hass is None:
        hass = MagicMock()
        hass.bus = MagicMock()
        hass.bus.async_fire = MagicMock()
    return SpriteManager(hass=hass, idle_timeout=idle_timeout)


# ---------------------------------------------------------------------------
# State transition tests
# ---------------------------------------------------------------------------

async def test_transition_to_higher_state_succeeds():
    manager = _manager()
    manager.transition("aria", EmotionState.IDLE)
    result = manager.transition("aria", EmotionState.SPEAKING)
    assert result is True
    assert manager.get_state("aria") == EmotionState.SPEAKING


async def test_transition_to_lower_state_is_blocked():
    manager = _manager()
    manager.transition("aria", EmotionState.ALERT)
    result = manager.transition("aria", EmotionState.LISTENING)
    assert result is False
    assert manager.get_state("aria") == EmotionState.ALERT


async def test_transition_to_same_state_is_allowed():
    manager = _manager()
    manager.transition("aria", EmotionState.SPEAKING)
    result = manager.transition("aria", EmotionState.SPEAKING)
    assert result is True


async def test_new_character_starts_at_idle():
    manager = _manager()
    assert manager.get_state("sera") == EmotionState.IDLE


async def test_all_seven_states_are_reachable():
    manager = _manager()
    states = [
        EmotionState.IDLE,
        EmotionState.PLEASED,
        EmotionState.LISTENING,
        EmotionState.SPEAKING,
        EmotionState.ALERT,
        EmotionState.WARNING,
    ]
    # Each transition goes upward, so all states are reachable in order
    for state in states:
        manager._states["aria"] = EmotionState.IDLE
        result = manager.transition("aria", state)
        assert result is True, f"Expected transition to {state.name} to succeed"


# ---------------------------------------------------------------------------
# Priority enforcement
# ---------------------------------------------------------------------------

async def test_alert_cannot_override_warning():
    manager = _manager()
    manager.transition("aria", EmotionState.WARNING)
    result = manager.transition("aria", EmotionState.ALERT)
    assert result is False
    assert manager.get_state("aria") == EmotionState.WARNING


async def test_warning_can_override_alert():
    manager = _manager()
    manager.transition("aria", EmotionState.ALERT)
    result = manager.transition("aria", EmotionState.WARNING)
    assert result is True
    assert manager.get_state("aria") == EmotionState.WARNING


async def test_warning_is_highest_priority():
    """No emotion can displace WARNING once set."""
    manager = _manager()
    manager.transition("aria", EmotionState.WARNING)
    for state in [EmotionState.ALERT, EmotionState.SPEAKING, EmotionState.LISTENING,
                  EmotionState.PLEASED, EmotionState.IDLE]:
        result = manager.transition("aria", state)
        assert result is False, f"Expected {state.name} to be blocked by WARNING"
    assert manager.get_state("aria") == EmotionState.WARNING


# ---------------------------------------------------------------------------
# Idle timeout
# ---------------------------------------------------------------------------

async def test_idle_timeout_resets_state_to_idle():
    manager = _manager(idle_timeout=0.05)
    manager.transition("aria", EmotionState.SPEAKING)
    assert manager.get_state("aria") == EmotionState.SPEAKING

    await asyncio.sleep(0.15)  # wait longer than idle_timeout
    assert manager.get_state("aria") == EmotionState.IDLE


async def test_transition_resets_idle_timer():
    manager = _manager(idle_timeout=0.1)
    manager.transition("aria", EmotionState.SPEAKING)

    # Transition again before timeout — timer should reset
    await asyncio.sleep(0.07)
    manager.transition("aria", EmotionState.SPEAKING)

    # Timeout from the first call would have expired here, but a second call reset it
    await asyncio.sleep(0.07)
    assert manager.get_state("aria") != EmotionState.IDLE  # timer not yet expired

    # Now wait for the second timer to expire
    await asyncio.sleep(0.07)
    assert manager.get_state("aria") == EmotionState.IDLE


async def test_idle_timeout_bypasses_priority():
    """Timer forces idle even when WARNING is active."""
    manager = _manager(idle_timeout=0.05)
    manager.transition("aria", EmotionState.WARNING)
    assert manager.get_state("aria") == EmotionState.WARNING

    await asyncio.sleep(0.15)
    assert manager.get_state("aria") == EmotionState.IDLE


# ---------------------------------------------------------------------------
# HA event payload
# ---------------------------------------------------------------------------

async def test_ha_event_fired_on_transition():
    hass = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()

    manager = _manager(hass=hass)
    manager.transition("aria", EmotionState.SPEAKING)

    hass.bus.async_fire.assert_called_once()
    call_args = hass.bus.async_fire.call_args
    assert call_args[0][0] == "voiceforge_emotion_change"


async def test_ha_event_payload_structure():
    hass = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()

    manager = _manager(hass=hass)
    manager.transition("aria", EmotionState.PLEASED)

    payload = hass.bus.async_fire.call_args[0][1]
    assert payload["character_id"] == "aria"
    assert payload["emotion"] == "pleased"
    assert payload["sprite_url"] == "/local/voiceforge/sprites/aria/pleased.gif"


async def test_ha_event_not_fired_when_transition_blocked():
    hass = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()

    manager = _manager(hass=hass)
    manager.transition("aria", EmotionState.WARNING)
    hass.bus.async_fire.reset_mock()

    # Blocked transition — no event
    manager.transition("aria", EmotionState.ALERT)
    hass.bus.async_fire.assert_not_called()


async def test_idle_timeout_fires_ha_event():
    hass = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()

    manager = _manager(hass=hass, idle_timeout=0.05)
    manager.transition("aria", EmotionState.SPEAKING)
    hass.bus.async_fire.reset_mock()

    await asyncio.sleep(0.15)

    hass.bus.async_fire.assert_called_once()
    payload = hass.bus.async_fire.call_args[0][1]
    assert payload["emotion"] == "idle"
