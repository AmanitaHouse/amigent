// The machine control's menu and the Amiga manager, shared by the viewer and the overview.
(async () => {
  "use strict";
  const UI = window.amigentUI;
  const { t } = UI;
  await UI.ready;
  const token = new URLSearchParams(location.search).get("t") || "";
  const api = (path) => `${path}?t=${encodeURIComponent(token)}`;
  let snapshot = { machines: [], current: "", overview: "" }, editing = null;
  const overviewPage = document.body.classList.contains("fleet");

  // ---------------------------------------------------------------- the menu

  const button = document.getElementById("machine");
  const panel = document.createElement("div");
  panel.id = "machine-menu";
  panel.className = "machine-menu";
  panel.setAttribute("aria-label", t("machines_title"));
  panel.innerHTML = `<div class="lbl" role="presentation"></div><div class="machine-items" role="group"></div>
    <div class="sep" role="separator"></div>
    <button role="menuitemradio" data-go="overview"><svg><use href="#i-grid"/></svg><span></span></button>
    <button role="menuitem" data-go="address"><svg><use href="#i-plus"/></svg><span></span></button>
    <button role="menuitem" data-go="manage"><svg><use href="#i-gear"/></svg><span></span></button>`;
  document.body.append(panel);
  panel.querySelector(".lbl").textContent = t("machines_title");
  panel.querySelector('[data-go="overview"] span').textContent = t("machines_overview");
  panel.querySelector('[data-go="address"] span').textContent = t("machines_connect_address");
  panel.querySelector('[data-go="manage"] span').textContent = t("machines_manage");
  const overview = panel.querySelector('[data-go="overview"]');
  overview.setAttribute("aria-checked", String(overviewPage));
  const items = panel.querySelector(".machine-items");
  const machineMenu = UI.menu(button, panel, { onOpen: () => refresh().catch(() => {}) });

  overview.addEventListener("click", () => { if (!overviewPage && snapshot.overview) location.assign(snapshot.overview); });
  panel.querySelector('[data-go="address"]').addEventListener("click", () => open({ connect: true }));
  panel.querySelector('[data-go="manage"]').addEventListener("click", () => open());

  const state = (a) => a.conflicts.length ? t("machines_conflict") : a.online === null
    ? t("machines_checking") : a.online ? t("machines_online") : t("machines_offline");

  function stateLine(a) {
    if (a.online && !a.conflicts.length) return [a.os, state(a)].filter(Boolean).join(" · ");
    if (!a.online && a.seen && !a.conflicts.length) {
      const seen = new Date(a.seen * 1000).toLocaleTimeString(UI.language, { hour: "2-digit", minute: "2-digit" });
      return `${state(a)} · ${t("machines_seen", { time: seen })}`;
    }
    return state(a);
  }

  // In the viewer, the current Amiga's state comes from its own live link.
  const live = (a) => a.id === snapshot.current && window.amigentCurrent && !a.conflicts.length
    ? { ...a, ...window.amigentCurrent, os: window.amigentCurrent.os || a.os } : a;
  document.addEventListener("amigent-current", () => paintMenu());

  function paintMenu() {
    const machines = snapshot.machines.map(live);
    const signature = JSON.stringify([machines.map((a) => [a.id, a.name, a.default, stateLine(a), a.conflicts.length]), snapshot.current]);
    if (items.dataset.signature === signature) return;
    items.dataset.signature = signature;
    const focused = items.contains(document.activeElement) ? document.activeElement.dataset.id : "";
    items.replaceChildren();
    for (const a of machines) {
      const item = document.createElement("button");
      item.setAttribute("role", "menuitemradio");
      item.dataset.id = a.id;
      const current = a.id === snapshot.current;
      item.setAttribute("aria-checked", String(current));
      item.disabled = a.conflicts.length > 0;
      item.innerHTML = '<i class="dot"></i><span class="two-line"><b></b><small></small></span><svg class="tick"><use href="#i-check"/></svg>';
      item.querySelector(".dot").className = "dot " + (a.conflicts.length ? "bad" : a.online ? "ok" : "");
      item.querySelector("b").textContent = a.name;
      if (a.default) {
        const star = document.createElement("span");
        star.className = "star";
        star.textContent = "★";
        star.title = t("machines_is_default");
        star.setAttribute("aria-label", t("machines_is_default"));
        item.querySelector("b").append(" ", star);
      }
      item.querySelector("small").textContent = stateLine(a);
      item.addEventListener("click", async () => {
        if (current) return;
        try { await connect(a.id); } catch (e) { await open(); showError(e.message); }
      });
      items.append(item);
      if (a.id === focused) item.focus();
    }
    if (!snapshot.machines.length) {
      const empty = document.createElement("div");
      empty.className = "note";
      empty.setAttribute("role", "none");
      empty.textContent = t("machines_none");
      items.append(empty);
    }
    machineMenu.refresh();
  }

  // ---------------------------------------------------------------- the manager

  const dialog = document.createElement("dialog");
  dialog.className = "machine-dialog";
  dialog.setAttribute("aria-labelledby", "machines-heading");
  dialog.innerHTML = `<header><h2 id="machines-heading"></h2><button class="icon close" type="button"><svg><use href="#i-close"/></svg></button></header>
    <p class="machine-error" role="alert" hidden></p>
    <section class="machine-list"></section><p class="empty" hidden></p>
    <form class="machine-connect"><label for="machine-target"></label><div><input id="machine-target" autocomplete="off" spellcheck="false" required><button class="primary" type="submit"></button></div><small></small></form>
    <form class="machine-editor" hidden><h3></h3><label for="machine-value"></label><input id="machine-value" autocomplete="off"><p></p><div><button class="cancel" type="button"></button><button class="save primary" type="submit"></button></div></form>`;
  document.body.append(dialog);
  const list = dialog.querySelector(".machine-list"), form = dialog.querySelector(".machine-editor");
  const input = form.querySelector("input"), error = dialog.querySelector(".machine-error");
  const direct = dialog.querySelector(".machine-connect"), tiles = new Map();
  dialog.querySelector("h2").textContent = t("machines_title");
  const close = dialog.querySelector(".close");
  close.title = t("machines_close");
  close.setAttribute("aria-label", close.title);
  dialog.querySelector(".empty").textContent = t("machines_empty");
  direct.querySelector("label").textContent = t("machines_connect_to");
  direct.querySelector("input").placeholder = t("machines_placeholder");
  direct.querySelector("button").textContent = t("machines_connect");
  direct.querySelector("small").textContent = t("machines_one_off");
  form.querySelector(".cancel").textContent = t("machines_cancel");
  const showError = (message) => { error.textContent = message; error.hidden = !message; };

  async function post(path, body) {
    const response = await fetch(api(path), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || response.statusText);
    return value;
  }
  async function connect(target) {
    const result = await post("/api/connect", { target });
    location.assign(result.url);
  }
  function edit(a, action) {
    editing = { id: a.id, action };
    list.hidden = direct.hidden = true;
    form.hidden = false;
    showError("");
    const label = t(`machines_${action}`);
    form.querySelector("h3").textContent = t("machines_edit_title", { action: label, name: a.name });
    form.querySelector("label").textContent = label;
    input.hidden = action === "remove";
    input.required = action !== "remove";
    input.value = action === "rename" ? a.name : a.host;
    input.maxLength = action === "rename" ? 80 : 253;
    form.querySelector("label").hidden = input.hidden;
    form.querySelector("p").textContent = t(action === "remove" ? "machines_remove_hint" : action === "address" ? "machines_address_hint" : "machines_rename_hint");
    const save = form.querySelector(".save");
    save.textContent = t(action === "remove" ? "machines_remove" : "machines_save");
    save.className = "save " + (action === "remove" ? "destructive" : "primary");
    (input.hidden ? form.querySelector(".cancel") : input).focus();
    if (!input.hidden) input.select();
  }
  function cancelEdit() {
    editing = null;
    form.hidden = true;
    list.hidden = direct.hidden = false;
    showError("");
  }
  async function refresh() {
    const response = await fetch(api("/api/machines"));
    if (!response.ok) throw new Error(t("machines_unavailable"));
    snapshot = await response.json();
    paintMenu();
    const live = new Set();
    for (const a of snapshot.machines) {
      live.add(a.id);
      let row = tiles.get(a.id);
      if (!row) {
        row = document.createElement("article");
        row.className = "machine-row";
        row.innerHTML = '<div><strong><span class="name"></span> <span class="badge" hidden></span></strong><span class="address"></span><span class="connection"><i class="dot"></i><span></span></span><p class="conflict" hidden></p></div><div class="machine-actions"></div>';
        row.querySelector(".badge").textContent = t("machines_is_default");
        for (const action of ["connect", "rename", "default", "address", "remove"]) {
          const button = document.createElement("button");
          button.type = "button";
          button.dataset.action = action;
          button.textContent = t(`machines_${action}`);
          if (action === "connect") button.className = "primary";
          button.addEventListener("click", async () => {
            try {
              if (action === "connect") await connect(row.amiga.id);
              else if (action === "default") { await post("/api/machines", { id: row.amiga.id, action }); await refresh(); }
              else edit(row.amiga, action);
            } catch (e) { showError(e.message); }
          });
          row.querySelector(".machine-actions").append(button);
        }
        tiles.set(a.id, row);
        list.append(row);
      }
      row.amiga = a;
      row.querySelector(".name").textContent = a.name;
      row.querySelector(".badge").hidden = !a.default;
      row.querySelector(".address").textContent = a.host;
      row.querySelector(".connection span").textContent = state(a);
      row.querySelector(".connection .dot").className = "dot " + (a.conflicts.length ? "bad" : a.online ? "ok" : "");
      row.querySelector(".conflict").hidden = !a.conflicts.length;
      row.querySelector(".conflict").textContent = a.error;
      row.querySelector('[data-action="connect"]').disabled = a.conflicts.length > 0 || a.id === snapshot.current;
      row.querySelector('[data-action="default"]').disabled = a.default;
    }
    for (const [id, row] of tiles) if (!live.has(id)) { row.remove(); tiles.delete(id); }
    dialog.querySelector(".empty").hidden = snapshot.machines.length > 0 || !!editing;
  }

  // open() the manager; open(id) focuses that Amiga; open({connect: true}) the address field.
  async function open(what) {
    cancelEdit();
    machineMenu.close(false);
    if (!dialog.open) dialog.showModal();
    if (what && what.connect) direct.querySelector("input").focus();
    try { await refresh(); } catch (e) { showError(e.message); }
    if (typeof what === "string" && tiles.has(what)) tiles.get(what).querySelector("button").focus();
  }
  window.amigentMachines = { open, openMenu: () => machineMenu.open() };
  close.addEventListener("click", () => dialog.close());
  form.querySelector(".cancel").addEventListener("click", cancelEdit);
  direct.addEventListener("submit", async (event) => {
    event.preventDefault();
    try { await connect(direct.querySelector("input").value); } catch (e) { showError(e.message); }
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!editing) return;
    const change = { ...editing };
    if (change.action === "rename") change.name = input.value;
    if (change.action === "address") change.address = input.value;
    const save = form.querySelector(".save");
    save.disabled = true;
    try {
      await post("/api/machines", change);
      cancelEdit();
      if (change.id === snapshot.current && change.action === "remove") location.assign(snapshot.overview);
      else if (change.id === snapshot.current && change.action === "address") await connect(change.id);
      else await refresh();
    } catch (e) { showError(e.message); } finally { save.disabled = false; }
  });
  try { await refresh(); } catch { snapshot.machines = []; paintMenu(); }
  setInterval(() => refresh().catch(() => { if (dialog.open) showError(t("machines_unavailable")); }), 5000);
})();
