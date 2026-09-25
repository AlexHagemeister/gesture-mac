"""Applies engine events to bindings and asks a Performer to carry out the
resulting actions. The Performer protocol is the seam between this package
and macOS: tests pass a recording fake, the app passes output.MacPerformer.
on_fire hears the label of each control a binding sets off, for the
command toast.
"""
from __future__ import annotations

from typing import Callable, Protocol

from ..engine.engine import GestureEngine
from ..engine.events import DeltaEvent, GestureEvent
from .actions import Click, HoldKey, Pointer, PressKey, Scroll
from .bindings import Binding, MappingDocument, Trigger


class Performer(Protocol):
    def key_down(self, chord: str) -> None: ...
    def key_up(self, chord: str) -> None: ...
    def key_press(self, chord: str) -> None: ...
    def scroll(self, dx: float, dy: float) -> None: ...
    def click(self, button: str, count: int) -> None: ...
    def move_to(self, fx: float, fy: float) -> None:
        """Put the cursor at a fraction of the main display, 0..1 from its
        top left."""
        ...
    def move_by(self, dx: float, dy: float) -> None:
        """Move the cursor from where it is by a fraction of the main
        display's width and height, stopping at its edges."""
        ...


class Mapper:
    def __init__(
        self,
        engine: GestureEngine,
        doc: MappingDocument,
        performer: Performer,
        on_fire: Callable[[str], None] | None = None,
    ) -> None:
        self.engine = engine
        self.doc = doc
        self.performer = performer
        self.on_fire = on_fire or (lambda label: None)
        """Called with the control's label each time a binding acts: a key
        goes down or is pressed, a click is made, or a continuous action
        engages. Runs on the engine's thread."""
        self.enabled = True
        """When False, events are ignored. Held keys are released on the
        way down so nothing sticks."""
        self._held: set[str] = set()
        """Chords currently held by hold-key bindings, keyed by binding id."""
        self._last_raw: dict[tuple[str, str], tuple[float, float]] = {}
        """Relative pointing: the previous raw anchor per (gesture, hand)
        while engaged, so each event moves the cursor by the change."""
        self._unsub = [engine.on("gesture", self._on_gesture), engine.on("delta", self._on_delta)]

    def set_enabled(self, on: bool) -> None:
        self.enabled = on
        if not on:
            self.release_all()

    def release_all(self) -> None:
        """Key-up everything still held (disable, quit, reload)."""
        for chord in list(self._held):
            self.performer.key_up(chord)
        self._held.clear()
        self._last_raw.clear()

    def load(self, doc: MappingDocument) -> None:
        self.release_all()
        self.doc = doc

    def dispose(self) -> None:
        self.release_all()
        for u in self._unsub:
            u()

    def _matching(self, gesture_id: str, hand: str) -> list[Binding]:
        return [
            b
            for b in self.doc.bindings
            if b.gesture_id == gesture_id
            and (b.hand == hand or (b.hand == "either" and hand != "both"))
            and (b.while_ is None or self.engine.is_engaged(b.while_.gesture_id, b.while_.hand))
        ]

    def _on_gesture(self, e: GestureEvent) -> None:
        fired: Trigger = f"flick-{e.direction or 'up'}" if e.phase == "flick" else e.phase  # type: ignore[assignment]
        if e.phase == "release":
            self._last_raw.pop((e.gesture_id, e.hand), None)
        for b in self._matching(e.gesture_id, e.hand):
            c = self.doc.control(b.control_id)
            if c is None or c.action is None:
                continue
            a = c.action
            if isinstance(a, HoldKey):
                # A held key goes down on engage (default) or, with trigger
                # "hold", only once the gesture has been held for hold_ms, so
                # a passing pose cannot fire it. Either way it stays down
                # until the gesture releases, and release always goes through
                # so a key never sticks after the app is disabled mid-pinch.
                down_on = "hold" if b.trigger == "hold" else "engage"
                if e.phase == down_on and self.enabled and a.key not in self._held:
                    self._held.add(a.key)
                    self.performer.key_down(a.key)
                    self.on_fire(c.label)
                elif e.phase == "release" and a.key in self._held:
                    self._held.discard(a.key)
                    self.performer.key_up(a.key)
            elif isinstance(a, PressKey):
                if self.enabled and b.trigger == fired:
                    self.performer.key_press(a.key)
                    self.on_fire(c.label)
            elif isinstance(a, Click):
                # Each phase fires once per engage in the engine, so one
                # pinch is one click and a held pinch never repeats.
                if self.enabled and b.trigger == fired:
                    self.performer.click(a.button, a.count)
                    self.on_fire(c.label)
            elif isinstance(a, (Pointer, Scroll)):
                # These act on every delta event, so they are named once,
                # when the gesture engages, not per frame.
                if self.enabled and e.phase == "engage":
                    self.on_fire(c.label)

    def _on_delta(self, e: DeltaEvent) -> None:
        if not self.enabled:
            return
        for b in self._matching(e.gesture_id, e.hand):
            c = self.doc.control(b.control_id)
            if c is None:
                continue
            if isinstance(c.action, Pointer):
                if b.mode == "absolute":
                    self._point_absolute(c.action, e)
                else:
                    self._point_relative(c.action, e)
                continue
            if not isinstance(c.action, Scroll):
                continue
            a = c.action
            sign = -1 if (a.invert != b.invert) else 1
            amount = e.step.get(a.axis) * a.sensitivity * sign
            if a.axis == "y":
                # Positive y is "hand moved up"; natural scrolling moves the
                # page with the hand, which is a positive wheel delta in Quartz.
                self.performer.scroll(0, amount)
            else:
                self.performer.scroll(amount, 0)

    def _point_absolute(self, a: Pointer, e: DeltaEvent) -> None:
        # The filtered anchor is in image coordinates; user space is the
        # mirror of it, and image y already grows downward like the
        # screen's. Clamp to the rectangle so the cursor reaches the
        # display's edges and stops there.
        x, y = e.filtered
        if self.engine.mirrored:
            x = 1 - x
        left, top, right, bottom = a.region()
        fx = (x - left) / (right - left)
        fy = (y - top) / (bottom - top)
        self.performer.move_to(min(max(fx, 0.0), 1.0), min(max(fy, 0.0), 1.0))

    def _point_relative(self, a: Pointer, e: DeltaEvent) -> None:
        # Trackpad feel: the first event after engage only records where
        # the finger is, so engaging never jumps the cursor. Each later
        # event moves it by the anchor's travel since the previous one,
        # in user space, scaled by the gain. The engine's One Euro
        # filtered anchor rather than the raw one: the raw baseline was
        # felt in round 1 ("a little jittery") and smoothing is now wanted.
        x, y = e.filtered
        if self.engine.mirrored:
            x = 1 - x
        key = (e.gesture_id, e.hand)
        last = self._last_raw.get(key)
        self._last_raw[key] = (x, y)
        if last is None:
            return
        dx, dy = (x - last[0]) * a.gain, (y - last[1]) * a.gain
        if dx or dy:
            self.performer.move_by(dx, dy)
