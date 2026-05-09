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

# ---------------------------------------------------------------------------
# ConfigFlow stub — defined first so it can be wired into the module stubs
# ---------------------------------------------------------------------------

class _ConfigFlow:
    """Minimal ConfigFlow stub — supports domain= class keyword and flow helpers."""

    def __init_subclass__(cls, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)

    def async_show_form(self, *, step_id, data_schema=None, errors=None):
        return {"type": "form", "step_id": step_id, "data_schema": data_schema, "errors": errors or {}}

    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    def async_abort(self, *, reason):
        return {"type": "abort", "reason": reason}


# ---------------------------------------------------------------------------
# IntentResponse stub — mirrors homeassistant.helpers.intent.IntentResponse
# ---------------------------------------------------------------------------

class _IntentResponse:
    """Minimal IntentResponse stub for conversation result assertions."""

    def __init__(self, language="en", intent=None):
        self.speech: dict = {}
        self.language = language

    def async_set_speech(self, speech: str, extra_data=None, response_type=None) -> None:
        self.speech["plain"] = {"speech": speech, "extra_data": extra_data}


# ---------------------------------------------------------------------------
# Stub homeassistant.config_entries — single object shared by _ha and sys.modules
# ---------------------------------------------------------------------------

_config_entries_stub = MagicMock()
_config_entries_stub.ConfigEntry = MagicMock
_config_entries_stub.ConfigFlow = _ConfigFlow

# ---------------------------------------------------------------------------
# Stub homeassistant.core
# ---------------------------------------------------------------------------

_core_stub = MagicMock()
_core_stub.HomeAssistant = MagicMock

# ---------------------------------------------------------------------------
# Stub homeassistant.helpers.intent
# ---------------------------------------------------------------------------

_intent_stub = MagicMock()
_intent_stub.IntentResponse = _IntentResponse

_helpers_stub = MagicMock()
_helpers_stub.intent = _intent_stub

# ---------------------------------------------------------------------------
# Stub homeassistant package — attribute access must return the same objects
# as sys.modules entries so `from homeassistant import x` works
# ---------------------------------------------------------------------------

_ha = MagicMock()
_ha.config_entries = _config_entries_stub
_ha.core = _core_stub
_ha.helpers = _helpers_stub

sys.modules["homeassistant"] = _ha
sys.modules["homeassistant.config_entries"] = _config_entries_stub
sys.modules["homeassistant.core"] = _core_stub
sys.modules["homeassistant.helpers"] = _helpers_stub
sys.modules["homeassistant.helpers.intent"] = _intent_stub

# ---------------------------------------------------------------------------
# Stub conversation types used by conversation.py
# ---------------------------------------------------------------------------

class _ConversationEntity:
    """Minimal base class stub for ConversationEntity."""

class _ConversationInput:
    def __init__(self, text: str, conversation_id: str = "test-session"):
        self.text = text
        self.conversation_id = conversation_id
        self.language = "en"

class _ConversationResult:
    def __init__(self, response, conversation_id=None):
        self.response = response          # _IntentResponse in wired code
        self.conversation_id = conversation_id

_conv_mod = MagicMock()
_conv_mod.ConversationEntity = _ConversationEntity
_conv_mod.ConversationInput = _ConversationInput
_conv_mod.ConversationResult = _ConversationResult
sys.modules["homeassistant.components"] = MagicMock()
sys.modules["homeassistant.components.conversation"] = _conv_mod

# ---------------------------------------------------------------------------
# Stub homeassistant.components.panel_custom
# ---------------------------------------------------------------------------

_panel_custom_stub = MagicMock()
_panel_custom_stub.async_register_panel = AsyncMock()
sys.modules["homeassistant.components.panel_custom"] = _panel_custom_stub

# ---------------------------------------------------------------------------
# Stub homeassistant.components.frontend (panel removal)
# ---------------------------------------------------------------------------

_frontend_stub = MagicMock()
_frontend_stub.async_remove_panel = MagicMock()
sys.modules["homeassistant.components.frontend"] = _frontend_stub

# ---------------------------------------------------------------------------
# Stub homeassistant.components.websocket_api
# ---------------------------------------------------------------------------

def _ws_command_factory(schema):
    """Store the schema on the decorated function; return it unchanged."""
    def decorator(fn):
        fn._ws_schema = schema
        return fn
    return decorator

_ws_api_stub = MagicMock()
_ws_api_stub.websocket_command = _ws_command_factory
_ws_api_stub.async_register_command = MagicMock()
sys.modules["homeassistant.components.websocket_api"] = _ws_api_stub

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
