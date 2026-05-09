"""Validate all four character cards load without errors."""

from pathlib import Path
import sys

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
