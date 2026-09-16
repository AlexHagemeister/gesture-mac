# CLAUDE.md: gesture-mac

Python menu-bar app: webcam hand gestures drive macOS (keys, scroll). Port of
the gesture engine in ~/dev/gesture-template. VISION.md has the why and the
milestones; this file is for agents working in the repo.

## Commands

```bash
uv sync                 # create .venv with all deps (Python 3.12)
uv run pytest -q        # headless tests: engine, mapper, key chords (~1 s)
uv run gesture-mac      # launch the menu-bar app (needs camera + Accessibility permission)
cd ui/web && pnpm install && pnpm build   # rebuild the HUD page into gesture_mac/ui/static/ (commit the output)
```

The built page is committed so the app runs without node. After any change
under ui/web/src, run the build and commit static/ with it. `pnpm dev` in
ui/web serves the page with hot reload, proxying /api and /ws to a running
app on 8765.

Run the tests before every commit. Launch the app to verify anything that
touches capture/, output/, or app/, since tests cannot see a camera or
post real events.

Before launching, check nothing is already running: `pgrep -fl gesture-mac`.
Two instances fight over the camera and both post keys. Alex may have it
running as `~/Applications/gesture-mac.app` (built by scripts/make-app.sh,
log in ~/Library/Logs/gesture-mac.log); that instance shows up in the same
pgrep and its parent is launchd, not a shell.

## Architecture in one paragraph

Data flows one way. `capture/` opens the camera (OpenCV) and runs MediaPipe's
GestureRecognizer, emitting a `Frame` (hands with landmarks, handedness, pose
label). `engine/` runs every registered gesture against each hand (or pair)
and emits `gesture` events (engage, hold, release, flick) and `delta` events
(x, y, angle, scale from the engage origin, user space). `mapping/` applies
those to bindings from a JSON document and hands `Action` objects to a
`Performer`. `output/` is the Mac performer (CGEvent via PyObjC). `app/`
is the rumps menu bar, the config files, and the capture thread that ties
the layers together. `ui/` is the HUD: an aiohttp server (static page, JSON
API for mappings and thresholds, websocket stream of frames and events) and
the WebKit window the menu opens it in. The page itself is TypeScript in
ui/web/, built into ui/static/, laid out like BetterTouchTool: bindings.ts
is the list of every binding plus the selected one's detail pane, live.ts
is the readout beside the video (hands in view, non-idle gestures with
score bars; nothing is drawn as text on the camera canvas), hud.ts draws
the mirrored frame and skeleton, keys.ts records a chord from the
keyboard. The video and readout stream only while the page is open. Each package's `__init__.py` docstring says what it
owns; the top-level `gesture_mac/__init__.py` lists the import order.

## Rules that keep it clean

- **Import downward only.** capture <- gestures <- engine <- mapping <- output <- app.
  Only capture/tracker.py imports MediaPipe. Only output/ imports Quartz.
  Only app/ imports rumps. Landmarks never leave capture/ and gestures/
  (the HUD feed carries them to the page; nothing in Python consumes them).
- **ui/ reads the runtime; the runtime never reads ui/.** ui/ imports
  app/runtime.py and app/config.py; only app/menubar.py imports ui/. Only
  ui/window.py imports WebKit.
- **Nothing per-client runs without a client.** The preview image, the
  engine subscription, and the frame loop start on the first websocket
  and stop on the last close (ui/wire.py Publisher). The server thread
  itself starts on the first Configure and then idles. The page's live
  view is off by default (remembered per page); off closes the socket.
- **The page never trusts itself about keys.** Chords are validated by
  the app (output/keys.py) before a document is saved, and a saved
  document is parsed by the same loader the mapper uses.
- **A gesture is one class with `score()` (and `anchor()` if continuous),
  registered in `gestures/registry.py`.** Thresholds, hysteresis, timing,
  per-hand instances, and delta tracking belong to `gestures/base.py`.
  Do not add per-gesture timing or smoothing code.
- **Axes are in user space**: x grows to the user's right, y upward, angle
  counter-clockwise as seen in the mirror. The engine flips once. Nothing
  downstream flips again.
- **Normalize by hand size.** Any distance a gesture scores or reports is
  divided by `hand_size()`.
- **Two thresholds, not one.** Enter above exit.
- **Actions are data** (`mapping/actions.py`); performing them is `output/`'s
  job. The mapper never imports Quartz. Tests use a recording fake performer.
- **Off means the camera is free.** The master switch releases the camera
  in the capture thread (Alex, 2026-09-15: a video call must be able to
  take it). Nothing else may hold the camera open while disabled, the HUD
  included.
- **A hold-key binding's trigger is "engage" or "hold".** Engage (the
  default) puts the key down as soon as the gesture engages; hold waits
  for the held phase (hold_ms after engage), so a passing pose cannot
  fire it (Alex, 2026-09-15: the point gesture was triggering by
  accident). Either way the key stays down until release. Other trigger
  values on a hold-key binding behave as engage.
- **Held keys never stick.** Anything that can stop the mapper (disable,
  reload, quit) goes through `Mapper.release_all()`.
- **Bindings serialize.** New binding fields get a default and a JSON key
  matching the template's camelCase. The document version stays 2 unless an
  old file would misbehave.
- **Keep the engine a faithful port.** If a behavior changes here, change it
  in the template too, or note the divergence in both CLAUDE.md files.
- **Comments say why, docstrings say what.** Every module opens with a
  docstring naming what it owns. No commentary inside functions unless the
  line would puzzle a reader.
- No em dashes anywhere in prose or comments.

## On-disk state

`~/Library/Application Support/gesture-mac/config.json` (enabled, camera
name, frame rates, HUD port) and `mappings.json` (seeded from
`presets/default.json` on first run). The HUD panel writes mappings.json
and hot-reloads; hand edits need Reload mappings in the menu.

## Keeping the page and the app in step

The wire format lives in two places by hand: `gesture_mac/ui/wire.py` and
`ui/web/src/types.ts`. A new action kind touches mapping/actions.py, the
performer, both of those, and ui/web/src/bindings.ts (KINDS, the Action
section of renderDetail, summary(), and startDraft's default). A new key
token touches output/keys.py and the code table in ui/web/src/keys.ts.
A new binding is a draft in the page until Save, because the app rejects
a document whose key chord is empty; edits to an existing binding write
through at once. Threshold edits from the panel are live and unsaved, the
same as the template.

## Things that are guesses until tuned with a real hand

Pinch closeness bounds (0.2 to 0.5 hand lengths), One Euro constants, flick
thresholds (0.6 hand lengths within 500 ms), the pose classifier's looseness
on Point and Thumbs up, the frame rates in config (15 active, 4 idle), and
the camera index mapping in capture/cameras.py (assumes OpenCV and
AVFoundation enumerate in the same order).

## Environment notes

- MediaPipe 1.0.x on Python 3.12 via uv. The model file lives in
  `models/gesture_recognizer.task` (gitignored; downloaded on first run from
  Google's CDN if missing).
- The process posting events needs Accessibility permission: System
  Settings > Privacy & Security > Accessibility, add the terminal the app
  was launched from (or the .app once packaged). Without it, events are
  silently dropped.
- MediaPipe handedness assumes a selfie-view source. `flip_handedness` in
  config exists for a non-selfie camera.
- Synthesized right-option (flagsChanged with the right-side device bit)
  was verified to toggle superwhisper on 2026-09-15.

## Known behavior

- Pinching while the app's own menu is open toggles superwhisper but the
  paste on release lands nowhere: an open menu holds keyboard focus. Not a
  bug. (Observed by Alex, 2026-09-15.)
