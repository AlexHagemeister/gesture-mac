"""OpenCV camera source. Opens a device by index, yields BGR frames at a
capped rate. Idle mode lowers the rate when nothing is in view; the
runtime decides when to enter it.
"""
from __future__ import annotations

import time

import cv2
import numpy as np


class Camera:
    def __init__(self, index: int, width: int = 640, height: int = 360) -> None:
        self.index = index
        self._cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
        if not self._cap.isOpened():
            raise RuntimeError(f"could not open camera index {index}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._last = 0.0

    def read(self, min_interval_s: float) -> np.ndarray | None:
        """Grab a frame, sleeping first so calls are at most 1/min_interval_s
        per second. Returns None on a read failure.

        The interval is measured from the start of the previous read, not its
        end: cap.read() itself blocks until the camera's next frame, and
        counting that wait as part of the interval is what let the loop's
        own sleep, the camera's wait, and tracking stack up to 10 fps against
        a 15 cap (issue #6). Measured this way, the cap is a ceiling, and a
        camera slower than it sets the pace on its own."""
        wait = self._last + min_interval_s - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        ok, bgr = self._cap.read()
        return bgr if ok else None

    def release(self) -> None:
        self._cap.release()
