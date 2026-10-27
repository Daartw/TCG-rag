/* PokéDex TCG — frontend sin dependencias */
(() => {
  "use strict";

  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const TYPES = {
    Grass: ["Planta", "var(--t-grass)"], Fire: ["Fuego", "var(--t-fire)"], Water: ["Agua", "var(--t-water)"],
    Lightning: ["Eléctrico", "var(--t-lightning)"], Psychic: ["Psíquico", "var(--t-psychic)"],
    Fighting: ["Lucha", "var(--t-fighting)"], Darkness: ["Oscuro", "var(--t-darkness)"],
    Metal: ["Metal", "var(--t-metal)"], Dragon: ["Dragón", "var(--t-dragon)"], Fairy: ["Hada", "var(--t-fairy)"],
    Colorless: ["Incoloro", "var(--t-colorless)"],
  };
  const SUPERTYPES = { "Pokémon": "Pokémon", Trainer: "Entrenador", Energy: "Energía" };
  const typeName = (t) => (TYPES[t] ? TYPES[t][0] : t);
  const typeColor = (t) => (TYPES[t] ? TYPES[t][1] : "var(--muted)");

  const api = async (path, opts) => {
    const res = await fetch(path, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
    return data;
  };

  const state = { page: 1, total: 0, loading: false, meta: null, sets: null, setsById: {}, history: [], cardCache: {} };

  /* ---------------- routing ---------------- */
  function navigate(url, replace = false) {
    if (replace) history.replaceState({}, "", url); else history.pushState({}, "", url);
    route();
  }
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[data-link]");
    if (a && !e.metaKey && !e.ctrlKey && a.origin === location.origin) {
      e.preventDefault();
      navigate(a.getAttribute("href"));
    }
  });
  window.addEventListener("popstate", route);

  function showView(name) {
    for (const v of ["explore", "sets", "chat"]) $(`#view-${v}`).hidden = v !== name;
    $$(".tabs a").forEach((a) => a.classList.toggle("active", a.dataset.tab === name));
  }

  let lastExploreKey = null;
  function route() {
    const path = location.pathname;
    const cardMatch = path.match(/^\/carta\/(.+)$/);
    const setMatch = path.match(/^\/set\/(.+)$/);
    if (path === "/asistente") {
      showView("chat"); closeDialog(false); document.title = `Asistente — ${siteName()}`;
      $("#chatInput").focus({ preventScroll: true });
      return;
    }
    if (path === "/set/" || path === "/set") {
      showView("sets"); closeDialog(false); renderSets(); document.title = `Sets — ${siteName()}`;
      return;
    }
    showView("explore");
    if (cardMatch) {
      openCard(decodeURIComponent(cardMatch[1]), false);
      if (lastExploreKey === null) loadExplore(true);
      return;
    }
    closeDialog(false);
    const params = new URLSearchParams(location.search);
    if (setMatch) params.set("set", decodeURIComponent(setMatch[1]));
    applyParamsToForm(params);
    const key = params.toString();
    if (key !== lastExploreKey) loadExplore(true);
    document.title = `${siteName()} — Catálogo de cartas Pokémon`;
  }
  const siteName = () => state.meta?.site_name || "PokéDex TCG";

  /* ---------------- explorar ---------------- */
  const form = $("#filters");

  function formParams() {
    const p = new URLSearchParams();
    const f = new FormData(form);
    for (const [k, v] of f.entries()) if (v && k !== "standard") p.set(k, v);
    if ($("#fStandard").checked) p.set("standard", "true");
    if (p.get("sort") === "newest") p.delete("sort");
    $$(".type-chip[aria-pressed=true]").forEach((b) => p.append("type", b.dataset.type));
    return p;
  }

  function applyParamsToForm(params) {
    $("#q").value = params.get("q") || "";
    $("#fSet").value = params.get("set") || "";
    $("#fSupertype").value = params.get("supertype") || "";
    $("#fRarity").value = params.get("rarity") || "";
    $("#fSort").value = params.get("sort") || "newest";
    $("#fStandard").checked = params.get("standard") === "true";
    const types = params.getAll("type");
    $$(".type-chip").forEach((b) => b.setAttribute("aria-pressed", String(types.includes(b.dataset.type))));
  }

  function syncUrl() {
    const p = formParams();
    const set = p.get("set");
    p.delete("set");
    const qs = p.toString();
    const url = (set ? `/set/${encodeURIComponent(set)}` : "/") + (qs ? `?${qs}` : "");
    if (url !== location.pathname + location.search) history.replaceState({}, "", url);
  }

  let debounce;
  form.addEventListener("input", (e) => {
    clearTimeout(debounce);
    debounce = setTimeout(() => { syncUrl(); loadExplore(true); }, e.target.id === "q" ? 280 : 0);
  });
  form.addEventListener("submit", (e) => e.preventDefault());
  $("#clearFilters").addEventListener("click", () => { form.reset(); $$(".type-chip").forEach((b) => b.setAttribute("aria-pressed", "false")); syncUrl(); loadExplore(true); });
  $("#loadMore").addEventListener("click", () => loadExplore(false));

  function tileHtml(c, extra = "") {
    const sub = [c.set?.name, c.number ? `#${c.number}` : ""].filter(Boolean).join(" · ");
    return `<button class="card-tile" data-card="${esc(c.id)}" title="${esc(c.name)}">
      <div class="img"><img loading="lazy" decoding="async" src="${esc(c.images?.small)}" alt="${esc(c.name)}" width="245" height="342"></div>
      <span class="name">${esc(c.name)}</span><span class="sub">${esc(sub)}${extra}</span></button>`;
  }

  async function loadExplore(reset) {
    if (state.loading && !reset) return;
    const params = formParams();
    lastExploreKey = new URLSearchParams(location.search).toString();
    const setId = params.get("set");
    if (reset) {
      state.page = 1;
      $("#grid").innerHTML = Array.from({ length: 12 }, () => '<div class="card-tile skeleton"><div class="img"></div></div>').join("");
    } else state.page += 1;
    params.set("page", state.page);
    params.set("page_size", 36);
    state.loading = true;
    const myRequest = (loadExplore.seq = (loadExplore.seq || 0) + 1);
    try {
      const data = await api(`/api/cards?${params}`);
      if (myRequest !== loadExplore.seq) return;
      state.total = data.total;
      const html = data.data.map((c) => tileHtml(c)).join("");
      if (reset) $("#grid").innerHTML = html || '<div class="empty">No hay cartas con esos filtros.</div>';
      else $("#grid").insertAdjacentHTML("beforeend", html);
      const shown = $$("#grid .card-tile").length;
      $("#resultCount").textContent = `${data.total.toLocaleString("es")} cartas${setId && state.setsById[setId] ? ` en ${state.setsById[setId].name}` : ""}`;
      $("#loadMore").hidden = shown >= data.total;
    } catch (err) {
      $("#grid").innerHTML = `<div class="empty">${esc(err.message)}</div>`;
    } finally {
      state.loading = false;
    }
  }

  document.addEventListener("click", (e) => {
    const tile = e.target.closest("[data-card]");
    if (tile) { e.preventDefault(); openCard(tile.dataset.card, true); }
  });

  /* ---------------- detalle de carta ---------------- */
  const dialog = $("#cardDialog");
  let returnUrl = "/";
  dialog.addEventListener("close", () => { if (location.pathname.startsWith("/carta/")) history.pushState({}, "", returnUrl); route(); });
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
  $(".close", dialog).addEventListener("click", () => dialog.close());

  function closeDialog() { if (dialog.open) { dialog.returnValue = ""; dialog.close(); } }

  const costIcons = (cost) => `<span class="costs">${(cost || []).map((t) => `<i style="--c:${typeColor(t)}" title="${esc(typeName(t))}"></i>`).join("")}</span>`;

  async function openCard(id, push) {
    if (push) {
      if (!location.pathname.startsWith("/carta/")) returnUrl = location.pathname + location.search;
      history.pushState({}, "", `/carta/${encodeURIComponent(id)}`);
    }
    $("#cardDetail").innerHTML = '<div class="detail"><div class="art skeleton"><div class="img" style="aspect-ratio:245/342;background:var(--surface-2);border-radius:12px"></div></div><div></div></div>';
    if (!dialog.open) dialog.showModal();
    try {
      const c = state.cardCache[id] || (state.cardCache[id] = await api(`/api/cards/${encodeURIComponent(id)}`));
      document.title = `${c.name} (${c.set.name}) — ${siteName()}`;
      $("#cardDetail").innerHTML = detailHtml(c);
      dialog.scrollTop = 0;
      loadPrice(c.id);
    } catch (err) {
      $("#cardDetail").innerHTML = `<div class="empty">${esc(err.message)}</div>`;
    }
  }

  function detailHtml(c) {
    const pills = [
      `<span class="pill">${esc(SUPERTYPES[c.supertype] || c.supertype)}${c.subtypes?.length ? " · " + esc(c.subtypes.join(", ")) : ""}</span>`,
      ...(c.types || []).map((t) => `<span class="pill" style="--c:${typeColor(t)}"><span class="dot"></span>${esc(typeName(t))}</span>`),
      c.hp ? `<span class="pill">${c.hp} HP</span>` : "",
      c.rarity ? `<span class="pill">${esc(c.rarity)}</span>` : "",
      c.regulation_mark ? `<span class="pill">Regulación ${esc(c.regulation_mark)}</span>` : "",
      `<span class="pill">${c.legal_standard ? "✓ Estándar" : "✗ Estándar"}</span>`,
      `<span class="pill">${c.legal_expanded ? "✓ Expandido" : "✗ Expandido"}</span>`,
    ].join("");
    const blocks = [];
    if (c.evolvesFrom) blocks.push(`<p class="muted small">Evoluciona de <a href="/?q=${encodeURIComponent(c.evolvesFrom)}" data-link>${esc(c.evolvesFrom)}</a></p>`);
    if (c.ancientTrait) blocks.push(`<div class="block"><span class="label">Rasgo antiguo</span><h4>${esc(c.ancientTrait.name)}</h4><p>${esc(c.ancientTrait.text)}</p></div>`);
    for (const a of c.abilities || []) blocks.push(`<div class="block"><span class="label">${esc(a.type || "Habilidad")}</span><h4>${esc(a.name)}</h4><p>${esc(a.text)}</p></div>`);
    for (const a of c.attacks || []) blocks.push(`<div class="block"><h4><span>${costIcons(a.cost)}${esc(a.name)}</span><span>${esc(a.damage || "")}</span></h4>${a.text ? `<p>${esc(a.text)}</p>` : ""}</div>`);
    for (const r of c.rules || []) blocks.push(`<div class="block"><p>${esc(r)}</p></div>`);
    if (c.supertype === "Pokémon") {
      const w = (c.weaknesses || []).map((x) => `${typeName(x.type)} ${x.value}`).join(", ") || "—";
      const r = (c.resistances || []).map((x) => `${typeName(x.type)} ${x.value}`).join(", ") || "—";
      blocks.push(`<div class="stats3"><div><span>Debilidad</span>${esc(w)}</div><div><span>Resistencia</span>${esc(r)}</div><div><span>Retirada</span>${costIcons(c.retreatCost)}${(c.retreatCost || []).length || 0}</div></div>`);
    }
    if (c.flavorText) blocks.push(`<p class="muted small"><em>${esc(c.flavorText)}</em></p>`);
    const printings = (c.printings || []).length
      ? `<h3 style="font-size:16px;margin:18px 0 8px">Otras impresiones (${c.printings.length})</h3><div class="printings">${c.printings.map((p) =>
          `<button data-card="${esc(p.id)}" title="${esc(p.set.name)} #${esc(p.number)}"><img loading="lazy" src="${esc(p.images.small)}" alt=""><span>${esc(p.set.name)}</span></button>`).join("")}</div>`
      : "";
    return `<div class="detail">
      <div class="art"><a href="${esc(c.images.large || c.images.small)}" target="_blank" rel="noopener"><img src="${esc(c.images.large || c.images.small)}" alt="${esc(c.name)}"></a></div>
      <div>
        <h2>${esc(c.name)}</h2>
        <p class="muted" style="margin:6px 0 0"><a href="/set/${encodeURIComponent(c.set.id)}" data-link>${esc(c.set.name)}</a> · ${esc(c.set.series)} · #${esc(c.number)}${c.set.printedTotal ? "/" + c.set.printedTotal : ""} · ${esc(c.release_date || "")}${c.artist ? ` · Ilus. ${esc(c.artist)}` : ""}</p>
        <div class="meta-line">${pills}</div>
        ${blocks.join("")}
        <div class="block prices" id="priceBlock"><span class="label">Precio de mercado</span><p class="typing"><span></span><span></span><span></span></p></div>
        ${printings}
      </div></div>`;
  }

  const money = (v, cur) => (v == null ? "—" : (cur === "USD" ? "US$" : "€") + Number(v).toFixed(2));
  async function loadPrice(id) {
    const el = $("#priceBlock");
    try {
      const p = await api(`/api/cards/${encodeURIComponent(id)}/price`);
      if (!$("#priceBlock") || $("#priceBlock") !== el) return;
      if (!p.available) { el.innerHTML = '<span class="label">Precio de mercado</span><p>Sin datos de precio por ahora.</p>'; return; }
      const rows = Object.entries(p.tcgplayer.prices_usd || {}).map(([variant, v]) =>
        `<tr><td>TCGPlayer · ${esc(variant)}</td><td>${money(v.low, "USD")}</td><td>${money(v.market, "USD")}</td><td>${money(v.high, "USD")}</td></tr>`);
      const cm = p.cardmarket.prices_eur || {};
      if (Object.keys(cm).length) rows.push(`<tr><td>Cardmarket</td><td>${money(cm.lowPrice, "EUR")}</td><td>${money(cm.trendPrice ?? cm.averageSellPrice, "EUR")}</td><td>${money(cm.avg30, "EUR")} <span class="muted tiny">(30d)</span></td></tr>`);
      const links = [p.tcgplayer.url && `<a href="${esc(p.tcgplayer.url)}" target="_blank" rel="noopener">TCGPlayer</a>`, p.cardmarket.url && `<a href="${esc(p.cardmarket.url)}" target="_blank" rel="noopener">Cardmarket</a>`].filter(Boolean).join(" · ");
      el.innerHTML = `<span class="label">Precio de mercado</span>${rows.length ? `<table><tr><th></th><th>Bajo</th><th>Mercado</th><th>Alto</th></tr>${rows.join("")}</table>` : "<p>Sin datos de precio.</p>"}<p class="tiny" style="margin-top:6px">${links} ${p.tcgplayer.updated_at ? "· actualizado " + esc(p.tcgplayer.updated_at) : ""}</p>`;
    } catch {
      el.innerHTML = '<span class="label">Precio de mercado</span><p>El servicio de precios no respondió.</p>';
    }
  }

  /* ---------------- sets ---------------- */
  function renderSets() {
    const el = $("#setList");
    if (!state.sets) { el.innerHTML = '<div class="empty">Cargando…</div>'; return; }
    const bySeries = new Map();
    for (const s of state.sets) { if (!bySeries.has(s.series)) bySeries.set(s.series, []); bySeries.get(s.series).push(s); }
    el.innerHTML = [...bySeries].map(([series, sets]) => `<div class="series"><h2>${esc(series)}</h2><div class="set-grid">${sets.map((s) => `
      <a class="set-tile" href="/set/${encodeURIComponent(s.id)}" data-link>
        <div class="logo">${s.images.logo ? `<img loading="lazy" src="${esc(s.images.logo)}" alt="" onerror="this.remove()">` : ""}</div>
        <strong>${esc(s.name)}</strong>
        <div class="row"><span>${esc(s.release_date)}</span><span>${s.card_count} cartas${s.legal_standard ? " · Estándar" : ""}</span></div>
      </a>`).join("")}</div></div>`).join("");
  }

  /* ---------------- asistente ---------------- */
  const messages = $("#messages");
  const input = $("#chatInput");
  input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = input.scrollHeight + "px"; });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#chatForm").requestSubmit(); } });
  $(".suggestions").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { input.value = b.textContent; $("#chatForm").requestSubmit(); } });

  function linkifyRefs(text) {
    // "Nombre [set-123]" -> enlace a la carta
    return esc(text).replace(/\[([a-z][a-z0-9]*-[A-Za-z0-9]+)\]/g, (m, id) => `<a class="cardref" data-card="${id}" href="/carta/${id}">[${id}]</a>`)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  }

  function headlinePrice(p) {
    if (!p) return "";
    for (const v of Object.values(p.tcgplayer?.prices_usd || {})) if (v.market != null) return `US$${v.market.toFixed(2)}`;
    const t = p.cardmarket?.prices_eur?.trendPrice;
    return t != null ? `€${t.toFixed(2)}` : "";
  }

  $("#chatForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = ""; input.style.height = "auto";
    messages.insertAdjacentHTML("beforeend", `<div class="msg user">${esc(text)}</div>`);
    const pending = document.createElement("div");
    pending.className = "msg bot";
    pending.innerHTML = '<p class="typing"><span></span><span></span><span></span></p>';
    messages.append(pending);
    pending.scrollIntoView({ behavior: "smooth", block: "end" });
    $("#chatSend").disabled = true;
    try {
      const r = await api("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: text, history: state.history.slice(-6) }) });
      const cards = (r.cards || []).map((c) => { const pr = headlinePrice(c.price); return `<button data-card="${esc(c.id)}" title="${esc(c.name)} — ${esc(c.set.name)}"><img loading="lazy" src="${esc(c.images.small)}" alt="${esc(c.name)}"><span>${esc(c.name)}</span><span>${pr ? `<b class="price">${pr}</b>` : esc(c.set.name)}</span></button>`; }).join("");
      pending.innerHTML = `<div class="text">${linkifyRefs(r.answer)}</div>${cards ? `<div class="cards">${cards}</div>` : ""}${r.warning ? `<p class="warn">${esc(r.warning)}</p>` : ""}`;
      state.history.push({ role: "user", content: text }, { role: "assistant", content: r.answer });
    } catch (err) {
      pending.innerHTML = `<p class="warn">${esc(err.message)}</p>`;
    } finally {
      $("#chatSend").disabled = false;
      pending.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  });

  /* ---------------- arranque ---------------- */
  function buildFilters(meta) {
    const f = meta.filters;
    $("#fSupertype").insertAdjacentHTML("beforeend", f.supertypes.map((s) => `<option value="${esc(s)}">${esc(SUPERTYPES[s] || s)}</option>`).join(""));
    $("#fRarity").insertAdjacentHTML("beforeend", f.rarities.map((s) => `<option>${esc(s)}</option>`).join(""));
    $("#fTypes").innerHTML = f.types.map((t) => `<button type="button" class="type-chip" data-type="${esc(t)}" aria-pressed="false" style="--c:${typeColor(t)}"><span class="dot"></span>${esc(typeName(t))}</button>`).join("");
    $("#fTypes").addEventListener("click", (e) => {
      const b = e.target.closest(".type-chip");
      if (!b) return;
      b.setAttribute("aria-pressed", String(b.getAttribute("aria-pressed") !== "true"));
      syncUrl(); loadExplore(true);
    });
  }

  async function init() {
    try {
      const [meta, sets] = await Promise.all([api("/api/meta"), api("/api/sets")]);
      state.meta = meta;
      state.sets = sets.data;
      state.setsById = Object.fromEntries(sets.data.map((s) => [s.id, s]));
      $("#siteName").textContent = meta.site_name;
      $("#heroStats").textContent = `${meta.card_count.toLocaleString("es")} cartas · ${meta.set_count} sets · última expansión: ${meta.latest_set?.name ?? "—"}`;
      buildFilters(meta);
      let group = "";
      $("#fSet").insertAdjacentHTML("beforeend", state.sets.map((s) => {
        let out = "";
        if (s.series !== group) { out += `${group ? "</optgroup>" : ""}<optgroup label="${esc(s.series)}">`; group = s.series; }
        return out + `<option value="${esc(s.id)}">${esc(s.name)}</option>`;
      }).join("") + "</optgroup>");
    } catch (err) {
      $("#heroStats").textContent = err.message;
    }
    route();
  }
  init();
})();
