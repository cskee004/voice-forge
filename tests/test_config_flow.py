"""
config_flow.py tests.

LLM connection is always mocked. Tests exercise flow logic (step sequencing,
error surfacing, entry creation) without HA runtime.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.voiceforge.config_flow import VoiceForgeConfigFlow
from custom_components.voiceforge.const import (
    CONF_ACTIVE_CHARACTER,
    CONF_ENDPOINT,
    CONF_HOUSEHOLD_MEMBERS,
    CONF_MODEL,
    CONF_PARENT_NOTIFY_ENTITY,
    CONF_WAKE_TIME,
)


# ---------------------------------------------------------------------------
# Shared test input data
# ---------------------------------------------------------------------------

STEP1 = {
    "endpoint": "http://localhost:11434/v1",
    "model": "llama3",
    "api_key": "sk-voiceforge",
}

STEP2 = {"active_character": "aria"}

STEP3 = {
    "household_members": "Dave, Johnny",
    "wake_time": "07:00",
    "school_schedule": "08:00-15:00",
    "parent_notify_entity": "notify.mobile_app_dave_phone",
}


def _patched_llm(return_value="I am online."):
    """Context manager: patches LLMClient so complete() returns return_value."""
    mock_client = MagicMock()
    mock_client.complete = AsyncMock(return_value=return_value)
    return patch(
        "custom_components.voiceforge.config_flow.LLMClient",
        return_value=mock_client,
    )


# ---------------------------------------------------------------------------
# Step 1 — LLM Connection
# ---------------------------------------------------------------------------

async def test_step_user_shows_form_when_no_input():
    flow = VoiceForgeConfigFlow()
    result = await flow.async_step_user(None)
    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_step_user_valid_input_advances_to_character():
    with _patched_llm():
        flow = VoiceForgeConfigFlow()
        result = await flow.async_step_user(STEP1)
    assert result["type"] == "form"
    assert result["step_id"] == "character"


async def test_step_user_connection_failure_shows_error():
    mock_client = MagicMock()
    mock_client.complete = AsyncMock(side_effect=Exception("unreachable"))
    with patch("custom_components.voiceforge.config_flow.LLMClient", return_value=mock_client):
        flow = VoiceForgeConfigFlow()
        result = await flow.async_step_user(STEP1)
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"].get("base") == "cannot_connect"


async def test_step_user_empty_response_shows_error():
    with _patched_llm(return_value=""):
        flow = VoiceForgeConfigFlow()
        result = await flow.async_step_user(STEP1)
    assert result["errors"].get("base") == "cannot_connect"


# ---------------------------------------------------------------------------
# Step 2 — Character Selection
# ---------------------------------------------------------------------------

async def test_step_character_shows_form_when_no_input():
    flow = VoiceForgeConfigFlow()
    result = await flow.async_step_character(None)
    assert result["type"] == "form"
    assert result["step_id"] == "character"


async def test_step_character_valid_input_advances_to_home_context():
    flow = VoiceForgeConfigFlow()
    result = await flow.async_step_character(STEP2)
    assert result["type"] == "form"
    assert result["step_id"] == "home_context"


# ---------------------------------------------------------------------------
# Step 3 — Home Context
# ---------------------------------------------------------------------------

async def test_step_home_context_shows_form_when_no_input():
    flow = VoiceForgeConfigFlow()
    result = await flow.async_step_home_context(None)
    assert result["type"] == "form"
    assert result["step_id"] == "home_context"


async def test_step_home_context_valid_input_advances_to_pipeline():
    flow = VoiceForgeConfigFlow()
    result = await flow.async_step_home_context(STEP3)
    assert result["type"] == "form"
    assert result["step_id"] == "pipeline"


# ---------------------------------------------------------------------------
# Step 4 — Pipeline Assignment + Entry Creation
# ---------------------------------------------------------------------------

async def test_step_pipeline_creates_entry():
    with _patched_llm():
        flow = VoiceForgeConfigFlow()
        await flow.async_step_user(STEP1)
    await flow.async_step_character(STEP2)
    await flow.async_step_home_context(STEP3)

    result = await flow.async_step_pipeline(user_input={})
    assert result["type"] == "create_entry"
    assert result["title"] == "VoiceForge"


async def test_step_pipeline_entry_contains_all_step_data():
    with _patched_llm():
        flow = VoiceForgeConfigFlow()
        await flow.async_step_user(STEP1)
    await flow.async_step_character(STEP2)
    await flow.async_step_home_context(STEP3)

    result = await flow.async_step_pipeline(user_input={})
    data = result["data"]
    assert data[CONF_ENDPOINT] == STEP1["endpoint"]
    assert data[CONF_MODEL] == STEP1["model"]
    assert data[CONF_ACTIVE_CHARACTER] == "aria"
    assert data[CONF_HOUSEHOLD_MEMBERS] == STEP3["household_members"]
    assert data[CONF_WAKE_TIME] == STEP3["wake_time"]
    assert data[CONF_PARENT_NOTIFY_ENTITY] == STEP3["parent_notify_entity"]
