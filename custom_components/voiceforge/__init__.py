import asyncio
import shutil
from pathlib import Path

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

# Source: bundled sprites shipped with the integration
_SPRITE_SRC = Path(__file__).parent / "sprites"


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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _copy_sprites(hass: HomeAssistant) -> None:
    src = _SPRITE_SRC
    dest = Path(hass.config.config_dir) / "www" / "voiceforge" / "sprites"
    if dest.exists() or not src.exists():
        return
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, shutil.copytree, str(src), str(dest))
