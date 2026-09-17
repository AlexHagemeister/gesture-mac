"""TrackerGuard: a tracker that raises is rebuilt, a run of failures stops
tracking with a reason, and reset starts over."""
from __future__ import annotations

import numpy as np

from gesture_mac.app.tracking import TrackerGuard
from gesture_mac.capture.types import Frame

BGR = np.zeros((4, 4, 3), dtype=np.uint8)


class FakeTracker:
    """Raises on track() while its script says so; close() raises after a
    fault, the way MediaPipe's does."""

    def __init__(self, script: list[bool], log: list[str]) -> None:
        self.script = script
        self.log = log
        self.faulted = False

    def track(self, bgr):
        fail = self.script.pop(0) if self.script else False
        if fail:
            self.faulted = True
            raise RuntimeError("Packet isn't the sole owner of the holder.\nmore lines")
        return Frame(t=0.0, width=4, height=4)

    def close(self):
        self.log.append("close")
        if self.faulted:
            raise RuntimeError("close after fault")


def make(script: list[bool], build_fails: int = 0):
    log: list[str] = []
    released: list[int] = []
    builds = {"n": 0}

    def build():
        builds["n"] += 1
        if builds["n"] <= build_fails:
            raise RuntimeError("model load failed")
        log.append("build")
        return FakeTracker(script, log)

    guard = TrackerGuard(build, on_failure=lambda: released.append(1), max_failures=3)
    return guard, log, released, builds


def test_healthy_frames_pass_through_one_build():
    guard, log, released, builds = make([False, False])
    assert isinstance(guard.track(BGR), Frame)
    assert isinstance(guard.track(BGR), Frame)
    assert builds["n"] == 1 and released == [] and guard.failures == 0


def test_one_failure_rebuilds_releases_keys_and_carries_on():
    guard, log, released, builds = make([False, True, False])
    assert guard.track(BGR) is not None
    assert guard.track(BGR) is None
    assert released == [1]
    assert log == ["build", "close", "build"]
    assert guard.track(BGR) is not None
    assert guard.stopped is None and guard.failures == 0


def test_failures_in_a_row_stop_with_the_reason():
    guard, log, released, builds = make([True, True, True, False])
    for _ in range(3):
        assert guard.track(BGR) is None
    assert guard.stopped == "RuntimeError: Packet isn't the sole owner of the holder."
    assert builds["n"] == 3
    assert len(released) == 3
    # Stopped means no more tracking and no more building.
    assert guard.track(BGR) is None
    assert builds["n"] == 3


def test_a_success_between_failures_resets_the_count():
    guard, log, released, builds = make([True, True, False, True, True, False])
    for _ in range(6):
        guard.track(BGR)
    assert guard.stopped is None
    assert guard.failures == 0


def test_rebuild_failures_count_too():
    guard, log, released, builds = make([True], build_fails=0)
    guard._build = _failing_after(guard._build, 1)
    assert guard.track(BGR) is None
    assert guard.stopped is not None
    assert guard.stopped.startswith("RuntimeError: model load failed")


def _failing_after(build, ok_calls: int):
    n = {"c": 0}

    def wrapped():
        n["c"] += 1
        if n["c"] > ok_calls:
            raise RuntimeError("model load failed")
        return build()

    return wrapped


def test_reset_starts_over():
    guard, log, released, builds = make([True, True, True, False])
    for _ in range(3):
        guard.track(BGR)
    assert guard.stopped is not None
    guard.reset()
    assert guard.track(BGR) is not None
    assert builds["n"] == 4 and guard.stopped is None
