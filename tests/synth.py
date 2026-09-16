"""Synthetic hands for headless tests. No camera, no MediaPipe."""
from __future__ import annotations

from gesture_mac.capture.types import LM, Frame, Hand, Landmark


def hand(pinch_gap: float, offset_y: float = 0.0, handedness: str = "right") -> Hand:
    """A right hand with wrist at (0.5, 0.8), middle knuckle 0.2 above it
    (hand size 0.2), thumb tip at (0.5, 0.5), index tip pinch_gap hand
    lengths to the right of it."""
    lm = [Landmark(0.5, 0.5 + offset_y) for _ in range(21)]
    lm[LM.WRIST] = Landmark(0.5, 0.8 + offset_y)
    lm[LM.MIDDLE_MCP] = Landmark(0.5, 0.6 + offset_y)
    lm[LM.THUMB_TIP] = Landmark(0.5, 0.5 + offset_y)
    lm[LM.INDEX_TIP] = Landmark(0.5 + pinch_gap * 0.2, 0.5 + offset_y)
    return Hand(handedness, 0.99, lm)  # type: ignore[arg-type]


def frame(t: float, hands: list[Hand]) -> Frame:
    return Frame(t, hands, 1280, 720)
