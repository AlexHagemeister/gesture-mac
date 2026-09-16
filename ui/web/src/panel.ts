/**
 * The mapping panel: pick a gesture and hand, see every binding it has,
 * add more (to a new or existing control), edit each control's action,
 * and tune the gesture's thresholds live. Ported from gesture-template's
 * panel/Panel.ts. What changed for the Mac: a control is an action
 * (hold-key, press-key, scroll) instead of a demo widget, key chords are
 * checked by the app before they are saved, and every edit writes
 * mappings.json through the app, which hot-reloads it.
 */
import type { Remote } from "./remote";
import { handMatches, type Action, type ActionType, type Binding, type Control, type HandSelector, type MappingDocument, type ScrollAxis, type Thresholds, type Trigger } from "./types";

const SINGLE_HANDS: HandSelector[] = ["either", "left", "right"];
const KINDS: Array<[ActionType, string]> = [["hold-key", "hold a key"], ["press-key", "press a key"], ["scroll", "scroll"]];
const TRIGGERS: Trigger[] = ["engage", "hold", "release", "flick-left", "flick-right", "flick-up", "flick-down"];
const KEY_HINT = "e.g. right-option, cmd+shift+4";

export class Panel {
  readonly root: HTMLElement;
  private readonly remote: Remote;
  private gestureId: string;
  private hand: HandSelector = "either";
  private readonly pickerEl: HTMLElement;
  private readonly controlsEl: HTMLElement;
  private readonly mappingEl: HTMLElement;
  private readonly thresholdsEl: HTMLElement;
  private readonly errorEl: HTMLElement;

  constructor(remote: Remote, mount: HTMLElement) {
    this.remote = remote;
    this.gestureId = remote.gestures[0]?.id ?? "";
    this.root = el("section", "panel");
    mount.append(this.root);

    this.pickerEl = el("div", "row");
    this.mappingEl = el("div", "mapping");
    this.thresholdsEl = el("div", "thresholds");
    this.controlsEl = el("div", "controls");
    this.errorEl = el("p", "error");

    const io = el("div", "row io");
    io.append(
      button("Export JSON", () => download("gesture-mappings.json", JSON.stringify(remote.doc, null, 2))),
      button("Import JSON", () => upload((text) => this.commit(() => JSON.parse(text) as MappingDocument))),
    );

    this.root.append(this.errorEl, h("Mapping"), this.pickerEl, this.mappingEl, h("Thresholds"), this.thresholdsEl, h("Controls"), this.controlsEl, io);
    this.renderAll();
    remote.on("mappings", () => this.renderAll());
    remote.on("thresholds", (m) => { if (m.gestureId === this.gestureId) this.renderThresholds(); });
    remote.on("gesture", (e) => {
      if (e.phase === "engage" || e.phase === "flick") this.flashBoundControls(e.gestureId, e.hand);
    });
  }

  private renderAll(): void {
    this.renderPicker();
    this.renderMapping();
    this.renderThresholds();
    this.renderControls();
  }

  // ---- writes ------------------------------------------------------------

  /** Apply a change to a copy of the document and save it. On rejection
   * the app's reason shows at the top and the panel re-renders unchanged. */
  private async commit(change: (doc: MappingDocument) => MappingDocument | void): Promise<void> {
    const copy = structuredClone(this.remote.doc);
    const next = change(copy) ?? copy;
    try {
      await this.remote.save(next);
      this.errorEl.textContent = "";
    } catch (err) {
      this.errorEl.textContent = (err as Error).message;
    }
    this.renderAll();
  }

  private gesture(id = this.gestureId) {
    return this.remote.gestures.find((g) => g.id === id);
  }

  private control(id: string): Control | undefined {
    return this.remote.doc.controls.find((c) => c.id === id);
  }

  // ---- gesture + hand picker ---------------------------------------------

  private renderPicker(): void {
    const g = this.gesture();
    const bimanual = g?.bimanual ?? false;
    if (bimanual) this.hand = "both";
    else if (this.hand === "both") this.hand = "either";
    this.pickerEl.replaceChildren(
      labeled("Gesture", select(this.remote.gestures.map((x) => [x.id, x.label]), this.gestureId, (v) => { this.gestureId = v; this.renderPicker(); this.renderMapping(); this.renderThresholds(); })),
      labeled("Hand", select(bimanual ? [["both", "both"]] : SINGLE_HANDS.map((x) => [x, x]), this.hand, (v) => { this.hand = v as HandSelector; this.renderMapping(); })),
    );
  }

