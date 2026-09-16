/**
 * Page wiring: fetch state, mount the HUD and panel, open the stream.
 * The header line shows connection, frame rate, and hands in view.
 */
import "./style.css";
import { Remote } from "./remote";
import { Hud } from "./hud";
import { Panel } from "./panel";

async function main(): Promise<void> {
  const app = document.getElementById("app")!;
  const status = document.getElementById("status")!;
  const remote = new Remote();
  await remote.init();
  const hud = new Hud(remote, app);
  new Panel(remote, app);

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
