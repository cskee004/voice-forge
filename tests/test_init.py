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

from custom_components.voiceforge import async_setup_entry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hass(config_dir: Path) -> MagicMock:
    hass = MagicMock()
    hass.data = {}
    hass.config.config_dir = str(config_dir)
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=None)
    return hass


def _make_entry() -> MagicMock:
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {}
    return entry


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
