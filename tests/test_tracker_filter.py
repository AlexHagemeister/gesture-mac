"""The in-frame test that drops a hand tracked mostly off the image edge."""
from __future__ import annotations

from gesture_mac.capture.tracker import in_frame_fraction
from gesture_mac.capture.types import Landmark


def _hand(xs: list[float]) -> list[Landmark]:
    return [Landmark(x, 0.5) for x in xs]


def test_all_inside_is_one():
    assert in_frame_fraction(_hand([0.1] * 21)) == 1.0


def test_half_off_the_edge_is_half():
    assert in_frame_fraction(_hand([0.5] * 10 + [1.2] * 10)) == 0.5


def test_empty_is_zero():
    assert in_frame_fraction([]) == 0.0
