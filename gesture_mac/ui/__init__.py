"""The HUD page: a local web server (aiohttp) that serves the built panel
from static/, streams frames and engine events over a websocket, and
reads and writes mappings.json on the panel's behalf, plus the WebKit
window the menu bar opens it in.

Nothing heavy runs without a client. Frame encoding and the event
subscription start when the first websocket connects and stop when the
last one leaves (wire.Publisher). The server itself idles at zero cost.

Imports app.runtime and app.config only. The runtime never imports this
package; the menu bar is its only caller.
"""
from .server import UiServer
from .window import HudWindow

__all__ = ["UiServer", "HudWindow"]
