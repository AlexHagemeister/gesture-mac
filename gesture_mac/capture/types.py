"""Core data types shared by every layer. The tracker produces a Frame per
video frame; everything downstream reads Frames and never touches MediaPipe.

Mirrors src/tracking/types.ts in the gesture-template repo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Handedness = Literal["left", "right"]
"""Which of the user's hands this is, from the user's own point of view."""

HandKey = Literal["left", "right", "both"]
"""A gesture's subject: one hand, or both hands together."""

HandSelector = Literal["left", "right", "both", "either"]
"""Which hand(s) a binding applies to."""


@dataclass(slots=True)
class Landmark:
    """A landmark in normalized image coordinates (0..1, origin top-left)."""

    x: float
    y: float
    z: float = 0.0


@dataclass(slots=True)
class Hand:
    """One tracked hand in one frame."""

    handedness: Handedness
    handedness_score: float
    """Model confidence in the handedness label (0..1)."""
    landmarks: list[Landmark]
    """21 landmarks, indexed per MediaPipe's hand model (see LM)."""
    pose_label: str = "None"
    """Built-in classifier label: None, Closed_Fist, Open_Palm, Pointing_Up,
    Thumb_Down, Thumb_Up, Victory, ILoveYou."""
    pose_score: float = 0.0


@dataclass(slots=True)
class HandPair:
    """Both hands, for two-hand gestures."""

    left: Hand
    right: Hand


@dataclass(slots=True)
class Frame:
    """Everything the tracker knows about one video frame."""

    t: float
    """Milliseconds, monotonic."""
    hands: list[Hand] = field(default_factory=list)
    width: int = 0
    height: int = 0


class LM:
    """Named indices into Hand.landmarks (MediaPipe hand model)."""

    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_DIP = 7
    INDEX_TIP = 8
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_DIP = 11
    MIDDLE_TIP = 12
    RING_MCP = 13
    RING_PIP = 14
    RING_DIP = 15
    RING_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20
