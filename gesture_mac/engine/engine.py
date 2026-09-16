"""Runs every registered gesture against the tracked hands, each frame, and
emits gesture and delta events. One state-machine instance per gesture per
hand (or per pair for two-hand gestures). Hands are identified by
handedness: if a frame contains two hands with the same label (a second
person), the lower-confidence one is ignored.

Mirrors src/engine/GestureEngine.ts in gesture-template.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..capture.types import Frame, Hand, HandKey, HandPair
from ..gestures.base import ContinuousGesture, Gesture, GestureInstance
from ..gestures.geometry import Pose, wrap_angle
from .events import AxisValues, DeltaEvent, Emitter, FlickDirection, GestureEvent
from .filters import OneEuro, OneEuro2D

TAU = math.pi * 2


@dataclass(slots=True)
class _Drag:
    origin: Pose
    angle_acc: float
    last_angle: float
    start_t: float
    filter: OneEuro2D
    angle_filter: OneEuro
    scale_filter: OneEuro
    last: AxisValues


@dataclass(slots=True)
class _Slot:
    inst: GestureInstance
    drag: _Drag | None = None


class GestureEngine(Emitter):
    """Feed Frames with update(); subscribe with on("gesture", fn),
    on("delta", fn), on("frame", fn)."""

    def __init__(
        self,
        gestures: list[Gesture],
        *,
        mirrored: bool = True,
        flick_distance: float = 0.6,
        flick_max_ms: float = 500,
        filter_opts: dict[str, float] | None = None,
    ) -> None:
        super().__init__()
        self.gestures = gestures
        # The video is a selfie view, so image-right is the user's left.
        # mirrored=True flips axes into user space once, here.
        self._mirror = -1 if mirrored else 1
        self.mirrored = mirrored
        """Whether a raw anchor's image x reads right to left for the user
        (the mapper's pointer needs to undo it without a filter)."""
        self._flick_distance = flick_distance
        self._flick_max_ms = flick_max_ms
        self._filter_opts = filter_opts or {}
        self._slots: dict[tuple[str, HandKey], _Slot] = {}
        for g in gestures:
            for h in self.hands_for(g):
                self._slots[(g.id, h)] = _Slot(g.new_instance())

    @staticmethod
    def hands_for(g: Gesture) -> list[HandKey]:
        """Which hand keys a gesture runs on."""
        return ["both"] if g.bimanual else ["left", "right"]

    def get_gesture(self, gesture_id: str) -> Gesture | None:
        return next((g for g in self.gestures if g.id == gesture_id), None)

    def get_state(self, gesture_id: str, hand: HandKey) -> GestureInstance | None:
        slot = self._slots.get((gesture_id, hand))
        return slot.inst if slot else None

    def is_engaged(self, gesture_id: str, hand: str) -> bool:
        """Whether a gesture is engaged on a hand key ("either" matches any)."""
        keys: list[HandKey] = ["left", "right", "both"] if hand == "either" else [hand]  # type: ignore[list-item]
        return any((st := self.get_state(gesture_id, k)) is not None and st.engaged for k in keys)

    def update(self, frame: Frame) -> None:
        """Feed one frame. Emits events synchronously."""
        by_hand = _pick_hands(frame.hands)
        pair = HandPair(by_hand["left"], by_hand["right"]) if "left" in by_hand and "right" in by_hand else None

        for g in self.gestures:
            for h in self.hands_for(g):
                slot = self._slots[(g.id, h)]
                inp = pair if h == "both" else by_hand.get(h)
                phases = g.step(slot.inst, inp, frame.t)
                cont = isinstance(g, ContinuousGesture)

                for phase in phases:
                    self.emit("gesture", GestureEvent(g.id, h, phase, frame.t, slot.inst.last_score))
                    if cont:
                        if phase == "engage" and inp is not None:
                            slot.drag = self._start_drag(g, inp, frame.t)
                        if phase == "release" and slot.drag is not None:
                            direction = self._flick_of(slot.drag, frame.t)
                            if direction:
                                self.emit(
                                    "gesture",
                                    GestureEvent(g.id, h, "flick", frame.t, slot.inst.last_score, direction),
                                )
                            slot.drag = None

                if slot.drag is not None and inp is not None and cont and slot.inst.engaged:
                    self.emit("delta", self._step_drag(g, slot.drag, inp, h, frame.t))
        self.emit("frame", frame)

    def _start_drag(self, g: ContinuousGesture, inp, t: float) -> _Drag:
        pose = g.anchor(inp)
        f = OneEuro2D(**self._filter_opts)
        af = OneEuro(**self._filter_opts)
        sf = OneEuro(**self._filter_opts)
        x, y = f.filter(pose.x, pose.y, t)
        origin = Pose(x, y, af.filter(pose.angle, t), sf.filter(pose.scale, t))
        return _Drag(origin, 0.0, origin.angle, t, f, af, sf, AxisValues())

    def _step_drag(self, g: ContinuousGesture, drag: _Drag, inp, h: HandKey, t: float) -> DeltaEvent:
        raw = g.anchor(inp)
        x, y = drag.filter.filter(raw.x, raw.y, t)
        angle = drag.angle_filter.filter(raw.angle, t)
        scale = drag.scale_filter.filter(raw.scale, t)
        drag.angle_acc += wrap_angle(angle - drag.last_angle)
        drag.last_angle = angle

        unit = drag.origin.scale if drag.origin.scale > 0 else 1.0
        m = self._mirror
        delta = AxisValues(
            x=(m * (x - drag.origin.x)) / unit,
            y=-(y - drag.origin.y) / unit,
            angle=(m * drag.angle_acc) / TAU,
            scale=math.log2(max(scale, 1e-6) / max(drag.origin.scale, 1e-6)),
        )
        step = AxisValues(
            delta.x - drag.last.x, delta.y - drag.last.y, delta.angle - drag.last.angle, delta.scale - drag.last.scale
        )
        abs_ = AxisValues(
            x=1 - x if m == -1 else x,
            y=1 - y,
            angle=(((m * angle) / TAU) % 1 + 1) % 1,
            scale=scale,
        )
        drag.last = delta
        return DeltaEvent(g.id, h, t, delta, step, abs_, (raw.x, raw.y), (x, y))

    def _flick_of(self, drag: _Drag, t: float) -> FlickDirection | None:
        if t - drag.start_t > self._flick_max_ms:
            return None
        x, y = drag.last.x, drag.last.y
        if max(abs(x), abs(y)) < self._flick_distance:
            return None
        if abs(x) >= abs(y):
            return "right" if x > 0 else "left"
        return "up" if y > 0 else "down"


def _pick_hands(hands: list[Hand]) -> dict[str, Hand]:
    """One hand per label; on a collision keep the higher handedness score."""
    out: dict[str, Hand] = {}
    for hand in hands:
        cur = out.get(hand.handedness)
        if cur is None or hand.handedness_score > cur.handedness_score:
            out[hand.handedness] = hand
    return out
