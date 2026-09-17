/**
 * The bindings editor, laid out like BetterTouchTool: every binding in a
 * list on the left (gesture, hand, what it does), and the selected one
 * opened in a detail pane. A binding row is a gesture-plus-hand that
 * drives a control; the control holds the action (hold a key, press a
 * key, scroll, click, move the pointer). Two rows can share one control, and the pane says so.
 *
 * Edits to an existing binding save as they are made (the app validates,
 * writes mappings.json, and hot-reloads). A new binding is a draft in
 * the pane until Save, since a key chord has to exist before the app
 * will accept the document. Thresholds edit live and are not saved, the
 * same as the template.
 */
import { recordChord, type Recording } from "./keys";
import type { Remote } from "./remote";
import { handMatches, pointerRegion, type Action, type ActionType, type Binding, type Control, type HandKey, type HandSelector, type MappingDocument, type MouseButton, type PointerMode, type PointerRegion, type ScrollAxis, type Smoothing, type Thresholds, type Trigger } from "./types";

const SINGLE_HANDS: Array<[HandSelector, string]> = [["either", "either hand"], ["left", "left hand"], ["right", "right hand"]];
const KINDS: Array<[ActionType, string]> = [["hold-key", "hold a key"], ["press-key", "press a key"], ["scroll", "scroll"], ["click", "click the mouse"], ["pointer", "move the pointer"]];
const BUTTONS: Array<[MouseButton, string]> = [["left", "left button"], ["right", "right button"], ["middle", "middle button"]];
const CLICK: Action = { type: "click", button: "left", count: 1 };
const POINTER: Action = { type: "pointer", gain: 2, offsetX: 0, offsetY: 0 };
const POINTER_MODES: Array<[PointerMode, string]> = [
  ["absolute", "absolute (finger position is cursor position)"],
  ["relative", "relative (trackpad: finger motion moves the cursor)"],
];
const GAIN_HELP = "How far the cursor travels for a given finger travel, in screen widths per camera-frame width. "
  + "1: moving your finger across the whole camera view moves the cursor across the whole screen. "
  + "2: half the view does it (faster, coarser). 0.5: it takes two passes (slower, finer).";
const ABS_GAIN_HELP = "How much of the camera view covers the screen: 1 is the whole view, 2 the middle half, 3 the middle third. "
  + "Higher means smaller hand moves (and more visible jitter).";
const OFFSET_X_HELP = "Slides the active region left or right, as a fraction of the view. 0 is centered; positive is to your right, negative to your left.";
const OFFSET_Y_HELP = "Slides the active region up or down, as a fraction of the view. 0 is centered; positive is up, negative is down. "
  + "Raise it so the bottom of the screen is reached before your hand drops out of view.";
const PRESS_TRIGGERS: Array<[Trigger, string]> = [
  ["engage", "on engage"], ["hold", "after held"], ["release", "on release"],
  ["flick-left", "flick left"], ["flick-right", "flick right"], ["flick-up", "flick up"], ["flick-down", "flick down"],
];
const KEY_HINT = "e.g. right-option, cmd+shift+4";
const DRAFT = "__draft__";

interface Draft { binding: Binding; control: Control }

export class Bindings {
  readonly list: HTMLElement;
  readonly detail: HTMLElement;
  private readonly remote: Remote;
  private selectedId: string | null = null;
  private draft: Draft | null = null;
  private recording: Recording | null = null;
  private readonly rowsEl: HTMLElement;
  private readonly errorEl: HTMLElement;
  private readonly engaged = new Set<string>();

