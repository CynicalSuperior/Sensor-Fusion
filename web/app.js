const state = {
  meta: null,
  hexes: [],
  selectedHex: "",
  maxCount: 1,
};

const els = {
  metaLine: document.getElementById("metaLine"),
  sourceFilter: document.getElementById("sourceFilter"),
  familyFilter: document.getElementById("familyFilter"),
  dateFrom: document.getElementById("dateFrom"),
  dateTo: document.getElementById("dateTo"),
  confidenceFilter: document.getElementById("confidenceFilter"),
  confidenceValue: document.getElementById("confidenceValue"),
  searchFilter: document.getElementById("searchFilter"),
  resetButton: document.getElementById("resetButton"),
  reloadButton: document.getElementById("reloadButton"),
  visibleEvents: document.getElementById("visibleEvents"),
  visibleHexes: document.getElementById("visibleHexes"),
  selectedHexLabel: document.getElementById("selectedHexLabel"),
  map: document.getElementById("hexMap"),
  timelineList: document.getElementById("timelineList"),
  timelineSubtitle: document.getElementById("timelineSubtitle"),
  timelineCount: document.getElementById("timelineCount"),
};

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json();
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(value || 0);
}

function toDateInput(value) {
  if (!value) return "";
  return value.slice(0, 10);
}

function filtersToParams() {
  const params = new URLSearchParams();
  const source = els.sourceFilter.value;
  const family = els.familyFilter.value;
  if (source && source !== "all") params.set("source", source);
  if (family && family !== "all") params.set("family", family);
  if (els.dateFrom.value) params.set("date_from", els.dateFrom.value);
  if (els.dateTo.value) params.set("date_to", els.dateTo.value);
  if (Number(els.confidenceFilter.value) > 0) params.set("min_conf", els.confidenceFilter.value);
  if (els.searchFilter.value.trim()) params.set("q", els.searchFilter.value.trim());
  return params;
}

function populateSelect(select, values, allLabel) {
  select.innerHTML = "";
  const all = document.createElement("option");
  all.value = "all";
  all.textContent = allLabel;
  select.appendChild(all);
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value || "unknown";
    select.appendChild(option);
  });
}

function hexPoints(cx, cy, size) {
  const points = [];
  for (let i = 0; i < 6; i += 1) {
    const angle = (Math.PI / 180) * (60 * i - 30);
    points.push([cx + size * Math.cos(angle), cy + size * Math.sin(angle)]);
  }
  return points;
}

function colorFor(count) {
  const t = Math.min(1, Math.log1p(count) / Math.log1p(state.maxCount));
  if (t < 0.45) {
    return interpolateColor([203, 217, 209], [127, 164, 137], t / 0.45);
  }
  return interpolateColor([127, 164, 137], [157, 63, 50], (t - 0.45) / 0.55);
}

function interpolateColor(a, b, t) {
  const channel = (i) => Math.round(a[i] + (b[i] - a[i]) * t);
  return `rgb(${channel(0)}, ${channel(1)}, ${channel(2)})`;
}

