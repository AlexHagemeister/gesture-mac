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
  | { type: "pointer"; gain: number; offsetX: number; offsetY: number };
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

/** The selected absolute pointer binding's region, for the HUD to draw:
 * edges as fractions of the mirrored view from its top left (user space,
 * the same as gesture_mac/mapping/actions.py Pointer.region()). */
export interface PointerRegion {
  gestureId: string;
  hand: HandSelector;
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/** Pointer.region() from actions.py, kept in step by hand: 1/gain of the
 * view around the middle, moved by the offsets (positive right and up),
 * slid inward so it never leaves the view. */
export function pointerRegion(gain: number, offsetX: number, offsetY: number): [number, number, number, number] {
  const half = 0.5 / Math.max(gain, 1);
  const cx = Math.min(Math.max(0.5 + offsetX, half), 1 - half);
  const cy = Math.min(Math.max(0.5 - offsetY, half), 1 - half);
  return [cx - half, cy - half, cx + half, cy + half];
}

/** True when a binding's hand selector covers an event's hand key. */
export function handMatches(selector: HandSelector, hand: HandKey): boolean {
  return selector === hand || (selector === "either" && hand !== "both");
}