  constructor(remote: Remote, listMount: HTMLElement, detailMount: HTMLElement) {
    this.remote = remote;
    this.list = el("section", "bindings-list");
    this.detail = el("section", "binding-detail");
    listMount.append(this.list);
    detailMount.append(this.detail);

    this.rowsEl = el("div", "rows");
    this.errorEl = el("p", "error");
    const foot = el("div", "row foot");
    foot.append(
      button("+ New binding", () => this.startDraft(), "primary"),
      button("Export", () => download("gesture-mappings.json", JSON.stringify(remote.doc, null, 2))),
      button("Import", () => upload((text) => this.commit(() => JSON.parse(text) as MappingDocument))),
    );
    this.list.append(h("Bindings"), this.rowsEl, foot);

    this.selectedId = remote.doc.bindings[0]?.id ?? null;
    this.renderAll();
    remote.on("mappings", () => this.renderAll());
    remote.on("thresholds", () => this.renderDetail());
    remote.on("smoothing", () => this.renderDetail());
    remote.on("gesture", (e) => {
      if (e.phase === "engage" || e.phase === "flick") this.flashRows(e.gestureId, e.hand);
    });
    remote.on("frame", (f) => {
      const now = new Set(Object.entries(f.states).filter(([, s]) => s.state === "active" || s.state === "held").map(([k]) => k));
      if (!sameSet(now, this.engaged)) {
        this.engaged.clear();
        for (const k of now) this.engaged.add(k);
        this.markLiveRows();
      }
    });
  }

  private renderAll(): void {
    this.errorEl.textContent = "";
    this.renderList();
    this.renderDetail();
  }

  // ---- writes ------------------------------------------------------------

  /** Apply a change to a copy of the document and save it. On rejection
   * the app's reason shows in the pane and nothing changes. */
  private async commit(change: (doc: MappingDocument) => MappingDocument | void): Promise<boolean> {
    const copy = structuredClone(this.remote.doc);
    const next = change(copy) ?? copy;
    try {
      await this.remote.save(next);
      this.errorEl.textContent = "";
      this.renderAll();
      return true;
    } catch (err) {
      this.errorEl.textContent = (err as Error).message;
      return false;
    }
  }

  private gesture(id: string) {
    return this.remote.gestures.find((g) => g.id === id);
  }

  private control(id: string): Control | undefined {
    return this.remote.doc.controls.find((c) => c.id === id);
  }

  /** The region the selected binding maps to the screen, when it is an
   * absolute pointer; the HUD draws it over the video. */
  pointerRegion(): PointerRegion | null {
    const sel = this.selected();
    const a = sel?.control?.action;
    if (!sel || !a || a.type !== "pointer" || sel.binding.mode === "relative") return null;
    const [left, top, right, bottom] = pointerRegion(a.gain ?? 2, a.offsetX ?? 0, a.offsetY ?? 0);
    return { gestureId: sel.binding.gestureId, hand: sel.binding.hand, left, top, right, bottom };
  }

  private selected(): { binding: Binding; control: Control | undefined; draft: boolean } | null {
    if (this.draft) return { binding: this.draft.binding, control: this.draft.control, draft: true };
    const b = this.remote.doc.bindings.find((x) => x.id === this.selectedId);
    if (!b) return null;
    return { binding: b, control: this.control(b.controlId), draft: false };
  }

  // ---- the list ----------------------------------------------------------

  private renderList(): void {
    this.rowsEl.replaceChildren();
    const rows = this.remote.doc.bindings.map((b) => this.row(b));
    if (this.draft) rows.push(this.draftRow());
    if (rows.length === 0) {
      const p = el("p", "muted");
      p.textContent = "No bindings yet.";
      this.rowsEl.append(p);
    }
    this.rowsEl.append(...rows);
    this.markLiveRows();
  }

  private row(b: Binding): HTMLElement {
    const g = this.gesture(b.gestureId);
    const c = this.control(b.controlId);
    const row = el("div", "binding-row");
    row.dataset.id = b.id;
    row.dataset.key = `${b.gestureId}:${b.hand}`;
    if (b.id === this.selectedId && !this.draft) row.classList.add("selected");
    const title = el("div", "row-title");
    title.textContent = `${g?.label ?? b.gestureId} · ${handText(b.hand)}`;
    const sub = el("div", "row-sub");
    sub.textContent = c ? `Action: ${summary(c)}${triggerNote(b, c)}` : `Action: missing control ${b.controlId}`;
    if (b.while) {
      const w = el("div", "row-sub");
      w.textContent = `Only while ${this.gesture(b.while.gestureId)?.label ?? b.while.gestureId} (${handText(b.while.hand)})`;
      row.append(title, sub, w);
    } else row.append(title, sub);
    row.onclick = () => { this.cancelDraft(); this.selectedId = b.id; this.renderAll(); };
    return row;
  }

