"""Action kinds: what a binding can do on the Mac. These are plain data.
The output package knows how to perform each one.

JSON shape (the "action" field of a control of kind "action"):

    {"type": "hold-key",  "key": "right-option"}
    {"type": "press-key", "key": "cmd+shift+4"}
    {"type": "scroll",    "axis": "y", "sensitivity": 40}

Key names: a chord of "+"-joined tokens. Modifiers: cmd, shift, option/alt,
ctrl, fn, and the sided forms right-option, left-cmd, etc. Base keys: a
letter, digit, f1..f20, space, return, tab, escape, delete, left/right/up/
down, and the named punctuation in output/keys.py. A chord of modifiers
alone (like "right-option") is legal and is what superwhisper listens for.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union


@dataclass(frozen=True, slots=True)
class HoldKey:
    """Key down on engage, key up on release. The pinch's lifetime becomes
    the key's: a short pinch is a tap, a long pinch is a hold, and the app
    on the other end (superwhisper) does its own tap/hold logic."""

    key: str
    type: Literal["hold-key"] = "hold-key"


@dataclass(frozen=True, slots=True)
class PressKey:
    """Key down then up, once, on the binding's trigger."""

    key: str
    type: Literal["press-key"] = "press-key"


@dataclass(frozen=True, slots=True)
class Scroll:
    """Scroll wheel driven by a continuous axis: each delta step scrolls
    by step * sensitivity lines. Stretch goal; the performer exists."""

    axis: Literal["x", "y"] = "y"
    sensitivity: float = 40.0
    invert: bool = False
    type: Literal["scroll"] = "scroll"


Action = Union[HoldKey, PressKey, Scroll]


def parse_action(d: dict) -> Action:
    kind = d.get("type")
    if kind == "hold-key":
        return HoldKey(key=str(d["key"]))
    if kind == "press-key":
        return PressKey(key=str(d["key"]))
    if kind == "scroll":
        return Scroll(
            axis=d.get("axis", "y"),
            sensitivity=float(d.get("sensitivity", 40.0)),
            invert=bool(d.get("invert", False)),
        )
    raise ValueError(f"unknown action type: {kind!r}")


def action_to_json(a: Action) -> dict:
    if isinstance(a, (HoldKey, PressKey)):
        return {"type": a.type, "key": a.key}
    return {"type": a.type, "axis": a.axis, "sensitivity": a.sensitivity, "invert": a.invert}
