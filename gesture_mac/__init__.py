"""gesture-mac: webcam hand gestures as a Mac peripheral.

Packages, in data-flow order. Each may import only from the ones above it.

    capture   camera + MediaPipe -> Frame (hands with landmarks, handedness, pose label)
    gestures  Gesture classes: score() and anchor(), plus the shared state machine
    engine    runs gestures per hand each frame, emits gesture and delta events
    mapping   bindings (JSON) from (gesture, hand, trigger) to actions
    output    performs actions on macOS: keys, scroll, volume (CGEvent via PyObjC)
    app       the menu-bar shell, config, and the runtime thread tying it together

Only capture/tracker.py imports MediaPipe. Only output/ imports Quartz.
Only app/ imports rumps. Landmarks never leave capture/ and gestures/.
"""