  private draftRow(): HTMLElement {
    const row = el("div", "binding-row selected draft");
    const title = el("div", "row-title");
    title.textContent = "New binding";
    const sub = el("div", "row-sub");
    sub.textContent = "unsaved";
    row.append(title, sub);
    return row;
  }

  private markLiveRows(): void {
    for (const row of this.rowsEl.querySelectorAll<HTMLElement>(".binding-row[data-key]")) {
      const [gid, hand] = row.dataset.key!.split(":") as [string, HandSelector];
      const live = [...this.engaged].some((k) => {
        const [g, h] = k.split(":") as [string, HandKey];
        return g === gid && handMatches(hand, h);
      });
      row.classList.toggle("live", live);
    }
  }

  private flashRows(gestureId: string, hand: HandKey): void {
    for (const row of this.rowsEl.querySelectorAll<HTMLElement>(".binding-row[data-key]")) {
      const [gid, sel] = row.dataset.key!.split(":") as [string, HandSelector];
      if (gid !== gestureId || !handMatches(sel, hand)) continue;
      row.classList.add("flash");
      setTimeout(() => row.classList.remove("flash"), 150);
    }
  }

  // ---- drafts ------------------------------------------------------------

  private startDraft(): void {
    const g = this.remote.gestures[0];
    if (!g) return;
    this.draft = {
      binding: newBinding(g.id, g.bimanual ? "both" : "either", DRAFT),
      control: { id: DRAFT, label: "", kind: "action", action: g.continuous ? { type: "scroll", axis: "y", sensitivity: 40, invert: false } : { type: "hold-key", key: "" } },
    };
    this.selectedId = null;
    this.renderAll();
  }

  private cancelDraft(): void {
    this.draft = null;
    this.recording?.cancel();
    this.recording = null;
  }

  private async saveDraft(): Promise<void> {
    const d = this.draft;
    if (!d) return;
    const a = d.control.action!;
    if ("key" in a) {
      const problem = a.key ? await this.remote.validateKey(a.key) : "type or record a key";
      if (problem) { this.errorEl.textContent = problem; return; }
    }
    const g = this.gesture(d.binding.gestureId);
    const label = d.control.label.trim() || `${g?.label ?? "gesture"} ${"key" in a ? a.key : a.type}`;
    const ok = await this.commit((doc) => {
      const id = uniqueId(slug(label), doc.controls);
      doc.controls.push({ id, label, kind: "action", action: a });
      doc.bindings.push({ ...d.binding, controlId: id });
      this.selectedId = d.binding.id;
    });
    if (ok) this.draft = null;
    this.renderAll();
  }

  // ---- the detail pane ---------------------------------------------------

