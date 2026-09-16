# gesture-mac

Webcam hand gestures as a Mac peripheral, from the menu bar. Pinch to hold
a key (superwhisper's dictation hotkey by default), with every binding
editable. Sibling of [gesture-template](../gesture-template), whose gesture
engine this ports to Python.

## Run

```bash
uv sync
uv run gesture-mac
```

Grant camera access when asked. Grant Accessibility to the terminal you
launched from (System Settings > Privacy & Security > Accessibility), or
key events go nowhere.

## Run without a terminal

```bash
./scripts/make-app.sh
```

builds `~/Applications/gesture-mac.app`, a launcher that runs the same
command with its output in `~/Library/Logs/gesture-mac.log`. Open it from
Finder or Spotlight, and add it under System Settings > General > Login
Items to start it at login. The bundle is what macOS asks camera and
Accessibility permission for, so grant both to "gesture-mac" once. Re-run
the script if the repo or uv moves.

Menu: **Gestures enabled** (the master switch, top of the menu: off
releases the camera for other apps and stops tracking), status
line, **Camera** picker, **Configure**, **Reload mappings**,
**Open mappings.json**, Quit.

## Configure: the bindings page

**Configure** opens a window laid out like BetterTouchTool: every binding in
a list on the left (gesture, hand, what it does), the selected one in a
detail pane (gesture and hand, the action with a Record button for the key
chord, when it fires, a modifier gesture, live thresholds). "Show live view"
in the header adds the mirror-mode camera with hand landmarks and a readout
of the gestures currently past idle. Every edit writes mappings.json and the
app reloads it on the spot.

The page is served by the app at http://127.0.0.1:8765/ (`hud_port` in
config.json), so it also opens in any browser. Frame encoding and the event
stream run only while a page is connected; tracking runs regardless.

## Default binding

Right-hand index pinch holds the right option key for as long as the pinch
lasts. With superwhisper bound to right option: a short pinch toggles
dictation, a long pinch dictates and pastes on release.

## Edit bindings

In the HUD's panel, or by hand in
`~/Library/Application Support/gesture-mac/mappings.json` followed by Reload
mappings. Schema in `gesture_mac/mapping/bindings.py`; action kinds and key
names in `gesture_mac/mapping/actions.py`. Gestures available:
index-pinch, middle-pinch, open-palm, fist, point, thumbs-up, double-pinch,
two-palms. Hands: left, right, either, both.

## Layout

```
gesture_mac/
  capture/   camera (OpenCV), camera list (AVFoundation), MediaPipe tracker -> Frame
  gestures/  Gesture base class (state machine), geometry, builtin/, registry
  engine/    GestureEngine: runs gestures per hand, emits gesture + delta events
  mapping/   bindings JSON, action kinds, Mapper (events -> Performer calls)
  output/    MacPerformer: CGEvent keys and scroll via PyObjC
  app/       config, capture thread (runtime), rumps menu bar, entry point
  ui/        HUD server (aiohttp: static page, JSON API, websocket), WebKit window, built page in static/
ui/web/      the page's TypeScript source (Vite); `pnpm build` writes gesture_mac/ui/static/
presets/     default.json, the seed for a fresh install
tests/       headless: engine, mapper, key chords, HUD server
```
