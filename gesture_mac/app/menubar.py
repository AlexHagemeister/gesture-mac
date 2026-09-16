"""The rumps menu bar app. Top item is the on/off toggle; below it the
camera picker, Configure (the bindings page), mapping reload, and quit. The runtime thread does
the work; this file only wires menu items to it and persists config changes.

The page's server starts the first time Configure is chosen and then
idles; the stream itself runs only while the window has the page open.
"""
from __future__ import annotations

import logging
import subprocess

import rumps
from AppKit import NSImage, NSImageSymbolConfiguration, NSImageSymbolScaleMedium

log = logging.getLogger(__name__)

from ..ui import HudWindow, UiServer
from .config import MAPPINGS_PATH, Config, load_config, save_config
from .runtime import Runtime

ICON_ON = "hand.raised"
ICON_OFF = "hand.raised.slash"
"""SF Symbols, drawn as template images so they follow the menu bar's
light or dark appearance like the system's own icons."""


def symbol_image(name: str) -> NSImage:
    img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, "gesture-mac")
    cfg = NSImageSymbolConfiguration.configurationWithPointSize_weight_scale_(16, 0, NSImageSymbolScaleMedium)
    img = img.imageWithSymbolConfiguration_(cfg)
    img.setTemplate_(True)
    return img


class GestureMacApp(rumps.App):
    def __init__(self) -> None:
        super().__init__("gesture-mac", quit_button=None)
        self.cfg: Config = load_config()
        self._pending_status: str | None = None
        self.runtime = Runtime(self.cfg, on_status=self._status)
        self.ui: UiServer | None = None
        self.hud_window = HudWindow()

        self.enabled_item = rumps.MenuItem("Gestures enabled", callback=self.toggle_enabled)
        self.enabled_item.state = self.cfg.enabled
        self.status_item = rumps.MenuItem("starting…")
        self.status_item.set_callback(None)
        self.camera_menu = rumps.MenuItem("Camera")
        self._build_camera_menu()

        self.menu = [
            self.enabled_item,
            self.status_item,
            None,
            self.camera_menu,
            rumps.MenuItem("Configure", callback=self.open_hud),
            rumps.MenuItem("Reload mappings", callback=self.reload_mappings),
            rumps.MenuItem("Open mappings.json", callback=self.open_mappings),
            None,
            rumps.MenuItem("Quit", callback=self.quit),
        ]
        self._apply_icon()
        # Start once the run loop is up (a one-shot timer), so the camera
        # permission prompt has an app to attach to.
        self._starter = rumps.Timer(self._start_runtime, 0.5)
        self._starter.start()

    def _start_runtime(self, timer: rumps.Timer) -> None:
        timer.stop()
        self.runtime.start()
        # Menu items may only change on the main thread (AppKit crashes if a
        # worker touches them while the menu is open), so the capture thread
        # leaves text here and this timer applies it.
        self._status_timer = rumps.Timer(self._flush_status, 0.5)
        self._status_timer.start()

    def _flush_status(self, _timer: rumps.Timer) -> None:
        text, self._pending_status = self._pending_status, None
        if text is not None:
            self.status_item.title = text

    # ---- menu callbacks --------------------------------------------------

    def toggle_enabled(self, item: rumps.MenuItem) -> None:
        on = not item.state
        item.state = on
        self.runtime.set_enabled(on)
        save_config(self.cfg)
        self._apply_icon()

    def reload_mappings(self, _item) -> None:
        try:
            self.runtime.reload_mappings()
        except Exception as e:  # a broken JSON file must not kill the app
            self._status(f"mappings error: {e}")

    def open_mappings(self, _item) -> None:
        subprocess.run(["open", "-t", str(MAPPINGS_PATH)], check=False)

    def open_hud(self, _item) -> None:
        try:
            if self.ui is None:
                self.ui = UiServer(self.runtime, self.cfg.hud_port)
            url = self.ui.start()
        except RuntimeError as e:
            self._status(str(e))
            return
        self.hud_window.show(url)

    def quit(self, _item) -> None:
        self.hud_window.close()
        if self.ui is not None:
            self.ui.stop()
        self.runtime.stop()
        rumps.quit_application()

    # ---- camera submenu --------------------------------------------------

    def _build_camera_menu(self) -> None:
        if self.camera_menu._menu is not None:  # rumps creates the submenu lazily
            self.camera_menu.clear()
        for cam in self.runtime.refresh_cameras():
            item = rumps.MenuItem(cam.name, callback=self._pick_camera)
            item.state = self.runtime.camera_info is not None and cam.unique_id == self.runtime.camera_info.unique_id
            self.camera_menu.add(item)
        self.camera_menu.add(None)
        self.camera_menu.add(rumps.MenuItem("Refresh list", callback=lambda _: self._build_camera_menu()))

    def _pick_camera(self, item: rumps.MenuItem) -> None:
        cam = next((c for c in self.runtime.cameras if c.name == item.title), None)
        if cam is None:
            return
        self.runtime.set_camera(cam)
        save_config(self.cfg)
        self._build_camera_menu()

    # ---- status ---------------------------------------------------------

    def _status(self, text: str) -> None:
        """Safe from any thread: stores the text for _flush_status."""
        self._pending_status = text
        log.info("status: %s", text)

    def _apply_icon(self) -> None:
        img = symbol_image(ICON_ON if self.cfg.enabled else ICON_OFF)
        # Before run() rumps reads _icon_nsimage when it creates the status
        # item; after, the item exists and takes the image directly.
        item = getattr(getattr(self, "_nsapp", None), "nsstatusitem", None)
        if item is not None:
            item.setImage_(img)
        else:
            self._icon_nsimage = img


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    GestureMacApp().run()
