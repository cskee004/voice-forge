from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.states = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.config.config_dir = "/config"
    hass.async_create_task = MagicMock()
    hass.loop = MagicMock()
    return hass


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    client.complete = AsyncMock(return_value="I am always here.")
    return client


@pytest.fixture
def mock_config_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "endpoint": "http://localhost:11434/v1",
        "model": "llama3",
        "api_key": "sk-voiceforge",
        "active_character": "aria",
    }
    return entry
