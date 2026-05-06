"""
conversation.py integration tests.

LLM calls are always mocked — never hit a real endpoint.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.voiceforge.conversation import VoiceForgeConversationAgent
from custom_components.voiceforge.const import EMERGENCY_RESPONSE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_agent(llm_response: str = "I am always here."):
    """Return a VoiceForgeConversationAgent with all deps mocked."""
    hass = MagicMock()
    hass.async_create_task = MagicMock()

    character = MagicMock()
    character.id = "aria"

    character_manager = MagicMock()
    character_manager.get_active_character.return_value = character

    llm_client = MagicMock()
    llm_client.complete = AsyncMock(return_value=llm_response)

    template_engine = MagicMock()
    template_engine.render.return_value = "You are ARIA."

    memory_manager = MagicMock()
    memory_manager.async_extract = AsyncMock()

    agent = VoiceForgeConversationAgent(
        hass=hass,
        character_manager=character_manager,
        llm_client=llm_client,
        template_engine=template_engine,
        memory_manager=memory_manager,
    )
    return agent


def _input(text: str, conv_id: str = "session-1"):
    from homeassistant.components.conversation import ConversationInput
    return ConversationInput(text=text, conversation_id=conv_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_happy_path_returns_llm_response():
    agent = _make_agent(llm_response="All doors are locked, Dave.")
    result = await agent.async_process(_input("Lock the doors."))
    assert "All doors are locked" in result.response


async def test_emergency_input_returns_emergency_response_without_llm_call():
    agent = _make_agent()
    result = await agent.async_process(_input("call 911"))
    assert result.response == EMERGENCY_RESPONSE
    agent._llm_client.complete.assert_not_called()


async def test_session_history_isolated_per_conversation_id():
    agent = _make_agent()
    await agent.async_process(_input("Hello.", conv_id="alice"))
    await agent.async_process(_input("Hi there.", conv_id="bob"))

    assert "alice" in agent._histories
    assert "bob" in agent._histories
    # Each session only contains its own turn
    alice_texts = [m["content"] for m in agent._histories["alice"]]
    bob_texts = [m["content"] for m in agent._histories["bob"]]
    assert "Hello." in alice_texts
    assert "Hello." not in bob_texts
    assert "Hi there." in bob_texts


async def test_idle_sessions_are_pruned():
    agent = _make_agent()
    # Seed a stale session directly
    agent._histories["old-session"] = [{"role": "user", "content": "old"}]
    agent._history_timestamps["old-session"] = time.time() - 3700  # >30 min ago

    # A new request on a fresh session should trigger pruning
    await agent.async_process(_input("New message.", conv_id="new-session"))

    assert "old-session" not in agent._histories
    assert "new-session" in agent._histories
