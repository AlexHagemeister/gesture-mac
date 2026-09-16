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

Menu: **Gestures enabled** (the master switch, top of the menu), status
line, **Camera** picker, **Reload mappings**, **Open mappings.json**, Quit.

## Default binding

Right-hand index pinch holds the right option key for as long as the pinch
lasts. With superwhisper bound to right option: a short pinch toggles
dictation, a long pinch dictates and pastes on release.

## Edit bindings

`~/Library/Application Support/gesture-mac/mappings.json`, then Reload
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
presets/     default.json, the seed for a fresh install
tests/       headless: engine, mapper, key chords
```
