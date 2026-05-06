"""Thin async wrapper around any OpenAI-compatible LLM endpoint."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from .const import DEFAULT_API_KEY

_LOGGER = logging.getLogger(__name__)


class LLMClient:
    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: str = DEFAULT_API_KEY,
    ) -> None:
        self._model = model
        self._client = AsyncOpenAI(base_url=endpoint, api_key=api_key)

    async def complete(self, messages: list[dict]) -> str:
        """Send messages to the LLM and return the response text.

        Returns an empty string and logs a warning on any failure so callers
        never have to handle exceptions — the conversation must continue.
        """
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("LLM endpoint unreachable or failed: %s", exc)
            return ""
