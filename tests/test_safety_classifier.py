"""
Two-stage emergency classifier tests.

Stage 1 — six unambiguous phrases that ALWAYS fire.
Stage 2 — ambiguous phrases that fire ONLY when no innocent context word
           follows the trigger (e.g. "help me find my shoes" must NOT fire).
"""

import pytest

from custom_components.voiceforge.safety_classifier import check_emergency


# ---------------------------------------------------------------------------
# Stage 1 — high-confidence phrases (always fire)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "call 911",
    "please call 911 right now",
    "i want to die",
    "I want to die",                    # case insensitive
    "someone is hurting me",
    "there's a fire in the kitchen",
    "i can't breathe",
    "I'm going to hurt myself",
])
def test_stage1_high_confidence_phrases_always_fire(text):
    assert check_emergency(text) is True


# ---------------------------------------------------------------------------
# Stage 2 — ambiguous phrases WITHOUT innocent context (must fire)
# ---------------------------------------------------------------------------

def test_help_me_alone_fires():
    assert check_emergency("help me") is True


def test_im_scared_alone_fires():
    assert check_emergency("i'm scared") is True


def test_im_hurt_alone_fires():
    assert check_emergency("i'm hurt") is True


def test_emergency_alone_fires():
    assert check_emergency("emergency") is True


# ---------------------------------------------------------------------------
# Stage 2 — ambiguous phrases WITH innocent context (must NOT fire)
# ---------------------------------------------------------------------------

def test_help_me_find_my_shoes_does_not_fire():
    assert check_emergency("help me find my shoes") is False


def test_im_scared_the_movie_does_not_fire():
    assert check_emergency("i'm scared the movie will be too long") is False


def test_help_me_watch_a_show_does_not_fire():
    assert check_emergency("help me watch a show") is False


def test_help_me_with_homework_does_not_fire():
    assert check_emergency("help me with my homework") is False
