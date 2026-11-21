// Shared by every Amigent page: settings, texts, appearance, menus, tabs, toasts and questions.
// Loaded in <head>, so the appearance is set before the page paints.
(() => {
  "use strict";

  const store = {
    get(key, fallback) { try { return localStorage.getItem("amigent." + key) ?? fallback; } catch { return fallback; } },
    set(key, value) { try { localStorage.setItem("amigent." + key, value); } catch { /* private window */ } },
  };

  // On a Mac, Cmd pastes and Option types characters such as @ and € on its own.
  const MAC = /Mac/.test(navigator.platform || navigator.userAgent);

  // ---------------------------------------------------------------- appearance

  const THEMES = ["auto", "light", "dark"];

  function applyTheme(value) {
    const root = document.documentElement;
    if (value === "light" || value === "dark") root.dataset.theme = value;
    else delete root.dataset.theme;
  }

  function setTheme(value) {
    if (!THEMES.includes(value)) value = "auto";
    store.set("theme", value);
    applyTheme(value);
  }

  applyTheme(store.get("theme", "auto"));

  // ---------------------------------------------------------------- texts

  // Each language is web/locales/<code>.json; English is the default and fills gaps.
  const LANGUAGES = {
    en: "English", de: "Deutsch", pl: "Polski", fr: "Français", es: "Español", it: "Italiano",
    fi: "Suomi", sv: "Svenska", da: "Dansk", cs: "Čeština", sk: "Slovenčina", hu: "Magyar",
    ru: "Русский",
  };

  function pickLanguage() {
    const chosen = store.get("lang", "auto");
    if (LANGUAGES[chosen]) return chosen;
    for (const tag of navigator.languages?.length ? navigator.languages : [navigator.language || "en"]) {
      const code = tag.toLowerCase().split("-")[0];
      if (LANGUAGES[code]) return code;
    }
    return "en";
  }

  const language = pickLanguage();
  let EN = {};
  let TEXT = {};

  const ready = (async () => {
    const load = (code) => fetch(`locales/${code}.json`).then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
    EN = await load("en");
    TEXT = language === "en" ? EN : await load(language);
    document.documentElement.lang = language;
  })();

  function t(key, values = {}) {
    let text = TEXT[key] ?? EN[key] ?? key;
    for (const [name, value] of Object.entries(values)) text = text.replaceAll(`{${name}}`, value);
    return text;
  }

  // Whether English has this text at all: keys from outside the page are checked first.
  function knows(key) {
    return Object.hasOwn(EN, key);
  }

  // The Mac variant of a text where there is one ("tip" -> "tip_mac").
  function mac(key) {
    return MAC && (TEXT[key + "_mac"] ?? EN[key + "_mac"]) !== undefined ? key + "_mac" : key;
  }

  function translate(root = document) {
    for (const el of root.querySelectorAll("[data-i18n]")) el.textContent = t(mac(el.dataset.i18n));
    for (const el of root.querySelectorAll("[data-i18n-title]")) el.title = t(mac(el.dataset.i18nTitle));
    for (const el of root.querySelectorAll("[data-i18n-placeholder]")) el.placeholder = t(el.dataset.i18nPlaceholder);
    for (const el of root.querySelectorAll("[data-i18n-aria]")) el.setAttribute("aria-label", t(el.dataset.i18nAria));
    for (const el of root.querySelectorAll("[data-i18n-label]")) {
      el.title = t(el.dataset.i18nLabel);
      el.setAttribute("aria-label", el.title);
    }
  }

  // ---------------------------------------------------------------- toasts

  function toast(text, bad = false) {
    let box = document.getElementById("toasts");
    if (!box) {
      box = document.createElement("div");
      box.id = "toasts";
      box.setAttribute("aria-live", "polite");
      document.body.append(box);
    }
    const el = document.createElement("div");
    el.className = "toast" + (bad ? " bad" : "");
    el.setAttribute("role", bad ? "alert" : "status");
    el.textContent = text;
    box.append(el);
    setTimeout(() => el.remove(), bad ? 7000 : 3500);
  }

  // ---------------------------------------------------------------- questions

  let askDialog = null;

  // A yes/no question in the page's own style; resolves true for the OK button.
  function ask({ title, text = "", ok, cancel = t("cancel"), danger = false }) {
    if (!askDialog) {
      askDialog = document.createElement("dialog");
      askDialog.className = "ask";
      askDialog.setAttribute("aria-labelledby", "ask-title");
      askDialog.innerHTML = `<form method="dialog"><h3 id="ask-title"></h3><p></p>
        <div class="buttons"><button value="cancel" autofocus></button><button value="ok"></button></div></form>`;
      document.body.append(askDialog);
    }
    askDialog.querySelector("h3").textContent = title;
    askDialog.querySelector("p").textContent = text;
    askDialog.querySelector("p").hidden = !text;
    askDialog.querySelector('[value="cancel"]').textContent = cancel;
    const yes = askDialog.querySelector('[value="ok"]');
    yes.textContent = ok;
    yes.className = danger ? "destructive" : "primary";
    askDialog.returnValue = "";
    askDialog.showModal();
    return new Promise((resolve) => {
      askDialog.addEventListener("close", () => resolve(askDialog.returnValue === "ok"), { once: true });
    });
  }

  // ---------------------------------------------------------------- menus

  const openMenus = new Set();
  const ITEM = '[role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"]';

  function shown(el) {
    return el.getClientRects().length > 0 && !el.disabled;
  }

  // A button that opens a popover menu. Arrow keys move, Esc closes, focus goes back.
  // Submenus: an item with aria-haspopup followed by a [role=menu] sibling, opened in place.
  function menu(button, panel, { align = "start", onOpen } = {}) {
    button.setAttribute("aria-haspopup", "menu");
    button.setAttribute("aria-expanded", "false");
    if (!panel.id) panel.id = "menu-" + Math.random().toString(36).slice(2);
    button.setAttribute("aria-controls", panel.id);
    panel.setAttribute("role", "menu");
    panel.classList.add("menu");
    panel.hidden = true;
    panel.tabIndex = -1;

    const items = () => [...panel.querySelectorAll(ITEM)].filter(shown);

    function place() {
      const r = button.getBoundingClientRect();
      panel.style.maxHeight = `${Math.max(160, innerHeight - r.bottom - 12)}px`;
      panel.style.top = `${r.bottom + 4}px`;
      const w = panel.offsetWidth;
      let left = align === "end" ? r.right - w : r.left;
      left = Math.max(8, Math.min(left, innerWidth - w - 8));
      panel.style.left = `${left}px`;
    }

    function setSub(item, open) {
      const sub = item.nextElementSibling;
      if (!sub || sub.getAttribute("role") !== "menu") return null;
      item.setAttribute("aria-expanded", String(open));
      sub.hidden = !open;
      return sub;
    }

    function collapse() {
      for (const item of panel.querySelectorAll('[aria-haspopup="menu"]')) setSub(item, false);
    }

    const api = {
      button,
      panel,
      get isOpen() { return !panel.hidden; },
      open(where = "first") {
        for (const other of [...openMenus]) if (other !== api) other.close(false);
        onOpen?.();
        collapse();
        panel.hidden = false;
        button.setAttribute("aria-expanded", "true");
        openMenus.add(api);
        place();
        const list = items();
        const checked = list.find((el) => el.getAttribute("aria-checked") === "true" && el.closest('[role="menu"]') === panel);
        (where === "last" ? list[list.length - 1] : checked || list[0] || panel).focus();
      },
      close(returnFocus = true) {
        if (panel.hidden) return;
        const inside = panel.contains(document.activeElement);
        panel.hidden = true;
        collapse();
        button.setAttribute("aria-expanded", "false");
        openMenus.delete(api);
        if (returnFocus || inside) button.focus();
      },
      refresh() { if (!panel.hidden) place(); },
    };

    button.addEventListener("click", () => (panel.hidden ? api.open() : api.close()));
    button.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        api.open(event.key === "ArrowUp" ? "last" : "first");
      }
    });

    panel.addEventListener("keydown", (event) => {
      const list = items();
      const at = list.indexOf(document.activeElement);
      const current = list[at];
      const go = (i) => list[(i + list.length) % list.length]?.focus();
      if (event.key === "ArrowDown") go(at + 1);
      else if (event.key === "ArrowUp") go(at < 0 ? -1 : at - 1);
      else if (event.key === "Home") go(0);
      else if (event.key === "End") go(-1);
      else if (event.key === "ArrowRight" && current?.getAttribute("aria-haspopup") === "menu") {
        const sub = setSub(current, true);
        sub?.querySelector(ITEM)?.focus();
        place();
      } else if ((event.key === "ArrowLeft" || event.key === "Escape") && current && current.closest('[role="menu"]') !== panel) {
        const parent = current.closest('[role="menu"]').previousElementSibling;
        setSub(parent, false);
        parent.focus();
        place();
      } else if (event.key === "Escape") api.close(true);
      else if (event.key === "Tab") { api.close(false); return; }
      else return;
      event.preventDefault();
      event.stopPropagation();
    });

    panel.addEventListener("click", (event) => {
      const item = event.target.closest(ITEM);
      if (!item || item.disabled) return;
      if (item.getAttribute("aria-haspopup") === "menu") {
        const sub = setSub(item, item.getAttribute("aria-expanded") !== "true");
        if (sub && !sub.hidden) sub.querySelector(ITEM)?.focus();
        place();
        return;
      }
      // The item's own handler ran first; give focus back only if it left focus here.
      api.close(false);
    });

    return api;
  }

  document.addEventListener("pointerdown", (event) => {
    for (const m of [...openMenus]) {
      if (!m.panel.contains(event.target) && !m.button.contains(event.target)) m.close(false);
    }
  });
  window.addEventListener("resize", () => { for (const m of openMenus) m.refresh(); });
  window.addEventListener("blur", () => { for (const m of [...openMenus]) m.close(false); });

  // ---------------------------------------------------------------- tabs

  // role=tablist with tabs pointing at their panels by aria-controls; arrows move, choice remembered.
  function tabs(list, { remember, onChange } = {}) {
    const all = [...list.querySelectorAll('[role="tab"]')];
    function select(tab, focus = false) {
      for (const each of all) {
        const on = each === tab;
        each.setAttribute("aria-selected", String(on));
        each.tabIndex = on ? 0 : -1;
        const pane = document.getElementById(each.getAttribute("aria-controls"));
        if (pane) pane.hidden = !on;
      }
      if (focus) tab.focus();
      if (remember) store.set(remember, tab.id);
      onChange?.(tab);
    }
    for (const tab of all) {
      tab.addEventListener("click", () => select(tab));
      tab.addEventListener("keydown", (event) => {
        const at = all.indexOf(tab);
        const next = { ArrowRight: at + 1, ArrowLeft: at - 1, Home: 0, End: all.length - 1 }[event.key];
        if (next === undefined) return;
        event.preventDefault();
        select(all[(next + all.length) % all.length], true);
      });
    }
    const start = remember && all.find((tab) => tab.id === store.get(remember, ""));
    select(start || all[0]);
    return { select: (id) => select(all.find((tab) => tab.id === id) || all[0]) };
  }

  window.amigentUI = {
    store, MAC, LANGUAGES, language, pickLanguage, ready, t, knows, mac, translate,
    THEMES, setTheme, theme: () => store.get("theme", "auto"),
    toast, ask, menu, tabs,
  };
})();
