# AI Architecture Guide

## Purpose of This Document

This file defines the **technical architecture of VoiceForge**.

The goal is to ensure the AI assistant understands how the system is structured so it can implement new features **without introducing architectural drift**.

All new code should follow the architectural patterns defined here.

---

# System Overview

VoiceForge is a HACS custom integration for Home Assistant. It registers as a `ConversationEntity` — the same slot used by the native Ollama integration. When a user speaks, HA routes the text to VoiceForge's `async_process()`. VoiceForge renders a character-faithful system prompt, calls any OpenAI-compatible LLM endpoint, and returns the response to the HA Assist pipeline.

```
User speaks
    │
    ▼
[HA Assist Pipeline]
    │  ConversationInput(text, conversation_id, language)
    ▼
[VoiceForgeConversationAgent.async_process()]
    │
    ├─► [Safety] _check_emergency(text) ──► EMERGENCY_RESPONSE (if match)
    │
    ├─► [CharacterManager] get_active_character() → CharacterCard
    │
    ├─► [TemplateEngine] render(character, hass) → system_prompt (str)
    │       ├── sanitize card text fields (escape Jinja2)
    │       ├── fetch live HA state snapshot (cached 30s)
    │       ├── inject top-5 memory entries
    │       └── append immutable safety layer
    │
    ├─► [LLMClient] complete(messages) → raw_response (str)
    │       └── openai SDK, async, any OpenAI-compatible endpoint
    │
    ├─► _clean_for_tts(raw_response) → clean_response (str)
    │
    ├─► hass.async_create_task(memory_manager.async_extract(...))
    │       └── background — locked per character_id, skipped if in-flight
    │
    └─► ConversationResult(response=clean_response)
         │
         ▼
    [Piper TTS → User hears character]
```

---

# System Layers

```
┌─────────────────────────────────────────────────────────┐
│                  Home Assistant Core                     │
│   ConversationEntity API  │  hass.states  │  hass.bus   │
└──────────────────┬──────────────────────────────────────┘
                   │ inherits / calls
┌──────────────────▼──────────────────────────────────────┐
│               VoiceForge Integration                     │
│                                                          │
│  conversation.py          ← entry point (ConversationEntity)
│  ├── character_manager.py ← loads/switches character cards
│  ├── llm_client.py        ← thin OpenAI-compat wrapper
│  ├── template_engine.py   ← renders system prompt (tiktoken budget)
│  ├── memory_manager.py    ← extracts, stores, injects facts
│  ├── message_manager.py   ← Type A/B messages, 3-layer delivery
│  └── sprite_manager.py    ← emotion state machine + HA events
│                                                          │
│  comfyui_client.py        ← offline sprite generation   │
│  config_flow.py           ← HA setup UI (4 steps)       │
│  [esphome_generator.py — v1.1, not in v1 scope]         │
└──────────────────┬──────────────────────────────────────┘
                   │ calls
┌──────────────────▼──────────────────────────────────────┐
│              External Services (LAN)                     │
│   Ollama :11434  │  ComfyUI :8188  │  faster-whisper    │
└─────────────────────────────────────────────────────────┘
```

---

# Data Flow

## Conversation Request Flow

```
async_process(ConversationInput)
       │
       ▼
1. _check_emergency(text) — TWO-STAGE classifier:
       │  Stage 1: 6 unambiguous phrases → always fire (call 911, i want to die, etc.)
       │  Stage 2: ambiguous phrases (help me, i am scared) → fire only if no
       │           innocent context words follow (find, with, the, do, watch, play)
       ├──[match]──► return EMERGENCY_RESPONSE (log to safety_log.json)
       │
       ▼ [no match]
2. character_manager.get_active_character() → CharacterCard
       │
       ▼
3. template_engine.render(character, hass)
       │  a. Sanitize card text (escape {{ }})
       │  b. Get HA state snapshot (cache 30s, invalidate on state_changed)
       │  c. Inject top-5 memory entries (ARIA: "logged", SHEPHERD: "held")
       │  d. Append immutable safety layer (always last, never trimmed)
       │  e. Enforce 2200-token budget (trim lore → examples → speech rules)
       ▼
4. _build_messages(user_input, system_prompt)
       │  history keyed by conversation_id (self._histories: dict[str, list])
       │  max 10 turns (20 messages) per conversation_id — drop oldest first
       │  sessions idle >30 min are purged to prevent unbounded growth
       ▼
5. llm_client.complete(messages) → str
       │  AsyncOpenAI(base_url=endpoint, api_key=key)
       ▼
6. _clean_for_tts(response) → str
       │  strip markdown, remove URLs, em-dash → comma, trim to ~400 chars
       ▼
7. hass.async_create_task(_run_memory_extraction(character, messages))
       │  async background — asyncio.Lock per character_id
       │  skip if lock held (extraction already in-flight)
       ▼
8. return ConversationResult(response=clean_response)
```

## Memory Extraction Flow (background)

```
_run_memory_extraction(character, messages)
       │
       ├── acquire asyncio.Lock(character_id) — skip if held
       │
       ├── llm_client.complete(extraction_prompt + last_N_turns)
       │       └── try/except: log warning on failure, return
       │
       ├── merge new facts into character_id.json
       │       └── deduplicate (string match, v1)
       │
       ├── FIFO eviction if len(entries) > max_memory_entries
       │
       └── write JSON (run_in_executor — never block event loop)
```

## Emotion State Machine

