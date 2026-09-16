# VISION: gesture-mac

## What this is

A Mac menu-bar app that turns webcam hand gestures into a new peripheral. A
pinch is a key, a pinch-and-drag is a scroll wheel, a pose is a shortcut.
BetterTouchTool is the model for the interface: every gesture, hand, and
action is a binding the user edits, not a rule the app hardcodes.

The first user is Alex, and the first job is one binding: a right-hand
index pinch holds the right option key, which is superwhisper's dictation
hotkey. A short pinch taps it (toggle dictation), a long pinch holds it
(dictate, then paste on release). Superwhisper does the tap/hold logic; the
app only makes the key follow the pinch.

## Why native

The sibling repo, gesture-template (~/dev/gesture-template), is the same
gesture engine in TypeScript for web apps. A browser cannot press keys or
scroll other apps, so the Mac side is a Python process with the engine
ported one to one, driving macOS through Quartz CGEvents.

## Milestones

1. **Pinch to dictate.** Menu bar with an on/off toggle at the top, camera
   picker, the engine port with tests, bindings JSON, hold-key and press-key
   actions, the default preset. Usable daily. (This prototype.)
2. **HUD and mapping panel.** A local web page served by the app, reusing
   the template's hud/ and panel/ modules over a websocket. Frame encoding
   and streaming run only while the page is open.
3. **Continuous axes.** Scroll from pinch-and-drag deltas. Volume. The
   performer for scroll exists already; the bindings need the panel to be
   worth editing.
4. **Pointer mode**, if landmark jitter permits. Stretch.

## Non-goals, for now

- A login item. Launched by hand until it earns autostart.
- A global hotkey for the on/off toggle. Wanted eventually; needs a free chord.
- Packaging as a .app bundle. `uv run gesture-mac` is enough.

## Principles carried from the template

Data flows one way (capture -> gestures -> engine -> mapping -> output).
A gesture is one class with score() and anchor(); timing lives in the base
class. Axes are in user space, normalized by hand size, with two thresholds
for hysteresis. Bindings serialize, and the JSON schema stays compatible
with the template's version-2 MappingDocument.

## Provenance

Design record in Alex's exocortex vault: wiki/projects/gesture-peripheral-mac.md
and the 2026-09-15 session captures. Decision to build native: Alex,
2026-09-15. Synthesized right-option verified against superwhisper the same day.