  private renderDetail(): void {
    const pane = this.detail;
    pane.replaceChildren();
    this.recording?.cancel();
    this.recording = null;
    const sel = this.selected();
    if (!sel) {
      pane.append(this.errorEl);
      const p = el("p", "muted");
      p.textContent = "Select a binding, or add one.";
      pane.append(p);
      return;
    }
    const { binding: b, control: c, draft } = sel;
    const g = this.gesture(b.gestureId);

    // Edits: a draft mutates in place and waits for Save; an existing
    // binding writes through at once.
    const updBinding = (patch: Partial<Binding>) => {
      if (draft) { Object.assign(b, patch); this.renderAll(); return; }
      void this.commit((doc) => { const t = doc.bindings.find((x) => x.id === b.id); if (t) Object.assign(t, patch); });
    };
    const setAction = (next: Action) => {
      if (!c) return;
      if (draft) { c.action = next; this.renderDetail(); return; }
      void this.commit((doc) => { const t = doc.controls.find((x) => x.id === c.id); if (t) t.action = next; });
    };
    const setLabel = (label: string) => {
      if (!c) return;
      if (draft) { c.label = label; return; }
      void this.commit((doc) => { const t = doc.controls.find((x) => x.id === c.id); if (t) t.label = label; });
    };

    const head = el("div", "detail-head");
    const title = el("h2");
    title.textContent = draft ? "New binding" : `${g?.label ?? b.gestureId} · ${handText(b.hand)}`;
    head.append(title);
    if (draft) head.append(button("Cancel", () => { this.cancelDraft(); this.selectedId = this.remote.doc.bindings[0]?.id ?? null; this.renderAll(); }), button("Save binding", () => void this.saveDraft(), "primary"));
    else head.append(button("Delete", () => void this.commit((doc) => {
      doc.bindings = doc.bindings.filter((x) => x.id !== b.id);
      if (!doc.bindings.some((x) => x.controlId === b.controlId)) doc.controls = doc.controls.filter((x) => x.id !== b.controlId);
      this.selectedId = doc.bindings[0]?.id ?? null;
    }), "danger"));
    pane.append(head, this.errorEl);

    // Gesture and hand.
    const gsec = section("Gesture");
    const bimanual = g?.bimanual ?? false;
    const grow = el("div", "row");
    grow.append(
      labeled("Gesture", select(this.remote.gestures.map((x) => [x.id, x.label]), b.gestureId, (v) => {
        const ng = this.gesture(v);
        const hand: HandSelector = ng?.bimanual ? "both" : (b.hand === "both" ? "either" : b.hand);
        if (draft && (c?.action?.type === "scroll" || c?.action?.type === "pointer") && !ng?.continuous) c.action = { type: "hold-key", key: "" };
        updBinding({ gestureId: v, hand });
      })),
      labeled("Hand", select(bimanual ? [["both", "both hands"]] : SINGLE_HANDS, b.hand, (v) => updBinding({ hand: v as HandSelector }))),
    );
    const hint = el("p", "hint");
    hint.textContent = g?.hint ?? "";
    gsec.append(grow, hint);
    pane.append(gsec);

    // Action.
    const asec = section("Action");
    if (!c) {
      const p = el("p", "error");
      p.textContent = `This binding points at a control that no longer exists (${b.controlId}). Delete it.`;
      asec.append(p);
    } else if (!c.action) {
      const p = el("p", "muted");
      p.textContent = `${c.kind} (a template control; does nothing on the Mac)`;
      asec.append(p);
    } else {
      const a = c.action;
      const arow = el("div", "row");
      arow.append(labeled("Kind", select(KINDS, a.type, (v) => {
        const kind = v as ActionType;
        if (kind === "scroll") setAction({ type: "scroll", axis: "y", sensitivity: 40, invert: false });
        else if (kind === "pointer") { setAction(POINTER); if (b.mode !== "absolute") updBinding({ mode: "absolute" }); }
        else if (kind === "click") setAction(CLICK);
        else if (!("key" in a)) {
          // Switching from scroll or click to a key: no key yet, so the
          // change waits in a draft-like state until a key is recorded.
          if (draft) setAction({ type: kind, key: "" });
          else { this.errorEl.textContent = "Record a key first, then switch the kind."; this.renderDetail(); }
        } else setAction({ type: kind, key: a.key });
      })));
      const nameIn = document.createElement("input");
      nameIn.type = "text";
      nameIn.placeholder = "name (optional)";
      nameIn.value = c.label === c.id && !draft ? c.label : c.label;
      nameIn.onchange = () => setLabel(nameIn.value.trim());
      arow.append(labeled("Name", nameIn));
      asec.append(arow);

      if (a.type === "hold-key" || a.type === "press-key") asec.append(this.keyEditor(a, draft, setAction));
      else if (a.type === "click") {
        const crow = el("div", "row");
        crow.append(
          labeled("Button", select(BUTTONS, a.button, (v) => setAction({ ...a, button: v as MouseButton }))),
          labeled("Clicks", select([["1", "single"], ["2", "double"]], String(a.count), (v) => setAction({ ...a, count: v === "2" ? 2 : 1 }))),
        );
        const p = el("p", "hint");
        p.textContent = "Clicks wherever the cursor is. Moving it is a pointer binding's job.";
        asec.append(crow, p);
      } else if (a.type === "pointer") {
        const relative = b.mode === "relative";
        const mrow = el("div", "row");
        mrow.append(labeled("Mode", select(POINTER_MODES, relative ? "relative" : "absolute", (v) => updBinding({ mode: v as PointerMode }))));
        const p = el("p", "hint");
        if (relative) {
          // Gain is the only knob of the trackpad feel, so it gets its own
          // explanation both as a tooltip on the label and as fixed text.
          mrow.append(labeled("Gain", numberInput(a.gain ?? 2, 0.1, 20, 0.1, (v) => setAction({ ...a, gain: v })), GAIN_HELP));
          p.textContent = "Engage, move, release, reposition, like a trackpad: the cursor starts from wherever it is and moves by your finger's travel times the gain. "
            + "Gain 1 means the whole camera view is one screen width; raise it for speed, lower it for precision. Smoothed fingertip position.";
          asec.append(mrow, p);
        } else {
          mrow.append(
            labeled("Gain", numberInput(a.gain ?? 2, 1, 10, 0.1, (v) => setAction({ ...a, gain: v })), ABS_GAIN_HELP),
            labeled("Offset (left/right)", numberInput(a.offsetX ?? 0, -0.5, 0.5, 0.05, (v) => setAction({ ...a, offsetX: v })), OFFSET_X_HELP),
            labeled("Offset (up/down)", numberInput(a.offsetY ?? 0, -0.5, 0.5, 0.05, (v) => setAction({ ...a, offsetY: v })), OFFSET_Y_HELP),
          );
          p.textContent = "The finger's position in a region of the camera view is the cursor's position on the screen. "
            + "Gain sets the region's size (2: the middle half of the view is the whole screen). The offsets slide it from the middle: "
            + "0 is centered, positive is right or up, negative is left or down. It is held inside the view. Smoothed fingertip position.";
          asec.append(mrow, p);
        }
      } else {
        const srow = el("div", "row");
        srow.append(
          labeled("Axis", select([["y", "y (up/down)"], ["x", "x (left/right)"]], a.axis, (v) => setAction({ ...a, axis: v as ScrollAxis }))),
          labeled("Sensitivity", numberInput(a.sensitivity, 1, 500, 5, (v) => setAction({ ...a, sensitivity: v }))),
          labeled("Invert", checkbox(a.invert, (v) => setAction({ ...a, invert: v }))),
        );
        asec.append(srow);
      }
      const shared = this.remote.doc.bindings.filter((x) => x.controlId === c.id && x.id !== b.id).length;
      if (shared > 0) {
        const p = el("p", "hint");
        p.textContent = `This action is shared with ${shared} other binding${shared > 1 ? "s" : ""}; editing it here changes those too.`;
        asec.append(p);
      }
    }
    pane.append(asec);

    // When it fires.
    const kind = c?.action?.type;
    if (kind === "hold-key" || kind === "press-key" || kind === "click") {
      const tsec = section("When");
      const trow = el("div", "row");
      const holdMs = g?.thresholds.holdMs ?? 0;
      if (kind === "hold-key") {
        trow.append(labeled("Key goes down", select([
          ["engage", "as soon as the gesture engages"],
          ["hold", `only after it is held (${holdMs} ms)`],
        ], b.trigger === "hold" ? "hold" : "engage", (v) => updBinding({ trigger: v as Trigger }))));
        const p = el("p", "hint");
        p.textContent = "Either way the key stays down until the gesture releases. \"After held\" ignores a passing pose.";
        tsec.append(trow, p);
      } else {
        trow.append(labeled(kind === "click" ? "Click" : "Press", select(PRESS_TRIGGERS, b.trigger, (v) => updBinding({ trigger: v as Trigger }))));
        tsec.append(trow);
      }
      pane.append(tsec);
    }

    // Modifier.
    const msec = section("Modifier");
    const mrow = el("div", "row");
    const others = this.remote.gestures.filter((x) => x.id !== b.gestureId);
    const modHand = select([["either", "either hand"], ["left", "left hand"], ["right", "right hand"], ["both", "both hands"]], b.while?.hand ?? "either", (v) => {
      if (b.while) updBinding({ while: { gestureId: b.while.gestureId, hand: v as HandSelector } });
    });
    mrow.append(labeled("Only while", select([["", "no other gesture"], ...others.map((x) => [x.id, x.label] as [string, string])], b.while?.gestureId ?? "", (v) => {
      updBinding(v ? { while: { gestureId: v, hand: modHand.value as HandSelector } } : { while: undefined });
    })));
    if (b.while) mrow.append(labeled("is engaged on", modHand));
    msec.append(mrow);
    pane.append(msec);

    // Tuning for this gesture.
    if (g) {
      const tsec = section(`Tuning: ${g.label}`);
      const grid = el("div", "thresholds");
      const field = (key: keyof Thresholds, label: string, min: number, max: number, step: number) =>
        labeled(label, numberInput(g.thresholds[key], min, max, step, (v) => { this.remote.setThresholds(g.id, { [key]: v }).catch((e: Error) => { this.errorEl.textContent = e.message; }); }));
      grid.append(
        field("enter", "Enter score", 0, 1, 0.05),
        field("exit", "Exit score", 0, 1, 0.05),
        field("onsetMs", "Onset delay (ms)", 0, 2000, 10),
        field("holdMs", "Hold time (ms)", 0, 5000, 50),
      );
      const note = el("p", "hint");
      note.textContent = "Applies to every binding on this gesture. Live until the app restarts; not saved.";
      tsec.append(grid, note);
      pane.append(tsec);
    }

    // Smoothing, shared by every continuous gesture.
    if (g?.continuous) {
      const ssec = section("Smoothing");
      const grid = el("div", "thresholds");
      const sm = this.remote.smoothing;
      const field = (key: keyof Smoothing, label: string, min: number, max: number, step: number, help: string) =>
        labeled(label, numberInput(sm[key], min, max, step, (v) => { this.remote.setSmoothing({ [key]: v }).catch((e: Error) => { this.errorEl.textContent = e.message; }); }), help);
      grid.append(
        field("minCutoff", "Slow moves", 0.1, 30, 0.5, "How closely it follows a slow or resting hand. Higher trails less on precise moves and shivers more when you hold still. 1 is about 160 ms behind, 3 about 50 ms."),
        field("dCutoff", "Pickup", 0.1, 30, 0.5, "How quickly it notices a move starting and loosens up. Higher reacts sooner and is twitchier on a shaky hand."),
        field("beta", "Fast moves", 0, 200, 5, "How much it loosens as the hand speeds up. Higher trails less on sweeps. 20 is already near raw at a brisk speed."),
      );
      const note = el("p", "hint");
      note.textContent = "Higher is snappier, lower is steadier. Applies to every continuous gesture, and to a move already in progress. Live until the app restarts; not saved.";
      ssec.append(grid, note);
      pane.append(ssec);
    }
  }

