"""Hold-key bindings follow the pinch's lifetime (or start at the held
phase with trigger "hold"); disabling releases held keys; press-key fires
once on its trigger."""
from gesture_mac.engine import GestureEngine
from gesture_mac.gestures.builtin.pinches import IndexPinch
from gesture_mac.gestures.builtin.poses import Fist
from gesture_mac.mapping import Mapper, MappingDocument, parse_action
from gesture_mac.mapping.bindings import Binding, Control, document_to_json, parse_document

from .synth import frame, hand


class Recorder:
    def __init__(self):
        self.log: list[tuple] = []

    def key_down(self, chord):
        self.log.append(("down", chord))

    def key_up(self, chord):
        self.log.append(("up", chord))

    def key_press(self, chord):
        self.log.append(("press", chord))

    def scroll(self, dx, dy):
        self.log.append(("scroll", round(dx, 3), round(dy, 3)))


def doc_with_hold(hand_sel="right"):
    return MappingDocument(
        controls=[Control("dictate", "Superwhisper", "action", parse_action({"type": "hold-key", "key": "right-option"}))],
        bindings=[Binding("b1", "index-pinch", hand_sel, "dictate")],
    )


def pinch_cycle(engine, t0=0):
    for t in range(t0, t0 + 100, 10):
        engine.update(frame(t, [hand(0.05)]))
    engine.update(frame(t0 + 110, [hand(1.0)]))


def test_hold_key_follows_pinch():
    engine = GestureEngine([IndexPinch()])
    rec = Recorder()
    Mapper(engine, doc_with_hold(), rec)
    pinch_cycle(engine)
    assert rec.log == [("down", "right-option"), ("up", "right-option")]


def test_hold_key_with_hold_trigger_waits_for_the_held_phase():
    engine = GestureEngine([IndexPinch()])
    rec = Recorder()
    doc = doc_with_hold()
    doc.bindings[0].trigger = "hold"
    Mapper(engine, doc, rec)
    # A short pinch (released before hold_ms) presses nothing.
    pinch_cycle(engine)
    assert rec.log == []
    # A long one goes down at the held phase and up on release.
    for t in range(1000, 1700, 10):
        engine.update(frame(t, [hand(0.05)]))
    assert rec.log == [("down", "right-option")]
    engine.update(frame(1710, [hand(1.0)]))
    assert rec.log == [("down", "right-option"), ("up", "right-option")]


def test_wrong_hand_does_nothing():
    engine = GestureEngine([IndexPinch()])
    rec = Recorder()
    Mapper(engine, doc_with_hold("left"), rec)
    pinch_cycle(engine)
    assert rec.log == []


def test_disable_releases_held_key_and_blocks_new():
    engine = GestureEngine([IndexPinch()])
    rec = Recorder()
    m = Mapper(engine, doc_with_hold(), rec)
    for t in range(0, 100, 10):
        engine.update(frame(t, [hand(0.05)]))
    assert rec.log == [("down", "right-option")]
    m.set_enabled(False)
    assert rec.log[-1] == ("up", "right-option")
    engine.update(frame(110, [hand(1.0)]))  # release while disabled: no double up
    pinch_cycle(engine, 200)
    assert rec.log == [("down", "right-option"), ("up", "right-option")]


def test_press_key_fires_once_on_trigger():
    engine = GestureEngine([Fist()])
    rec = Recorder()
    doc = MappingDocument(
        controls=[Control("shot", "Screenshot", "action", parse_action({"type": "press-key", "key": "cmd+shift+4"}))],
        bindings=[Binding("b1", "fist", "either", "shot", trigger="hold")],
    )
    Mapper(engine, doc, rec)
    fist = hand(1.0)
    fist.pose_label, fist.pose_score = "Closed_Fist", 0.95
    for t in range(0, 700, 10):
        engine.update(frame(t, [fist]))
    assert rec.log == [("press", "cmd+shift+4")]


def test_document_round_trips():
    raw = {
        "version": 2,
        "controls": [
            {"id": "vol", "label": "Volume", "kind": "slider", "value": 50, "min": 0, "max": 100},
            {"id": "d", "label": "Dictate", "kind": "action", "action": {"type": "hold-key", "key": "right-option"}},
        ],
        "bindings": [
            {"id": "b1", "gestureId": "index-pinch", "hand": "right", "controlId": "d", "trigger": "engage",
             "axis": "y", "mode": "relative", "sensitivity": 100.0, "invert": False,
             "while": {"gestureId": "fist", "hand": "left"}}
        ],
    }
    doc = parse_document(raw)
    assert doc.control("vol").extra == {"value": 50, "min": 0, "max": 100}
    assert doc.bindings[0].while_.gesture_id == "fist"
    assert document_to_json(doc) == raw
