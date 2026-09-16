"""What goes over the websocket and the JSON API, and the Publisher that
turns runtime state into messages while at least one client is connected.

Messages (JSON text frames, "type" field):

    frame      one video frame: JPEG (base64), hands with landmarks (image
               coords 0..1), and every gesture instance's state and score
    gesture    an engine gesture event (engage, hold, release, flick)
    delta      an engine delta event (axes in user space, anchors in image coords)
    mappings   the mapping document changed (any client, or a disk reload)
    thresholds one gesture's thresholds changed

The API's state object (GET /api/state) carries the gesture list with
thresholds, the mapping document, and where it lives on disk.
"""
from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import asdict
from typing import Any, Awaitable, Callable

import cv2

from ..app.runtime import Runtime
from ..capture.types import Frame
from ..engine.events import DeltaEvent, GestureEvent
from ..mapping.bindings import document_to_json

log = logging.getLogger(__name__)

JPEG_QUALITY = 70

Send = Callable[[dict], Awaitable[None]]


def gesture_list(rt: Runtime) -> list[dict]:
    return [
        {
            "id": g.id,
            "label": g.label,
            "hint": g.hint,
            "continuous": g.continuous,
            "bimanual": g.bimanual,
            "thresholds": thresholds_json(g.thresholds),
        }
        for g in rt.engine.gestures
    ]


def thresholds_json(t) -> dict:
    return {"enter": t.enter, "exit": t.exit, "onsetMs": t.onset_ms, "holdMs": t.hold_ms}


def thresholds_patch(raw: dict) -> dict[str, float]:
    """camelCase from the page to the dataclass's field names, numbers only."""
    names = {"enter": "enter", "exit": "exit", "onsetMs": "onset_ms", "holdMs": "hold_ms"}
    patch = {}
    for k, v in raw.items():
        if k not in names:
            raise ValueError(f"unknown threshold: {k}")
        patch[names[k]] = float(v)
    return patch


def state_json(rt: Runtime, mappings_path: str) -> dict:
    return {
        "gestures": gesture_list(rt),
        "mappings": document_to_json(rt.mapper.doc),
        "mappingsPath": mappings_path,
        "enabled": rt.cfg.enabled,
    }


def gesture_json(e: GestureEvent) -> dict:
    return {
        "type": "gesture",
        "gestureId": e.gesture_id,
        "hand": e.hand,
        "phase": e.phase,
        "t": e.t,
        "score": e.score,
        "direction": e.direction,
    }


def delta_json(e: DeltaEvent) -> dict:
    return {
        "type": "delta",
        "gestureId": e.gesture_id,
        "hand": e.hand,
        "t": e.t,
        "delta": asdict(e.delta),
        "step": asdict(e.step),
        "abs": asdict(e.abs),
        "raw": list(e.raw),
        "filtered": list(e.filtered),
    }


def frame_json(rt: Runtime, frame: Frame, image_b64: str | None) -> dict:
    states = {}
    for g in rt.engine.gestures:
        for h in rt.engine.hands_for(g):
            st = rt.engine.get_state(g.id, h)
            if st is not None:
                states[f"{g.id}:{h}"] = {"state": st.state, "score": round(st.last_score, 3)}
    return {
        "type": "frame",
        "t": frame.t,
        "width": frame.width,
        "height": frame.height,
        "image": image_b64,
        "hands": [
            {
                "handedness": h.handedness,
                "poseLabel": h.pose_label,
                "poseScore": round(h.pose_score, 3),
                "landmarks": [[round(l.x, 4), round(l.y, 4)] for l in h.landmarks],
            }
            for h in frame.hands
        ],
        "states": states,
    }


def encode_jpeg(bgr) -> str:
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode("ascii")


class Publisher:
    """Fans runtime state out to websocket clients. Owns the on/off of every
    per-client cost: the preview image, the engine subscription, and the
    frame loop all exist only between the first connect and the last leave.
    """

    def __init__(self, rt: Runtime, loop: asyncio.AbstractEventLoop) -> None:
        self.rt = rt
        self.loop = loop
        self.clients: dict[Any, Send] = {}
        self._unsub: list[Callable[[], None]] = []
        self._task: asyncio.Task | None = None

    # ---- client bookkeeping (event-loop thread) ---------------------------

    def add(self, key: Any, send: Send) -> None:
        self.clients[key] = send
        if len(self.clients) == 1:
            self._start()

    def remove(self, key: Any) -> None:
        self.clients.pop(key, None)
        if not self.clients:
            self._stop()

    def _start(self) -> None:
        log.info("hud: first client, starting stream")
        self.rt.set_preview(True)
        eng = self.rt.engine
        # Engine callbacks run on the capture thread; hop to the loop.
        self._unsub = [
            eng.on("gesture", lambda e: self._post(gesture_json(e))),
            eng.on("delta", lambda e: self._post(delta_json(e))),
        ]
        self._task = self.loop.create_task(self._frames())

    def _stop(self) -> None:
        log.info("hud: last client left, stopping stream")
        for u in self._unsub:
            u()
        self._unsub = []
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self.rt.set_preview(False)

    def _post(self, msg: dict) -> None:
        self.loop.call_soon_threadsafe(lambda: self.loop.create_task(self.broadcast(msg)))

    # ---- sending -----------------------------------------------------------

    async def broadcast(self, msg: dict) -> None:
        for key, send in list(self.clients.items()):
            try:
                await send(msg)
            except Exception:  # a dead socket drops out on its own close
                log.debug("hud: send failed for %r", key)

    async def _frames(self) -> None:
        last_t = None
        while True:
            frame = self.rt.last_frame
            if frame is not None and frame.t != last_t:
                last_t = frame.t
                bgr = self.rt.last_bgr
                image = encode_jpeg(bgr) if bgr is not None else None
                await self.broadcast(frame_json(self.rt, frame, image))
            await asyncio.sleep(1.0 / max(self.rt.cfg.fps, 1.0))
