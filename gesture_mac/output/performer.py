"""CGEvent-based performer: keys, scroll wheel, mouse clicks, and cursor
moves via Quartz.

Verified 2026-09-15: a synthesized right-option (flagsChanged with the
Alternate flag plus the right-side device bit) toggles superwhisper, and a
second one closes it.

Requires the running process (the terminal or the packaged app) to have
Accessibility permission, or events are silently dropped.
"""
from __future__ import annotations

import ctypes

import time

import Quartz as Q

from .keys import Chord, parse_chord

MOUSE_BUTTONS: dict[str, tuple[int, int, int]] = {
    "left": (Q.kCGMouseButtonLeft, Q.kCGEventLeftMouseDown, Q.kCGEventLeftMouseUp),
    "right": (Q.kCGMouseButtonRight, Q.kCGEventRightMouseDown, Q.kCGEventRightMouseUp),
    "middle": (Q.kCGMouseButtonCenter, Q.kCGEventOtherMouseDown, Q.kCGEventOtherMouseUp),
}


class MacPerformer:
    def __init__(self, press_hold_s: float = 0.03) -> None:
        self._src = Q.CGEventSourceCreate(Q.kCGEventSourceStateHIDSystemState)
        self._press_hold_s = press_hold_s
        self._chords: dict[str, Chord] = {}

    def _chord(self, text: str) -> Chord:
        c = self._chords.get(text)
        if c is None:
            c = self._chords[text] = parse_chord(text)
        return c

    # ---- modifiers -------------------------------------------------------

    def _post_modifier(self, keycode: int, flags_after: int) -> None:
        ev = Q.CGEventCreateKeyboardEvent(self._src, keycode, True)
        Q.CGEventSetType(ev, Q.kCGEventFlagsChanged)
        Q.CGEventSetFlags(ev, flags_after)
        Q.CGEventPost(Q.kCGHIDEventTap, ev)

    def _modifiers_down(self, chord: Chord) -> int:
        acc = 0
        for keycode, fl in chord.modifiers:
            acc |= fl
            self._post_modifier(keycode, acc)
        return acc

    def _modifiers_up(self, chord: Chord) -> None:
        acc = chord.flags
        for keycode, fl in reversed(chord.modifiers):
            acc &= ~fl
            self._post_modifier(keycode, acc)

    # ---- Performer protocol ---------------------------------------------

    def key_down(self, text: str) -> None:
        chord = self._chord(text)
        flags = self._modifiers_down(chord)
        if chord.base is not None:
            ev = Q.CGEventCreateKeyboardEvent(self._src, chord.base, True)
            Q.CGEventSetFlags(ev, flags)
            Q.CGEventPost(Q.kCGHIDEventTap, ev)

    def key_up(self, text: str) -> None:
        chord = self._chord(text)
        if chord.base is not None:
            ev = Q.CGEventCreateKeyboardEvent(self._src, chord.base, False)
            Q.CGEventSetFlags(ev, chord.flags)
            Q.CGEventPost(Q.kCGHIDEventTap, ev)
        self._modifiers_up(chord)

    def key_press(self, text: str) -> None:
        self.key_down(text)
        time.sleep(self._press_hold_s)
        self.key_up(text)

    def scroll(self, dx: float, dy: float) -> None:
        # Pixel units so fractional per-frame steps still move something.
        ev = Q.CGEventCreateScrollWheelEvent(self._src, Q.kCGScrollEventUnitPixel, 2, int(round(dy)), int(round(dx)))
        Q.CGEventPost(Q.kCGHIDEventTap, ev)

    def move_to(self, fx: float, fy: float) -> None:
        # A mouse-moved event rather than a warp, so apps see hover too.
        # Main display only (issue #9's scope).
        b = Q.CGDisplayBounds(Q.CGMainDisplayID())
        where = (b.origin.x + fx * b.size.width, b.origin.y + fy * b.size.height)
        ev = Q.CGEventCreateMouseEvent(self._src, Q.kCGEventMouseMoved, where, Q.kCGMouseButtonLeft)
        Q.CGEventPost(Q.kCGHIDEventTap, ev)

    def move_by(self, dx: float, dy: float) -> None:
        # From the cursor's live position, so a relative binding continues
        # from wherever the mouse or another binding last left it.
        b = Q.CGDisplayBounds(Q.CGMainDisplayID())
        here = Q.CGEventGetLocation(Q.CGEventCreate(None))
        x = min(max(here.x + dx * b.size.width, b.origin.x), b.origin.x + b.size.width - 1)
        y = min(max(here.y + dy * b.size.height, b.origin.y), b.origin.y + b.size.height - 1)
        ev = Q.CGEventCreateMouseEvent(self._src, Q.kCGEventMouseMoved, (x, y), Q.kCGMouseButtonLeft)
        Q.CGEventPost(Q.kCGHIDEventTap, ev)

    def click(self, button: str, count: int) -> None:
        """Click where the cursor already is. The click-state field counts
        up across the presses of a multi-click so the target sees a real
        double-click rather than two singles."""
        btn, down, up = MOUSE_BUTTONS[button]
        where = Q.CGEventGetLocation(Q.CGEventCreate(None))
        for n in range(1, count + 1):
            for kind in (down, up):
                ev = Q.CGEventCreateMouseEvent(self._src, kind, where, btn)
                Q.CGEventSetIntegerValueField(ev, Q.kCGMouseEventClickState, n)
                Q.CGEventPost(Q.kCGHIDEventTap, ev)
                time.sleep(self._press_hold_s)


def accessibility_trusted(prompt: bool = False) -> bool:
    """Whether macOS will deliver the events this performer posts. Without
    the Accessibility grant they are silently dropped, which looks exactly
    like a binding that does nothing. With prompt=True, macOS shows its
    "would like to control this Mac" dialog when the grant is missing
    (the dialog only ever appears on request; posting events never
    triggers it). Re-signing the bundle (a rebuild that changes Info.plist
    or the launcher) changes its code hash and invalidates the grant, so
    the app asks at start and says so."""
    import objc
    from Foundation import NSDictionary

    lib = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
    lib.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
    lib.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
    opts = NSDictionary.dictionaryWithObject_forKey_(bool(prompt), "AXTrustedCheckOptionPrompt")
    return bool(lib.AXIsProcessTrustedWithOptions(objc.pyobjc_id(opts)))
