"""The HUD server, driven headless: a fake runtime with a real engine and
mapper, aiohttp's test client, no camera, no window."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest

from gesture_mac.app.config import Config
from gesture_mac.engine import GestureEngine
from gesture_mac.engine.events import GestureEvent
from gesture_mac.gestures import default_gestures
from gesture_mac.mapping import Mapper
from gesture_mac.mapping.bindings import document_to_json
from gesture_mac.ui import wire
from gesture_mac.ui.server import build_app

from .synth import frame, hand
from .test_mapper import Recorder, doc_with_hold


@dataclass
class FakeRuntime:
    """The slice of Runtime the ui package touches."""

    cfg: Config = field(default_factory=Config)
    engine: GestureEngine = field(default_factory=lambda: GestureEngine(default_gestures()))
    last_frame: object = None
    last_bgr: object = None
    preview: bool = False
    statuses: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.mapper = Mapper(self.engine, doc_with_hold(), Recorder())

    def set_preview(self, on: bool) -> None:
        self.preview = on
        if not on:
            self.last_bgr = None

    def set_thresholds(self, gesture_id: str, **patch):
        from dataclasses import replace

        g = self.engine.get_gesture(gesture_id)
        if g is None:
            raise KeyError(gesture_id)
        g.thresholds = replace(g.thresholds, **patch)
        return g.thresholds

    def on_status(self, text: str) -> None:
        self.statuses.append(text)


@pytest.fixture
def rt() -> FakeRuntime:
    return FakeRuntime()


@pytest.fixture
def mappings_path(tmp_path: Path) -> Path:
    p = tmp_path / "mappings.json"
    p.write_text(json.dumps(document_to_json(doc_with_hold())))
    return p


@pytest.fixture
async def client(aiohttp_client, rt, mappings_path):
    publisher = wire.Publisher(rt, asyncio.get_running_loop())
    return await aiohttp_client(build_app(rt, publisher, mappings_path))


async def test_state_lists_gestures_and_mappings(client, rt):
    r = await client.get("/api/state")
    body = await r.json()
    assert [g["id"] for g in body["gestures"]] == [g.id for g in rt.engine.gestures]
    assert body["gestures"][0]["thresholds"]["enter"] == rt.engine.gestures[0].thresholds.enter
    assert body["mappings"]["controls"][0]["action"]["key"] == "right-option"


async def test_put_mappings_saves_and_hot_reloads(client, rt, mappings_path):
    doc = document_to_json(doc_with_hold())
    doc["controls"][0]["action"]["key"] = "cmd+shift+4"
    doc["controls"][0]["action"]["type"] = "press-key"
    r = await client.put("/api/mappings", json=doc)
    assert r.status == 200
    assert json.loads(mappings_path.read_text())["controls"][0]["action"]["key"] == "cmd+shift+4"
    assert rt.mapper.doc.controls[0].action.key == "cmd+shift+4"
    assert "mappings saved from HUD" in rt.statuses


async def test_put_mappings_rejects_bad_key_without_writing(client, rt, mappings_path):
    before = mappings_path.read_text()
    doc = document_to_json(doc_with_hold())
    doc["controls"][0]["action"]["key"] = "hyper+q"
    r = await client.put("/api/mappings", json=doc)
    assert r.status == 400
    assert "hyper" in (await r.json())["error"]
    assert mappings_path.read_text() == before
    assert rt.mapper.doc.controls[0].action.key == "right-option"


async def test_put_mappings_rejects_wrong_version(client):
    r = await client.put("/api/mappings", json={"version": 1, "controls": [], "bindings": []})
    assert r.status == 400


async def test_validate_key(client):
    ok = await (await client.post("/api/validate-key", json={"key": "right-option"})).json()
    bad = await (await client.post("/api/validate-key", json={"key": "cmd+shift+4+5"})).json()
    assert ok == {"ok": True, "error": None}
    assert bad["ok"] is False and "base key" in bad["error"]


async def test_thresholds_patch_is_live(client, rt):
    r = await client.put("/api/thresholds/index-pinch", json={"enter": 0.9, "holdMs": 250})
    assert r.status == 200
    t = rt.engine.get_gesture("index-pinch").thresholds
    assert (t.enter, t.hold_ms) == (0.9, 250)
    assert (await client.put("/api/thresholds/nope", json={"enter": 0.9})).status == 404
    assert (await client.put("/api/thresholds/index-pinch", json={"bogus": 1})).status == 400


async def test_stream_runs_only_while_a_client_is_connected(client, rt):
    assert rt.preview is False
    ws = await client.ws_connect("/ws")
    await asyncio.sleep(0)
    assert rt.preview is True

    # A frame with an image, once the runtime has one.
    rt.last_bgr = np.zeros((36, 64, 3), dtype=np.uint8)
    rt.last_frame = frame(1000, [hand(0.1)])
    msg = json.loads((await asyncio.wait_for(ws.receive(), 2)).data)
    assert msg["type"] == "frame"
    assert msg["hands"][0]["handedness"] == "right"
    assert len(msg["hands"][0]["landmarks"]) == 21
    assert msg["image"].startswith("/9j/")  # JPEG magic, base64
    assert "index-pinch:right" in msg["states"]

    # Engine events reach the socket.
    rt.engine.emit("gesture", GestureEvent("index-pinch", "right", "engage", 1000, 0.95))
    msg = None
    for _ in range(5):
        msg = json.loads((await asyncio.wait_for(ws.receive(), 2)).data)
        if msg["type"] == "gesture":
            break
    assert msg and msg["phase"] == "engage"

    await ws.close()
    await asyncio.sleep(0.05)
    assert rt.preview is False
    assert rt.last_bgr is None
