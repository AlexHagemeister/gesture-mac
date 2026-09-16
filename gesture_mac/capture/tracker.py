"""MediaPipe GestureRecognizer wrapper. The only module that imports
MediaPipe. Feed BGR frames from OpenCV; get Frame objects back.

Runs the recognizer in VIDEO mode (synchronous per frame) rather than
LIVE_STREAM: the capture loop already runs on its own thread, and a
synchronous call keeps frame and result paired without a callback queue.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from .types import Frame, Hand, Landmark

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task"


def default_model_path() -> Path:
    return Path(__file__).resolve().parents[2] / "models" / "gesture_recognizer.task"


def ensure_model(path: Path) -> Path:
    if not path.exists():
        import urllib.request

        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, path)
    return path


class Tracker:
    def __init__(self, model_path: Path | None = None, num_hands: int = 2, flip_handedness: bool = False) -> None:
        import mediapipe as mp

        path = ensure_model(model_path or default_model_path())
        opts = mp.tasks.vision.GestureRecognizerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=num_hands,
        )
        self._mp = mp
        self._rec = mp.tasks.vision.GestureRecognizer.create_from_options(opts)
        self._flip = flip_handedness
        self._t0 = time.monotonic()
        self._last_ts_ms = -1

    def now_ms(self) -> float:
        return (time.monotonic() - self._t0) * 1000

    def track(self, bgr: np.ndarray) -> Frame:
        """Run the recognizer on one BGR frame. Timestamps must increase, so
        a frame arriving inside the same millisecond is nudged forward."""
        rgb = bgr[:, :, ::-1]
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        t = self.now_ms()
        ts = max(int(t), self._last_ts_ms + 1)
        self._last_ts_ms = ts
        result = self._rec.recognize_for_video(image, ts)
        h, w = bgr.shape[:2]
        frame = Frame(t=t, width=w, height=h)
        for i, lms in enumerate(result.hand_landmarks):
            hd = result.handedness[i][0]
            label = hd.category_name.lower()
            if self._flip:
                label = "left" if label == "right" else "right"
            pose = result.gestures[i][0] if result.gestures and result.gestures[i] else None
            frame.hands.append(
                Hand(
                    handedness=label,  # type: ignore[arg-type]
                    handedness_score=float(hd.score),
                    landmarks=[Landmark(lm.x, lm.y, lm.z) for lm in lms],
                    pose_label=pose.category_name if pose else "None",
                    pose_score=float(pose.score) if pose else 0.0,
                )
            )
        return frame

    def close(self) -> None:
        self._rec.close()
