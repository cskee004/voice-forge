"""
__init__.py tests.

Covers: sprite static file setup, manager wiring, panel registration,
WebSocket command registration and handler behaviour.
"""

import shutil
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from custom_components.voiceforge import async_setup_entry, async_unload_entry
from custom_components.voiceforge.const import DOMAIN

# Grab the stubs installed by conftest so we can assert against them.
_panel_custom = sys.modules["homeassistant.components.panel_custom"]
_frontend = sys.modules["homeassistant.components.frontend"]
_ws_api = sys.modules["homeassistant.components.websocket_api"]
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


# ---------------------------------------------------------------------------
# Panel registration tests (Task 16)
# ---------------------------------------------------------------------------

async def test_panel_static_path_registered(tmp_path):
    """Static panel files must be served under /voiceforge-panel."""
    hass = _make_hass(tmp_path)
    with patch("custom_components.voiceforge._SPRITE_SRC", tmp_path / "no_sprites"):
        await async_setup_entry(hass, _make_entry())

    registered = [c[0][0] for c in hass.http.register_static_path.call_args_list]
    assert "/voiceforge-panel" in registered


async def test_panel_registered_in_sidebar(tmp_path):
    """async_register_panel must be called with the right sidebar metadata."""
    _panel_custom.async_register_panel.reset_mock()
    hass = _make_hass(tmp_path)
    with patch("custom_components.voiceforge._SPRITE_SRC", tmp_path / "no_sprites"):
        await async_setup_entry(hass, _make_entry())

    _panel_custom.async_register_panel.assert_called_once()
    kwargs = _panel_custom.async_register_panel.call_args.kwargs
    assert kwargs.get("frontend_url_path") == "voiceforge"
    assert kwargs.get("sidebar_title") == "VoiceForge"
    assert kwargs.get("sidebar_icon") == "mdi:robot-excited"
    assert "voiceforge-panel" in (kwargs.get("module_url") or "")


async def test_panel_removed_on_unload(tmp_path):
    """async_remove_panel must be called when the entry is unloaded."""
    _frontend.async_remove_panel.reset_mock()
    hass = _make_hass(tmp_path)
    entry = _make_entry()
    with patch("custom_components.voiceforge._SPRITE_SRC", tmp_path / "no_sprites"):
        await async_setup_entry(hass, entry)

    await async_unload_entry(hass, entry)

    _frontend.async_remove_panel.assert_called_once_with(hass, "voiceforge")


async def test_ws_commands_registered(tmp_path):
    """Both WebSocket commands must be registered during setup."""
    _ws_api.async_register_command.reset_mock()
    hass = _make_hass(tmp_path)
    with patch("custom_components.voiceforge._SPRITE_SRC", tmp_path / "no_sprites"):
        await async_setup_entry(hass, _make_entry())

    assert _ws_api.async_register_command.call_count >= 2


async def test_ws_get_state_returns_character_data(tmp_path):
    """ws_get_state handler returns active character ID and full character list."""
    from custom_components.voiceforge import ws_get_state

    hass = _make_hass(tmp_path)
    active = MagicMock(id="aria", name="ARIA", description="Adaptive AI")
    char_mgr = MagicMock()
    char_mgr.get_active_character.return_value = active
    char_mgr.get_all_characters.return_value = [active]
    hass.data = {DOMAIN: {"e1": {
        "character_manager": char_mgr,
        "message_manager": MagicMock(),
        "memory_manager": MagicMock(),
    }}}

    connection = MagicMock()
    ws_get_state(hass, connection, {"id": 1, "type": "voiceforge/get_state"})

    connection.send_result.assert_called_once()
    result = connection.send_result.call_args[0][1]
    assert result["active_character_id"] == "aria"
    assert len(result["characters"]) == 1
    assert result["characters"][0]["id"] == "aria"


async def test_ws_switch_character_calls_manager(tmp_path):
    """ws_switch_character handler delegates to character_manager.switch_character."""
    from custom_components.voiceforge import ws_switch_character

    hass = _make_hass(tmp_path)
    char_mgr = MagicMock()
    hass.data = {DOMAIN: {"e1": {"character_manager": char_mgr}}}

    connection = MagicMock()
    ws_switch_character(
        hass, connection,
        {"id": 2, "type": "voiceforge/switch_character", "character_id": "sera"},
    )

    char_mgr.switch_character.assert_called_once_with("sera")
    connection.send_result.assert_called_once()
