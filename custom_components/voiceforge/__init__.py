import asyncio
import shutil
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[str] = []

# Source: bundled sprites shipped with the integration
_SPRITE_SRC = Path(__file__).parent / "sprites"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    await _copy_sprites(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _copy_sprites(hass: HomeAssistant) -> None:
    src = _SPRITE_SRC
    dest = Path(hass.config.config_dir) / "www" / "voiceforge" / "sprites"

    if dest.exists() or not src.exists():
        return

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, shutil.copytree, str(src), str(dest))
