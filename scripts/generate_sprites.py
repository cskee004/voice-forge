"""
Generate founding-four sprite GIFs via ComfyUI.

Usage:
    python scripts/generate_sprites.py --list-checkpoints
    python scripts/generate_sprites.py --checkpoint my_model.safetensors
    python scripts/generate_sprites.py --character aria --emotion idle
    python scripts/generate_sprites.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import httpx
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
CHARACTERS_DIR = REPO_ROOT / "custom_components" / "voiceforge" / "characters"
OUTPUT_DIR = REPO_ROOT / "custom_components" / "voiceforge" / "sprites"

EMOTIONS = ["idle", "listening", "speaking", "alert", "pleased", "warning"]


# ---------------------------------------------------------------------------
# ComfyUI helpers
# ---------------------------------------------------------------------------

async def list_checkpoints(base_url: str) -> list[str]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{base_url}/object_info/CheckpointLoaderSimple")
        resp.raise_for_status()
        info = resp.json()
        inputs = info.get("CheckpointLoaderSimple", {}).get("input", {})
        required = inputs.get("required", {})
        ckpt_entry = required.get("ckpt_name", [[]])
        return list(ckpt_entry[0]) if ckpt_entry else []


async def pick_checkpoint(base_url: str, requested: str | None) -> str:
    available = await list_checkpoints(base_url)
    if not available:
        raise RuntimeError(
            "ComfyUI returned no checkpoints. Make sure at least one .safetensors "
            "model is installed in ComfyUI/models/checkpoints/."
        )
    if requested:
        if requested not in available:
            print(f"WARNING: '{requested}' not found. Available: {available}")
            print(f"Using first available: {available[0]}")
        else:
            return requested
    print(f"Auto-selected checkpoint: {available[0]}")
    return available[0]


# ---------------------------------------------------------------------------
# Card loading
# ---------------------------------------------------------------------------

def load_cards(character_filter: str | None) -> list[dict]:
    cards = []
    for path in sorted(CHARACTERS_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as f:
            card = yaml.safe_load(f)
        if character_filter and card.get("id") != character_filter:
            continue
        cards.append(card)
    if not cards:
        raise RuntimeError(
            f"No cards found in {CHARACTERS_DIR}"
            + (f" matching character '{character_filter}'" if character_filter else "")
        )
    return cards


def build_prompt(card: dict, emotion: str) -> str:
    """Merge base style prompt + per-emotion sprite note."""
    avatar = card.get("avatar", {})
    base = avatar.get("sprite_style_prompt", "").strip().replace("\n", " ")
    notes: dict[str, str] = avatar.get("sprite_notes", {})
    note = notes.get(emotion, "").strip()
    return f"{base}, {note}" if note else base


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

async def generate_all(
    base_url: str,
    checkpoint: str,
    cards: list[dict],
    emotion_filter: str | None,
    dry_run: bool,
) -> None:
    # Import here so the script can run --list-checkpoints without the full HA env
    sys.path.insert(0, str(REPO_ROOT))
    from custom_components.voiceforge.comfyui_client import ComfyUIClient

    client = ComfyUIClient(base_url=base_url)
    total = 0
    ok = 0

    for card in cards:
        char_id = card["id"]
        char_name = card.get("name", char_id)
        avatar = card.get("avatar", {})
        fps = avatar.get("sprite_fps", 8)

        emotions = [emotion_filter] if emotion_filter else EMOTIONS
        for emotion in emotions:
            prompt = build_prompt(card, emotion)
            out_path = OUTPUT_DIR / char_id / f"{emotion}.gif"
            total += 1

            if dry_run:
                print(f"[DRY RUN] {char_name}/{emotion}")
                print(f"          checkpoint : {checkpoint}")
                print(f"          fps        : {fps}")
                print(f"          prompt     : {prompt[:120]}...")
                print(f"          output     : {out_path}")
                continue

            print(f"Generating {char_name}/{emotion} ... ", end="", flush=True)
            result = await client.generate_sprite(
                character_id=char_id,
                emotion=emotion,
                style_prompt=prompt,
                output_dir=OUTPUT_DIR,
                fps=fps,
                checkpoint=checkpoint,
            )
            if result:
                print(f"OK -> {result.relative_to(REPO_ROOT)}")
                ok += 1
            else:
                print("FAILED (check ComfyUI logs)")

    if not dry_run:
        print(f"\nDone: {ok}/{total} sprites generated -> {OUTPUT_DIR.relative_to(REPO_ROOT)}")
    else:
        print(f"\n[DRY RUN] Would generate {total} sprites.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate VoiceForge sprite GIFs via ComfyUI.")
    parser.add_argument("--comfyui-url", default="http://localhost:8188", help="ComfyUI base URL")
    parser.add_argument("--checkpoint", default=None, help="Checkpoint filename (auto-detected if omitted)")
    parser.add_argument("--list-checkpoints", action="store_true", help="List available checkpoints and exit")
    parser.add_argument("--character", default=None, help="Generate only this character (e.g. aria)")
    parser.add_argument("--emotion", default=None, choices=EMOTIONS, help="Generate only this emotion")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without calling ComfyUI")
    args = parser.parse_args(argv)

    base_url = args.comfyui_url.rstrip("/")

    if args.list_checkpoints:
        try:
            checkpoints = await list_checkpoints(base_url)
        except Exception as exc:
            print(f"ERROR: Could not reach ComfyUI at {base_url}: {exc}")
            sys.exit(1)
        if not checkpoints:
            print("No checkpoints found.")
        else:
            print(f"Available checkpoints at {base_url}:")
            for c in checkpoints:
                print(f"  {c}")
        return

    cards = load_cards(args.character)

    if args.dry_run:
        checkpoint = args.checkpoint or "pixel_art.safetensors"
        await generate_all(base_url, checkpoint, cards, args.emotion, dry_run=True)
        return

    try:
        checkpoint = await pick_checkpoint(base_url, args.checkpoint)
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    await generate_all(base_url, checkpoint, cards, args.emotion, dry_run=False)


if __name__ == "__main__":
    asyncio.run(main())
