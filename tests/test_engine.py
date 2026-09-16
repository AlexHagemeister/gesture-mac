"""Port of gesture-template's test/engine.smoke.ts: engage/hold/release
timing, hysteresis, user-space deltas, lost-hand release, flick."""
from gesture_mac.engine import GestureEngine
from gesture_mac.gestures.builtin.pinches import IndexPinch

from .synth import frame, hand


def make() -> tuple[GestureEngine, list[str], dict]:
    engine = GestureEngine([IndexPinch()])
    phases: list[str] = []
    last = {"dy": 0.0}
    engine.on("gesture", lambda e: phases.append(f"{e.phase}{'-' + e.direction if e.direction else ''}@{e.t:g}"))
    engine.on("delta", lambda e: last.__setitem__("dy", e.delta.y))
    return engine, phases, last


def test_onset_delay_and_hysteresis():
    engine, phases, _ = make()
    engine.update(frame(0, [hand(1.0)]))
    assert phases == []
    engine.update(frame(10, [hand(0.05)]))
    engine.update(frame(40, [hand(0.05)]))
    assert phases == [], "no engage before onset delay"
    engine.update(frame(80, [hand(0.05)]))
    assert phases == ["engage@80"]
    # gap 0.3 -> closeness 0.67, inside the band between exit and enter
    engine.update(frame(100, [hand(0.3)]))
    engine.update(frame(110, [hand(0.05)]))
    assert phases == ["engage@80"], "wobble inside the band must not release"


def test_hold_fires_after_hold_ms():
    engine, phases, _ = make()
    for t in range(0, 700, 10):
        engine.update(frame(t, [hand(0.05)]))
    assert phases == ["engage@60", "hold@560"]


def test_upward_move_is_positive_y_and_release():
    engine, phases, last = make()
    for t in range(0, 100, 10):
        engine.update(frame(t, [hand(0.05)]))
    for t in range(200, 700, 10):
        engine.update(frame(t, [hand(0.05, -0.2)]))
    assert 0.8 < last["dy"] < 1.2, last["dy"]
    engine.update(frame(710, [hand(1.0)]))
    assert phases[-1] == "release@710"


def test_lost_hand_releases():
    engine, phases, _ = make()
    engine.update(frame(800, [hand(0.05)]))
    engine.update(frame(900, [hand(0.05)]))
    engine.update(frame(1000, []))
    assert phases[-1] == "release@1000"


def test_flick_up():
    engine, phases, _ = make()
    engine.update(frame(2000, [hand(0.05)]))
    engine.update(frame(2100, [hand(0.05)]))
    for t in range(2110, 2300, 10):
        engine.update(frame(t, [hand(0.05, -0.2)]))
    engine.update(frame(2310, [hand(1.0)]))
    assert "flick-up@2310" in phases


def test_second_hand_with_same_label_is_ignored():
    engine, phases, _ = make()
    weak = hand(1.0)
    weak.handedness_score = 0.5
    for t in range(0, 100, 10):
        engine.update(frame(t, [weak, hand(0.05)]))
    assert phases == ["engage@60"]
