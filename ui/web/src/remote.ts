/**
 * The page's one connection to the app: the initial state over HTTP, the
 * live stream over the websocket, and the writes (mappings, key checks,
 * thresholds) back over HTTP. Holds the current gesture list and mapping
 * document so the HUD and panel read from one place.
 */
import type { GestureInfo, MappingDocument, Msg, StateResponse, Thresholds } from "./types";

type Listener<T> = (msg: T) => void;
type Kind = Msg["type"] | "status";
type MsgOf<K extends Msg["type"]> = Extract<Msg, { type: K }>;

export class Remote {
  gestures: GestureInfo[] = [];
  doc: MappingDocument = { version: 2, controls: [], bindings: [] };
  mappingsPath = "";
  connected = false;
  private listeners = new Map<Kind, Set<Listener<never>>>();
  private socket: WebSocket | null = null;
  private closed = false;

  async init(): Promise<void> {
    const state = await this.getJson<StateResponse>("/api/state");
    this.gestures = state.gestures;
    this.doc = state.mappings;
    this.mappingsPath = state.mappingsPath;
  }

  on<K extends Msg["type"]>(kind: K, fn: Listener<MsgOf<K>>): () => void;
  on(kind: "status", fn: Listener<boolean>): () => void;
  on(kind: Kind, fn: Listener<never>): () => void {
    let set = this.listeners.get(kind);
    if (!set) { set = new Set(); this.listeners.set(kind, set); }
    set.add(fn);
    return () => { set!.delete(fn); };
  }

  private emit(kind: Kind, msg: unknown): void {
    for (const fn of this.listeners.get(kind) ?? []) (fn as Listener<unknown>)(msg);
  }

  connect(): void {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    this.socket = ws;
    ws.onopen = () => { this.connected = true; this.emit("status", true); };
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data as string) as Msg;
      if (msg.type === "mappings") this.doc = msg.mappings;
      if (msg.type === "thresholds") {
        const g = this.gestures.find((x) => x.id === msg.gestureId);
        if (g) g.thresholds = msg.thresholds;
      }
      this.emit(msg.type, msg);
    };
    ws.onclose = () => {
      this.connected = false;
      this.emit("status", false);
      if (!this.closed) setTimeout(() => this.connect(), 1000);
    };
  }

  close(): void {
    this.closed = true;
    this.socket?.close();
  }

  /** Replace the mapping document. The app validates, saves, hot-reloads. */
  async save(doc: MappingDocument): Promise<void> {
    this.doc = await this.sendJson<MappingDocument>("PUT", "/api/mappings", doc);
  }

  async validateKey(key: string): Promise<string | null> {
    const r = await this.sendJson<{ ok: boolean; error: string | null }>("POST", "/api/validate-key", { key });
    return r.ok ? null : (r.error ?? "invalid key");
  }

  async setThresholds(gestureId: string, patch: Partial<Thresholds>): Promise<void> {
    const t = await this.sendJson<Thresholds>("PUT", `/api/thresholds/${encodeURIComponent(gestureId)}`, patch);
    const g = this.gestures.find((x) => x.id === gestureId);
    if (g) g.thresholds = t;
  }

  private async getJson<T>(url: string): Promise<T> {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    return (await r.json()) as T;
  }

  private async sendJson<T>(method: string, url: string, body: unknown): Promise<T> {
    const r = await fetch(url, { method, headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
    const data = (await r.json()) as T & { error?: string };
    if (!r.ok) throw new Error(data.error ?? `${url}: ${r.status}`);
    return data;
  }
}
