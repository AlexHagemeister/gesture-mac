"""Chord names to macOS virtual keycodes and event flags.

A chord is "+"-joined tokens, case-insensitive: modifiers (cmd, shift,
option/alt, ctrl, fn, with optional left-/right- prefixes) and at most one
base key. Parsing yields the base keycode (or None for a modifier-only
chord), the list of modifier keycodes, and the combined CGEvent flags.

Keycodes are the kVK_* constants from Carbon's Events.h (US layout).
"""
from __future__ import annotations

from dataclasses import dataclass

# Modifier keycodes and their CGEventFlags. The device-specific flag bits
# (NX_DEVICE*KEYMASK) tell listeners which side was pressed; superwhisper's
# "right option" hotkey needs the right-side bit.
_ALT, _SHIFT, _CTRL, _CMD, _FN = 0x80000, 0x20000, 0x40000, 0x100000, 0x800000
_DEV = {
    "left-shift": (56, _SHIFT | 0x02),
    "right-shift": (60, _SHIFT | 0x04),
    "left-ctrl": (59, _CTRL | 0x01),
    "right-ctrl": (62, _CTRL | 0x2000),
    "left-option": (58, _ALT | 0x20),
    "right-option": (61, _ALT | 0x40),
    "left-cmd": (55, _CMD | 0x08),
    "right-cmd": (54, _CMD | 0x10),
    "fn": (63, _FN),
}
_MOD_ALIASES = {
    "shift": "left-shift",
    "ctrl": "left-ctrl",
    "control": "left-ctrl",
    "option": "left-option",
    "alt": "left-option",
    "opt": "left-option",
    "cmd": "left-cmd",
    "command": "left-cmd",
    "meta": "left-cmd",
    "right-alt": "right-option",
    "right-opt": "right-option",
    "right-command": "right-cmd",
    "right-control": "right-ctrl",
    "left-alt": "left-option",
    "left-command": "left-cmd",
    "left-control": "left-ctrl",
}

_BASE: dict[str, int] = {
    **{c: k for c, k in zip("asdfhgzxcv", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25, "7": 26,
    "-": 27, "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35,
    "return": 36, "enter": 36, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42,
    ",": 43, "/": 44, "n": 45, "m": 46, ".": 47, "tab": 48, "space": 49, "`": 50,
    "delete": 51, "backspace": 51, "escape": 53, "esc": 53,
    "f17": 64, "f18": 79, "f19": 80, "f20": 90,
    "f5": 96, "f6": 97, "f7": 98, "f3": 99, "f8": 100, "f9": 101, "f11": 103,
    "f13": 105, "f16": 106, "f14": 107, "f10": 109, "f12": 111, "f15": 113,
    "help": 114, "home": 115, "pageup": 116, "forwarddelete": 117, "f4": 118,
    "end": 119, "f2": 120, "pagedown": 121, "f1": 122, "left": 123, "right": 124,
    "down": 125, "up": 126,
}


@dataclass(frozen=True, slots=True)
class Chord:
    modifiers: tuple[tuple[int, int], ...]
    """(keycode, flags) per modifier, in the order given."""
    base: int | None
    """Keycode of the non-modifier key, or None for a modifier-only chord."""

    @property
    def flags(self) -> int:
        f = 0
        for _, fl in self.modifiers:
            f |= fl
        return f


def parse_chord(text: str) -> Chord:
    mods: list[tuple[int, int]] = []
    base: int | None = None
    for raw in text.split("+"):
        tok = raw.strip().lower()
        if not tok:
            continue
        tok = _MOD_ALIASES.get(tok, tok)
        if tok in _DEV:
            mods.append(_DEV[tok])
        elif tok in _BASE:
            if base is not None:
                raise ValueError(f"chord {text!r} has more than one base key")
            base = _BASE[tok]
        else:
            raise ValueError(f"unknown key token {raw!r} in chord {text!r}")
    if base is None and not mods:
        raise ValueError(f"empty chord {text!r}")
    return Chord(tuple(mods), base)