function renderMap() {
  const hexes = state.hexes;
  const frame = document.getElementById("mapFrame").getBoundingClientRect();
  const width = Math.max(520, frame.width || 820);
  const height = Math.max(420, frame.height || 560);
  const dpr = window.devicePixelRatio || 1;
  els.map.width = Math.round(width * dpr);
  els.map.height = Math.round(height * dpr);
  const ctx = els.map.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  state.renderedHexes = [];

  if (!hexes.length) {
    ctx.fillStyle = "#68716b";
    ctx.font = "16px Inter, system-ui, sans-serif";
    ctx.fillText("No hexes match the current filters.", 28, 46);
    return;
  }

  const coords = hexes.map((hex) => ({
    ...hex,
    x: Math.sqrt(3) * (hex.hex_q + hex.hex_r / 2),
    y: 1.5 * hex.hex_r,
  }));
  const minX = Math.min(...coords.map((hex) => hex.x));
  const maxX = Math.max(...coords.map((hex) => hex.x));
  const minY = Math.min(...coords.map((hex) => hex.y));
  const maxY = Math.max(...coords.map((hex) => hex.y));
  const pad = 34;
  const scale = Math.max(
    4,
    Math.min((width - pad * 2) / Math.max(1, maxX - minX + 2), (height - pad * 2) / Math.max(1, maxY - minY + 2))
  );
  const radius = Math.max(8, Math.min(22, scale * 0.9));

  coords.forEach((hex) => {
    const cx = (hex.x - minX + 1) * scale + pad;
    const cy = (hex.y - minY + 1) * scale + pad;
    const points = hexPoints(cx, cy, radius);
    ctx.beginPath();
    points.forEach(([x, y], index) => {
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.fillStyle = colorFor(hex.event_count);
    ctx.globalAlpha = 0.92;
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.strokeStyle = hex.hex_cell === state.selectedHex ? "#101714" : "rgba(31, 37, 33, 0.42)";
    ctx.lineWidth = hex.hex_cell === state.selectedHex ? 3 : 1;
    ctx.stroke();
    state.renderedHexes.push({ ...hex, cx, cy, radius });
  });
}

function eventTitle(event) {
  const type = event.app6_type || event.object_type || event.object_family || "event";
  const status = event.status ? ` - ${event.status}` : "";
  return `${type}${status}`;
}

function eventDetails(event) {
  const parts = [
    event.identity,
    event.signal_type,
    event.mission,
    event.uav_type,
    event.route_type,
    `confidence ${Number(event.confidence || 0).toFixed(2)}`,
    `${Number(event.lat).toFixed(4)}, ${Number(event.lon).toFixed(4)}`,
  ].filter(Boolean);
  return parts.join(" | ");
}

function renderTimeline(payload) {
  const events = payload.events || [];
  els.timelineList.innerHTML = "";
  els.timelineCount.textContent = `${formatNumber(payload.count)} events`;
  els.timelineSubtitle.textContent = payload.hex_cell
    ? `Timeline for ${payload.hex_cell}`
    : "Showing earliest matching events.";

  if (!events.length) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "No events match the current selection.";
    els.timelineList.appendChild(empty);
    return;
  }

  events.forEach((event) => {
    const item = document.createElement("li");
    item.className = "timeline-item";

    const time = document.createElement("time");
    time.className = "timeline-time";
    const observed = new Date(event.observed_at);
    time.dateTime = event.observed_at;
    time.innerHTML = `${observed.toLocaleDateString()}<br />${observed.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    })}`;

    const main = document.createElement("div");
    main.className = "timeline-main";

    const source = document.createElement("span");
    source.className = "source-pill";
    source.textContent = event.source;

    const title = document.createElement("div");
    title.className = "event-title";
    title.textContent = eventTitle(event);

    const meta = document.createElement("div");
    meta.className = "event-meta";
    meta.textContent = `${event.source_id} | ${eventDetails(event)}`;

    main.append(source, title, meta);
    item.append(time, main);
    els.timelineList.appendChild(item);
  });
}

async function loadHexes() {
  const params = filtersToParams();
  const payload = await getJson(`/api/hexes?${params.toString()}`);
  state.hexes = payload.hexes || [];
  state.maxCount = Math.max(1, ...state.hexes.map((hex) => hex.event_count));
  els.visibleEvents.textContent = formatNumber(payload.event_count || 0);
  els.visibleHexes.textContent = formatNumber(payload.count || 0);
  if (state.selectedHex && !state.hexes.some((hex) => hex.hex_cell === state.selectedHex)) {
    state.selectedHex = "";
  }
  els.selectedHexLabel.textContent = state.selectedHex || "None";
  renderMap();
  await loadTimeline();
}

async function loadTimeline() {
  const params = filtersToParams();
  if (state.selectedHex) params.set("hex_cell", state.selectedHex);
  params.set("limit", "300");
  const payload = await getJson(`/api/timeline?${params.toString()}`);
  renderTimeline(payload);
}

async function selectHex(hexCell) {
  state.selectedHex = hexCell;
  els.selectedHexLabel.textContent = hexCell || "None";
  renderMap();
  await loadTimeline();
}

function resetFilters() {
  els.sourceFilter.value = "all";
  els.familyFilter.value = "all";
  els.dateFrom.value = state.meta ? toDateInput(state.meta.observed_min) : "";
  els.dateTo.value = state.meta ? toDateInput(state.meta.observed_max) : "";
  els.confidenceFilter.value = "0";
  els.confidenceValue.textContent = "0.00";
  els.searchFilter.value = "";
  state.selectedHex = "";
  loadHexes().catch(showError);
}

function showError(error) {
  els.metaLine.textContent = error.message;
  els.timelineList.innerHTML = `<li class="empty-state">${error.message}</li>`;
}

let filterTimer = null;
function scheduleFilterUpdate() {
  clearTimeout(filterTimer);
  filterTimer = setTimeout(() => {
    loadHexes().catch(showError);
  }, 180);
}

async function init() {
  state.meta = await getJson("/api/meta");
  els.metaLine.textContent = `${formatNumber(state.meta.total_events)} events, ${formatNumber(
    state.meta.total_hexes
  )} hex cells, ${formatNumber(state.meta.total_clusters)} fusion clusters`;
  populateSelect(els.sourceFilter, state.meta.sources, "All sources");
  populateSelect(els.familyFilter, state.meta.families, "All families");
  els.dateFrom.value = toDateInput(state.meta.observed_min);
  els.dateTo.value = toDateInput(state.meta.observed_max);
  await loadHexes();
}

[els.sourceFilter, els.familyFilter, els.dateFrom, els.dateTo].forEach((el) => {
  el.addEventListener("change", scheduleFilterUpdate);
});
els.confidenceFilter.addEventListener("input", () => {
  els.confidenceValue.textContent = Number(els.confidenceFilter.value).toFixed(2);
  scheduleFilterUpdate();
});
els.searchFilter.addEventListener("input", scheduleFilterUpdate);
els.resetButton.addEventListener("click", resetFilters);
els.reloadButton.addEventListener("click", async () => {
  await getJson("/api/reload");
  state.selectedHex = "";
  await init();
});
els.map.addEventListener("click", async (event) => {
  const rect = els.map.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  let best = null;
  let bestDistance = Infinity;
  (state.renderedHexes || []).forEach((hex) => {
    const distance = Math.hypot(hex.cx - x, hex.cy - y);
    if (distance < bestDistance && distance <= hex.radius * 1.35) {
      best = hex;
      bestDistance = distance;
    }
  });
  if (best) {
    await selectHex(best.hex_cell);
  }
});
window.addEventListener("resize", () => renderMap());

init().catch(showError);
