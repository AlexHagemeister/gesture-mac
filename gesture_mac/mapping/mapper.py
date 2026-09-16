"""Applies engine events to bindings and asks a Performer to carry out the
resulting actions. The Performer protocol is the seam between this package
and macOS: tests pass a recording fake, the app passes output.MacPerformer.
"""
from __future__ import annotations

from typing import Protocol

from ..engine.engine import GestureEngine
from ..engine.events import DeltaEvent, GestureEvent
from .actions import HoldKey, PressKey, Scroll
from .bindings import Binding, MappingDocument, Trigger


class Performer(Protocol):
    def key_down(self, chord: str) -> None: ...
    def key_up(self, chord: str) -> None: ...
    def key_press(self, chord: str) -> None: ...
    def scroll(self, dx: float, dy: float) -> None: ...


class Mapper:
    def __init__(self, engine: GestureEngine, doc: MappingDocument, performer: Performer) -> None:
        self.engine = engine
        self.doc = doc
        self.performer = performer
        self.enabled = True
        """When False, events are ignored. Held keys are released on the
        way down so nothing sticks."""
        self._held: set[str] = set()
        """Chords currently held by hold-key bindings, keyed by binding id."""
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
        for b in self._matching(e.gesture_id, e.hand):
            c = self.doc.control(b.control_id)
            if c is None or c.action is None:
                continue
            a = c.action
            if isinstance(a, HoldKey):
                # A held key follows the gesture's lifetime regardless of the
                # binding's trigger. Release always goes through so a key
                # never sticks after the app is disabled mid-pinch.
                if e.phase == "engage" and self.enabled and a.key not in self._held:
                    self._held.add(a.key)
                    self.performer.key_down(a.key)
                elif e.phase == "release" and a.key in self._held:
                    self._held.discard(a.key)
                    self.performer.key_up(a.key)
            elif isinstance(a, PressKey):
                if self.enabled and b.trigger == fired:
                    self.performer.key_press(a.key)

    def _on_delta(self, e: DeltaEvent) -> None:
        if not self.enabled:
            return
        for b in self._matching(e.gesture_id, e.hand):
            c = self.doc.control(b.control_id)
            if c is None or not isinstance(c.action, Scroll):
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
