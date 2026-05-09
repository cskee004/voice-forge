"""Persistent memory extraction, storage, and injection.

Extraction is gated by an internal per-character turn counter so
conversation.py can call async_extract() on every turn without caring
about when actual LLM work happens.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, UTC
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

_EXTRACTION_PROMPT = (
    "Review the conversation below and extract a JSON array of short, specific "
    "facts about the user or household that are worth remembering long-term. "
    "Return ONLY a valid JSON array of strings, e.g. [\"fact one\", \"fact two\"]. "
    "If there is nothing worth remembering, return []. "
    "Conversation:\n"
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_memory(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"character_id": path.stem, "entries": []}


def _save_memory(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class MemoryManager:
    def __init__(self, memory_dir: str, llm_client) -> None:
        self._memory_dir = Path(memory_dir)
        self._llm_client = llm_client
        self._turn_counts: dict[str, int] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def async_extract(self, character, messages: list[dict]) -> None:
        """Called every conversation turn. Internally gates to every N turns."""
        char_id = character.id
        summarize_after = character.memory.get("summarize_after_turns", 5)
        max_entries = character.memory.get("max_memory_entries", 50)

        self._turn_counts[char_id] = self._turn_counts.get(char_id, 0) + 1
        if self._turn_counts[char_id] < summarize_after:
            return

        if char_id not in self._locks:
            self._locks[char_id] = asyncio.Lock()
        lock = self._locks[char_id]

        if lock.locked():
            _LOGGER.debug("Memory extraction in-flight for %s — skipping", char_id)
            return

        async with lock:
            self._turn_counts[char_id] = 0
            await self._run_extraction(char_id, messages, max_entries)

    async def _run_extraction(
        self, char_id: str, messages: list[dict], max_entries: int
    ) -> None:
        conversation_text = "\n".join(
            f"{m['role'].capitalize()}: {m['content']}" for m in messages[-10:]
        )
        prompt = [{"role": "user", "content": _EXTRACTION_PROMPT + conversation_text}]

        try:
            raw = await self._llm_client.complete(prompt)
            new_facts = _parse_facts(raw)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Memory extraction failed for %s: %s", char_id, exc)
            return

        if not new_facts:
            return

        loop = asyncio.get_running_loop()
        memory_path = self._memory_dir / f"{char_id}.json"

        data = await loop.run_in_executor(None, _load_memory, memory_path)
        existing_facts = {e["fact"] for e in data["entries"]}
        now = _now_iso()

        for fact in new_facts:
            if fact in existing_facts:
                continue
            data["entries"].append({
                "id": f"mem_{uuid.uuid4().hex[:8]}",
                "category": "household",
                "fact": fact,
                "confidence": "medium",
                "observed": now,
                "last_referenced": now,
            })
            existing_facts.add(fact)

        # FIFO eviction — drop oldest entries first
        if len(data["entries"]) > max_entries:
            data["entries"] = data["entries"][-max_entries:]

        data["last_updated"] = now
        await loop.run_in_executor(None, _save_memory, memory_path, data)

    def get_memories(self, character_id: str, limit: int = 5) -> list[str]:
        """Return the most recent memory facts for a character."""
        path = self._memory_dir / f"{character_id}.json"
        data = _load_memory(path)
        entries = data.get("entries", [])
        return [e["fact"] for e in entries[-limit:]]


def _parse_facts(raw: str) -> list[str]:
    """Extract a list of fact strings from the LLM's JSON response."""
    raw = raw.strip()
    # Find the first [ ... ] block
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        facts = json.loads(raw[start : end + 1])
        return [str(f).strip() for f in facts if str(f).strip()]
    except json.JSONDecodeError:
        return []
