"""gesture-mac: webcam hand gestures as a Mac peripheral.

Packages, in data-flow order. Each may import only from the ones above it.

    capture   camera + MediaPipe -> Frame (hands with landmarks, handedness, pose label)
    gestures  Gesture classes: score() and anchor(), plus the shared state machine
    engine    runs gestures per hand each frame, emits gesture and delta events
    mapping   bindings (JSON) from (gesture, hand, trigger) to actions
    output    performs actions on macOS: keys, scroll, volume (CGEvent via PyObjC)
    app       config and the runtime thread tying the layers together, plus the menu bar
    ui        the HUD page: local HTTP + websocket server and the WebKit window

ui/ sits between app/runtime.py and app/menubar.py: it reads the runtime
and the config, and only the menu bar imports it. The runtime never imports ui.

Only capture/tracker.py imports MediaPipe. Only output/ imports Quartz.
Only app/ imports rumps. Only ui/window.py imports WebKit. Landmarks never
leave capture/, gestures/, and the HUD feed.
"""
