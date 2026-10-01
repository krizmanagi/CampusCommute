"use strict";

(() => {
  const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });

  const state = {
    day: 0,
    hour: 9,
    routeId: "campus-loop",
    search: "",
    overview: null,
    detail: null,
    metadata: null,
    hoverHour: null,
  };

  // Each request type gets a sequence number so slow, stale responses are dropped.
  const seq = { overview: 0, detail: 0 };

  // ---------------------------------------------------------------- helpers
  const escapeHtml = (value) =>
    String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const formatHour = (hour) => `${String(hour).padStart(2, "0")}:00`;
  const pct = (value) => `${Math.round(value * 100)}%`;
  const minutes = (value) => `${Number.isInteger(value) ? value : value.toFixed(1)} min`;

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(body.error || `Request failed (${response.status})`);
      error.details = body.errors || [];
      throw error;
    }
    return body;
  }

  function readUrlState() {
    const params = new URLSearchParams(location.search);
    const day = Number(params.get("day"));
    const hour = Number(params.get("hour"));
    if (params.has("day") && Number.isInteger(day) && day >= 0 && day <= 6) state.day = day;
    if (params.has("hour") && Number.isInteger(hour) && hour >= 0 && hour <= 23) state.hour = hour;
    if (params.get("route")) state.routeId = params.get("route");
  }

  function writeUrlState() {
    const params = new URLSearchParams({ day: state.day, hour: state.hour, route: state.routeId });
    history.replaceState(null, "", `?${params}`);
  }

  function setStatus(message, kind = "", details = []) {
    const el = $("status");
    el.className = `status ${kind}`;
    el.innerHTML = escapeHtml(message) +
      (details.length ? `<ul>${details.map((d) => `<li>${escapeHtml(d)}</li>`).join("")}</ul>` : "");
  }

  // ---------------------------------------------------------------- loading
  async function loadMetadata() {
    state.metadata = await fetchJson("/api/metadata");
    if (!state.metadata.routes.some((r) => r.id === state.routeId)) {
      state.routeId = state.metadata.routes[0].id;
    }
    renderMetadata();
  }

  async function loadOverview() {
    const id = ++seq.overview;
    const data = await fetchJson(`/api/overview?day=${state.day}&hour=${state.hour}`);
    if (id !== seq.overview) return;
    state.overview = data;
    renderOverview();
    renderRouteList();
    renderSuggestion();
  }

  async function loadDetail() {
    const id = ++seq.detail;
    const data = await fetchJson(`/api/routes/${encodeURIComponent(state.routeId)}?day=${state.day}`);
    if (id !== seq.detail) return;
    state.detail = data;
    renderDetail();
  }

  async function refreshAll() {
    writeUrlState();
    try {
      await Promise.all([loadOverview(), loadDetail()]);
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  // ---------------------------------------------------------------- rendering
  function renderMetadata() {
    const meta = state.metadata;
    $("source-badge").textContent = meta.source;
    $("source-badge").title = meta.source;
    const a = meta.assumptions;
    $("assumption-text").textContent =
      `Suggestions assume ${a.vehicle_capacity}-seat vehicles at ${pct(a.target_occupancy)} target occupancy, ` +
      `choosing from ${a.interval_options.join(", ")}-minute intervals.`;

    const weeks = meta.weeks;
    $("facts").innerHTML = [
      ["Source", meta.source],
      ["Observations", nf.format(meta.observation_count)],
      ["Routes", meta.route_count],
      ["Weeks", weeks.length ? `${weeks.length} (${weeks[0]}–${weeks[weeks.length - 1]})` : "0"],
    ].map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd>`).join("");

    const ev = meta.evaluation;
    $("evaluation").innerHTML = ev
      ? `<div class="muted">Holdout MAE · week ${ev.holdout_week}</div>
         <div class="big">${ev.mae.toFixed(1)} boardings</div>
         <p>Forecasting ${nf.format(ev.predictions)} hourly observations in the latest week from
            week${ev.training_weeks.length > 1 ? "s" : ""} ${ev.training_weeks.join(", ")}.
            Naive route-average baseline: ${ev.baseline_mae.toFixed(1)}.
            Mean recorded boardings: ${ev.mean_actual_boardings.toFixed(1)} per hour.</p>`
      : `<div class="muted">Holdout evaluation</div>
         <p>Needs at least two weeks of observations.</p>`;
  }

  function renderOverview() {
    const { metrics, day_name, hour } = state.overview;
    $("m-hour").textContent = nf.format(metrics.hour_boardings);
    $("m-day").textContent = `${nf.format(metrics.day_boardings)} across ${day_name}`;
    $("m-busiest").textContent = metrics.busiest_route.name;
    $("m-busiest-sub").textContent = `${nf.format(metrics.busiest_route.forecast)} boardings at ${formatHour(hour)}`;
    $("m-over").textContent = metrics.routes_exceeding_target;
    $("m-over").closest(".metric").classList.toggle("metric-alert", metrics.routes_exceeding_target > 0);
    $("m-wait").textContent = minutes(metrics.average_wait_minutes);
    $("m-trips").textContent = `${nf.format(metrics.trips_per_hour)} suggested trips per hour`;
    $("ranking-when").textContent = `${day_name.slice(0, 3)} ${formatHour(hour)}`;

    const top = state.overview.routes.slice(0, 6);
    const max = Math.max(1, ...top.map((r) => r.forecast));
    $("ranking").innerHTML = top.map((r, i) => `
      <li class="rank-row" data-route="${escapeHtml(r.id)}" title="${escapeHtml(r.name)}">
        <span class="rank-pos">${i + 1}</span>
        <span class="rank-name">${escapeHtml(r.name)}</span>
        <span class="rank-value">${nf.format(r.forecast)}${r.exceeds_target ? " ⚠" : ""}</span>
        <span class="rank-bar" aria-hidden="true"><span style="width:${(r.forecast / max) * 100}%"></span></span>
      </li>`).join("");
  }

  function renderRouteList() {
    if (!state.overview || !state.metadata) return;
    const stopsById = Object.fromEntries(state.metadata.routes.map((r) => [r.id, r.stops]));
    const query = state.search.trim().toLowerCase();
    const routes = state.overview.routes
      .filter((r) => !query || r.name.toLowerCase().includes(query) ||
        (stopsById[r.id] || []).some((s) => s.toLowerCase().includes(query)))
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name));

    $("route-count").textContent = query ? `${routes.length} of ${state.overview.routes.length}` : `${routes.length}`;
    $("routes").innerHTML = routes.length
      ? routes.map((r) => `
        <li>
          <button type="button" class="route-item" role="option" data-route="${escapeHtml(r.id)}"
                  aria-selected="${r.id === state.routeId}">
            <span class="name">${escapeHtml(r.name)}</span>
            <span class="value">${nf.format(r.forecast)}</span>
            <span class="meta">Every ${r.interval_minutes} min · ${pct(r.occupancy)} full${
              r.exceeds_target ? ' · <span class="flag">over target</span>' : ""}</span>
          </button>
        </li>`).join("")
      : `<li class="empty">No routes match “${escapeHtml(state.search)}”.</li>`;
  }

  function renderSuggestion() {
    if (!state.overview) return;
    const r = state.overview.routes.find((x) => x.id === state.routeId);
    if (!r) return;
    const a = state.overview.assumptions;
    const notice = r.exceeds_target
      ? `<div class="notice notice-critical" role="alert">${iconAlert()}<span><strong>Over target capacity.</strong>
           Forecast ${nf.format(r.forecast)} boardings exceeds ${nf.format(r.target_capacity)} even at
           ${r.interval_minutes}-minute service (${pct(r.occupancy)} of seats). Consider larger vehicles or extra runs.</span></div>`
      : `<div class="notice notice-good">${iconCheck()}<span>Every ${r.interval_minutes} minutes covers
           ${nf.format(r.forecast)} forecast boardings within the ${pct(a.target_occupancy)} occupancy target
           (${nf.format(r.target_capacity)} per hour).</span></div>`;
    $("suggestion").innerHTML = `
      ${stat("Forecast boardings", nf.format(r.forecast), `${WEEKDAYS[state.day]} ${formatHour(state.hour)}`)}
      ${stat("Suggested interval", `${r.interval_minutes} min`, `${nf.format(r.trips_per_hour)} trips per hour`)}
      ${stat("Seat capacity", nf.format(r.seats_per_hour), `${pct(r.occupancy)} occupied`)}
      ${stat("Estimated wait", minutes(r.estimated_wait_minutes), "half the interval")}
      ${notice}`;
  }

  const stat = (label, value, note) => `
    <div class="stat"><div class="stat-label">${escapeHtml(label)}</div>
    <div class="stat-value">${escapeHtml(value)}</div><div class="stat-note">${escapeHtml(note)}</div></div>`;

  const iconAlert = () =>
    `<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M8 1.5 15 14H1L8 1.5Zm-.75 4.5v4h1.5V6h-1.5Zm0 5v1.5h1.5V11h-1.5Z"/></svg>`;
  const iconCheck = () =>
    `<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M8 1a7 7 0 1 1 0 14A7 7 0 0 1 8 1Zm3.2 4.4L7 9.6 4.8 7.4 3.7 8.5 7 11.8l5.3-5.3-1.1-1.1Z"/></svg>`;

  function renderDetail() {
    const d = state.detail;
    $("route-name").textContent = d.name;
    $("route-summary").textContent =
      `${nf.format(d.daily_total)} forecast boardings on ${d.day_name} · peak at ${formatHour(d.peak_hour)}`;
    $("chart-day").textContent = d.day_name;
    $("stops").innerHTML = d.stops.map((s) => `<li>${escapeHtml(s)}</li>`).join("");
    renderTable();
    drawChart();
  }

  function renderTable() {
    if (!state.detail) return;
    $("hourly-table").innerHTML = state.detail.hourly.map((h) => `
      <tr class="${h.hour === state.hour ? "is-selected" : ""}">
        <td>${formatHour(h.hour)}</td>
        <td>${nf.format(h.forecast)}</td>
        <td>${h.interval_minutes} min${h.exceeds_target ? " ⚠" : ""}</td>
        <td>${pct(h.occupancy)}</td>
        <td>${minutes(h.estimated_wait_minutes)}</td>
      </tr>`).join("");
  }

  // ---------------------------------------------------------------- chart
  const chart = { bars: [], plot: null };

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function niceMax(value) {
    if (value <= 0) return { max: 10, step: 2.5 };
    const magnitude = 10 ** Math.floor(Math.log10(value));
    const step = [1, 2, 2.5, 5, 10].find((s) => s * magnitude * 4 >= value) * magnitude;
    return { max: step * 4, step };
  }

  function roundedTopRect(ctx, x, y, w, h, r) {
    const radius = Math.min(r, w / 2, h);
    ctx.beginPath();
    ctx.moveTo(x, y + h);
    ctx.lineTo(x, y + radius);
    ctx.arcTo(x, y, x + radius, y, radius);
    ctx.lineTo(x + w - radius, y);
    ctx.arcTo(x + w, y, x + w, y + radius, radius);
    ctx.lineTo(x + w, y + h);
    ctx.closePath();
    ctx.fill();
  }

  function drawChart() {
    const canvas = $("chart");
    const d = state.detail;
    if (!d) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);

    const colors = {
      base: cssVar("--bar-base"), selected: cssVar("--bar-selected"), over: cssVar("--bar-over"),
      grid: cssVar("--grid"), text: cssVar("--text-muted"), ref: cssVar("--ref-line"),
    };
    const font = getComputedStyle(document.body).fontFamily;
    const refCapacity = 60 / Math.min(...d.assumptions.interval_options) *
      d.assumptions.vehicle_capacity * d.assumptions.target_occupancy;

    const dataMax = Math.max(refCapacity, ...d.hourly.map((h) => h.forecast));
    const { max, step } = niceMax(dataMax * 1.05);
    const pad = { top: 12, right: 8, bottom: 26, left: 40 };
    const plot = { x: pad.left, y: pad.top, w: rect.width - pad.left - pad.right, h: rect.height - pad.top - pad.bottom };
    chart.plot = plot;
    const yOf = (v) => plot.y + plot.h - (v / max) * plot.h;

    // Gridlines and y ticks
    ctx.font = `11px ${font}`;
    ctx.fillStyle = colors.text;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.lineWidth = 1;
    for (let v = 0; v <= max + 1e-9; v += step) {
      const y = Math.round(yOf(v)) + 0.5;
      ctx.strokeStyle = colors.grid;
      ctx.beginPath(); ctx.moveTo(plot.x, y); ctx.lineTo(plot.x + plot.w, y); ctx.stroke();
      ctx.fillText(nf.format(v), plot.x - 8, y);
    }

    // Bars
    const slot = plot.w / 24;
    const barW = Math.max(2, Math.min(24, slot - 2));
    chart.bars = d.hourly.map((h) => {
      const x = plot.x + h.hour * slot + (slot - barW) / 2;
      const y = yOf(h.forecast);
      const barH = plot.y + plot.h - y;
      ctx.fillStyle = h.exceeds_target ? colors.over : h.hour === state.hour ? colors.selected : colors.base;
      if (barH > 0.5) roundedTopRect(ctx, x, y, barW, barH, 4);
      return { hour: h.hour, x0: plot.x + h.hour * slot, x1: plot.x + (h.hour + 1) * slot, data: h };
    });

    // Selected hour marker beneath the axis (keeps the selection visible on over-target bars)
    const sel = chart.bars[state.hour];
    ctx.fillStyle = colors.selected;
    ctx.fillRect(sel.x0 + (slot - barW) / 2, plot.y + plot.h + 2, barW, 3);

    // Reference capacity line
    const refY = Math.round(yOf(refCapacity)) + 0.5;
    ctx.strokeStyle = colors.ref;
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(plot.x, refY); ctx.lineTo(plot.x + plot.w, refY); ctx.stroke();
    ctx.fillStyle = colors.text;
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    ctx.fillText(`10-min target · ${nf.format(refCapacity)}/hr`, plot.x + 4, refY - 3);

    // Hover highlight
    if (state.hoverHour !== null) {
      const b = chart.bars[state.hoverHour];
      ctx.fillStyle = colors.grid;
      ctx.globalAlpha = 0.35;
      ctx.fillRect(b.x0, plot.y, b.x1 - b.x0, plot.h);
      ctx.globalAlpha = 1;
    }

    // X labels
    ctx.fillStyle = colors.text;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const every = slot < 18 ? 6 : slot < 30 ? 3 : 2;
    for (let h = 0; h < 24; h += every) {
      ctx.fillText(String(h).padStart(2, "0"), plot.x + h * slot + slot / 2, plot.y + plot.h + 9);
    }
  }

  function hourAt(event) {
    const rect = $("chart").getBoundingClientRect();
    const x = event.clientX - rect.left;
    const bar = chart.bars.find((b) => x >= b.x0 && x < b.x1);
    return bar ? bar.hour : null;
  }

  function showTooltip(event) {
    const hour = hourAt(event);
    const tip = $("tooltip");
    if (hour === null) { hideTooltip(); return; }
    if (hour !== state.hoverHour) { state.hoverHour = hour; drawChart(); }
    const h = state.detail.hourly[hour];
    tip.innerHTML = `<strong>${formatHour(hour)}${h.exceeds_target ? " · over target ⚠" : ""}</strong>
      <div class="row"><span>Forecast</span><span>${nf.format(h.forecast)}</span></div>
      <div class="row"><span>Interval</span><span>${h.interval_minutes} min</span></div>
      <div class="row"><span>Occupancy</span><span>${pct(h.occupancy)}</span></div>
      <div class="row"><span>Est. wait</span><span>${minutes(h.estimated_wait_minutes)}</span></div>`;
    tip.hidden = false;
    const wrap = $("chart-wrap").getBoundingClientRect();
    const bar = chart.bars[hour];
    const left = Math.min(Math.max(0, bar.x0 + (bar.x1 - bar.x0) / 2 - tip.offsetWidth / 2), wrap.width - tip.offsetWidth);
    tip.style.left = `${left}px`;
    tip.style.top = `${Math.max(0, event.clientY - wrap.top - tip.offsetHeight - 14)}px`;
  }

  function hideTooltip() {
    $("tooltip").hidden = true;
    if (state.hoverHour !== null) { state.hoverHour = null; drawChart(); }
  }

  // ---------------------------------------------------------------- interactions
  function selectRoute(routeId) {
    if (routeId === state.routeId) return;
    state.routeId = routeId;
    writeUrlState();
    renderRouteList();
    renderSuggestion();
    loadDetail().catch((e) => setStatus(e.message, "error"));
  }

  function setHour(hour) {
    state.hour = hour;
    $("hour-input").value = hour;
    $("hour-output").textContent = formatHour(hour);
    renderTable();
    drawChart();
    writeUrlState();
    clearTimeout(setHour.timer);
    setHour.timer = setTimeout(() => loadOverview().catch((e) => setStatus(e.message, "error")), 80);
  }

  async function importCsv(file) {
    if (!file) return;
    setStatus(`Importing ${file.name}…`);
    try {
      state.metadata = await fetchJson("/api/import", {
        method: "POST",
        headers: { "Content-Type": "text/csv", "X-Filename": file.name.replace(/[^\w.\- ]/g, "") },
        body: await file.text(),
      });
      renderMetadata();
      await refreshAll();
      setStatus(`Imported ${nf.format(state.metadata.observation_count)} observations from ${file.name}.`, "ok");
    } catch (error) {
      setStatus(error.message, "error", error.details);
    }
  }

  async function resetDemo() {
    const button = $("reset-button");
    button.disabled = true;
    try {
      state.metadata = await fetchJson("/api/demo/reset", { method: "POST" });
      renderMetadata();
      await refreshAll();
      setStatus("Synthetic demo data restored.", "ok");
    } catch (error) {
      setStatus(error.message, "error");
    } finally {
      button.disabled = false;
    }
  }

  function bindEvents() {
    $("day-select").addEventListener("change", (e) => { state.day = Number(e.target.value); refreshAll(); });
    $("hour-input").addEventListener("input", (e) => setHour(Number(e.target.value)));
    $("route-search").addEventListener("input", (e) => { state.search = e.target.value; renderRouteList(); });
    $("routes").addEventListener("click", (e) => {
      const item = e.target.closest("[data-route]");
      if (item) selectRoute(item.dataset.route);
    });
    $("routes").addEventListener("keydown", (e) => {
      if (!["ArrowDown", "ArrowUp"].includes(e.key)) return;
      const items = [...$("routes").querySelectorAll(".route-item")];
      const index = items.indexOf(document.activeElement);
      const next = items[index + (e.key === "ArrowDown" ? 1 : -1)];
      if (next) { e.preventDefault(); next.focus(); }
    });
    $("ranking").addEventListener("click", (e) => {
      const row = e.target.closest("[data-route]");
      if (row) selectRoute(row.dataset.route);
    });
    const canvas = $("chart");
    canvas.addEventListener("mousemove", showTooltip);
    canvas.addEventListener("mouseleave", hideTooltip);
    canvas.addEventListener("click", (e) => { const h = hourAt(e); if (h !== null) setHour(h); });
    $("import-input").addEventListener("change", (e) => { importCsv(e.target.files[0]); e.target.value = ""; });
    $("reset-button").addEventListener("click", resetDemo);
    new ResizeObserver(() => drawChart()).observe($("chart-wrap"));
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", drawChart);
  }

  async function init() {
    readUrlState();
    $("day-select").innerHTML = WEEKDAYS.map((d, i) => `<option value="${i}">${d}</option>`).join("");
    $("day-select").value = state.day;
    $("hour-input").value = state.hour;
    $("hour-output").textContent = formatHour(state.hour);
    bindEvents();
    try {
      await loadMetadata();
      await refreshAll();
    } catch (error) {
      setStatus(`Could not load the dashboard: ${error.message}`, "error");
    }
  }

  init();
})();