  // ---- mapping editor ----------------------------------------------------

  private renderMapping(): void {
    const m = this.mappingEl;
    m.replaceChildren();
    const gesture = this.gesture();
    const hint = el("p", "hint");
    hint.textContent = gesture?.hint ?? "";
    m.append(hint);

    for (const b of this.remote.doc.bindings.filter((x) => x.gestureId === this.gestureId && x.hand === this.hand)) m.append(this.bindingRow(b));

    // Add row: new control, or an existing one.
    const add = el("div", "row add");
    const kindSel = select(KINDS.map(([k, t]) => [k, `new: ${t}`]), gesture?.continuous ? "scroll" : "hold-key", () => { keyIn.style.display = kindSel.value === "scroll" ? "none" : ""; });
    const nameIn = document.createElement("input");
    nameIn.placeholder = "control name";
    nameIn.size = 14;
    const keyIn = document.createElement("input");
    keyIn.type = "text";
    keyIn.placeholder = KEY_HINT;
    keyIn.size = 18;
    keyIn.style.display = kindSel.value === "scroll" ? "none" : "";
    const keyErr = el("p", "error");
    add.append(labeled("Add", kindSel), nameIn, keyIn, button("Add mapping", async () => {
      const kind = kindSel.value as ActionType;
      const label = nameIn.value.trim() || `${gesture?.label ?? "control"} ${kind}`;
      let action: Action;
      if (kind === "scroll") action = { type: "scroll", axis: "y", sensitivity: 40, invert: false };
      else {
        const key = keyIn.value.trim();
        const err = key ? await this.remote.validateKey(key) : "type a key chord";
        if (err) { keyErr.textContent = err; keyIn.classList.add("invalid"); return; }
        action = { type: kind, key };
      }
      await this.commit((doc) => {
        const id = uniqueId(slug(label), doc.controls);
        doc.controls.push({ id, label, kind: "action", action });
        doc.bindings.push(newBinding(this.gestureId, this.hand, id));
      });
    }));
    m.append(add, keyErr);

    const existing = this.remote.doc.controls;
    if (existing.length) {
      const row = el("div", "row add");
      const sel = select(existing.map((c) => [c.id, `${c.label} (${summary(c)})`]), existing[0]!.id, () => {});
      row.append(labeled("Or map to existing", sel), button("Add", () => this.commit((doc) => { doc.bindings.push(newBinding(this.gestureId, this.hand, sel.value)); })));
      m.append(row);
    }
  }

  private bindingRow(b: Binding): HTMLElement {
    const c = this.control(b.controlId);
    const row = el("div", "binding");
    const head = el("div", "row");
    const title = el("span", "binding-title");
    title.textContent = c ? `→ ${c.label} (${summary(c)})` : `→ missing control ${b.controlId}`;
    head.append(title, button("×", () => this.commit((doc) => { doc.bindings = doc.bindings.filter((x) => x.id !== b.id); }), "remove-inline"));
    row.append(head);

    const opts = el("div", "row");
    const upd = (patch: Partial<Binding>) => this.commit((doc) => {
      const target = doc.bindings.find((x) => x.id === b.id);
      if (target) Object.assign(target, patch);
    });
    const kind = c?.action?.type;
    if (kind === "press-key") {
      opts.append(labeled("Trigger", select(TRIGGERS.map((t) => [t, t]), b.trigger ?? "engage", (v) => upd({ trigger: v as Trigger }))));
    }
    if (kind === "hold-key") {
      const note = el("span", "summary");
      note.textContent = "held for the gesture's lifetime";
      opts.append(note);
    }
    if (kind === "scroll") {
      opts.append(labeled("Invert", checkbox(b.invert ?? false, (v) => upd({ invert: v }))));
    }
    // Modifier: only while another gesture is engaged.
    const others = this.remote.gestures.filter((g) => g.id !== this.gestureId);
    const modSel = select([["", "none"], ...others.map((g) => [g.id, g.label] as [string, string])], b.while?.gestureId ?? "", (v) => {
      upd(v ? { while: { gestureId: v, hand: modHand.value as HandSelector } } : { while: undefined });
    });
    const modHand = select([["either", "either"], ["left", "left"], ["right", "right"], ["both", "both"]], b.while?.hand ?? "either", (v) => {
      if (b.while) upd({ while: { gestureId: b.while.gestureId, hand: v as HandSelector } });
    });
    opts.append(labeled("Only while", modSel));
    if (b.while) opts.append(labeled("on hand", modHand));
    row.append(opts);
    return row;
  }

