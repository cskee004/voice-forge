# VoiceForge

### Character-driven voice assistant integration for Home Assistant

<!-- CLAUDE_STATS_START -->
#### Claude Code Stats

![sessions: 3](https://img.shields.io/badge/sessions-3-1a1b27?style=for-the-badge&logo=anthropic&logoColor=white) ![API calls: 916](https://img.shields.io/badge/API%20calls-916-7aa2f7?style=for-the-badge&logo=anthropic&logoColor=white) ![tokens: 90.1M](https://img.shields.io/badge/tokens-90.1M-bb9af7?style=for-the-badge&logo=anthropic&logoColor=white) ![thinking time: 6.9m](https://img.shields.io/badge/thinking%20time-6.9m-7dcfff?style=for-the-badge&logo=anthropic&logoColor=white) ![wall clock: 12.5h](https://img.shields.io/badge/wall%20clock-12.5h-3d59a1?style=for-the-badge&logo=anthropic&logoColor=white) ![est. cost: $45.88](https://img.shields.io/badge/est.%20cost-%2445.88-73daca?style=for-the-badge&logo=anthropic&logoColor=white)
<!-- CLAUDE_STATS_END -->

---

## What it is

VoiceForge is a [HACS](https://hacs.xyz) custom integration for Home Assistant that replaces the default voice assistant with a fully character-faithful AI persona. Instead of a generic assistant, your household talks to a consistent, persistent character that remembers context across sessions, delivers personal messages, and reacts to home events in character.

It plugs into the standard HA Assist pipeline — Whisper handles speech-to-text, Piper handles text-to-speech, and VoiceForge owns everything in between: system prompt rendering, LLM call, memory extraction, and response cleaning for TTS delivery.

---

## Features

- **Swappable character cards** — YAML-defined personas with identity, speech rules, lore, and few-shot examples. Switch characters via the HA UI without restarting.
- **Persistent cross-session memory** — The integration extracts facts from conversation and stores them per character. On the next conversation, the top relevant memories are injected back into the system prompt automatically.
- **Personal message board** — Characters can generate and hold personal messages for household members, delivered at configured times (wake time, school return). Supports event-triggered messages (Type A) and scheduled messages (Type B).
- **Two-stage safety classifier** — Emergency phrases bypass the LLM entirely and return a direct emergency response. Built to be robust against false positives (a child asking for help finding their shoes does not trigger it).
- **Animated sprite display** — A 7-state emotion state machine fires HA events on state change. Sprites are pre-generated GIFs displayed on a 27" kiosk dashboard and M5Stack CoreS3 SE (v1.1).
- **Any OpenAI-compatible endpoint** — Configured against Ollama by default. Works with any endpoint that speaks the OpenAI API.
- **Full HA config flow** — Set up entirely through the Home Assistant UI. Four steps: LLM connection, character selection, household config, pipeline assignment.

---

## Hardware stack

| Component | Role |
|-----------|------|
| Raspberry Pi 4 | Runs Home Assistant |
| Windows PC (RTX 3080) | Runs Ollama, ComfyUI, faster-whisper |
| 27" kiosk display | Dashboard panel with live sprite |
| M5Stack CoreS3 SE | Satellite voice input + sprite display (v1.1) |

The integration is built for a dedicated local AI stack

---

## Installation

> **Status: in active development.** Not yet available in HACS. See [current build status](#status) below.

When released:

1. Install via HACS → Integrations → VoiceForge
2. Restart Home Assistant
3. Add integration → search VoiceForge
4. Complete the 4-step config flow
5. Assign to your Assist pipeline in Settings → Voice assistants

---

## Requirements

- Home Assistant 2024.6+
- An OpenAI-compatible LLM endpoint (Ollama recommended)
- Python packages (installed automatically): `openai>=1.0.0`, `pillow>=10.0.0`, `tiktoken>=0.7.0`

---

## Status

| Phase | What | Status |
|-------|------|--------|
| Phase 0 | Token budget validation | ✅ Done |
| Phase 1 | Core engine (`conversation.py`, `character_manager.py`, `llm_client.py`, `template_engine.py`, `config_flow.py`) | 🔄 In progress |
| Phase 2 | Memory & messages (`memory_manager.py`, `message_manager.py`) | Backlog |
| Phase 3 | Four founding character cards | Backlog |
| Phase 4 | Sprite system (`sprite_manager.py`, ComfyUI pipeline) | Backlog |
| Phase 5 | Dashboard panel | Backlog |
| Phase 6 | CI/CD, README, hardware validation, HACS submission | Backlog |

---

## Built with

- [Claude Code](https://claude.ai/code) — AI-assisted development, TDD throughout
- [Home Assistant](https://www.home-assistant.io/) — integration platform
- [Ollama](https://ollama.com/) — local LLM inference
- [HACS](https://hacs.xyz) — distribution

