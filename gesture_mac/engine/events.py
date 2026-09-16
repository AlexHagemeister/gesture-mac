"""What the engine emits. Consumers (the mapper, the HUD) subscribe to these
and never see landmarks unless they ask for the frame itself.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Literal

from ..capture.types import HandKey
from ..gestures.base import Phase

FlickDirection = Literal["left", "right", "up", "down"]
Axis = Literal["x", "y", "angle", "scale"]


@dataclass(slots=True)
class AxisValues:
    x: float = 0.0
    y: float = 0.0
    angle: float = 0.0
    scale: float = 0.0

    def get(self, axis: Axis) -> float:
        return getattr(self, axis)


@dataclass(slots=True)
class GestureEvent:
    gesture_id: str
    hand: HandKey
    """"left" | "right" for one-hand gestures, "both" for two-hand ones."""
    phase: Phase
    t: float
    score: float
    direction: FlickDirection | None = None
    """Set when phase is "flick"."""


@dataclass(slots=True)
class DeltaEvent:
    """Emitted every frame while a continuous gesture is engaged. All axes are
    in user space: x grows to the user's right, y grows upward, angle grows
    counter-clockwise as the user sees it in the mirror."""

    gesture_id: str
    hand: HandKey
    t: float
    delta: AxisValues
    """Offset from the engage origin. x, y in hand-size units; angle in turns
    (1 = full rotation); scale as log2 of the size ratio (1 = doubled)."""
    step: AxisValues
    """Change since the previous delta event, same units."""
    abs: AxisValues
    """Absolute readings for clutch-free control: x, y in 0..1 across the
    frame (user space); angle in turns 0..1; scale as the raw size."""
    raw: tuple[float, float] = (0.0, 0.0)
    """Current anchor in normalized image coords, unfiltered, for HUDs."""
    filtered: tuple[float, float] = (0.0, 0.0)


class Emitter:
    """Minimal typed-by-name emitter, so the engine has no event dependency."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable]] = defaultdict(list)

    def on(self, kind: str, fn: Callable) -> Callable[[], None]:
        self._listeners[kind].append(fn)
        return lambda: self._listeners[kind].remove(fn)

    def emit(self, kind: str, event: object) -> None:
        for fn in list(self._listeners[kind]):
            fn(event)
