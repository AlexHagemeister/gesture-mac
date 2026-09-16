"""Small geometry helpers over hand landmarks. Everything is in normalized
image coordinates unless it says otherwise. Gesture authors compose these
to write score() and anchor() functions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..capture.types import LM, Hand, Landmark


@dataclass(slots=True)
class Point:
    x: float
    y: float


@dataclass(slots=True)
class Pose:
    """What a continuous gesture tracks: a position, an orientation, and a
    size. The engine turns changes in each into axes (x, y, angle, scale).
    angle is radians; scale is any positive length (only ratios are used)."""

    x: float
    y: float
    angle: float
    scale: float


def dist(a: Point | Landmark, b: Point | Landmark) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def midpoint(a: Point | Landmark, b: Point | Landmark) -> Point:
    return Point((a.x + b.x) / 2, (a.y + b.y) / 2)


def angle_of(a: Point | Landmark, b: Point | Landmark) -> float:
    """Angle of the vector from a to b, radians, image coordinates."""
    return math.atan2(b.y - a.y, b.x - a.x)


def wrap_angle(a: float) -> float:
    """Wrap an angle difference into (-pi, pi]."""
    return math.atan2(math.sin(a), math.cos(a))


def hand_size(hand: Hand) -> float:
    """A distance-from-camera invariant hand size: wrist to middle knuckle.
    Use it to normalize any other distance on the hand."""
    return dist(hand.landmarks[LM.WRIST], hand.landmarks[LM.MIDDLE_MCP])


def hand_angle(hand: Hand) -> float:
    """Orientation of the hand: angle of wrist -> middle knuckle."""
    return angle_of(hand.landmarks[LM.WRIST], hand.landmarks[LM.MIDDLE_MCP])


def norm_dist(hand: Hand, a: int, b: int) -> float:
    """Distance between two landmarks as a fraction of hand size."""
    return dist(hand.landmarks[a], hand.landmarks[b]) / hand_size(hand)


def finger_extended(hand: Hand, tip: int) -> bool:
    """Whether a finger is extended: its tip is farther from the wrist than
    its PIP joint by a margin. Works for index..pinky (pass the TIP index)."""
    wrist = hand.landmarks[LM.WRIST]
    pip = hand.landmarks[tip - 2]
    return dist(hand.landmarks[tip], wrist) > dist(pip, wrist) * 1.1


def thumb_extended(hand: Hand) -> bool:
    """Thumb uses a different test: tip far from the index knuckle."""
    return norm_dist(hand, LM.THUMB_TIP, LM.INDEX_MCP) > 0.9


def closeness(value: float, lo: float, hi: float) -> float:
    """Map a value in [lo, hi] to a score in [1, 0]: 1 at or below lo, 0 at
    or above hi, linear between. For "closer is better" scores."""
    if value <= lo:
        return 1.0
    if value >= hi:
        return 0.0
    return 1 - (value - lo) / (hi - lo)


def hand_pose(hand: Hand, at: Point) -> Pose:
    """A hand's default pose: position at a point, hand orientation, hand size."""
    return Pose(at.x, at.y, hand_angle(hand), hand_size(hand))
