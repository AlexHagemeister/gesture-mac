/**
 * Record a key chord from the keyboard instead of typing its name. The
 * names produced are the ones gesture_mac/output/keys.py parses: sided
 * modifiers (left-option, right-cmd, ...) and the base-key tokens. The
 * browser reports which side a modifier was pressed on via KeyboardEvent
 * .code, which is what makes "right-option" recordable at all.
 *
 * Recording ends when a base key goes down (chord = modifiers + key) or
 * when the last held modifier comes up with no base key pressed (chord =
 * modifiers only, which is what superwhisper listens for).
 */

const MODIFIERS: Record<string, string> = {
  AltLeft: "left-option", AltRight: "right-option",
  ShiftLeft: "left-shift", ShiftRight: "right-shift",
  ControlLeft: "left-ctrl", ControlRight: "right-ctrl",
  MetaLeft: "left-cmd", MetaRight: "right-cmd",
};

const BASE: Record<string, string> = {
  Space: "space", Enter: "return", Tab: "tab", Escape: "escape",
  Backspace: "delete", Delete: "forwarddelete",
  ArrowLeft: "left", ArrowRight: "right", ArrowUp: "up", ArrowDown: "down",
  Home: "home", End: "end", PageUp: "pageup", PageDown: "pagedown", Help: "help",
  Minus: "-", Equal: "=", BracketLeft: "[", BracketRight: "]", Backslash: "\\",
  Semicolon: ";", Quote: "'", Comma: ",", Period: ".", Slash: "/", Backquote: "`",
};

/** Modifier name from an event: by .code (which side), or by .key plus
 * .location when a synthetic event carries no code. */
function modifierToken(e: KeyboardEvent): string | null {
  if (e.code in MODIFIERS) return MODIFIERS[e.code]!;
  const side = e.location === 2 ? "right" : "left";
  const byKey: Record<string, string> = { Alt: "option", Shift: "shift", Control: "ctrl", Meta: "cmd" };
  return e.key in byKey ? `${side}-${byKey[e.key]}` : null;
}

function baseToken(e: KeyboardEvent): string | null {
  const code = e.code || keyToCode(e.key);
  if (code in BASE) return BASE[code]!;
  let m = /^Key([A-Z])$/.exec(code);
  if (m) return m[1]!.toLowerCase();
  m = /^Digit([0-9])$/.exec(code);
  if (m) return m[1]!;
  m = /^F([0-9]{1,2})$/.exec(code);
  if (m && Number(m[1]) >= 1 && Number(m[1]) <= 20) return `f${m[1]}`;
  return null;
}

/** A .code guess for events that lack one (automation tools, some
 * synthetic events): single characters and the named keys we know. */
function keyToCode(key: string): string {
  if (/^[a-z]$/i.test(key)) return `Key${key.toUpperCase()}`;
  if (/^[0-9]$/.test(key)) return `Digit${key}`;
  if (/^F[0-9]{1,2}$/.test(key)) return key;
  const named: Record<string, string> = { " ": "Space", "-": "Minus", "=": "Equal", "[": "BracketLeft", "]": "BracketRight", "\\": "Backslash", ";": "Semicolon", "'": "Quote", ",": "Comma", ".": "Period", "/": "Slash", "`": "Backquote" };
  return named[key] ?? key;
}

export interface Recording {
  /** Stop listening without producing a chord. */
  cancel(): void;
}

/**
 * Listen on `target` until a chord is complete, then call `done` with its
 * name and stop. `progress` gets the partial chord as modifiers go down so
 * the UI can show what has been captured so far.
 */
export function recordChord(target: HTMLElement, done: (chord: string) => void, progress: (partial: string) => void): Recording {
  const held = new Set<string>();
  const seen: string[] = [];

  const finish = (chord: string) => {
    stop();
    done(chord);
  };
  const onDown = (e: KeyboardEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.repeat) return;
    const mod = modifierToken(e);
    if (mod) {
      held.add(mod);
      if (!seen.includes(mod)) seen.push(mod);
      progress(seen.join("+"));
      return;
    }
    // A chord sent all at once (modifier flags on the base key's event,
    // no modifier keydown of its own): read the flags.
    if (held.size === 0) {
      if (e.metaKey) seen.push("left-cmd");
      if (e.ctrlKey) seen.push("left-ctrl");
      if (e.altKey) seen.push("left-option");
      if (e.shiftKey) seen.push("left-shift");
    }
    const base = baseToken(e);
    if (base) finish([...seen, base].join("+"));
  };
  const onUp = (e: KeyboardEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const mod = modifierToken(e);
    if (!mod) return;
    held.delete(mod);
    if (held.size === 0 && seen.length) finish(seen.join("+"));
  };
  const onBlur = () => stop();
  const stop = () => {
    target.removeEventListener("keydown", onDown, true);
    target.removeEventListener("keyup", onUp, true);
    target.removeEventListener("blur", onBlur);
  };

  target.addEventListener("keydown", onDown, true);
  target.addEventListener("keyup", onUp, true);
  target.addEventListener("blur", onBlur);
  target.focus();
  return { cancel: stop };
}
