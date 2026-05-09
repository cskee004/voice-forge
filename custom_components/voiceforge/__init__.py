import asyncio
import shutil
from pathlib import Path

import voluptuous as vol
from homeassistant.components.frontend import async_remove_panel
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.components.websocket_api import (
    async_register_command,
    websocket_command,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .character_manager import CharacterManager
from .const import (
    CHARACTERS_DIR,
    CONF_ACTIVE_CHARACTER,
    CONF_API_KEY,
    CONF_ENDPOINT,
    CONF_MODEL,
    DEFAULT_API_KEY,
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    DOMAIN,
    MEMORY_DIR,
    MESSAGES_FILE,
)
from .llm_client import LLMClient
from .memory_manager import MemoryManager
from .message_manager import MessageManager
from .sprite_manager import SpriteManager
from .template_engine import TemplateEngine

PLATFORMS: list[str] = ["conversation"]

_SPRITE_SRC = Path(__file__).parent / "sprites"
_PANEL_DIR = Path(__file__).parent / "www"


# ---------------------------------------------------------------------------
# WebSocket command handlers (decorated at module load time)
# ---------------------------------------------------------------------------

@websocket_command({vol.Required("type"): "voiceforge/get_state"})
def ws_get_state(hass: HomeAssistant, connection, msg: dict) -> None:
    """Return active character and full character list."""
    entry_data = _get_entry_data(hass)
    if entry_data is None:
        connection.send_error(msg["id"], "not_setup", "VoiceForge not configured")
        return
    char_mgr = entry_data["character_manager"]
    active = char_mgr.get_active_character()
    characters = [
        {"id": c.id, "name": c.name, "description": c.description}
        for c in char_mgr.get_all_characters()
    ]
    connection.send_result(msg["id"], {
        "active_character_id": active.id if active else None,
        "characters": characters,
    })


@websocket_command({
    vol.Required("type"): "voiceforge/switch_character",
    vol.Required("character_id"): str,
})
def ws_switch_character(hass: HomeAssistant, connection, msg: dict) -> None:
    """Switch the active character."""
    entry_data = _get_entry_data(hass)
    if entry_data is None:
        connection.send_error(msg["id"], "not_setup", "VoiceForge not configured")
        return
    char_id = msg["character_id"]
    entry_data["character_manager"].switch_character(char_id)
    connection.send_result(msg["id"], {"active_character_id": char_id})


def _get_entry_data(hass: HomeAssistant) -> dict | None:
    for data in hass.data.get(DOMAIN, {}).values():
        return data
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    await _copy_sprites(hass)

    config_dir = Path(hass.config.config_dir)

    llm_client = LLMClient(
        endpoint=entry.data.get(CONF_ENDPOINT, DEFAULT_ENDPOINT),
        model=entry.data.get(CONF_MODEL, DEFAULT_MODEL),
        api_key=entry.data.get(CONF_API_KEY, DEFAULT_API_KEY),
    )

    characters_dir = Path(__file__).parent / CHARACTERS_DIR
    character_manager = CharacterManager(str(characters_dir))
    character_manager.load_all()
    character_manager.switch_character(entry.data.get(CONF_ACTIVE_CHARACTER, "aria"))

    memory_dir = config_dir / MEMORY_DIR
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_manager = MemoryManager(str(memory_dir), llm_client)

    messages_file = config_dir / MESSAGES_FILE
    messages_file.parent.mkdir(parents=True, exist_ok=True)
    message_manager = MessageManager(str(messages_file), llm_client)

    sprite_manager = SpriteManager(hass=hass)
    template_engine = TemplateEngine()

    hass.data[DOMAIN][entry.entry_id] = {
        "llm_client": llm_client,
        "character_manager": character_manager,
        "memory_manager": memory_manager,
        "message_manager": message_manager,
        "sprite_manager": sprite_manager,
        "template_engine": template_engine,
    }

    hass.http.register_static_path("/voiceforge-panel", str(_PANEL_DIR))
    await async_register_panel(
        hass,
        webcomponent_name="voiceforge-panel",
        sidebar_title="VoiceForge",
        sidebar_icon="mdi:robot-excited",
        frontend_url_path="voiceforge",
        module_url="/voiceforge-panel/voiceforge-panel.js",
        config_panel_domain=DOMAIN,
    )
    async_register_command(hass, ws_get_state)
    async_register_command(hass, ws_switch_character)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        async_remove_panel(hass, "voiceforge")
    return unloaded


async def _copy_sprites(hass: HomeAssistant) -> None:
    src = _SPRITE_SRC
    dest = Path(hass.config.config_dir) / "www" / "voiceforge" / "sprites"
    if dest.exists() or not src.exists():
        return
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, shutil.copytree, str(src), str(dest))
