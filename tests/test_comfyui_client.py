"""
comfyui_client.py tests.

All HTTP calls and asyncio.sleep are mocked. Minimal real PNG data is
generated via Pillow so the GIF assembly path runs against real code.
"""

import asyncio
import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from custom_components.voiceforge.comfyui_client import ComfyUIClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_png() -> bytes:
    """Return bytes for a tiny valid RGBA PNG (used as a fake frame)."""
    buf = io.BytesIO()
    Image.new("RGBA", (8, 8), color=(0, 0, 0, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _http_response(json_data=None, content=b""):
    """Build a minimal mock httpx response."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=json_data or {})
    resp.content = content
    return resp


def _complete_history(prompt_id: str, filename: str = "frame_0.png") -> dict:
    return {
        prompt_id: {
            "outputs": {
                "9": {
                    "images": [{"filename": filename, "subfolder": "", "type": "output"}]
                }
            },
            "status": {"completed": True},
        }
    }


def _make_mock_client(post_json: dict, get_responses: list):
    """Build a mock httpx.AsyncClient class with pre-configured responses."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=_http_response(json_data=post_json))
    mock_client.get = AsyncMock(side_effect=get_responses)
    return MagicMock(return_value=mock_client), mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_generate_sprite_returns_path_on_success(tmp_path):
    prompt_id = "abc123"
    png = _minimal_png()

    MockClientClass, _ = _make_mock_client(
        post_json={"prompt_id": prompt_id},
        get_responses=[
            _http_response(json_data=_complete_history(prompt_id)),  # history → done
            _http_response(content=png),                             # view → PNG frame
        ],
    )

    with patch("custom_components.voiceforge.comfyui_client.httpx.AsyncClient", MockClientClass):
        client = ComfyUIClient(base_url="http://localhost:8188")
        result = await client.generate_sprite("aria", "idle", "glowing red eye", str(tmp_path))

    assert result is not None
    assert result == tmp_path / "aria" / "idle.gif"
    assert result.exists()


async def test_generate_sprite_returns_none_when_unreachable(tmp_path):
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
    mock_client.__aexit__ = AsyncMock(return_value=False)
    MockClientClass = MagicMock(return_value=mock_client)

    with patch("custom_components.voiceforge.comfyui_client.httpx.AsyncClient", MockClientClass):
        client = ComfyUIClient(base_url="http://localhost:8188")
        result = await client.generate_sprite("aria", "idle", "glowing red eye", str(tmp_path))

    assert result is None


async def test_generate_sprite_logs_warning_when_unreachable(tmp_path, caplog):
    import logging
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
    mock_client.__aexit__ = AsyncMock(return_value=False)
    MockClientClass = MagicMock(return_value=mock_client)

    with patch("custom_components.voiceforge.comfyui_client.httpx.AsyncClient", MockClientClass):
        with caplog.at_level(logging.WARNING):
            client = ComfyUIClient(base_url="http://localhost:8188")
            await client.generate_sprite("aria", "idle", "prompt", str(tmp_path))

    assert any("aria" in r.message.lower() or "idle" in r.message.lower() for r in caplog.records)


async def test_generate_sprite_polls_until_complete(tmp_path):
    prompt_id = "poll123"
    png = _minimal_png()

    MockClientClass, mock_client = _make_mock_client(
        post_json={"prompt_id": prompt_id},
        get_responses=[
            _http_response(json_data={}),                                    # poll 1 → not in history yet
            _http_response(json_data=_complete_history(prompt_id)),          # poll 2 → done
            _http_response(content=png),                                     # view → PNG frame
        ],
    )

    with patch("custom_components.voiceforge.comfyui_client.httpx.AsyncClient", MockClientClass):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            client = ComfyUIClient(base_url="http://localhost:8188")
            result = await client.generate_sprite("aria", "speaking", "prompt", str(tmp_path))

    assert result is not None
    assert mock_client.get.call_count >= 2  # at least two history polls


async def test_output_saved_at_correct_path(tmp_path):
    prompt_id = "path123"
    png = _minimal_png()

    MockClientClass, _ = _make_mock_client(
        post_json={"prompt_id": prompt_id},
        get_responses=[
            _http_response(json_data=_complete_history(prompt_id)),
            _http_response(content=png),
        ],
    )

    with patch("custom_components.voiceforge.comfyui_client.httpx.AsyncClient", MockClientClass):
        client = ComfyUIClient(base_url="http://localhost:8188")
        result = await client.generate_sprite("sera", "warning", "armored face", str(tmp_path))

    assert result == tmp_path / "sera" / "warning.gif"
    assert (tmp_path / "sera" / "warning.gif").exists()


async def test_gif_assembled_from_multiple_frames(tmp_path):
    """Multiple PNG frames are assembled into one animated GIF."""
    prompt_id = "frames123"
    png = _minimal_png()

    history = {
        prompt_id: {
            "outputs": {
                "9": {
                    "images": [
                        {"filename": "f0.png", "subfolder": "", "type": "output"},
                        {"filename": "f1.png", "subfolder": "", "type": "output"},
                        {"filename": "f2.png", "subfolder": "", "type": "output"},
                    ]
                }
            }
        }
    }

    MockClientClass, mock_client = _make_mock_client(
        post_json={"prompt_id": prompt_id},
        get_responses=[
            _http_response(json_data=history),
            _http_response(content=png),  # frame 0
            _http_response(content=png),  # frame 1
            _http_response(content=png),  # frame 2
        ],
    )

    with patch("custom_components.voiceforge.comfyui_client.httpx.AsyncClient", MockClientClass):
        client = ComfyUIClient(base_url="http://localhost:8188")
        result = await client.generate_sprite("aria", "speaking", "prompt", str(tmp_path))

    assert result is not None
    # 3 view calls (one per frame) + 1 history call = 4 total GET calls
    assert mock_client.get.call_count == 4


async def test_custom_checkpoint_used_in_workflow(tmp_path):
    """Custom checkpoint name propagates into the submitted workflow."""
    prompt_id = "ckpt123"
    png = _minimal_png()
    captured_payload = {}

    async def capture_post(url, json=None, **kwargs):
        captured_payload.update(json or {})
        return _http_response(json_data={"prompt_id": prompt_id})

    MockClientClass, mock_client = _make_mock_client(
        post_json={"prompt_id": prompt_id},
        get_responses=[
            _http_response(json_data=_complete_history(prompt_id)),
            _http_response(content=png),
        ],
    )
    mock_client.post = AsyncMock(side_effect=capture_post)

    with patch("custom_components.voiceforge.comfyui_client.httpx.AsyncClient", MockClientClass):
        client = ComfyUIClient(base_url="http://localhost:8188")
        await client.generate_sprite(
            "aria", "idle", "glowing red eye", str(tmp_path),
            checkpoint="my_pixel_model.safetensors",
        )

    loader = captured_payload["prompt"]["4"]
    assert loader["inputs"]["ckpt_name"] == "my_pixel_model.safetensors"
