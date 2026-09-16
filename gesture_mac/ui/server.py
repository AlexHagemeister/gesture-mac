"""The HTTP + websocket server behind the HUD page. Runs aiohttp on its
own thread with its own event loop, bound to 127.0.0.1 only.

Routes:

    GET  /                      the built page (static/index.html)
    GET  /assets/...            the page's bundle
    GET  /api/state             gestures, thresholds, mapping document
    PUT  /api/mappings          replace the document: validate, save, hot-reload
    POST /api/validate-key      {"key": chord} -> {"ok": bool, "error": str|null}
    PUT  /api/thresholds/{id}   live threshold patch for one gesture
    GET  /ws                    the stream (see wire.py)

Every write to mappings.json goes through the same parser the mapper
loads with, so the panel cannot save a document the app cannot read.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from pathlib import Path

from aiohttp import WSMsgType, web

from ..app.config import ensure_mappings
from ..app.runtime import Runtime
from ..mapping.bindings import document_to_json, parse_document, save_document
from ..output.keys import parse_chord
from . import wire

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def build_app(rt: Runtime, publisher: wire.Publisher, mappings_path: Path | None = None) -> web.Application:
    """The aiohttp app, separated from the thread so tests can drive it."""
    path = mappings_path or ensure_mappings()
    app = web.Application()

    async def index(_req: web.Request) -> web.StreamResponse:
        page = STATIC_DIR / "index.html"
        if not page.exists():
            return web.Response(
                text="HUD page not built. Run `pnpm install && pnpm build` in ui/web.",
                status=503,
            )
        return web.FileResponse(page)

    async def state(_req: web.Request) -> web.Response:
        return web.json_response(wire.state_json(rt, str(path)))

    async def put_mappings(req: web.Request) -> web.Response:
        try:
            doc = parse_document(await req.json())
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            return web.json_response({"error": f"invalid mapping document: {e}"}, status=400)
        for c in doc.controls:
            if c.action is not None and hasattr(c.action, "key"):
                try:
                    parse_chord(c.action.key)
                except ValueError as e:
                    return web.json_response({"error": f"control {c.id!r}: {e}"}, status=400)
        save_document(doc, path)
        rt.mapper.load(doc)
        rt.on_status("mappings saved from HUD")
        out = document_to_json(doc)
        await publisher.broadcast({"type": "mappings", "mappings": out})
        return web.json_response(out)

    async def validate_key(req: web.Request) -> web.Response:
        body = await req.json()
        try:
            parse_chord(str(body.get("key", "")))
        except ValueError as e:
            return web.json_response({"ok": False, "error": str(e)})
        return web.json_response({"ok": True, "error": None})

    async def put_thresholds(req: web.Request) -> web.Response:
        gid = req.match_info["id"]
        try:
            t = rt.set_thresholds(gid, **wire.thresholds_patch(await req.json()))
        except KeyError:
            return web.json_response({"error": f"unknown gesture: {gid}"}, status=404)
        except (ValueError, TypeError) as e:
            return web.json_response({"error": str(e)}, status=400)
        out = wire.thresholds_json(t)
        await publisher.broadcast({"type": "thresholds", "gestureId": gid, "thresholds": out})
        return web.json_response(out)

    async def ws(req: web.Request) -> web.WebSocketResponse:
        sock = web.WebSocketResponse(heartbeat=20)
        await sock.prepare(req)

        async def send(msg: dict) -> None:
            await sock.send_str(json.dumps(msg))

        publisher.add(sock, send)
        try:
            async for m in sock:
                if m.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                    break
        finally:
            publisher.remove(sock)
        return sock

    app.router.add_get("/", index)
    app.router.add_get("/api/state", state)
    app.router.add_put("/api/mappings", put_mappings)
    app.router.add_post("/api/validate-key", validate_key)
    app.router.add_put("/api/thresholds/{id}", put_thresholds)
    app.router.add_get("/ws", ws)
    if (STATIC_DIR / "assets").exists():
        app.router.add_static("/assets", STATIC_DIR / "assets")
    return app


class UiServer:
    """Owns the server thread. start() blocks until the port is bound and
    returns the page URL; stop() tears the loop down."""

    def __init__(self, rt: Runtime, port: int) -> None:
        self.rt = rt
        self.port = port
        self.url: str | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._error: BaseException | None = None

    def start(self) -> str:
        if self.url:
            return self.url
        self._thread = threading.Thread(target=self._run, name="gesture-hud", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)
        if self._error is not None:
            raise RuntimeError(f"HUD server failed to start: {self._error}")
        if self.url is None:
            raise RuntimeError("HUD server did not start in time")
        return self.url

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        publisher = wire.Publisher(self.rt, loop)
        runner = web.AppRunner(build_app(self.rt, publisher), access_log=None)
        try:
            loop.run_until_complete(runner.setup())
            site = web.TCPSite(runner, "127.0.0.1", self.port)
            loop.run_until_complete(site.start())
            self.url = f"http://127.0.0.1:{self.port}/"
            log.info("hud: serving %s", self.url)
        except BaseException as e:
            self._error = e
            self._ready.set()
            return
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(runner.cleanup())
            loop.close()
