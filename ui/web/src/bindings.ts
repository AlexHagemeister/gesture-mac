/**
 * The bindings editor, laid out like BetterTouchTool: every binding in a
 * list on the left (gesture, hand, what it does), and the selected one
 * opened in a detail pane. A binding row is a gesture-plus-hand that
 * drives a control; the control holds the action (hold a key, press a
 * key, scroll). Two rows can share one control, and the pane says so.
 *
 * Edits to an existing binding save as they are made (the app validates,
 * writes mappings.json, and hot-reloads). A new binding is a draft in
 * the pane until Save, since a key chord has to exist before the app
 * will accept the document. Thresholds edit live and are not saved, the
 * same as the template.
 */
import { recordChord, type Recording } from "./keys";
import type { Remote } from "./remote";
import { handMatches, type Action, type ActionType, type Binding, type Control, type HandKey, type HandSelector, type MappingDocument, type ScrollAxis, type Thresholds, type Trigger } from "./types";

const SINGLE_HANDS: Array<[HandSelector, string]> = [["either", "either hand"], ["left", "left hand"], ["right", "right hand"]];
const KINDS: Array<[ActionType, string]> = [["hold-key", "hold a key"], ["press-key", "press a key"], ["scroll", "scroll"]];
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
    if (a.type !== "scroll") {
      const problem = a.key ? await this.remote.validateKey(a.key) : "type or record a key";
      if (problem) { this.errorEl.textContent = problem; return; }
    }
    const g = this.gesture(d.binding.gestureId);
    const label = d.control.label.trim() || `${g?.label ?? "gesture"} ${a.type === "scroll" ? "scroll" : a.key}`;
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
        if (draft && c?.action?.type === "scroll" && !ng?.continuous) c.action = { type: "hold-key", key: "" };
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
        else if (a.type === "scroll") {
          // Switching from scroll to a key: no key yet, so the change waits
          // in a draft-like state until a key is recorded.
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
      else {
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
    if (kind === "hold-key" || kind === "press-key") {
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
        trow.append(labeled("Press", select(PRESS_TRIGGERS, b.trigger, (v) => updBinding({ trigger: v as Trigger }))));
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
  return `scroll ${a.axis} ×${a.sensitivity}${a.invert ? " inverted" : ""}`;
}

function triggerNote(b: Binding, c: Control): string {
  const t = c.action?.type;
  if (t === "hold-key") return b.trigger === "hold" ? " (after held)" : "";
  if (t === "press-key") return ` (${PRESS_TRIGGERS.find(([k]) => k === b.trigger)?.[1] ?? b.trigger})`;
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

function labeled(label: string, input: HTMLElement): HTMLElement {
  const l = el("label");
  const s = el("span");
  s.textContent = label;
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
