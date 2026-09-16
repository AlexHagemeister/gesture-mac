"""Base classes for gestures. A gesture reads an input (one hand, or a pair
of hands for two-hand gestures) and returns score(): a 0..1 reading of how
strongly the input matches. The base class owns the state machine that
turns noisy scores into clean events:

    idle --(score >= enter)--> candidate --(onset_ms elapsed)--> active
    active --(hold_ms elapsed)--> held
    candidate/active/held --(score <= exit)--> idle  (release if it was active)

Two thresholds (enter above exit) give hysteresis so a jittery score does
not flicker. One GestureInstance exists per gesture per hand (or per pair).

Mirrors src/gestures/Gesture.ts and ContinuousGesture.ts in gesture-template.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Generic, Literal, TypeVar

from ..capture.types import Hand, HandPair
from .geometry import Pose

Phase = Literal["engage", "hold", "release", "flick"]
"""engage/hold/release come from the state machine. flick is emitted by the
engine on release of a continuous gesture that moved fast and far."""

State = Literal["idle", "candidate", "active", "held"]


@dataclass(frozen=True, slots=True)
class GestureThresholds:
    enter: float = 0.8
    """Score at or above which the gesture becomes a candidate."""
    exit: float = 0.6
    """Score at or below which an active gesture releases. Must be < enter."""
    onset_ms: float = 60
    """How long the score must stay above enter before engage fires."""
    hold_ms: float = 500
    """How long after engage before hold fires."""


DEFAULT_THRESHOLDS = GestureThresholds()


@dataclass(slots=True)
class GestureInstance:
    """Per-instance runtime state. Created by the engine."""

    state: State = "idle"
    since: float = 0.0
    last_score: float = 0.0

    @property
    def engaged(self) -> bool:
        return self.state in ("active", "held")


I = TypeVar("I", Hand, HandPair)


class Gesture(Generic[I]):
    """A momentary gesture. Subclasses set id, label, hint and write score()."""

    id: str = ""
    label: str = ""
    hint: str = ""
    continuous: bool = False
    bimanual: bool = False

    def __init__(self, **thresholds: float) -> None:
        self.thresholds = replace(DEFAULT_THRESHOLDS, **thresholds)

    def score(self, inp: I) -> float:  # pragma: no cover - abstract
        """How strongly this input matches the gesture right now, 0..1."""
        raise NotImplementedError

    def new_instance(self) -> GestureInstance:
        return GestureInstance()

    def step(self, inst: GestureInstance, inp: I | None, t: float) -> list[Phase]:
        """Advance the state machine one tick. Returns the phases that fired
        this tick (usually zero or one). Called by the engine; not overridden."""
        fired: list[Phase] = []
        score = self.score(inp) if inp is not None else 0.0
        inst.last_score = score
        th = self.thresholds

        if inst.state == "idle":
            if score >= th.enter:
                inst.state = "candidate"
                inst.since = t
        elif inst.state == "candidate":
            if score <= th.exit:
                inst.state = "idle"
            elif t - inst.since >= th.onset_ms:
                inst.state = "active"
                inst.since = t
                fired.append("engage")
                if th.hold_ms <= 0:
                    inst.state = "held"
                    fired.append("hold")
        elif inst.state == "active":
            if score <= th.exit:
                inst.state = "idle"
                fired.append("release")
            elif t - inst.since >= th.hold_ms:
                inst.state = "held"
                fired.append("hold")
        elif inst.state == "held":
            if score <= th.exit:
                inst.state = "idle"
                fired.append("release")
        return fired


class ContinuousGesture(Gesture[I]):
    """A gesture that also reports motion while engaged. Subclasses add
    anchor(): the pose whose change drives the axes. On engage the engine
    records the pose; every later frame it emits deltas from that origin:
    x and y in hand-size units, angle in turns, scale as a log2 ratio.
    Release and re-engage resets the origin, like lifting a finger."""

    continuous = True

    def anchor(self, inp: I) -> Pose:  # pragma: no cover - abstract
        """The pose tracked while engaged, in normalized image coordinates."""
        raise NotImplementedError


class BimanualGesture(Gesture[HandPair]):
    """A gesture that reads both hands. Scores 0 unless both are present."""

    bimanual = True


class BimanualContinuousGesture(ContinuousGesture[HandPair]):
    bimanual = True
