"""Two-hand gestures. The pair's pose is the midpoint between hands
(position), the angle of the line between them (rotate), and their
separation in hand-size units (spread / converge).
"""
from __future__ import annotations

from ...capture.types import LM, Hand, HandPair
from ..base import BimanualContinuousGesture
from ..geometry import Point, Pose, angle_of, closeness, dist, hand_size, midpoint, norm_dist


def pinch_score(hand: Hand) -> float:
    return closeness(norm_dist(hand, LM.THUMB_TIP, LM.INDEX_TIP), 0.2, 0.5)


def pinch_point(hand: Hand) -> Point:
    return midpoint(hand.landmarks[LM.THUMB_TIP], hand.landmarks[LM.INDEX_TIP])


def pair_pose(a: Point, b: Point, pair: HandPair) -> Pose:
    avg_hand = (hand_size(pair.left) + hand_size(pair.right)) / 2
    m = midpoint(a, b)
    return Pose(m.x, m.y, angle_of(a, b), dist(a, b) / avg_hand)


class DoublePinch(BimanualContinuousGesture):
    """Both hands index-pinched: pan, rotate, and spread with the pair."""

    id = "double-pinch"
    label = "Double pinch"
    hint = "Index-pinch with both hands. Move together to pan, twist to rotate, spread to scale."

    def score(self, pair: HandPair) -> float:
        return min(pinch_score(pair.left), pinch_score(pair.right))

    def anchor(self, pair: HandPair) -> Pose:
        return pair_pose(pinch_point(pair.left), pinch_point(pair.right), pair)


class TwoPalms(BimanualContinuousGesture):
    """Both palms open and facing the camera: the classic spread / converge."""

    id = "two-palms"
    label = "Two palms"
    hint = "Both palms open to the camera. Spread or converge to scale, twist to rotate."

    def score(self, pair: HandPair) -> float:
        def s(h: Hand) -> float:
            return h.pose_score if h.pose_label == "Open_Palm" else 0.0

        return min(s(pair.left), s(pair.right))

    def anchor(self, pair: HandPair) -> Pose:
        lm = LM.MIDDLE_MCP
        a, b = pair.left.landmarks[lm], pair.right.landmarks[lm]
        return pair_pose(Point(a.x, a.y), Point(b.x, b.y), pair)
