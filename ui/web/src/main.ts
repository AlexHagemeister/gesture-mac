/**
 * Page wiring: fetch state, mount the three regions (bindings list, the
 * selected binding's detail, the live view with its readout), open the
 * stream. The header line shows connection, frame rate, and hands in view.
 */
import "./style.css";
import { Remote } from "./remote";
import { Hud } from "./hud";
import { Live } from "./live";
import { Bindings } from "./bindings";

async function main(): Promise<void> {
  const status = document.getElementById("status")!;
  const listMount = document.getElementById("list")!;
  const detailMount = document.getElementById("detail")!;
  const liveMount = document.getElementById("live")!;
  const remote = new Remote();
  await remote.init();
  const hud = new Hud(remote, liveMount);
  new Live(remote, liveMount);
  new Bindings(remote, listMount, detailMount);

  let hands = 0;
  remote.on("frame", (f) => { hands = f.hands.length; });
  remote.on("status", (up) => { if (!up) status.textContent = "Disconnected. Reconnecting…"; });
  setInterval(() => {
    if (!remote.connected) return;
    status.textContent = `${hud.fps.toFixed(0)} fps, ${hands} hand(s). Mappings: ${remote.mappingsPath}`;
  }, 500);
  remote.connect();
}

main().catch((err: Error) => {
  console.error(err);
  document.getElementById("status")!.textContent = `Error: ${err?.message ?? err}`;
});
