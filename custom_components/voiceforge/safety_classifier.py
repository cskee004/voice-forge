"""Two-stage emergency keyword classifier.

Stage 1 — six unambiguous phrases that always trigger an emergency response.
Stage 2 — ambiguous phrases that trigger only when no innocent context word
           appears after the trigger in the input text.
"""

from __future__ import annotations

# Phrases that are never ambiguous — always escalate.
_STAGE_1: frozenset[str] = frozenset({
    "call 911",
    "i want to die",
    "someone is hurting",
    "i'm going to hurt",
    "im going to hurt",
    "there's a fire",
    "theres a fire",
    "i can't breathe",
    "i cant breathe",
})

# Phrases that could be harmless depending on context.
_STAGE_2: frozenset[str] = frozenset({
    "help me",
    "i'm scared",
    "im scared",
    "i am scared",
    "i'm hurt",
    "im hurt",
    "i am hurt",
    "emergency",
})

# Words that, when they follow a Stage 2 trigger, indicate a normal request.
_INNOCENT_CONTEXT: frozenset[str] = frozenset({
    "find",
    "with",
    "the",
    "do",
    "watch",
    "play",
    "my",
    "a",
    "movie",
    "show",
    "game",
    "book",
    "song",
    "shoes",
    "homework",
})


def check_emergency(text: str) -> bool:
    """Return True if the text signals a genuine emergency.

    Stage 1 phrases fire unconditionally.
    Stage 2 phrases fire only when no innocent context word follows them.
    """
    lower = text.lower()

    for phrase in _STAGE_1:
        if phrase in lower:
            return True

    for phrase in _STAGE_2:
        if phrase in lower:
            idx = lower.index(phrase)
            after = lower[idx + len(phrase):]
            words_after = after.split()
            if not any(w in _INNOCENT_CONTEXT for w in words_after):
                return True

    return False
