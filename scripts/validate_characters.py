"""Validate all four character cards load without errors."""

from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock

# Stub HA so the voiceforge package __init__.py can be imported without
# homeassistant installed (CI environment, dev machines, etc.)
_mock = MagicMock()
_mock.async_register_panel = AsyncMock()
for _mod in (
    "homeassistant", "homeassistant.core", "homeassistant.config_entries",
    "homeassistant.components", "homeassistant.components.conversation",
    "homeassistant.components.frontend", "homeassistant.components.panel_custom",
    "homeassistant.components.websocket_api",
    "homeassistant.helpers", "homeassistant.helpers.intent",
):
    sys.modules.setdefault(_mod, _mock)

sys.path.insert(0, str(Path(__file__).parent.parent))

from custom_components.voiceforge.character_manager import CharacterManager

mgr = CharacterManager("custom_components/voiceforge/characters")
mgr.load_all()

if not mgr._library:
    print("ERROR: no cards loaded")
    sys.exit(1)

for cid, card in sorted(mgr._library.items()):
    turns = card.memory["summarize_after_turns"]
    max_m = card.memory["max_memory_entries"]
    ex = len(card.examples)
    gr = len(card.guardrail_response_text)
    print(f"  {cid:12s}  name={card.name:10s}  examples={ex}  memory={turns}T/{max_m}max  guardrail={gr}chars")

print(f"\n{len(mgr._library)}/4 cards loaded OK")
