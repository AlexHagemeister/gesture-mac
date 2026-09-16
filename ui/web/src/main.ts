/**
 * Page wiring: fetch state, mount the three regions (bindings list, the
 * selected binding's detail, the live view with its readout), open the
 * stream. The header line shows connection, frame rate, and hands in view.
 * The live view is optional: its toggle in the header opens and closes the
 * stream, and the choice is remembered in localStorage.
 */
import "./style.css";
import { Remote } from "./remote";
import { Hud } from "./hud";
import { Live } from "./live";
import { Bindings } from "./bindings";

async function main(): Promise<void> {
  const status = document.getElementById("status")!;
  const toggle = document.getElementById("live-toggle") as HTMLButtonElement;
  const listMount = document.getElementById("list")!;
  const detailMount = document.getElementById("detail")!;
  const liveMount = document.getElementById("live")!;
  const remote = new Remote();
  await remote.init();
  const hud = new Hud(remote, liveMount);
  new Live(remote, liveMount);
  new Bindings(remote, listMount, detailMount);

  let hands = 0;
  let live = false;
  remote.on("frame", (f) => { hands = f.hands.length; });
  remote.on("status", (up) => { if (!up && live) status.textContent = "Disconnected. Reconnecting…"; });
  setInterval(() => {
    if (!live) { status.textContent = `Live view off. Mappings: ${remote.mappingsPath}`; return; }
    if (!remote.connected) return;
    status.textContent = `${hud.fps.toFixed(0)} fps, ${hands} hand(s). Mappings: ${remote.mappingsPath}`;
  }, 500);

  const setLive = (on: boolean) => {
    live = on;
    document.body.classList.toggle("live-on", on);
    toggle.textContent = on ? "Hide live view" : "Show live view";
    toggle.classList.toggle("on", on);
    if (on) remote.resume(); else remote.pause();
    try { localStorage.setItem("liveView", on ? "1" : "0"); } catch { /* private mode */ }
  };
  toggle.onclick = () => setLive(!live);
  let remembered = false;
  try { remembered = localStorage.getItem("liveView") === "1"; } catch { /* private mode */ }
  remote.pause();
  setLive(remembered);
}

main().catch((err: Error) => {
  console.error(err);
  document.getElementById("status")!.textContent = `Error: ${err?.message ?? err}`;
});
