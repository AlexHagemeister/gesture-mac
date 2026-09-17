/**
 * The JSON the app speaks: the mapping document (gesture_mac/mapping/
 * bindings.py, camelCase on the wire), the gesture list, and the socket
 * messages (gesture_mac/ui/wire.py). Keep the two sides in step by hand.
 */
export type HandKey = "left" | "right" | "both";
export type HandSelector = HandKey | "either";
export type Trigger = "engage" | "hold" | "release" | "flick-left" | "flick-right" | "flick-up" | "flick-down";
export type Phase = "engage" | "hold" | "release" | "flick";
export type ScrollAxis = "x" | "y";
export type MouseButton = "left" | "right" | "middle";
export type PointerMode = "absolute" | "relative";

export type Action =
  | { type: "hold-key"; key: string }
  | { type: "press-key"; key: string }
  | { type: "scroll"; axis: ScrollAxis; sensitivity: number; invert: boolean }
  | { type: "click"; button: MouseButton; count: 1 | 2 }
  | { type: "pointer"; left: number; top: number; right: number; bottom: number; gain: number };
export type ActionType = Action["type"];

export interface Control {
  id: string;
  label: string;
  kind: string;
  action?: Action;
  [extra: string]: unknown;
}

export interface Binding {
  id: string;
  gestureId: string;
  hand: HandSelector;
  controlId: string;
  trigger: Trigger;
  axis: string;
  mode: string;
  sensitivity: number;
  invert: boolean;
  while?: { gestureId: string; hand: HandSelector };
}

export interface MappingDocument {
  version: 2;
  controls: Control[];
  bindings: Binding[];
}

export interface Thresholds { enter: number; exit: number; onsetMs: number; holdMs: number }

export interface GestureInfo {
  id: string;
  label: string;
  hint: string;
  continuous: boolean;
  bimanual: boolean;
  thresholds: Thresholds;
}

export interface StateResponse {
  gestures: GestureInfo[];
  mappings: MappingDocument;
  mappingsPath: string;
  enabled: boolean;
}

export interface HandInfo {
  handedness: "left" | "right";
  poseLabel: string;
  poseScore: number;
  landmarks: Array<[number, number]>;
}

export interface FrameMsg {
  type: "frame";
  t: number;
  width: number;
  height: number;
  image: string | null;
  hands: HandInfo[];
  states: Record<string, { state: string; score: number }>;
}

export interface GestureMsg {
  type: "gesture";
  gestureId: string;
  hand: HandKey;
  phase: Phase;
  t: number;
  score: number;
  direction: "left" | "right" | "up" | "down" | null;
}

export interface Axes { x: number; y: number; angle: number; scale: number }

export interface DeltaMsg {
  type: "delta";
  gestureId: string;
  hand: HandKey;
  t: number;
  delta: Axes;
  step: Axes;
  abs: Axes;
  raw: [number, number];
  filtered: [number, number];
}

export interface MappingsMsg { type: "mappings"; mappings: MappingDocument }
export interface ThresholdsMsg { type: "thresholds"; gestureId: string; thresholds: Thresholds }

export type Msg = FrameMsg | GestureMsg | DeltaMsg | MappingsMsg | ThresholdsMsg;

/** True when a binding's hand selector covers an event's hand key. */
export function handMatches(selector: HandSelector, hand: HandKey): boolean {
  return selector === hand || (selector === "either" && hand !== "both");
}
