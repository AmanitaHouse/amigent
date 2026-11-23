// Amigent fleet: one tile per Amiga, one click to its remote desktop,
// one command line to drive the whole party.
(() => {
  "use strict";

  const UI = window.amigentUI;
  const { t } = UI;
  const $ = (id) => document.getElementById(id);
  const token = new URLSearchParams(location.search).get("t") || "";
  // The page asks every few seconds; the fleet itself greets each Amiga every 20 (PREVIEW_EVERY).
  const POLL_MS = 5000;

  function bytes(n) {
    if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(1)} GB`;
    if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(0)} MB`;
    return `${Math.round(n / 1024)} KB`;
  }

  const tiles = new Map();
  const api = (path) => `${path}?t=${encodeURIComponent(token)}`;

  // the specs behind a tile, folded away until someone asks
  function details(a) {
    const i = a.info || {};
    const rows = [
      [t("about_system"), [i.os, i.kickstart && t("kickstart_n", { version: i.kickstart }),
        i.workbench && t("workbench_n", { version: i.workbench })].filter(Boolean).join(", ")],
      [t("about_cpu"), UI.cpuLine(i)],
      [t("about_memory"), i.chip_total ? t("mem_detail", {
        chip: i.chip_free == null ? "–" : bytes(i.chip_free), chip_total: bytes(i.chip_total),
        fast: bytes(i.fast_free), fast_total: bytes(i.fast_total) }) : ""],
      [t("about_network"), i.tcp ? `bsdsocket.library ${i.tcp}` : ""],
      ...(i.volumes || []).map((v) => [v.name + ":", t("free_of", { free: bytes(v.free), size: bytes(v.size) })]),
    ].filter(([, v]) => v);
    const dl = document.createElement("dl");
    for (const [k, v] of rows) {
      const dt = document.createElement("dt"); dt.textContent = k;
      const dd = document.createElement("dd"); dd.textContent = v;
      dl.append(dt, dd);
    }
    return dl;
  }

  async function restart(el) {
    const name = el.amiga.name;
    const yes = await UI.ask({ title: t("fleet_restart_title", { name }), text: t("restart_text"),
      ok: t("restart_go"), danger: true });
    if (!yes) return;
    const reply = await fetch(api(`/api/restart/${el.amiga.id}`), { method: "POST", body: "{}" }).catch(() => null);
    const data = reply && reply.ok ? await reply.json() : { ok: false, error: reply ? reply.statusText : t("fleet_offline") };
    if (data.ok) UI.toast(t("restarting"));
    else UI.toast(t("failed", { path: name, error: data.error }), true);
  }

  function tile(a) {
    let el = tiles.get(a.id);
    if (!el) {
      el = document.createElement("article");
      el.className = "tile";
      el.innerHTML = `<button class="open"><div class="shot"><img alt=""></div>
        <div class="meta"><b><span class="name"></span> <span class="star" hidden>★</span></b><span class="state"><i class="dot"></i><em></em></span><small></small></div></button>
        <div class="tools"><button class="manage"></button><button class="more" aria-expanded="false"></button><button class="reboot"></button></div>`;
      el.querySelector(".open").addEventListener("click", async () => {
        const reply = await fetch(api(`/api/open/${a.id}`));
        if (reply.ok) location.assign((await reply.json()).url);
        else window.amigentMachines?.open(a.id);
      });
      el.querySelector(".manage").textContent = t("fleet_manage");
      el.querySelector(".manage").addEventListener("click", () => window.amigentMachines?.open(a.id));
      el.querySelector(".more").addEventListener("click", (event) => {
        const open = event.currentTarget.getAttribute("aria-expanded") !== "true";
        event.currentTarget.setAttribute("aria-expanded", String(open));
        el.querySelector("dl")?.remove();
        if (open) el.append(details(el.amiga));
      });
      el.querySelector(".reboot").addEventListener("click", () => restart(el));
      const star = el.querySelector(".star");
      star.title = t("machines_is_default");
      star.setAttribute("aria-label", star.title);
      $("tiles").append(el);
      tiles.set(a.id, el);
    }
    el.amiga = a;
    el.querySelector(".name").textContent = a.name;
    el.querySelector(".star").hidden = !a.default;
    const state = el.querySelector(".state");
    el.querySelector(".dot").className = "dot " + (a.online ? "ok" : a.online === false ? "bad" : "");
    state.classList.toggle("bad", a.online === false);
    state.querySelector("em").textContent = a.conflicts?.length ? t("machines_conflict") : a.online ? a.host : a.online === false ? t("fleet_offline") : t("connecting");
    el.querySelector("small").textContent = a.online
      ? [a.os, a.cpu, a.free ? t("status_free", { size: bytes(a.free) }) : ""].filter(Boolean).join(" · ")
      : a.host;
    const open = el.querySelector(".open");
    open.title = t("fleet_open", { name: a.name });
    open.setAttribute("aria-label", open.title);
    el.querySelector(".more").textContent = t("fleet_details");
    el.querySelector(".reboot").textContent = t("fleet_restart");
    el.querySelector(".reboot").disabled = !a.online;
    if (el.querySelector(".more").getAttribute("aria-expanded") === "true") {
      el.querySelector("dl")?.remove();
      el.append(details(a));
    }
    const image = el.querySelector("img");
    image.hidden = !a.preview;
    if (a.preview) image.src = api(`/api/preview/${a.id}`) + `&s=${a.seen}`;
    el.classList.toggle("offline", a.online === false);
  }

  // one line for the whole fleet; answers stack up per Amiga, rc > 5 glows red
  $("run").addEventListener("submit", async (event) => {
    event.preventDefault();
    const command = $("command").value.trim();
    if (!command) return;
    const go = $("run-go");
    go.disabled = true;
    $("results").hidden = false;
    $("results").textContent = t("fleet_running", { command });
    try {
      const reply = await fetch(api("/api/run"), { method: "POST", body: JSON.stringify({ command }) });
      const list = reply.ok ? await reply.json() : [];
      $("results").textContent = "";
      for (const r of list) {
        const art = document.createElement("article");
        art.className = r.ok && r.rc <= 5 ? "" : "bad";
        const head = document.createElement("header");
        const name = document.createElement("b"); name.textContent = r.name;
        const rc = document.createElement("span"); rc.className = "rc";
        rc.textContent = r.ok ? t("fleet_rc", { rc: r.rc }) : r.error;
        head.append(name, rc);
        art.append(head);
        if (r.ok && r.output) {
          const pre = document.createElement("pre"); pre.textContent = r.output;
          art.append(pre);
        }
        $("results").append(art);
      }
    } finally {
      go.disabled = false;
    }
  });

  async function refresh() {
    try {
      const list = await (await fetch(api("/api/fleet"))).json();
      list.forEach(tile);
      const live = new Set(list.map(a => a.id));
      for (const [id, el] of tiles) if (!live.has(id)) { el.remove(); tiles.delete(id); }
      const up = list.filter((a) => a.online).length;
      const summary = t("fleet_summary", { up, total: list.length });
      $("machine-sub").textContent = summary;
      $("machine-dot").className = "dot " + (up ? "ok" : list.length ? "bad" : "");
      $("machine").setAttribute("aria-label", t("machine_switch", { name: t("fleet_title"), state: summary }));
    } catch { /* fleet process gone; freeze the last frame */ }
  }

  UI.ready.then(() => {
    UI.translate();
    document.title = `Amigent · ${t("fleet_title")}`;
    refresh();
    setInterval(refresh, POLL_MS);
  });
})();
