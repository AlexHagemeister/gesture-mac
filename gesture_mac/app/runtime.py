"""The capture thread. Owns the camera, tracker, engine, mapper, and
performer, and runs the loop: read frame -> track -> engine.update, at
cfg.fps while a hand is in view and cfg.idle_fps otherwise. While gestures
are disabled the camera is released, so another app (a video call) can
have it; enabling reopens it. A tracker fault mid-stream is TrackerGuard's
to recover from; when it gives up the loop parks like the disabled state,
camera released, until the master switch is flipped.

The menu bar talks to it through set_enabled(), set_camera(), reload_mappings(),
and stop(). The HUD server reads last_frame and last_bgr (kept only while
set_preview(True)) and edits thresholds (live only) and smoothing (saved to config) through
set_thresholds() and set_smoothing(). Everything
else is private to the thread.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import replace
from typing import Callable

import numpy as np

from ..capture.camera import Camera
from ..capture.cameras import CameraInfo, camera_authorized, camera_status_authorized, list_cameras, resolve_camera
from ..capture.tracker import Tracker
from ..capture.types import Frame
from ..engine import GestureEngine
from ..gestures import GestureThresholds, default_gestures
from ..mapping import Mapper, load_document
from ..output import MacPerformer, accessibility_trusted
from .config import Config, ensure_mappings, save_config
from .tracking import TrackerGuard

log = logging.getLogger(__name__)


class Runtime:
    def __init__(self, cfg: Config, on_status: Callable[[str], None] | None = None) -> None:
        self.cfg = cfg
        self.on_status = on_status or (lambda s: None)
        os.environ.setdefault("OPENCV_AVFOUNDATION_SKIP_AUTH", "1")
        self.camera_ok = False
        self.engine = GestureEngine(default_gestures())
        try:
            self.engine.set_smoothing(**cfg.smoothing)
        except (ValueError, TypeError) as e:
            log.warning("ignoring smoothing in config.json: %s", e)
        self.mapper = Mapper(self.engine, load_document(ensure_mappings()), MacPerformer())
        self.mapper.set_enabled(cfg.enabled)
        self.engine.on("gesture", lambda e: log.info("%s %s %s", e.gesture_id, e.hand, e.phase))
        self.cameras: list[CameraInfo] = list_cameras()
        self.camera_info: CameraInfo | None = resolve_camera(cfg.camera, self.cameras)
        self._camera_change = threading.Event()
        self._wake = threading.Event()
        """Set by set_enabled so a disabled loop reopens the camera at once."""
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="gesture-capture", daemon=True)
        self.last_frame: Frame | None = None
        """Most recent frame, for a HUD to read. Written by the thread."""
        self.last_bgr: np.ndarray | None = None
        """The image behind last_frame, kept only while a HUD client wants
        it (set_preview). Encoding is the client's problem, not this thread's."""
        self._preview = False

    # ---- controls from the menu bar -------------------------------------

    def start(self) -> None:
        """Call on the main thread once the app's run loop exists: the
        camera permission prompt needs it. OpenCV's own prompt cannot run
        from the capture thread, hence OPENCV_AVFOUNDATION_SKIP_AUTH."""
        self.camera_ok = camera_authorized()
        if not self.camera_ok:
            self.on_status("camera permission denied")
        if not accessibility_trusted(prompt=True):
            log.warning("Accessibility not granted: key and scroll events will be dropped")
            self.on_status("no Accessibility grant: keys dropped")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3)
        self.mapper.dispose()

    def set_enabled(self, on: bool) -> None:
        self.cfg.enabled = on
        self.mapper.set_enabled(on)
        self._wake.set()

    def set_camera(self, info: CameraInfo) -> None:
        self.cfg.camera = info.name
        self.camera_info = info
        self._camera_change.set()

    def refresh_cameras(self) -> list[CameraInfo]:
        self.cameras = list_cameras()
        return self.cameras

    def reload_mappings(self) -> None:
        self.mapper.load(load_document(ensure_mappings()))
        self.on_status("mappings reloaded")

    # ---- controls from the HUD server -------------------------------------

    def set_preview(self, on: bool) -> None:
        """Keep the raw image around for the HUD. Off drops it so nothing is
        retained for a page nobody is looking at."""
        self._preview = on
        if not on:
            self.last_bgr = None

    def set_thresholds(self, gesture_id: str, **patch: float) -> GestureThresholds:
        """Live threshold edit from the panel. Not persisted, like the template."""
        g = self.engine.get_gesture(gesture_id)
        if g is None:
            raise KeyError(gesture_id)
        g.thresholds = replace(g.thresholds, **patch)
        return g.thresholds

    def set_smoothing(self, **patch: float) -> dict[str, float]:
        """Live smoothing edit from the panel, saved so the next launch
        starts with it: these are tuned by feel over time (Alex, issue #24)."""
        out = self.engine.set_smoothing(**patch)
        self.cfg.smoothing = out
        save_config(self.cfg)
        return out

    # ---- the loop --------------------------------------------------------

    def _build_tracker(self) -> Tracker:
        return Tracker(
            flip_handedness=self.cfg.flip_handedness,
            hand_confidence=self.cfg.hand_confidence,
            min_in_frame=self.cfg.min_in_frame,
        )

    def _run(self) -> None:
        tracker = TrackerGuard(self._build_tracker, on_failure=self.mapper.release_all)
        camera: Camera | None = None
        last_hand_t = time.monotonic()
        frames, report_t = 0, time.monotonic()
        track_s = 0.0
        """Tracking time summed over the report window, for the status line."""
        try:
            while not self._stop.is_set():
                if not self.camera_ok:
                    self.camera_ok = camera_status_authorized()
                    if not self.camera_ok:
                        self.on_status("camera permission denied (System Settings > Privacy & Security > Camera)")
                        time.sleep(5)
                        continue
                if not self.cfg.enabled or tracker.stopped is not None:
                    if camera is not None:
                        camera.release()
                        camera = None
                        self.last_frame = None
                        self.last_bgr = None
                        if tracker.stopped is not None:
                            self.on_status(f"tracking stopped: {tracker.stopped} (switch off and on to retry)")
                        else:
                            self.on_status("off, camera released")
                    # The switch clears a stop: set_enabled wakes the loop,
                    # and a wake while enabled is the "on" flip.
                    if self._wake.wait(0.5) and self.cfg.enabled and tracker.stopped is not None:
                        tracker.reset()
                    self._wake.clear()
                    continue
                if camera is None or self._camera_change.is_set():
                    self._camera_change.clear()
                    if camera is not None:
                        camera.release()
                    if self.camera_info is None:
                        self.on_status("no camera found")
                        time.sleep(2)
                        self.refresh_cameras()
                        self.camera_info = resolve_camera(self.cfg.camera, self.cameras)
                        continue
                    try:
                        camera = Camera(self.camera_info.index)
                        self.on_status(f"camera: {self.camera_info.name}")
                    except RuntimeError as e:
                        log.warning("%s", e)
                        camera = None
                        self.on_status("camera failed to open")
                        time.sleep(2)
                        continue

                idle = time.monotonic() - last_hand_t > self.cfg.idle_after_s
                rate = self.cfg.idle_fps if idle else self.cfg.fps
                bgr = camera.read(1.0 / max(rate, 0.5))
                if bgr is None:
                    continue
                t0 = time.monotonic()
                frame = tracker.track(bgr)
                track_s += time.monotonic() - t0
                if frame is None:
                    continue
                if frame.hands:
                    last_hand_t = time.monotonic()
                self.last_frame = frame
                if self._preview:
                    self.last_bgr = bgr
                self.engine.update(frame)
                frames += 1
                if time.monotonic() - report_t >= 2.0:
                    fps = frames / (time.monotonic() - report_t)
                    # Tracking time per frame is the loop's ceiling: past one
                    # camera period (33 ms at 30) a frame gets dropped.
                    ms = 1000 * track_s / frames
                    self.on_status(f"{fps:.0f} fps, {ms:.0f} ms track, {len(frame.hands)} hand(s){', idle' if idle else ''}")
                    frames, report_t, track_s = 0, time.monotonic(), 0.0
        finally:
            if camera is not None:
                camera.release()
            tracker.close()
