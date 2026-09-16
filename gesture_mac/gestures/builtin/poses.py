"""Static hand poses. These lean on the GestureRecognizer model's built-in
classifier (its score is already 0..1) and add a geometric sanity check
where the classifier is known to be loose. Momentary only.
"""
from __future__ import annotations

from ...capture.types import LM, Hand
from ..base import Gesture
from ..geometry import finger_extended, thumb_extended


def pose_score(hand: Hand, label: str) -> float:
    """Score from the built-in classifier if its label matches, else 0."""
    return hand.pose_score if hand.pose_label == label else 0.0


class OpenPalm(Gesture[Hand]):
    id = "open-palm"
    label = "Open palm"
    hint = "All five fingers spread, palm to camera."

    def score(self, hand: Hand) -> float:
        return pose_score(hand, "Open_Palm")


class Fist(Gesture[Hand]):
    id = "fist"
    label = "Fist"
    hint = "Close all fingers."

    def score(self, hand: Hand) -> float:
        return pose_score(hand, "Closed_Fist")


class Point(Gesture[Hand]):
    id = "point"
    label = "Point"
    hint = "Index finger up, others curled."

    def score(self, hand: Hand) -> float:
        # Classifier label is Pointing_Up; the geometric check keeps it honest
        # when the finger points sideways.
        from_model = pose_score(hand, "Pointing_Up")
        geometric = (
            0.85
            if finger_extended(hand, LM.INDEX_TIP)
            and not finger_extended(hand, LM.MIDDLE_TIP)
            and not finger_extended(hand, LM.RING_TIP)
            and not finger_extended(hand, LM.PINKY_TIP)
            else 0.0
        )
        return max(from_model, geometric)


class ThumbsUp(Gesture[Hand]):
    id = "thumbs-up"
    label = "Thumbs up"
    hint = "Fist with thumb extended upward."

    def score(self, hand: Hand) -> float:
        from_model = pose_score(hand, "Thumb_Up")
        geometric = (
            0.8
            if thumb_extended(hand)
            and not finger_extended(hand, LM.INDEX_TIP)
            and not finger_extended(hand, LM.MIDDLE_TIP)
            else 0.0
        )
        return max(from_model, geometric)
