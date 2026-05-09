import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.voiceforge.llm_client import LLMClient
from custom_components.voiceforge.const import DEFAULT_API_KEY


MESSAGES = [{"role": "user", "content": "Hello."}]


def _make_openai_mock(content: str):
    """Return a mock AsyncOpenAI instance whose completions return content."""
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=response)
    return mock_client


async def test_complete_returns_response_content():
    mock_openai = _make_openai_mock("I am always here.")
    with patch(
        "custom_components.voiceforge.llm_client.AsyncOpenAI",
        return_value=mock_openai,
    ):
        client = LLMClient("http://localhost:11434/v1", "llama3")
        result = await client.complete(MESSAGES)
    assert result == "I am always here."


async def test_complete_on_unreachable_endpoint_returns_empty_string(caplog):
    mock_openai = MagicMock()
    mock_openai.chat.completions.create = AsyncMock(
        side_effect=Exception("Connection refused")
    )
    with patch(
        "custom_components.voiceforge.llm_client.AsyncOpenAI",
        return_value=mock_openai,
    ):
        client = LLMClient("http://localhost:11434/v1", "llama3")
        with caplog.at_level(logging.WARNING):
            result = await client.complete(MESSAGES)
    assert result == ""
    assert "connection refused" in caplog.text.lower() or "unreachable" in caplog.text.lower()


async def test_api_key_defaults_to_sk_voiceforge():
    with patch(
        "custom_components.voiceforge.llm_client.AsyncOpenAI"
    ) as mock_cls:
        mock_cls.return_value = _make_openai_mock("ok")
        LLMClient("http://localhost:11434/v1", "llama3")
        _, kwargs = mock_cls.call_args
        assert kwargs.get("api_key") == DEFAULT_API_KEY
