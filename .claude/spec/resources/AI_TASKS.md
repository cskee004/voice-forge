# AI Development Tasks

## How This File Works

This file is the **single source of truth** for task status. Do not track status in CLAUDE.md or anywhere else.

### Numbering rules

- Backlog items have **no task numbers**. A task gets a number only when work begins.
- Numbers are **permanent** once assigned — they appear in git commit messages and must never change.
- To start a task: pick the next available integer (highest number in the Completed list + 1), assign it, move the item to In Progress, and use `(Task N)` in every commit for that task.

### Commit format

```
type: short description (Task N)
```

### Lifecycle

1. New work → **Backlog** (no number, plain description)
2. Work starts → assign number, move to **In Progress**
3. Tests green + committed → move to **Completed** (one line, newest first)

### Mid-task discoveries

If something unexpected comes up that is not the current task, add it to Backlog (no number) and finish the current task first. Do not interrupt a task by starting another.

---

## 🔄 In Progress

---

## ✅ Completed

Newest first. One line per task.

**Task 15** — Founding four sprites generated: SDXL + Pixel Art XL LoRA, per-frame distinct seeds (42+i*1000), 1024x768->320x240 nearest-exact downscale, lora param + LoraLoader/ImageScale workflow (TDD, 10/10). 24 GIFs committed. 90/90 total green.

**Task 14** — Integration wiring: PLATFORMS=["conversation"], async_setup_entry wires all 6 managers, conversation.py gets platform async_setup_entry + HA entity properties + IntentResponse return type. 16/16 new tests + 86/86 total green.

**Task 13** — Four founding character YAML cards installed: ARIA (8ex), SERA (8ex), MALACHAR (8ex), SHEPHERD (9ex). All 4/4 load against CARD_SCHEMA. install_characters.py + validate_characters.py scripts added.

**Task 12** — Sprite static file setup in `async_setup_entry`: copies `sprites/` → `www/voiceforge/sprites/` via `shutil.copytree` in `run_in_executor`. Skips if dest exists or src missing. 5/5 tests green.

**Task 11** — `comfyui_client.py`: async httpx client, submit workflow → poll /history → download frames → assemble animated GIF via Pillow. Unreachable/timeout → None + warning log. 6/6 tests green.

**Task 10** — `config_flow.py`: 4-step flow (LLM connection + test, character select, home context, pipeline instructions), accumulates data in `self._data`, creates entry on Step 4 submit. conftest `_ConfigFlow` stub fixed to share object with sys.modules. 10/10 tests green.

**Task 9** — `sprite_manager.py`: EmotionState IntEnum (7 states, priority WARNING>ALERT>SPEAKING>LISTENING>PLEASED>IDLE), transition() priority guard, 60s idle timer with cancel/reschedule, HA `voiceforge_emotion_change` event. 15/15 tests green.

**Task 8** — `message_manager.py`: Type A/B messages, single asyncio.Lock, 30-min rate limit, unread dedup, 7-day TTL pruning. 6/6 tests green.

**Task 7** — `memory_manager.py`: N-turn gated async_extract(), asyncio.Lock skip, FIFO eviction, run_in_executor I/O, failure continues. 5/5 tests green.

**Task 6** — `conversation.py`: VoiceForgeConversationAgent, full async_process() pipeline, per-conv_id history, 30-min TTL pruning, _clean_for_tts(). 4/4 tests green.

**Task 5** — `safety_classifier.py`: two-stage check_emergency(), Stage 1 always fires, Stage 2 gated by innocent context words. 16/16 tests green.

**Task 4** — `template_engine.py`: render(), Jinja2 sanitization, tiktoken budget, lore trimmed before examples, safety layer always last. 5/5 tests green.

**Task 3** — `llm_client.py`: thin AsyncOpenAI wrapper, complete() returns "" + logs warning on failure, api_key defaults to sk-voiceforge. 3/3 tests green.

**Task 2** — `character_manager.py`: CharacterCard dataclass, voluptuous CARD_SCHEMA, load_card/load_all/switch_character/get_active_character; Windows stubs (fcntl.py, resource.py) + conftest HA stubs. 4/4 tests green.

**Task 1** — Repository scaffold: directory structure, manifest.json, hacs.json, const.py, __init__.py, pytest.ini, conftest.py with mock_hass/mock_llm_client/mock_config_entry fixtures.

---

## 📋 Backlog

Work in this order. TDD throughout — test first, watch it fail, then implement.

---

### Phase 0 — Pre-flight

- ~~**Pre-task: validate ARIA system prompt token budget**~~ ✓ DONE (2026-05-05): Shell = 1720 tokens. Fix applied: budget raised to 2200 tokens, all 8 examples always rendered. 480 tokens headroom for live state + memory. See §20.2.

---

### Phase 1 — Core Engine

- **`character_manager.py`** — YAML card loading, voluptuous schema validation, character switching. No HA dependencies. TDD: write `test_character_manager.py` first. Covers: valid card loads, missing required field raises error + falls back to ARIA, missing `guardrail_response` uses default fallback, card switch updates active character.

- **`character_manager.py`** — YAML card loading, voluptuous schema validation, character switching. No HA dependencies. TDD: write `test_character_manager.py` first. Covers: valid card loads, missing required field raises error + falls back to ARIA, missing `guardrail_response` uses default fallback, card switch updates active character.

