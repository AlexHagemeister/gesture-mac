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

## Feel: affordances and feedback

Gesture control is a new kind of input for almost everyone who touches it,
its first user included. Nobody arrives with habits for it, so the app has
to teach itself and never leave the user guessing. These are directions,
not features:

- **Always answer "did it see me?"** Every state that matters (hand in
  view, gesture recognized, command fired) has a readout the user can
  catch without opening a window. Feedback comes in layers of rising
  attention: a glance, a moment, a watch, full detail.
- **Name what happened.** When a binding fires, the user can tell which
  one it was, by the name they gave it.
- **Feedback stays out of the way.** No feedback surface takes keyboard
  focus or clicks from the app the user is working in, and each one can
  be turned off.
- **Configuring is part of the experience.** Setting up a binding should
  feel as direct as using one: see the gesture, pick the action, try it,
  adjust. Tuning (thresholds, smoothing, pointer regions) is visible and
  live, not numbers edited blind.
- **Mistakes are cheap and legible.** An accidental trigger is a design
  problem, not user error. Prefer clutches, holds, and gates that make
  intent explicit, and make it clear why a gesture did or did not fire.
- **Don't double up.** When the target app already gives feedback
  (superwhisper's start sound and waveform), the app adds nothing on top.

## Why native

The sibling repo, gesture-template (~/dev/gesture-template), is the same
gesture engine in TypeScript for web apps. A browser cannot press keys or
scroll other apps, so the Mac side is a Python process with the engine
ported one to one, driving macOS through Quartz CGEvents.

## Milestones

1. **Pinch to dictate.** Menu bar with an on/off toggle at the top, camera
   picker, the engine port with tests, bindings JSON, hold-key and press-key
   actions, the default preset. Usable daily. (This prototype.)
2. **HUD and mapping panel.** A local web page served by the app, the
   template's hud/ and panel/ ported to run over a websocket, opened in
   an app-owned WebKit window from the menu. Frame encoding and streaming
   run only while the page is open. (Built 2026-09-15; the panel edits
   hold-key, press-key, and scroll controls. Relaid the same evening as
   a BetterTouchTool-style bindings list with a detail pane, a key
   recorder, and a readout of active gestures beside the video instead
   of text over it.)
3. **Continuous axes.** Scroll from pinch-and-drag deltas. Volume. The
   performer for scroll exists already; the bindings need the panel to be
   worth editing.
4. **Pointer mode**, if landmark jitter permits. Stretch.

## Non-goals, for now

- A full .app build. scripts/make-app.sh wraps `uv run` in a launcher
  bundle (2026-09-15) so the app runs without a terminal and can be a
  login item; a self-contained bundle is still parked.
- A global hotkey for the on/off toggle. Wanted eventually; needs a free chord.

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
Feel section: Alex, 2026-09-25, "especially given how experimental the app
is, like how it'll be a brand new experience so it needs to feel good and
intuitive to use and configure."