  /** The key field: type a chord name, or press Record and press the keys. */
  private keyEditor(a: Extract<Action, { key: string }>, draft: boolean, setAction: (next: Action) => void): HTMLElement {
    const wrap = el("div", "key-editor");
    const row = el("div", "row");
    const key = document.createElement("input");
    key.type = "text";
    key.value = a.key;
    key.placeholder = KEY_HINT;
    key.className = "key";
    const err = el("p", "error");
    const apply = async (chord: string) => {
      const problem = await this.remote.validateKey(chord);
      key.classList.toggle("invalid", !!problem);
      err.textContent = problem ?? "";
      if (!problem) setAction({ type: a.type, key: chord });
      else if (draft) setAction({ type: a.type, key: chord });
    };
    key.onchange = () => void apply(key.value.trim());
    const rec = button("Record", () => {
      if (this.recording) { this.recording.cancel(); this.recording = null; rec.textContent = "Record"; rec.classList.remove("on"); return; }
      rec.textContent = "Press keys…";
      rec.classList.add("on");
      key.value = "";
      this.recording = recordChord(wrap, (chord) => {
        this.recording = null;
        rec.textContent = "Record";
        rec.classList.remove("on");
        key.value = chord;
        void apply(chord);
      }, (partial) => { key.value = partial; });
    });
    wrap.tabIndex = -1;
    row.append(labeled(a.type === "hold-key" ? "Key to hold" : "Key to press", key), rec);
    wrap.append(row, err);
    return wrap;
  }
}