- **`llm_client.py`** — Thin `AsyncOpenAI` wrapper. `async def complete(messages: list[dict]) -> str`. Config-driven endpoint + model + api_key. TDD: write `test_llm_client.py` first. Covers: successful completion, endpoint unreachable returns empty string + logs warning, api_key defaults to "sk-voiceforge".

- **`template_engine.py`** — System prompt rendering. Two-pass: sanitize card fields, build state dict directly, concatenate as f-string (no Jinja2 for prompt assembly). tiktoken budget enforcement (default 4 examples, add more if under 1500 tokens). Immutable safety layer always appended last. TDD: write `test_template_engine.py` first. Covers: safety layer present and last, Jinja2 in card fields is escaped, token count under 2000, truncation priority order (lore trimmed before examples), 4-example default.

- **`test_safety_classifier.py` + `_check_emergency()` in `conversation.py`** — Two-stage classifier (Stage 1: 6 unambiguous phrases; Stage 2: medium-confidence without innocent context words). Write test file first. Covers: each high-confidence phrase fires, "help me find my shoes" does NOT fire, "help me" alone fires, "i'm scared the movie" does NOT fire.

- **`conversation.py`** — `VoiceForgeConversationAgent(ConversationEntity)`. Full `async_process()` flow per architecture doc. `self._histories: dict[str, list]` keyed by `conversation_id`, 30-min idle TTL. TDD: write `test_conversation.py` first. Covers: happy path end-to-end, emergency integration test (LLM call count == 0 on emergency input, EMERGENCY_RESPONSE returned), session history isolated per conversation_id, idle sessions pruned.

- **`config_flow.py`** — 4-step HA config UI. Step 1: LLM endpoint + model + api_key + test connection. Step 2: active character selector. Step 3: household members, wake time, school schedule, parent notify entity. Step 4: pipeline assignment instructions.

---

### Phase 2 — Memory & Messages

- **`memory_manager.py`** — Extraction (N-turn counter owned by manager, asyncio.Lock per character_id), storage (flat JSON, run_in_executor), injection (top-5 by recency). TDD: write `test_memory_manager.py` first. Covers: extraction fires on turn N not turn N-1, lock held → extraction skipped, FIFO eviction at max_memory_entries, file read/write uses executor, failure logs and continues.

- **`message_manager.py`** — Type A (event-driven) and Type B (schedule-via-`async_track_point_in_time`). Single asyncio.Lock for messages.json writes. Rate limiting (30-min cooldown per character per trigger). Deduplication. 7-day TTL on load. Layer 2 voice delivery via schedule window proxy. TDD: write `test_message_manager.py` first. Covers: Type A stored correctly, Type B generated with LLM + parent_notified flag set, second call within 30min skipped, existing unread same-trigger blocks generation, expired messages pruned on load, concurrent write lock prevents race.

---

### Phase 3 — Four Character Cards

- **Complete all four founding character YAML cards** — ARIA, SERA, MALACHAR, SHEPHERD per Section 13 checklist. Each needs: full persona, 6–8 examples, lore, memory config, message_board config, guardrail_response (all four already have this), voice tuning. Run tiktoken against each card shell to confirm total prompt fits within 2200-token budget (shell ≤ 1720 leaves ~480 for live state + memory).

---

### Phase 4 — Sprite System

- **`sprite_manager.py`** — Emotion state machine (7 states, priority order: warning > alert > speaking > listening > pleased > idle), 60s inactivity → idle, HA event firing (`voiceforge_emotion_change`). TDD: write `test_sprite_manager.py` first. Covers: each state transition, priority (alert cannot override warning), 60s timeout, HA event payload structure (character_id, emotion, sprite_url format).

- **`comfyui_client.py`** — Async REST client for offline sprite generation. Frame assembly → animated GIF via Pillow. Never called during live conversation. ComfyUI unreachable → log warning, return None (caller uses placeholder PNG).

- **Sprite static file setup** — `async_setup()` copies bundled sprites from `custom_components/voiceforge/sprites/` to `/config/www/voiceforge/sprites/` via `shutil.copytree(dirs_exist_ok=True)` in `run_in_executor`. Idempotent.

- **Generate founding four sprites** — Run ComfyUI with style prompts from character cards. 6 emotions × 4 characters = 24 GIFs. Commit to `sprites/` directory.

---

### Phase 5 — Dashboard Panel

- **`www/voiceforge-panel/`** — Custom Lovelace panel. Character library (grid, active highlight, one-tap switch). Message board feed (Type A + B, unread indicator, filter by character/member). Memory viewer (collapsed, read-only). WebSocket listener for `voiceforge_emotion_change` → swap sprite `src`. Register panel in `__init__.py`.

---

### Phase 6 — Polish & Ship

- **CI/CD** — GitHub Actions: `pytest --cov=custom_components/voiceforge` on every PR, YAML schema validation for character cards. Add `pytest-homeassistant-custom-component` to dev requirements.

- **README** — Installation, HACS setup, Ollama config, first character selection, memory privacy note, M5Stack v1.1 note.

- **Hardware validation gate** — Manual test on Pi 4 + Ollama on Windows PC: clean install, all four characters in-character, memory persists across restart, safety classifier fires, character switching works.

- **HACS submission prep** — Verify manifest.json, hacs.json, README, version tags, issue tracker URL filled in.

---