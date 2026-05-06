"""
message_manager.py tests.

LLM calls always mocked. File I/O uses tmp_path.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, UTC
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.voiceforge.message_manager import MessageManager

MESSAGE_TTL_DAYS = 7
RATE_LIMIT_SECONDS = 1800  # 30 min


def _manager(tmp_path: Path, llm_response: str = "Here is a message for you.") -> MessageManager:
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(return_value=llm_response)
    return MessageManager(messages_file=str(tmp_path / "messages.json"), llm_client=llm_client)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_type_a_message_stored_correctly(tmp_path):
    manager = _manager(tmp_path)
    stored = await manager.store_type_a(
        character_id="aria",
        trigger_type="late_night_door_open",
        body="The back door opened at 2 AM, Dave.",
        to="all",
    )
    assert stored is True

    data = json.loads((tmp_path / "messages.json").read_text(encoding="utf-8"))
    msgs = data["messages"]
    assert len(msgs) == 1
    assert msgs[0]["type"] == "event"
    assert msgs[0]["from"] == "aria"
    assert msgs[0]["trigger_type"] == "late_night_door_open"
    assert msgs[0]["body"] == "The back door opened at 2 AM, Dave."
    assert msgs[0]["read"] is False
    assert msgs[0]["announced"] is False


async def test_type_b_generated_with_llm_and_parent_notified(tmp_path):
    manager = _manager(tmp_path, llm_response="Good morning, Johnny. Have a great day!")
    stored = await manager.generate_type_b(
        character_id="sera",
        trigger_type="morning_summary",
        to="Johnny",
        prompt="Write a cheerful morning message for Johnny.",
    )
    assert stored is True

    data = json.loads((tmp_path / "messages.json").read_text(encoding="utf-8"))
    msg = data["messages"][0]
    assert msg["type"] == "personal"
    assert msg["body"] == "Good morning, Johnny. Have a great day!"
    assert msg["parent_notified"] is True
    manager._llm_client.complete.assert_called_once()


async def test_second_call_within_30min_is_skipped(tmp_path):
    manager = _manager(tmp_path)
    await manager.store_type_a("aria", "late_night_door_open", "First message.", "all")

    # Second call for same trigger — should be blocked by rate limit
    stored = await manager.store_type_a("aria", "late_night_door_open", "Second message.", "all")
    assert stored is False

    data = json.loads((tmp_path / "messages.json").read_text(encoding="utf-8"))
    assert len(data["messages"]) == 1  # only the first was stored


async def test_existing_unread_same_trigger_blocks_generation(tmp_path):
    manager = _manager(tmp_path)
    # Seed an existing unread message with the same trigger to the same recipient
    seed = {
        "messages": [{
            "id": "msg_existing",
            "type": "event",
            "to": "Johnny",
            "from": "sera",
            "body": "Old message.",
            "ts": _iso(datetime.now(UTC)),
            "read": False,
            "announced": False,
            "trigger_type": "morning_summary",
        }],
        "rate_limits": {},
    }
    (tmp_path / "messages.json").write_text(json.dumps(seed), encoding="utf-8")

    stored = await manager.generate_type_b("sera", "morning_summary", "Johnny", "prompt")
    assert stored is False
    manager._llm_client.complete.assert_not_called()


async def test_expired_messages_pruned_on_load(tmp_path):
    old_ts = _iso(datetime.now(UTC) - timedelta(days=8))
    recent_ts = _iso(datetime.now(UTC))
    seed = {
        "messages": [
            {"id": "old", "type": "event", "to": "all", "from": "aria",
             "body": "Old.", "ts": old_ts, "read": False, "announced": False,
             "trigger_type": "morning_summary"},
            {"id": "new", "type": "event", "to": "all", "from": "aria",
             "body": "Recent.", "ts": recent_ts, "read": False, "announced": False,
             "trigger_type": "security_event"},
        ],
        "rate_limits": {},
    }
    (tmp_path / "messages.json").write_text(json.dumps(seed), encoding="utf-8")

    manager = _manager(tmp_path)
    # Use a trigger that doesn't conflict with any seeded message
    await manager.store_type_a("aria", "child_arrived_home", "New event.", "all")

    data = json.loads((tmp_path / "messages.json").read_text(encoding="utf-8"))
    ids = [m["id"] for m in data["messages"]]
    assert "old" not in ids
    assert "new" in ids


async def test_concurrent_write_lock_prevents_race(tmp_path):
    manager = _manager(tmp_path)

    # Fire two stores simultaneously
    results = await asyncio.gather(
        manager.store_type_a("aria", "security_event", "Message A.", "all"),
        manager.store_type_a("aria", "unusual_temperature_spike", "Message B.", "all"),
    )

    data = json.loads((tmp_path / "messages.json").read_text(encoding="utf-8"))
    # Both messages with different trigger types must be present — no data loss
    triggers = {m["trigger_type"] for m in data["messages"]}
    assert "security_event" in triggers
    assert "unusual_temperature_spike" in triggers