// ---- document helpers --------------------------------------------------------

function newBinding(gestureId: string, hand: HandSelector, controlId: string): Binding {
  return { id: `b${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`, gestureId, hand, controlId, trigger: "engage", axis: "y", mode: "relative", sensitivity: 100, invert: false };
}

function summary(c: Control): string {
  const a = c.action;
  if (!a) return c.kind;
  if (a.type === "hold-key") return `hold ${a.key}`;
  if (a.type === "press-key") return `press ${a.key}`;
  if (a.type === "click") return `${a.count === 2 ? "double-click" : "click"} ${a.button}`;
  if (a.type === "pointer") return `move the pointer (gain ${a.gain ?? 2}, offset ${a.offsetX ?? 0} × ${a.offsetY ?? 0})`;
  return `scroll ${a.axis} ×${a.sensitivity}${a.invert ? " inverted" : ""}`;
}

function triggerNote(b: Binding, c: Control): string {
  const t = c.action?.type;
  if (t === "hold-key") return b.trigger === "hold" ? " (after held)" : "";
  if (t === "press-key" || t === "click") return ` (${PRESS_TRIGGERS.find(([k]) => k === b.trigger)?.[1] ?? b.trigger})`;
  return "";
}

function handText(h: HandSelector): string {
  return h === "either" ? "either hand" : h === "both" ? "both hands" : `${h} hand`;
}

