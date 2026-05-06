"""
pytest-homeassistant-custom-component is Linux-only (requires fcntl, resource,
etc.) and cannot run on Windows. For local development we stub the minimal
HA surface the package __init__.py imports, allowing pure-Python modules like
character_manager to be tested without a full HA installation.

CI should run on Linux where the full pytest-homeassistant-custom-component
package is available.
"""

import sys
from unittest.mock import AsyncMock, MagicMock

# --- Stub homeassistant core so package __init__.py can be imported on Windows ---
_ha = MagicMock()
_ha.config_entries = MagicMock()
_ha.core = MagicMock()

sys.modules.setdefault("homeassistant", _ha)
sys.modules.setdefault("homeassistant.config_entries", MagicMock())
sys.modules.setdefault("homeassistant.core", MagicMock())

# Provide ConfigEntry and HomeAssistant as simple classes so type annotations work
sys.modules["homeassistant.config_entries"].ConfigEntry = MagicMock
sys.modules["homeassistant.core"].HomeAssistant = MagicMock

# Stub conversation types used by conversation.py
class _ConversationEntity:
    """Minimal base class stub for ConversationEntity."""

class _ConversationInput:
    def __init__(self, text: str, conversation_id: str = "test-session"):
        self.text = text
        self.conversation_id = conversation_id
        self.language = "en"

class _ConversationResult:
    def __init__(self, response: str):
        self.response = response

_conv_mod = MagicMock()
_conv_mod.ConversationEntity = _ConversationEntity
_conv_mod.ConversationInput = _ConversationInput
_conv_mod.ConversationResult = _ConversationResult
sys.modules["homeassistant.components"] = MagicMock()
sys.modules["homeassistant.components.conversation"] = _conv_mod

import pytest  # noqa: E402 (must follow sys.modules setup)


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
