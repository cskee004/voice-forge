"""Type A (event-driven) and Type B (LLM-composed personal) message management."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, UTC
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

_RATE_LIMIT_SECONDS = 1800   # 30 minutes
_MESSAGE_TTL_DAYS = 7


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_data(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"messages": [], "rate_limits": {}}


def _save_data(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _prune_expired(data: dict) -> dict:
    cutoff = datetime.now(UTC) - timedelta(days=_MESSAGE_TTL_DAYS)
    data["messages"] = [
        m for m in data["messages"]
        if datetime.fromisoformat(m["ts"]) > cutoff
    ]
    return data


def _is_rate_limited(data: dict, trigger_type: str) -> bool:
    last = data["rate_limits"].get(trigger_type)
    if not last:
        return False
    elapsed = (datetime.now(UTC) - datetime.fromisoformat(last)).total_seconds()
    return elapsed < _RATE_LIMIT_SECONDS


def _has_unread_same_trigger(data: dict, trigger_type: str, to: str) -> bool:
    return any(
        m["trigger_type"] == trigger_type and m["to"] == to and not m["read"]
        for m in data["messages"]
    )


def _new_message(type_: str, character_id: str, trigger_type: str, body: str, to: str) -> dict:
    return {
        "id": f"msg_{uuid.uuid4().hex[:8]}",
        "type": type_,
        "to": to,
        "from": character_id,
        "body": body,
        "ts": _now_iso(),
        "read": False,
        "announced": False,
        "trigger_type": trigger_type,
    }


class MessageManager:
    def __init__(self, messages_file: str, llm_client) -> None:
        self._path = Path(messages_file)
        self._llm_client = llm_client
        self._lock = asyncio.Lock()

    async def store_type_a(
        self,
        character_id: str,
        trigger_type: str,
        body: str,
        to: str = "all",
    ) -> bool:
        """Store a pre-composed Type A event message. Returns True if stored."""
        async with self._lock:
            data = _load_data(self._path)
            data = _prune_expired(data)

            if _is_rate_limited(data, trigger_type):
                return False
            if _has_unread_same_trigger(data, trigger_type, to):
                return False

            data["messages"].append(_new_message("event", character_id, trigger_type, body, to))
            data["rate_limits"][trigger_type] = _now_iso()
            _save_data(self._path, data)
            return True

    async def generate_type_b(
        self,
        character_id: str,
        trigger_type: str,
        to: str,
        prompt: str,
    ) -> bool:
        """Generate a Type B personal message via LLM. Returns True if stored."""
        # Pre-flight checks under lock before the expensive LLM call
        async with self._lock:
            data = _load_data(self._path)
            data = _prune_expired(data)

            if _is_rate_limited(data, trigger_type):
                return False
            if _has_unread_same_trigger(data, trigger_type, to):
                return False

        # LLM call outside the lock — can take several seconds
        try:
            body = await self._llm_client.complete(
                [{"role": "user", "content": prompt}]
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Type B message generation failed: %s", exc)
            return False

        # Write under lock
        async with self._lock:
            data = _load_data(self._path)
            data = _prune_expired(data)

            msg = _new_message("personal", character_id, trigger_type, body, to)
            msg["parent_notified"] = True
            data["messages"].append(msg)
            data["rate_limits"][trigger_type] = _now_iso()
            _save_data(self._path, data)
            return True
