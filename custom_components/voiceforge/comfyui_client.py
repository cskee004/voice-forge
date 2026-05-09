"""Async ComfyUI REST client for offline sprite generation."""

from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path

import httpx
from PIL import Image

_LOGGER = logging.getLogger(__name__)

_POLL_INTERVAL = 2.0   # seconds between /history polls
_POLL_TIMEOUT = 120    # max seconds before giving up
_OUTPUT_NODE = "9"     # SaveImage node ID in the bundled workflow

_EMOTION_MODIFIERS: dict[str, str] = {
    "idle": "resting, ambient glow, slow pulse",
    "pleased": "happy, warm expression, slight smile",
    "listening": "attentive, focused, head tilted",
    "speaking": "animated, expressive, mouth open",
    "alert": "heightened attention, eyes widened, energized",
    "warning": "intense, alarmed, urgent, fills frame",
}


class ComfyUIClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def generate_sprite(
        self,
        character_id: str,
        emotion: str,
        style_prompt: str,
        output_dir: str | Path,
        base_image: bytes | None = None,
        fps: int = 8,
        frame_count: int = 6,
        checkpoint: str = "pixel_art.safetensors",
    ) -> Path | None:
        """Generate an animated GIF sprite. Returns the saved Path or None on failure."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                workflow = _build_workflow(style_prompt, emotion, frame_count, checkpoint)
                prompt_id = await self._submit(client, workflow)
                images = await self._poll_until_done(client, prompt_id)
                frames = await self._download_frames(client, images)
                gif_bytes = _assemble_gif(frames, fps)

                out_path = Path(output_dir) / character_id / f"{emotion}.gif"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(gif_bytes)
                return out_path

        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "ComfyUI sprite generation failed for %s/%s: %s",
                character_id,
                emotion,
                exc,
            )
            return None

    async def _submit(self, client: httpx.AsyncClient, workflow: dict) -> str:
        resp = await client.post(f"{self._base_url}/prompt", json={"prompt": workflow})
        resp.raise_for_status()
        return resp.json()["prompt_id"]

    async def _poll_until_done(
        self, client: httpx.AsyncClient, prompt_id: str
    ) -> list[dict]:
        elapsed = 0.0
        while elapsed < _POLL_TIMEOUT:
            resp = await client.get(f"{self._base_url}/history/{prompt_id}")
            resp.raise_for_status()
            history = resp.json()
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_outputs in outputs.values():
                    if "images" in node_outputs:
                        return node_outputs["images"]
                return []
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL
        raise TimeoutError(f"ComfyUI timed out after {_POLL_TIMEOUT}s (prompt {prompt_id})")

    async def _download_frames(
        self, client: httpx.AsyncClient, images: list[dict]
    ) -> list[bytes]:
        frames: list[bytes] = []
        for img in images:
            params = {
                "filename": img["filename"],
                "subfolder": img.get("subfolder", ""),
                "type": img.get("type", "output"),
            }
            resp = await client.get(f"{self._base_url}/view", params=params)
            resp.raise_for_status()
            frames.append(resp.content)
        return frames


def _build_workflow(
    style_prompt: str,
    emotion: str,
    frame_count: int,
    checkpoint: str = "pixel_art.safetensors",
) -> dict:
    modifier = _EMOTION_MODIFIERS.get(emotion, "")
    full_prompt = f"{style_prompt}, {modifier}" if modifier else style_prompt
    return {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 320, "height": 240, "batch_size": frame_count},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": full_prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "blurry, low quality, noise", "clip": ["4", 1]},
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
                "seed": 42,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        _OUTPUT_NODE: {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": "voiceforge"},
        },
    }


def _assemble_gif(frames: list[bytes], fps: int) -> bytes:
    images = [Image.open(io.BytesIO(f)).convert("RGBA") for f in frames]
    buf = io.BytesIO()
    duration_ms = max(1, int(1000 / fps))
    images[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        loop=0,
        duration=duration_ms,
        optimize=False,
    )
    return buf.getvalue()
