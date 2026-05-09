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
        result = await client.generate_sprite(
            "aria", "idle", "glowing red eye", str(tmp_path), frame_count=1
        )

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
            result = await client.generate_sprite(
                "aria", "speaking", "prompt", str(tmp_path), frame_count=1
            )

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
        result = await client.generate_sprite(
            "sera", "warning", "armored face", str(tmp_path), frame_count=1
        )

    assert result == tmp_path / "sera" / "warning.gif"
    assert (tmp_path / "sera" / "warning.gif").exists()


async def test_gif_assembled_from_multiple_frames(tmp_path):
    """3 separate per-frame POST calls produce a 3-frame animated GIF."""
    png = _minimal_png()
    frame_count = 3

    # Each frame: 1 POST, 1 history GET (done), 1 view GET
    get_responses = []
    for i in range(frame_count):
        pid = f"frame{i}"
        get_responses.append(_http_response(json_data=_complete_history(pid, f"f{i}.png")))
        get_responses.append(_http_response(content=png))

    post_call = [0]
    async def rotating_post(url, json=None, **kwargs):
        pid = f"frame{post_call[0]}"
        post_call[0] += 1
        return _http_response(json_data={"prompt_id": pid})

    MockClientClass, mock_client = _make_mock_client(
        post_json={},
        get_responses=get_responses,
    )
    mock_client.post = AsyncMock(side_effect=rotating_post)

    with patch("custom_components.voiceforge.comfyui_client.httpx.AsyncClient", MockClientClass):
        client = ComfyUIClient(base_url="http://localhost:8188")
        result = await client.generate_sprite(
            "aria", "speaking", "prompt", str(tmp_path), frame_count=frame_count
        )

    assert result is not None
    assert mock_client.post.call_count == frame_count       # one POST per frame
    assert mock_client.get.call_count == frame_count * 2   # history + view per frame


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


async def test_lora_workflow_includes_lora_loader_and_image_scale(tmp_path):
    """When a LoRA is given: LoraLoader node present, latent is 1024x768, ImageScale downsamples to 320x240."""
    prompt_id = "lora123"
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
            checkpoint="sd_xl_base.safetensors",
            lora="pixel-art-xl-v1.1.safetensors",
        )

    nodes = captured_payload["prompt"]
    # LoraLoader must be present
    lora_nodes = [n for n in nodes.values() if n["class_type"] == "LoraLoader"]
    assert len(lora_nodes) == 1
    assert lora_nodes[0]["inputs"]["lora_name"] == "pixel-art-xl-v1.1.safetensors"
    # Latent image must be SDXL resolution
    latent_nodes = [n for n in nodes.values() if n["class_type"] == "EmptyLatentImage"]
    assert latent_nodes[0]["inputs"]["width"] == 1024
    assert latent_nodes[0]["inputs"]["height"] == 768
    # ImageScale must downscale to 320x240 with nearest-exact
    scale_nodes = [n for n in nodes.values() if n["class_type"] == "ImageScale"]
    assert len(scale_nodes) == 1
    assert scale_nodes[0]["inputs"]["width"] == 320
    assert scale_nodes[0]["inputs"]["height"] == 240
    assert scale_nodes[0]["inputs"]["upscale_method"] == "nearest-exact"


async def test_no_lora_workflow_unchanged(tmp_path):
    """Without a LoRA the original SD 1.5 workflow is used (no LoraLoader, no ImageScale)."""
    prompt_id = "nolora123"
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
        await client.generate_sprite("aria", "idle", "glowing red eye", str(tmp_path))

    nodes = captured_payload["prompt"]
    assert not any(n["class_type"] == "LoraLoader" for n in nodes.values())
    assert not any(n["class_type"] == "ImageScale" for n in nodes.values())
    latent = next(n for n in nodes.values() if n["class_type"] == "EmptyLatentImage")
    assert latent["inputs"]["width"] == 320
    assert latent["inputs"]["height"] == 240


async def test_each_frame_uses_distinct_seed(tmp_path):
    """Each frame is submitted as a separate workflow with seed = 42 + frame_index * 1000."""
    frame_count = 3
    png = _minimal_png()
    seeds_used = []

    call_count = 0

    async def capture_post(url, json=None, **kwargs):
        nonlocal call_count
        prompt_id = f"frame{call_count}"
        call_count += 1
        nodes = (json or {}).get("prompt", {})
        sampler = next((n for n in nodes.values() if n.get("class_type") == "KSampler"), None)
        if sampler:
            seeds_used.append(sampler["inputs"]["seed"])
        return _http_response(json_data={"prompt_id": prompt_id})

    def make_get_side_effect():
        # Each frame: one history poll (done) + one view download
        responses = []
        for i in range(frame_count):
            pid = f"frame{i}"
            responses.append(_http_response(json_data=_complete_history(pid, f"f{i}.png")))
            responses.append(_http_response(content=png))
        return responses

    MockClientClass, mock_client = _make_mock_client(
        post_json={},
        get_responses=make_get_side_effect(),
    )
    mock_client.post = AsyncMock(side_effect=capture_post)

    with patch("custom_components.voiceforge.comfyui_client.httpx.AsyncClient", MockClientClass):
        client = ComfyUIClient(base_url="http://localhost:8188")
        result = await client.generate_sprite(
            "aria", "idle", "glowing red eye", str(tmp_path),
            frame_count=frame_count,
        )

    assert result is not None
    assert mock_client.post.call_count == frame_count
    assert len(seeds_used) == frame_count
    # Each frame must use a distinct seed spaced 1000 apart
    assert seeds_used == [42 + i * 1000 for i in range(frame_count)]
