"""
__init__.py tests.

Focused on the sprite static file setup logic inside async_setup_entry.
hass is a plain MagicMock. The bundled sprite source path is patched
so tests work without real sprite files present.
"""

import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from custom_components.voiceforge import async_setup_entry, async_unload_entry
from custom_components.voiceforge.const import DOMAIN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hass(config_dir: Path) -> MagicMock:
    hass = MagicMock()
    hass.data = {}
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.config.config_dir = str(config_dir)
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=None)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    return hass


def _make_entry() -> MagicMock:
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {
        "endpoint": "http://localhost:11434/v1",
        "model": "llama3",
        "api_key": "sk-voiceforge",
        "active_character": "aria",
    }
    return entry


_MANAGER_PATCH_TARGETS = [
    "custom_components.voiceforge.CharacterManager",
    "custom_components.voiceforge.LLMClient",
    "custom_components.voiceforge.MemoryManager",
    "custom_components.voiceforge.MessageManager",
    "custom_components.voiceforge.SpriteManager",
    "custom_components.voiceforge.TemplateEngine",
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_async_setup_entry_returns_true(tmp_path):
    hass = _make_hass(tmp_path)
    with patch("custom_components.voiceforge._SPRITE_SRC", tmp_path / "nonexistent"):
        result = await async_setup_entry(hass, _make_entry())
    assert result is True


async def test_sprites_copied_when_dest_missing(tmp_path):
    src = tmp_path / "sprites_src"
    src.mkdir()
    (src / "aria").mkdir()
    (src / "aria" / "idle.gif").write_bytes(b"GIF89a")

    dest_base = tmp_path / "config"
    dest_base.mkdir()
    hass = _make_hass(dest_base)

    with patch("custom_components.voiceforge._SPRITE_SRC", src):
        await async_setup_entry(hass, _make_entry())

    dest = dest_base / "www" / "voiceforge" / "sprites"
    assert dest.exists()
    assert (dest / "aria" / "idle.gif").exists()


async def test_sprites_skipped_when_dest_exists(tmp_path):
    src = tmp_path / "sprites_src"
    src.mkdir()
    (src / "aria").mkdir()
    (src / "aria" / "idle.gif").write_bytes(b"GIF89a")

    dest_base = tmp_path / "config"
    dest = dest_base / "www" / "voiceforge" / "sprites"
    dest.mkdir(parents=True)
    sentinel = dest / "already_here.txt"
    sentinel.write_text("do not overwrite")

    hass = _make_hass(dest_base)

    with patch("custom_components.voiceforge._SPRITE_SRC", src):
        await async_setup_entry(hass, _make_entry())

    # Dest existed — copytree skipped — new files from src were not added
    assert not (dest / "aria" / "idle.gif").exists()
    assert sentinel.read_text() == "do not overwrite"


async def test_sprites_skipped_when_src_missing(tmp_path):
    """No crash when bundled sprites directory doesn't exist (e.g., dev environment)."""
    hass = _make_hass(tmp_path)
    # src path points to a directory that does not exist
    with patch("custom_components.voiceforge._SPRITE_SRC", tmp_path / "does_not_exist"):
        result = await async_setup_entry(hass, _make_entry())
    assert result is True


async def test_copy_runs_in_executor(tmp_path):
    """The copy is dispatched to a thread-pool executor, not run on the event loop."""
    src = tmp_path / "sprites_src"
    src.mkdir()

    dest_base = tmp_path / "config"
    dest_base.mkdir()
    hass = _make_hass(dest_base)

    captured_calls = []

    async def fake_run_in_executor(executor, func, *args):
        captured_calls.append((func, args))
        # Actually run the function so downstream assertions work
        func(*args)

    with patch("custom_components.voiceforge._SPRITE_SRC", src):
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                side_effect=fake_run_in_executor
            )
            await async_setup_entry(hass, _make_entry())

    assert len(captured_calls) == 1
    func, _ = captured_calls[0]
    assert func is shutil.copytree


# ---------------------------------------------------------------------------
# Manager wiring tests
# ---------------------------------------------------------------------------

async def test_setup_stores_all_managers_in_hass_data(tmp_path):
    hass = _make_hass(tmp_path)
    entry = _make_entry()

    mocks = {t.split(".")[-1]: MagicMock() for t in _MANAGER_PATCH_TARGETS}
    patches = [patch(t, mocks[t.split(".")[-1]]) for t in _MANAGER_PATCH_TARGETS]
    for p in patches:
        p.start()
    try:
        with patch("custom_components.voiceforge._SPRITE_SRC", tmp_path / "no_sprites"):
            await async_setup_entry(hass, entry)
    finally:
        for p in patches:
            p.stop()

    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]
    data = hass.data[DOMAIN][entry.entry_id]
    for key in ("character_manager", "llm_client", "memory_manager",
                "message_manager", "sprite_manager", "template_engine"):
        assert key in data, f"missing key: {key}"


async def test_setup_forwards_conversation_platform(tmp_path):
    hass = _make_hass(tmp_path)
    entry = _make_entry()

    mocks = {t.split(".")[-1]: MagicMock() for t in _MANAGER_PATCH_TARGETS}
    patches = [patch(t, mocks[t.split(".")[-1]]) for t in _MANAGER_PATCH_TARGETS]
    for p in patches:
        p.start()
    try:
        with patch("custom_components.voiceforge._SPRITE_SRC", tmp_path / "no_sprites"):
            await async_setup_entry(hass, entry)
    finally:
        for p in patches:
            p.stop()

    call_args = hass.config_entries.async_forward_entry_setups.call_args
    forwarded_platforms = call_args[0][1]
    assert "conversation" in forwarded_platforms


async def test_unload_removes_entry_data(tmp_path):
    hass = _make_hass(tmp_path)
    entry = _make_entry()

    mocks = {t.split(".")[-1]: MagicMock() for t in _MANAGER_PATCH_TARGETS}
    patches = [patch(t, mocks[t.split(".")[-1]]) for t in _MANAGER_PATCH_TARGETS]
    for p in patches:
        p.start()
    try:
        with patch("custom_components.voiceforge._SPRITE_SRC", tmp_path / "no_sprites"):
            await async_setup_entry(hass, entry)
    finally:
        for p in patches:
            p.stop()

    assert entry.entry_id in hass.data[DOMAIN]

    result = await async_unload_entry(hass, entry)

    assert result is True
    assert entry.entry_id not in hass.data[DOMAIN]
