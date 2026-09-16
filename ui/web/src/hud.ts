/**
 * Mirror-mode view: the app's JPEG frames, flipped like a mirror, with
 * hand landmarks drawn on top, per-hand gesture scores, and the drag
 * origin of any engaged continuous gesture (raw point and filtered point,
 * so you can see the filter working). Ported from gesture-template's
 * hud/Hud.ts; the frame and states arrive over the socket instead of
 * from a local engine, and the landmark drawing is our own twenty lines
 * so the page does not ship MediaPipe just to draw a skeleton.
 */
import type { Remote } from "./remote";
import type { DeltaMsg, FrameMsg, HandInfo, HandKey } from "./types";

const COLORS = { left: "#4cc9f0", right: "#f72585", both: "#ffd166" } as const;

/** MediaPipe's hand skeleton: which of the 21 landmarks connect. */
const CONNECTIONS: Array<[number, number]> = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [0, 17], [17, 18], [18, 19], [19, 20],
];

export class Hud {
  readonly root: HTMLElement;
  private readonly img: HTMLImageElement;
  private readonly canvas: HTMLCanvasElement;
  private readonly ctx: CanvasRenderingContext2D;
  private readonly remote: Remote;
  private lastDeltas = new Map<string, DeltaMsg>();
  private frames = 0;
  private fpsAt = performance.now();
  fps = 0;

  constructor(remote: Remote, mount: HTMLElement) {
    this.remote = remote;
    this.root = document.createElement("div");
    this.root.className = "hud";
    this.img = document.createElement("img");
    this.img.alt = "";
    this.canvas = document.createElement("canvas");
    this.root.append(this.img, this.canvas);
    mount.append(this.root);
    this.ctx = this.canvas.getContext("2d")!;

    remote.on("delta", (e) => this.lastDeltas.set(`${e.gestureId}:${e.hand}`, e));
    remote.on("gesture", (e) => { if (e.phase === "release") this.lastDeltas.delete(`${e.gestureId}:${e.hand}`); });
    remote.on("frame", (f) => this.render(f));
    remote.on("status", (up) => { if (!up) this.lastDeltas.clear(); });
  }

  private render(frame: FrameMsg): void {
    if (frame.width === 0) return;
    this.frames++;
    const now = performance.now();
    if (now - this.fpsAt >= 1000) {
      this.fps = (this.frames * 1000) / (now - this.fpsAt);
      this.frames = 0;
      this.fpsAt = now;
    }
    if (frame.image) this.img.src = `data:image/jpeg;base64,${frame.image}`;

    const { canvas, ctx } = this;
    if (canvas.width !== frame.width || canvas.height !== frame.height) {
      canvas.width = frame.width;
      canvas.height = frame.height;
      this.root.style.setProperty("--video-aspect", String(frame.width / frame.height));
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Landmarks are in raw (unmirrored) image space; the canvas is mirrored by
    // CSS alongside the image, so we draw unflipped and let CSS flip both.
    for (const hand of frame.hands) this.drawHand(hand);
    for (const d of this.lastDeltas.values()) this.drawDrag(d);

    // Text must read correctly, so it is drawn in a counter-flipped context.
    ctx.save();
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    this.drawScores(frame);
    ctx.restore();
  }

  private drawHand(hand: HandInfo): void {
    const { ctx, canvas } = this;
    const color = COLORS[hand.handedness];
    const pts = hand.landmarks.map(([x, y]) => [x * canvas.width, y * canvas.height] as const);
    ctx.strokeStyle = color;
    ctx.lineWidth = 4;
    ctx.beginPath();
    for (const [a, b] of CONNECTIONS) {
      const p = pts[a], q = pts[b];
      if (!p || !q) continue;
      ctx.moveTo(p[0], p[1]);
      ctx.lineTo(q[0], q[1]);
    }
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1;
    for (const [x, y] of pts) {
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }
  }

  private drawDrag(d: DeltaMsg): void {
    const { ctx, canvas } = this;
    const color = COLORS[d.hand];
    const px = (p: [number, number]) => [p[0] * canvas.width, p[1] * canvas.height] as const;
    const [rx, ry] = px(d.raw);
    const [fx, fy] = px(d.filtered);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(rx, ry, 10, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(fx, fy, 6, 0, Math.PI * 2);
    ctx.fill();
  }

  private drawScores(frame: FrameMsg): void {
    const { ctx } = this;
    // Scale text with the canvas so it reads the same at any video size.
    const fs = Math.round(this.canvas.width / 60);
    ctx.font = `${fs}px ui-monospace, monospace`;
    ctx.textBaseline = "top";
    const columns = { left: fs, right: this.canvas.width - fs * 24, both: this.canvas.width / 2 - fs * 12 } as const;
    const seen = new Set<string>();
    for (const hand of frame.hands) {
      if (seen.has(hand.handedness)) continue;
      seen.add(hand.handedness);
      this.drawColumn(frame, hand.handedness, columns[hand.handedness], fs, `${hand.handedness.toUpperCase()}  pose=${hand.poseLabel} ${hand.poseScore.toFixed(2)}`);
    }
    if (frame.hands.length >= 2) this.drawColumn(frame, "both", columns.both, fs, "BOTH");
  }

  private drawColumn(frame: FrameMsg, hand: HandKey, x: number, fs: number, title: string): void {
    const { ctx } = this;
    let y = fs;
    ctx.fillStyle = COLORS[hand];
    ctx.fillText(title, x, y);
    y += fs * 1.3;
    for (const g of this.remote.gestures) {
      if (g.bimanual !== (hand === "both")) continue;
      const st = frame.states[`${g.id}:${hand}`];
      if (!st) continue;
      const engaged = st.state === "active" || st.state === "held";
      ctx.fillStyle = engaged ? "#ffd166" : "rgba(255,255,255,0.75)";
      const bar = "#".repeat(Math.round(st.score * 10)).padEnd(10, "·");
      ctx.fillText(`${g.label.padEnd(13)} ${bar} ${st.state}`, x, y);
      y += fs * 1.2;
    }
    const d = [...this.lastDeltas.values()].find((e) => e.hand === hand);
    if (d) {
      ctx.fillStyle = "#ffd166";
      const v = d.delta;
      ctx.fillText(`Δ x=${v.x.toFixed(2)} y=${v.y.toFixed(2)} a=${v.angle.toFixed(2)} s=${v.scale.toFixed(2)}`, x, y);
    }
  }
}
