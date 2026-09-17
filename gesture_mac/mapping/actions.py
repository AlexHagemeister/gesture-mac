"""Action kinds: what a binding can do on the Mac. These are plain data.
The output package knows how to perform each one.

JSON shape (the "action" field of a control of kind "action"):

    {"type": "hold-key",  "key": "right-option"}
    {"type": "press-key", "key": "cmd+shift+4"}
    {"type": "scroll",    "axis": "y", "sensitivity": 40}
    {"type": "click",     "button": "left", "count": 1}
    {"type": "pointer",   "gain": 2.0, "offsetX": 0.0, "offsetY": 0.0}

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


@dataclass(frozen=True, slots=True)
class Click:
    """Mouse click at the cursor's current position, once, on the binding's
    trigger. count 2 is a double-click. Moving the cursor is the pointer
    slices' job (issues #8 to #10); this only proves the mouse-event path."""

    button: Literal["left", "right", "middle"] = "left"
    count: int = 1
    type: Literal["click"] = "click"


@dataclass(frozen=True, slots=True)
class Pointer:
    """Cursor driven by a continuous gesture's anchor. The binding's mode
    field picks the feel; gain means the same in both: screen widths per
    camera-frame width of finger travel. Absolute: a region of the
    mirrored frame, 1/gain of its width and height, centered in the view
    and then moved by (offset_x, offset_y) in fractions of the view, user
    space (0 is centered, positive is to the user's right and up), maps
    to the whole main display; region() slides it inward so it never
    leaves the frame. Relative: the cursor moves from wherever it is by
    the anchor's travel times gain, and the offset is unused. Both follow
    the engine's One Euro filtered anchor (issues #9, #10, #20)."""

    gain: float = 2.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    type: Literal["pointer"] = "pointer"

    def region(self) -> tuple[float, float, float, float]:
        """(left, top, right, bottom) of the absolute-mode region in the
        mirrored view, fractions from the top left. A gain below 1 would
        need more than the frame, so it acts as 1."""
        half = 0.5 / max(self.gain, 1.0)
        cx = min(max(0.5 + self.offset_x, half), 1 - half)
        cy = min(max(0.5 - self.offset_y, half), 1 - half)
        return (cx - half, cy - half, cx + half, cy + half)

Action = Union[HoldKey, PressKey, Scroll, Click, Pointer]


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
    if kind == "click":
        button = d.get("button", "left")
        if button not in ("left", "right", "middle"):
            raise ValueError(f"unknown mouse button: {button!r}")
        count = int(d.get("count", 1))
        if count not in (1, 2):
            raise ValueError(f"click count must be 1 or 2, not {count}")
        return Click(button=button, count=count)
    if kind == "pointer":
        if any(k in d for k in ("left", "top", "right", "bottom")):
            p = _pointer_from_edges(d)
        elif "centerX" in d or "centerY" in d:
            # Issue #20's first round stored the center as fractions from
            # the top left.
            p = Pointer(
                gain=float(d.get("gain", 2.0)),
                offset_x=float(d.get("centerX", 0.5)) - 0.5,
                offset_y=0.5 - float(d.get("centerY", 0.5)),
            )
        else:
            p = Pointer(
                gain=float(d.get("gain", 2.0)),
                offset_x=float(d.get("offsetX", 0.0)),
                offset_y=float(d.get("offsetY", 0.0)),
            )
        if not p.gain > 0:
            raise ValueError(f"pointer gain must be positive, not {p.gain}")
        if not (-0.5 <= p.offset_x <= 0.5 and -0.5 <= p.offset_y <= 0.5):
            raise ValueError("pointer offset must be within -0.5..0.5")
        return p
    raise ValueError(f"unknown action type: {kind!r}")


def _pointer_from_edges(d: dict) -> Pointer:
    """A document from before issue #20 describes the region as four edges.
    The offset is their midpoint's distance from the middle of the view.
    The gain comes from the region's width,
    except when the edges are the untouched old defaults and a gain was
    saved (tuned for relative mode in issue #10), which is then kept."""
    left, top = float(d.get("left", 0.2)), float(d.get("top", 0.2))
    right, bottom = float(d.get("right", 0.8)), float(d.get("bottom", 0.8))
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError("pointer rectangle edges must be within 0..1 with left < right and top < bottom")
    untouched = (left, top, right, bottom) == (0.2, 0.2, 0.8, 0.8)
    gain = float(d["gain"]) if untouched and "gain" in d else 1 / (right - left)
    return Pointer(gain=gain, offset_x=(left + right) / 2 - 0.5, offset_y=0.5 - (top + bottom) / 2)


def action_to_json(a: Action) -> dict:
    if isinstance(a, (HoldKey, PressKey)):
        return {"type": a.type, "key": a.key}
    if isinstance(a, Click):
        return {"type": a.type, "button": a.button, "count": a.count}
    if isinstance(a, Pointer):
        return {"type": a.type, "gain": a.gain, "offsetX": a.offset_x, "offsetY": a.offset_y}
    return {"type": a.type, "axis": a.axis, "sensitivity": a.sensitivity, "invert": a.invert}
