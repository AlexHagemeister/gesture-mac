/**
 * The live readout beside the video: which hands are in view, the pose
 * the model sees, and every gesture that is currently past idle (a
 * candidate filling toward engage, or active/held), with its score bar.
 * Idle gestures are not listed, so the readout stays short as the
 * gesture list grows. Text lives in the DOM, not on the camera canvas,
 * so it reads the same over any background.
 */
import type { Remote } from "./remote";
import type { DeltaMsg, FrameMsg, HandKey } from "./types";

const ORDER: HandKey[] = ["left", "right", "both"];

export class Live {
  readonly root: HTMLElement;
  private readonly remote: Remote;
  private readonly deltas = new Map<string, DeltaMsg>();

  constructor(remote: Remote, mount: HTMLElement) {
    this.remote = remote;
    this.root = document.createElement("div");
    this.root.className = "live-readout";
    mount.append(this.root);
    remote.on("delta", (e) => this.deltas.set(`${e.gestureId}:${e.hand}`, e));
    remote.on("gesture", (e) => { if (e.phase === "release") this.deltas.delete(`${e.gestureId}:${e.hand}`); });
    remote.on("frame", (f) => this.render(f));
    remote.on("status", (up) => { if (!up) { this.deltas.clear(); this.empty("Disconnected"); } });
    this.empty("No hands in view");
  }

  private empty(text: string): void {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = text;
    this.root.replaceChildren(p);
  }

  private render(frame: FrameMsg): void {
    if (frame.hands.length === 0) { this.empty("No hands in view"); return; }
    const blocks: HTMLElement[] = [];
    for (const key of ORDER) {
      const hand = frame.hands.find((h) => h.handedness === key);
      if (key === "both" ? frame.hands.length < 2 : !hand) continue;
      const block = document.createElement("div");
      block.className = `hand ${key}`;
      const title = document.createElement("div");
      title.className = "hand-title";
      title.textContent = hand ? `${key} hand · ${hand.poseLabel.replace(/_/g, " ").toLowerCase()} ${hand.poseScore.toFixed(2)}` : "both hands";
      block.append(title);

      let listed = 0;
      for (const g of this.remote.gestures) {
        if (g.bimanual !== (key === "both")) continue;
        const st = frame.states[`${g.id}:${key}`];
        if (!st || st.state === "idle") continue;
        listed++;
        const row = document.createElement("div");
        row.className = `g ${st.state}`;
        const label = document.createElement("span");
        label.className = "label";
        label.textContent = g.label;
        const bar = document.createElement("span");
        bar.className = "bar";
        const fill = document.createElement("i");
        fill.style.width = `${Math.round(st.score * 100)}%`;
        bar.append(fill);
        const state = document.createElement("span");
        state.className = "state";
        state.textContent = st.state;
        row.append(label, bar, state);
        block.append(row);
      }
      if (listed === 0) {
        const none = document.createElement("div");
        none.className = "muted";
        none.textContent = "no gesture";
        block.append(none);
      }
      const d = [...this.deltas.values()].find((e) => e.hand === key);
      if (d) {
        const line = document.createElement("div");
        line.className = "delta";
        line.textContent = `Δ x ${d.delta.x.toFixed(2)}  y ${d.delta.y.toFixed(2)}  angle ${d.delta.angle.toFixed(2)}  scale ${d.delta.scale.toFixed(2)}  ·  at x ${d.abs.x.toFixed(2)}  y ${d.abs.y.toFixed(2)}`;
        block.append(line);
      }
      blocks.push(block);
    }
    this.root.replaceChildren(...blocks);
  }
}
