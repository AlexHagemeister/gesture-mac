"""The bindings document: JSON on disk, version 2, the same schema as
gesture-template's MappingDocument so presets move between the two.

    {
      "version": 2,
      "controls": [
        {"id": "dictate", "label": "Superwhisper", "kind": "action",
         "action": {"type": "hold-key", "key": "right-option"}}
      ],
      "bindings": [
        {"id": "b1", "gestureId": "index-pinch", "hand": "right",
         "controlId": "dictate", "trigger": "engage"}
      ]
    }

Control kinds "button", "toggle", "slider" from the template load and are
kept in the document (so a template preset round-trips) but do nothing on
the Mac side. Kind "action" is the Mac addition. Binding fields are the
template's, camelCase in JSON, snake_case here.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from ..capture.types import HandSelector
from .actions import Action, action_to_json, parse_action

Trigger = Literal["engage", "hold", "release", "flick-left", "flick-right", "flick-up", "flick-down"]


@dataclass(slots=True)
class Control:
    id: str
    label: str
    kind: str
    action: Action | None = None
    """Set when kind == "action"."""
    extra: dict = field(default_factory=dict)
    """Fields of non-action kinds, kept verbatim for round-tripping."""


@dataclass(slots=True)
class While:
    gesture_id: str
    hand: HandSelector


@dataclass(slots=True)
class Binding:
    id: str
    gesture_id: str
    hand: HandSelector
    control_id: str
    trigger: Trigger = "engage"
    """Press actions: which event fires them. Hold actions ignore it."""
    axis: str = "y"
    mode: str = "relative"
    sensitivity: float = 100.0
    invert: bool = False
    while_: While | None = None
    """Only apply while this other gesture is engaged (a modifier hand)."""


@dataclass(slots=True)
class MappingDocument:
    controls: list[Control] = field(default_factory=list)
    bindings: list[Binding] = field(default_factory=list)
    version: int = 2

    def control(self, control_id: str) -> Control | None:
        return next((c for c in self.controls if c.id == control_id), None)


def parse_document(raw: dict) -> MappingDocument:
    if raw.get("version") != 2:
        raise ValueError(f"unsupported mapping document version: {raw.get('version')!r}")
    controls = []
    for c in raw.get("controls", []):
        known = {"id", "label", "kind", "action"}
        extra = {k: v for k, v in c.items() if k not in known}
        action = parse_action(c["action"]) if c.get("kind") == "action" else None
        controls.append(Control(c["id"], c.get("label", c["id"]), c["kind"], action, extra))
    bindings = []
    for b in raw.get("bindings", []):
        w = b.get("while")
        bindings.append(
            Binding(
                id=b["id"],
                gesture_id=b["gestureId"],
                hand=b.get("hand", "either"),
                control_id=b["controlId"],
                trigger=b.get("trigger", "engage"),
                axis=b.get("axis", "y"),
                mode=b.get("mode", "relative"),
                sensitivity=float(b.get("sensitivity", 100)),
                invert=bool(b.get("invert", False)),
                while_=While(w["gestureId"], w["hand"]) if w else None,
            )
        )
    return MappingDocument(controls, bindings)


def document_to_json(doc: MappingDocument) -> dict:
    controls = []
    for c in doc.controls:
        d = {"id": c.id, "label": c.label, "kind": c.kind, **c.extra}
        if c.action is not None:
            d["action"] = action_to_json(c.action)
        controls.append(d)
    bindings = []
    for b in doc.bindings:
        d = {
            "id": b.id,
            "gestureId": b.gesture_id,
            "hand": b.hand,
            "controlId": b.control_id,
            "trigger": b.trigger,
            "axis": b.axis,
            "mode": b.mode,
            "sensitivity": b.sensitivity,
            "invert": b.invert,
        }
        if b.while_:
            d["while"] = {"gestureId": b.while_.gesture_id, "hand": b.while_.hand}
        bindings.append(d)
    return {"version": 2, "controls": controls, "bindings": bindings}


def load_document(path: Path) -> MappingDocument:
    return parse_document(json.loads(path.read_text()))


def save_document(doc: MappingDocument, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document_to_json(doc), indent=2) + "\n")