```
INPUTS → SpriteManager.transition(new_state, character_id)
   │
   ├── conversation started → listening
   ├── async_process called → listening  
   ├── async_process returns → speaking
   ├── TTS finished (or 10s timeout) → idle
   ├── voiceforge_alert event → alert
   ├── voiceforge_pleased event → pleased
   ├── voiceforge_warning event → warning
   └── 60s inactivity → idle
       │
       ▼
hass.bus.async_fire('voiceforge_emotion_change', {
    'character_id': ...,
    'emotion': ...,
    'sprite_url': '/local/voiceforge/sprites/{id}/{emotion}.gif'
})
       │
       ▼
Display surfaces subscribe (kiosk WebSocket, M5Stack ESPHome API)
```

---

# Storage Model

```
/config/voiceforge/
├── memory/
│   ├── aria.json          # per-character memory entries
│   ├── sera.json
│   ├── malachar.json
│   └── shepherd.json
├── messages/
│   └── messages.json      # all Type A + Type B messages
├── safety_log.json        # guardrail trigger log (admin only)
└── sprites/               # runtime sprite location
    ├── aria/
    │   ├── idle.gif
    │   ├── listening.gif
    │   ├── speaking.gif
    │   ├── alert.gif
    │   ├── pleased.gif
    │   └── warning.gif
    ├── sera/
    ├── malachar/
    └── shepherd/

/config/www/voiceforge/
└── sprites/               # served at /local/voiceforge/sprites/
    └── [symlink or copy of /config/voiceforge/sprites/]

/config/voiceforge/characters/
└── *.yaml                 # user-created character cards (survives updates)

/custom_components/voiceforge/characters/
└── *.yaml                 # bundled founding four (read-only, restored on update)
```

### Memory JSON Schema

```json
{
  "character_id": "aria",
  "last_updated": "ISO-8601",
  "entries": [
    {
      "id": "mem_001",
      "category": "preferences|schedule|household|events",
      "fact": "string",
      "confidence": "high|medium|low",
      "observed": "ISO-8601",
      "last_referenced": "ISO-8601"
    }
  ]
}
```

### Message JSON Schema

```json
{
  "messages": [
    {
      "id": "msg_001",
      "type": "event|personal",
      "to": "household_member_name or 'all'",
      "from": "character_id",
      "body": "string",
      "ts": "ISO-8601",
      "read": false,
      "announced": false,
      "trigger_type": "late_night_door_open|morning_summary|..."
    }
  ],
  "rate_limits": {
    "late_night_door_open": "ISO-8601",
    "morning_summary": "ISO-8601"
  }
}
```

---

# Architectural Principles

1. **Safety first, always** — `_check_emergency()` runs before any other logic in `async_process()`. No character, no config, no user setting can bypass it.

2. **LLM calls are always async** — `llm_client.complete()` uses `AsyncOpenAI`. Never call a synchronous HTTP client from `async_process()`. Never block the HA event loop.

3. **File I/O is always in executor** — All JSON reads/writes use `asyncio.get_running_loop().run_in_executor(None, ...)`. SD card I/O on Pi 4 can take 10-50ms — enough to block HA.

4. **Memory is enhancement, not requirement** — If `memory_manager` fails at any point, log a warning and continue. The conversation still returns. Characters work without memory.

5. **Character cards cannot touch the safety layer** — The immutable safety rules are appended by `template_engine.py` after rendering all character card content. No card field can override, append to, or remove them.

6. **Template injection is prevented** — Character card text fields are sanitized before any rendering. Jinja2 syntax from community cards cannot reach HA state. Only `template_engine.py` reads HA state.

7. **voluptuous for schema validation** — Not Pydantic. HA bundles voluptuous; Pydantic versioning has caused HACS integration failures across HA releases.

8. **Single active character per integration (v1)** — One `active_character_id` shared across all users. Character switching is immediate. Per-satellite character assignment is v2.

9. **Sprite generation never blocks conversation** — ComfyUI calls are offline-only. `sprite_manager.py` never calls `comfyui_client.py` during a live conversation.

10. **Extraction lock prevents duplicate writes** — `memory_manager.py` holds one `asyncio.Lock` per `character_id`. If extraction is in-flight, new extraction requests are dropped (not queued). `memory_manager` also owns the N-turn counter — `conversation.py` calls `async_extract()` on every turn; the manager gates actual extraction to every N turns internally.

11. **Message manager also holds a write lock** — `message_manager.py` holds one `asyncio.Lock` (single shared lock, not per-character). Two simultaneous event triggers (e.g., `morning_summary` + `late_night_door_open`) must not race on `messages.json`. Same pattern as `memory_manager`.

12. **Session history is per-conversation, not global** — `VoiceForgeConversationAgent` stores `self._histories: dict[str, list]` keyed by `conversation_id` from `ConversationInput`. Max 10 turns per `conversation_id`. Sessions idle >30 min are pruned.

13. **Type B message scheduler uses HA time helpers** — `async_setup_entry()` registers `async_track_point_in_time()` callbacks for configured `wake_time` and `school_return_time`. Each callback re-registers itself for the next day. `async_unload_entry()` cancels subscriptions.

14. **Token budget uses tiktoken** — `template_engine.py` uses `tiktoken` (`cl100k_base` encoding) to count tokens before sending. Target: <2200 tokens (built for RTX 3080/Ollama — budget reflects character fidelity, not minimal hardware). Truncation priority: safety layer (never) → identity → live state → memory → speech rules → examples → lore.

15. **TDD always** — Every function has a test written before the implementation. Watch the test fail first. No production code without a failing test.

---

# AI Assistant Responsibilities

- Follow this architecture when adding new code
- **Write the test first.** Every new function/method needs a failing test before implementation.
- Every LLM call must be async (via `llm_client.complete()` — never call Ollama directly)
- Every file read/write must use `run_in_executor`
- Safety classifier runs first in `async_process()` — never reorder
- Character card text fields are sanitized before any rendering
- Use voluptuous for new schema validation, not Pydantic
- Memory failures must log and continue — never raise
- Check `AI_TASKS.md` for current task status before starting work
