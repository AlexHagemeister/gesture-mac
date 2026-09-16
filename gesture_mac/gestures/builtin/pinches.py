"""Pinch gestures: thumb tip touching another fingertip. Continuous, anchored
at the pinch point with the hand's orientation and size as the angle and
scale axes. Score is the closeness of the two tips as a fraction of hand size.
"""
from __future__ import annotations

from ...capture.types import LM, Hand
from ..base import ContinuousGesture
from ..geometry import Pose, closeness, hand_pose, midpoint, norm_dist


class Pinch(ContinuousGesture[Hand]):
    tip: int = LM.INDEX_TIP

    def score(self, hand: Hand) -> float:
        # Touching is ~0.15 hand-lengths apart (tips have volume); clearly open is ~0.5.
        return closeness(norm_dist(hand, LM.THUMB_TIP, self.tip), 0.2, 0.5)

    def anchor(self, hand: Hand) -> Pose:
        return hand_pose(hand, midpoint(hand.landmarks[LM.THUMB_TIP], hand.landmarks[self.tip]))


class IndexPinch(Pinch):
    id = "index-pinch"
    label = "Index pinch"
    hint = "Touch thumb and index fingertips. Move, twist, or approach the camera to drive axes."
    tip = LM.INDEX_TIP


class MiddlePinch(Pinch):
    id = "middle-pinch"
    label = "Middle pinch"
    hint = "Touch thumb and middle fingertips. Move, twist, or approach the camera to drive axes."
    tip = LM.MIDDLE_TIP
