"""The list of gestures the engine knows about. Adding a gesture = write a
class in builtin/ (or anywhere) and add it here."""
from __future__ import annotations

from .base import Gesture
from .builtin.bimanual import DoublePinch, TwoPalms
from .builtin.pinches import IndexPinch, MiddlePinch
from .builtin.poses import Fist, OpenPalm, Point, ThumbsUp


def default_gestures() -> list[Gesture]:
    return [
        IndexPinch(),
        MiddlePinch(),
        OpenPalm(),
        Fist(),
        Point(),
        ThumbsUp(),
        DoublePinch(),
        TwoPalms(),
    ]