  // ---- thresholds --------------------------------------------------------

  private renderThresholds(): void {
    const t = this.thresholdsEl;
    t.replaceChildren();
    const g = this.gesture();
    if (!g) return;
    const field = (key: keyof Thresholds, label: string, min: number, max: number, step: number) =>
      labeled(label, numberInput(g.thresholds[key], min, max, step, (v) => { this.remote.setThresholds(g.id, { [key]: v }).catch((e: Error) => { this.errorEl.textContent = e.message; }); }));
    t.append(
      field("enter", "Enter score", 0, 1, 0.05),
      field("exit", "Exit score", 0, 1, 0.05),
      field("onsetMs", "Onset delay (ms)", 0, 2000, 10),
      field("holdMs", "Hold time (ms)", 0, 5000, 50),
    );
    const note = el("p", "hint");
    note.textContent = "Live until the app restarts; not saved (tune, then change the constant in the gesture class).";
    t.append(note);
  }

  // ---- controls ----------------------------------------------------------

  private renderControls(): void {
    this.controlsEl.replaceChildren();
    for (const c of this.remote.doc.controls) this.controlsEl.append(this.controlCard(c));
  }

  private controlCard(c: Control): HTMLElement {
    const card = el("div", `control ${c.action?.type ?? c.kind}`);
    card.dataset.id = c.id;
    const title = el("div", "title");
    title.textContent = c.label;
    const body = el("div", "body action-fields");
    card.append(title, body);
    this.fillAction(body, c);
    card.append(button("×", () => this.commit((doc) => {
      doc.controls = doc.controls.filter((x) => x.id !== c.id);
      doc.bindings = doc.bindings.filter((x) => x.controlId !== c.id);
    }), "remove"));
    return card;
  }

  private fillAction(body: HTMLElement, c: Control): void {
    const a = c.action;
    if (!a) {
      const s = el("span", "summary");
      s.textContent = `${c.kind} (template control, inert on the Mac)`;
      body.append(s);
      return;
    }
    const setAction = (next: Action) => this.commit((doc) => {
      const target = doc.controls.find((x) => x.id === c.id);
      if (target) target.action = next;
    });
    if (a.type === "hold-key" || a.type === "press-key") {
      const key = document.createElement("input");
      key.type = "text";
      key.value = a.key;
      key.placeholder = KEY_HINT;
      const err = el("p", "error");
      key.onchange = async () => {
        const problem = await this.remote.validateKey(key.value.trim());
        key.classList.toggle("invalid", !!problem);
        err.textContent = problem ?? "";
        if (!problem) setAction({ type: a.type, key: key.value.trim() });
      };
      body.append(labeled(a.type === "hold-key" ? "Hold key" : "Press key", key), err);
    } else {
      body.append(
        labeled("Axis", select([["y", "y (up/down)"], ["x", "x (left/right)"]], a.axis, (v) => setAction({ ...a, axis: v as ScrollAxis }))),
        labeled("Sensitivity", numberInput(a.sensitivity, 1, 500, 5, (v) => setAction({ ...a, sensitivity: v }))),
        labeled("Invert", checkbox(a.invert, (v) => setAction({ ...a, invert: v }))),
      );
    }
  }

  private flashBoundControls(gestureId: string, hand: "left" | "right" | "both"): void {
    for (const b of this.remote.doc.bindings) {
      if (b.gestureId !== gestureId || !handMatches(b.hand, hand)) continue;
      const card = this.controlsEl.querySelector<HTMLElement>(`[data-id="${CSS.escape(b.controlId)}"]`);
      if (!card) continue;
      card.classList.add("flash");
      setTimeout(() => card.classList.remove("flash"), 150);
    }
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
