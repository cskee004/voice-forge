# CLAUDE.md

## gstack

For all web browsing, use the `/browse` skill from gstack. Never use `mcp__claude-in-chrome__*` tools.

Available gstack skills: `/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/design-consultation`, `/design-shotgun`, `/design-html`, `/review`, `/ship`, `/land-and-deploy`, `/canary`, `/benchmark`, `/browse`, `/connect-chrome`, `/qa`, `/qa-only`, `/design-review`, `/setup-browser-cookies`, `/setup-deploy`, `/retro`, `/investigate`, `/document-release`, `/codex`, `/cso`, `/autoplan`, `/plan-devex-review`, `/devex-review`, `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`, `/learn`

---

## Reference Documents

- `.claude/spec/resources/AI_ARCHITECTURE.md` — system architecture, data flow, storage model, coding principles. Read before writing any code.
- `.claude/spec/resources/AI_TASKS.md` — current task list and phase status. Check before starting any work.
- `.claude/spec/VoiceForge_Spec.md` — full engineering specification v1.4+ with all amendments. Authoritative for behavior, schema, and API shape.
- `.claude/spec/aria.yaml`, `sera.yaml`, `malachar.yaml`, `shepherd.yaml` — founding character cards. Reference for schema and content.

---

## Current Status

See `.claude/spec/resources/AI_TASKS.md` for the authoritative task list and what's next. Do not duplicate status here.

---

## AI Collaboration Rules

- Write idiomatic — small focused functions, clear names, no unnecessary abstractions
- Read relevant files before proposing changes
- Make small, incremental changes — one task at a time
- Modify only files relevant to the current task
- Do not rename or delete files unless explicitly instructed
- Request confirmation before any change that touches multiple parts of the system

---

## Testing

**Always use TDD.** Write the test first. Watch it fail. Write minimal code to pass. No production code without a failing test first.

Framework: `pytest` + `pytest-homeassistant-custom-component`

Run tests:
```bash
pytest tests/ -v
pytest tests/ --cov=custom_components/voiceforge --cov-report=term-missing
```

Test files (one per module):
- `tests/test_character_manager.py` — schema validation, load/switch, missing fields
- `tests/test_template_engine.py` — prompt rendering, token budget truncation, Jinja2 sanitization
- `tests/test_memory_manager.py` — extraction N-turn gate, storage, FIFO eviction, lock skip
- `tests/test_llm_client.py` — OpenAI-compat wrapper, endpoint config
- `tests/test_conversation.py` — full `async_process()` cycle + emergency integration test (LLM never called on emergency input)
- `tests/test_safety_classifier.py` — two-stage keyword classifier, true positives, false positive reduction
- `tests/test_message_manager.py` — Type A/B generation, rate limiting, TTL expiry, deduplication, concurrent write lock
- `tests/test_sprite_manager.py` — 7 state transitions, priority ordering, 60s idle timeout, HA event payload

LLM calls are **always mocked** in tests. Never hit a real endpoint.

---

## Session Stats (run before every commit)

Before every `git commit`, run the session stats script to update the README badges and the stats report:

```bash
# Windows (adjust log path to match your Claude Code install):
python scripts/session_stats.py "C:\Users\chris\.claude\projects\C--code-voice-forge" docs/claude_stats.md --readme README.md

# Pi / Linux:
python scripts/session_stats.py "$HOME/.claude/projects/$(basename $(pwd))" docs/claude_stats.md --readme README.md
```

Then stage the updated files alongside the task commit:
```bash
git add docs/claude_stats.md README.md
```

The script reads Claude Code session logs, generates `docs/claude_stats.md`, and injects live shields.io badges into README.md between the `<!-- CLAUDE_STATS_START -->` and `<!-- CLAUDE_STATS_END -->` markers.

---

## Deployment (Pi / HA)

Copy component to HA and restart:
```bash
cp -r custom_components/voiceforge ~/homeassistant/custom_components/
ha core restart                          # HA supervised
# or: sudo systemctl restart home-assistant@homeassistant
```

View live logs:
```bash
journalctl -fu home-assistant@homeassistant
# or tail directly:
tail -f ~/homeassistant/home-assistant.log
```

---

## Task Management

Tasks are tracked in `.claude/spec/resources/AI_TASKS.md`. Read that file for current status and what's next.

**Commit message format:**
```
type: short description (Task N)
```

Full task lifecycle rules are in AI_TASKS.md.

---

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool.

Key routing rules:
- Product ideas, brainstorming → invoke /office-hours
- Bugs, errors, "why is this broken" → invoke /investigate
- Ship, deploy, create PR → invoke /ship
- QA, test the site → invoke /qa
- Code review, check my diff → invoke /review
- Architecture review → invoke /plan-eng-review
- Design polish → invoke /design-review
