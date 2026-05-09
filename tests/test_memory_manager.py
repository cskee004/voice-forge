"""
memory_manager.py tests.

LLM calls are always mocked. File I/O uses tmp_path.
"""

import asyncio
import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.voiceforge.memory_manager import MemoryManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_character(summarize_after: int = 3, max_entries: int = 5) -> MagicMock:
    char = MagicMock()
    char.id = "aria"
    char.memory = {
        "enabled": True,
        "summarize_after_turns": summarize_after,
        "max_memory_entries": max_entries,
    }
    return char


def _make_manager(tmp_path: Path, llm_response: str = '["User likes tea."]') -> MemoryManager:
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(return_value=llm_response)
    return MemoryManager(memory_dir=str(tmp_path), llm_client=llm_client)


MESSAGES = [{"role": "user", "content": "I like tea."}]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_extraction_fires_on_turn_n_not_before(tmp_path):
    manager = _make_manager(tmp_path)
    character = _make_character(summarize_after=3)

    # Turns 1 and 2 — LLM must NOT be called
    await manager.async_extract(character, MESSAGES)
    await manager.async_extract(character, MESSAGES)
    manager._llm_client.complete.assert_not_called()

    # Turn 3 — LLM MUST be called
    await manager.async_extract(character, MESSAGES)
    manager._llm_client.complete.assert_called_once()


async def test_lock_held_extraction_is_skipped(tmp_path):
    manager = _make_manager(tmp_path)
    character = _make_character(summarize_after=1)

    # Seed the lock for this character and hold it
    lock = asyncio.Lock()
    manager._locks["aria"] = lock
    await lock.acquire()  # hold it — simulates in-flight extraction

    await manager.async_extract(character, MESSAGES)

    manager._llm_client.complete.assert_not_called()
    lock.release()


async def test_fifo_eviction_at_max_memory_entries(tmp_path):
    character = _make_character(summarize_after=1, max_entries=3)
    # Pre-seed memory file with 3 entries (at the limit)
    memory_file = tmp_path / "aria.json"
    existing = {
        "character_id": "aria",
        "entries": [
            {"id": f"mem_{i:03d}", "fact": f"old fact {i}", "category": "preferences",
             "confidence": "high", "observed": "2026-01-01T00:00:00", "last_referenced": "2026-01-01T00:00:00"}
            for i in range(3)
        ],
    }
    memory_file.write_text(json.dumps(existing), encoding="utf-8")

    # Extraction adds one new fact — oldest should be evicted
    manager = _make_manager(tmp_path, llm_response='["Brand new fact."]')
    await manager.async_extract(character, MESSAGES)

    data = json.loads(memory_file.read_text(encoding="utf-8"))
    facts = [e["fact"] for e in data["entries"]]
    assert len(facts) == 3                      # still at max
    assert "old fact 0" not in facts            # oldest evicted
    assert "Brand new fact." in facts           # new one present


async def test_file_write_persists_to_disk(tmp_path):
    manager = _make_manager(tmp_path, llm_response='["User prefers dim lighting."]')
    character = _make_character(summarize_after=1)

    await manager.async_extract(character, MESSAGES)

    memory_file = tmp_path / "aria.json"
    assert memory_file.exists()
    data = json.loads(memory_file.read_text(encoding="utf-8"))
    facts = [e["fact"] for e in data["entries"]]
    assert "User prefers dim lighting." in facts


async def test_failure_logs_and_continues(tmp_path, caplog):
    manager = _make_manager(tmp_path)
    manager._llm_client.complete = AsyncMock(side_effect=Exception("Ollama down"))
    character = _make_character(summarize_after=1)

    with caplog.at_level(logging.WARNING):
        # Must not raise
        await manager.async_extract(character, MESSAGES)

    assert "ollama down" in caplog.text.lower() or "failed" in caplog.text.lower()
