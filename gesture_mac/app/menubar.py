"""The rumps menu bar app. Top item is the on/off toggle; below it the
camera picker, mapping reload, and quit. The runtime thread does the work;
this file only wires menu items to it and persists config changes.
"""
from __future__ import annotations

import logging
import subprocess

import rumps

log = logging.getLogger(__name__)

from .config import MAPPINGS_PATH, Config, load_config, save_config
from .runtime import Runtime

ICON_ON = "🤏"
ICON_OFF = "✋"


class GestureMacApp(rumps.App):
    def __init__(self) -> None:
        super().__init__("gesture-mac", title=ICON_ON, quit_button=None)
        self.cfg: Config = load_config()
        self.runtime = Runtime(self.cfg, on_status=self._status)

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

    def quit(self, _item) -> None:
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
        self.status_item.title = text
        log.info("status: %s", text)

    def _apply_icon(self) -> None:
        self.title = ICON_ON if self.cfg.enabled else ICON_OFF


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    GestureMacApp().run()