function sameSet(a: Set<string>, b: Set<string>): boolean {
  if (a.size !== b.size) return false;
  for (const x of a) if (!b.has(x)) return false;
  return true;
}

// ---- tiny DOM helpers ------------------------------------------------------

function el(tag: string, className = ""): HTMLElement {
  const e = document.createElement(tag);
  if (className) e.className = className;
  return e;
}

function h(text: string): HTMLElement {
  const e = el("h3");
  e.textContent = text;
  return e;
}

function section(title: string): HTMLElement {
  const s = el("div", "section");
  s.append(h(title));
  return s;
}

function labeled(label: string, input: HTMLElement, help = ""): HTMLElement {
  const l = el("label");
  const s = el("span");
  s.textContent = label;
  if (help) {
    // A small circled i whose tooltip carries the explanation, so any
    // parameter can get one without widening the row.
    const i = el("span", "info");
    i.textContent = "i";
    i.title = help;
    l.title = help;
    s.append(" ", i);
  }
  l.append(s, input);
  return l;
}

function select(options: Array<[string, string]>, value: string, onChange: (v: string) => void): HTMLSelectElement {
  const s = document.createElement("select");
  for (const [v, text] of options) {
    const o = document.createElement("option");
    o.value = v; o.textContent = text;
    s.append(o);
  }
  s.value = value;
  s.onchange = () => onChange(s.value);
  return s;
}

function numberInput(value: number, min: number, max: number, step: number, onChange: (v: number) => void): HTMLInputElement {
  const i = document.createElement("input");
  i.type = "number";
  i.min = String(min); i.max = String(max); i.step = String(step); i.value = String(value);
  i.onchange = () => onChange(Number(i.value));
  return i;
}

function checkbox(value: boolean, onChange: (v: boolean) => void): HTMLInputElement {
  const i = document.createElement("input");
  i.type = "checkbox";
  i.checked = value;
  i.onchange = () => onChange(i.checked);
  return i;
}

function button(text: string, onClick: () => void, className = ""): HTMLButtonElement {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = text;
  if (className) b.className = className;
  b.onclick = onClick;
  return b;
}

function slug(s: string): string {
  return s.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "control";
}

function uniqueId(base: string, existing: Control[]): string {
  const ids = new Set(existing.map((c) => c.id));
  if (!ids.has(base)) return base;
  let n = 2;
  while (ids.has(`${base}-${n}`)) n++;
  return `${base}-${n}`;
}

function download(name: string, text: string): void {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

function upload(onText: (text: string) => void): void {
  const i = document.createElement("input");
  i.type = "file";
  i.accept = "application/json";
  i.onchange = () => i.files?.[0]?.text().then(onText);
  i.click();
}
