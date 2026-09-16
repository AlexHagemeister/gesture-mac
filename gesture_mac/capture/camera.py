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
        per second. Returns None on a read failure."""
        wait = self._last + min_interval_s - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        ok, bgr = self._cap.read()
        self._last = time.monotonic()
        return bgr if ok else None

    def release(self) -> None:
        self._cap.release()
