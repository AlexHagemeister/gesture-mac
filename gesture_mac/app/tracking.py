"""Tracker supervision for the capture thread. TrackerGuard owns the
tracker, runs each frame through it, and rebuilds it when it raises, so a
MediaPipe fault mid-stream costs one frame instead of the thread (issue
#22). After max_failures failures in a row it gives up and reports why;
reset() (the master switch) starts it over. The tracker is anything with
track(bgr) -> Frame and close(), built by the factory it is given, so
tests can hand it one that raises on demand.
"""
from __future__ import annotations

import logging
from typing import Callable, Protocol

import numpy as np

from ..capture.types import Frame

log = logging.getLogger(__name__)


class TrackerLike(Protocol):
    def track(self, bgr: np.ndarray) -> Frame: ...
    def close(self) -> None: ...


class TrackerGuard:
    def __init__(
        self,
        build: Callable[[], TrackerLike],
        on_failure: Callable[[], None] = lambda: None,
        max_failures: int = 3,
    ) -> None:
        """on_failure runs after every failure, before the rebuild: the
        runtime releases held keys there, since the gesture that held
        them may not be seen releasing."""
        self._build = build
        self._on_failure = on_failure
        self.max_failures = max_failures
        self.failures = 0
        """Failures in a row (a frame that raised, or a rebuild that did).
        A tracked frame resets it."""
        self.stopped: str | None = None
        """Why tracking gave up, or None while it runs."""
        self._tracker: TrackerLike | None = None

    def track(self, bgr: np.ndarray) -> Frame | None:
        """The frame's hands, or None when the tracker failed on it. The
        tracker is rebuilt in place unless the failure was the last one
        allowed, in which case stopped names the reason."""
        if self.stopped is not None:
            return None
        try:
            if self._tracker is None:
                self._tracker = self._build()
            frame = self._tracker.track(bgr)
        except Exception as e:
            self._fail(e)
            return None
        self.failures = 0
        return frame

    def _fail(self, e: Exception) -> None:
        self.failures += 1
        self._on_failure()
        self._discard()
        reason = f"{type(e).__name__}: {e}".splitlines()[0]
        if self.failures >= self.max_failures:
            log.error("tracker failed %d times in a row, stopping: %s", self.failures, reason)
            self.stopped = reason
            return
        log.warning("tracker failed (%d of %d), rebuilding: %s", self.failures, self.max_failures, reason)
        try:
            self._tracker = self._build()
        except Exception as e2:
            self._fail(e2)

    def _discard(self) -> None:
        # A tracker that raised mid-frame raises again from close (seen in
        # the #22 log), and a failed close is nothing to act on.
        t, self._tracker = self._tracker, None
        if t is not None:
            try:
                t.close()
            except Exception:
                log.debug("tracker close failed after a fault", exc_info=True)

    def reset(self) -> None:
        """Forget the stop and the failure count; the next track() rebuilds."""
        self.failures = 0
        self.stopped = None

    def close(self) -> None:
        self._discard()
