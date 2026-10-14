// Naver Map sidebar panel: search places, pick origin/destination, and draw the
// naver_map.get_directions route on Home Assistant's own <ha-map> (OSM tiles via
// core's map_tiles proxy). Plain custom element, no build step.
//
// Panel strings live in the dictionary below, chosen by hass.language: panel
// JS is outside the backend translations/ files, which only cover services.

const MODES = ["car", "transit", "walk", "bicycle"];
const ENTITY_DOMAINS = ["person", "zone", "device_tracker"];
const REQUERY_DELAY = 800; // ms; marker drags re-query Directions 5, a paid API
const COLORS = { origin: "#03c75a", destination: "#e5484d", route: "#03c75a" };

const STRINGS = {
  en: {
    title: "Naver Map",
    origin: "Origin",
    destination: "Destination",
    search: "Search",
    searchPlaceholder: "Search a place",
    entity: "Entity…",
    pickOnMap: "Pick on map",
    pickingHint: "Click the map to set the point",
    modes: { car: "Car", transit: "Transit", walk: "Walk", bicycle: "Bicycle" },
    duration: "Duration",
    distance: "Distance",
    arrival: "Arrival",
    transfers: "Transfers",
    fare: "Fare",
    noEta: "No travel time available",
    straightLine: "Route line unavailable; showing straight segments",
    openInNaver: "Open in Naver Map",
    loading: "Looking up the route…",
    mapUnavailable:
      "The map component isn't loaded yet. Open the Overview dashboard once, then come back.",
    selected: "Map point",
    hour: "h",
    minute: "min",
    won: "KRW",
  },
  ko: {
    title: "네이버 지도",
    origin: "출발",
    destination: "도착",
    search: "검색",
    searchPlaceholder: "장소 검색",
    entity: "엔티티…",
    pickOnMap: "지도에서 선택",
    pickingHint: "지도를 클릭해 지점을 지정하세요",
    modes: { car: "자동차", transit: "대중교통", walk: "도보", bicycle: "자전거" },
    duration: "소요 시간",
    distance: "거리",
    arrival: "도착 예정",
    transfers: "환승",
    fare: "요금",
    noEta: "예상시간 없음",
    straightLine: "경로선을 가져오지 못해 직선으로 표시합니다",
    openInNaver: "네이버 지도에서 열기",
    loading: "경로를 찾는 중…",
    mapUnavailable: "지도 구성요소가 아직 로드되지 않았습니다. 개요 대시보드를 한 번 연 뒤 다시 와 주세요.",
    selected: "지도에서 선택한 지점",
    hour: "시간",
    minute: "분",
    won: "원",
  },
};

const escapeHtml = (text) =>
  String(text ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );

// <ha-map> is lazy-loaded by the frontend and is not defined when the panel URL
// is opened directly. Public route first (window.loadCardHelpers, set once a
// dashboard has loaded); otherwise load the lovelace panel through
// partial-panel-resolver, the approach community card helpers use. That second
// step relies on frontend internals, so any failure just reports "unavailable".
async function ensureHaMap() {
  if (customElements.get("ha-map")) return true;
  try {
    if (!window.loadCardHelpers) {
      await customElements.whenDefined("partial-panel-resolver");
      const resolver = document.createElement("partial-panel-resolver");
      resolver.hass = { panels: [{ url_path: "tmp", component_name: "lovelace" }] };
      resolver._updateRoutes();
      await resolver.routerOptions.routes.tmp.load();
    }
    const helpers = await window.loadCardHelpers();
    await helpers.createCardElement({ type: "map", entities: ["zone.home"] });
    await Promise.race([
      customElements.whenDefined("ha-map"),
      new Promise((resolve) => setTimeout(resolve, 10000)),
    ]);
  } catch (err) {
    console.warn("[naver-map-panel] could not load ha-map:", err);
  }
  return Boolean(customElements.get("ha-map"));
}

class NaverMapPanel extends HTMLElement {
  constructor() {
    super();
    this._points = { origin: null, destination: null };
    this._queries = { origin: "", destination: "" };
    this._results = { origin: [], destination: [] };
    this._mode = "car";
    this._route = null;
    this._error = null;
    this._loading = false;
    this._picking = null;
    this._requestId = 0;
    this._requeryTimer = null;
    this._entityIds = "";
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (this._map) {
      this._map.hass = hass;
      this._syncMapEntities();
    }
    if (this._menuButton) this._menuButton.hass = hass;
    if (first && this.isConnected) this._render();
  }

  get hass() {
    return this._hass;
  }

  set narrow(narrow) {
    this._narrow = narrow;
    this.classList.toggle("narrow", Boolean(narrow));
    if (this._menuButton) this._menuButton.narrow = narrow;
  }

  get _t() {
    const lang = (this._hass?.language || "en").split("-")[0];
    return STRINGS[lang] || STRINGS.en;
  }

  connectedCallback() {
    if (this._root) return;
    this._root = this.attachShadow({ mode: "open" });
    this._root.innerHTML = `
      <style>${STYLE}</style>
      <div class="layout">
        <div class="header"><span class="menu"></span><span class="title"></span></div>
        <div class="sheet"></div>
        <div class="map"></div>
      </div>`;
    this._sheet = this._root.querySelector(".sheet");
    this._sheet.addEventListener("click", (ev) => this._onClick(ev));
    this._sheet.addEventListener("change", (ev) => this._onChange(ev));
    this._sheet.addEventListener("input", (ev) => {
      if (ev.target.dataset.query) this._queries[ev.target.dataset.query] = ev.target.value;
    });
    this._sheet.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && ev.target.dataset.query) this._search(ev.target.dataset.query);
    });
    customElements.whenDefined("ha-menu-button").then(() => {
      this._menuButton = document.createElement("ha-menu-button");
      this._menuButton.hass = this._hass;
      this._menuButton.narrow = this._narrow;
      this._root.querySelector(".menu").appendChild(this._menuButton);
    });
    this._setUpMap();
    if (this._hass) this._render();
  }

  async _setUpMap() {
    const container = this._root.querySelector(".map");
    if (!(await ensureHaMap())) {
      container.innerHTML = `<div class="notice">${escapeHtml(this._t.mapUnavailable)}</div>`;
      return;
    }
    const map = document.createElement("ha-map");
    map.clickable = true;
    map.autoFit = false;
    map.themeMode = "auto";
    map.hass = this._hass;
    map.addEventListener("map-clicked", (ev) => this._onMapClicked(ev.detail.location));
    map.addEventListener("editable-location-moved", (ev) =>
      this._onMarkerMoved(ev.detail.id, ev.detail.location)
    );
    container.appendChild(map);
    this._map = map;
    this._syncMapEntities();
    this._drawMap();
  }

  // person/zone/device_tracker states that carry coordinates.
  _locatedEntities() {
    return Object.values(this._hass?.states || {})
      .filter(
        (s) =>
          ENTITY_DOMAINS.includes(s.entity_id.split(".")[0]) &&
          typeof s.attributes.latitude === "number" &&
          typeof s.attributes.longitude === "number"
      )
      .sort((a, b) => a.entity_id.localeCompare(b.entity_id));
  }

  _syncMapEntities() {
    if (!this._map) return;
    const ids = this._locatedEntities()
      .filter((s) => !s.entity_id.startsWith("device_tracker."))
      .map((s) => s.entity_id);
    const key = ids.join(",");
    if (key === this._entityIds) return;
    this._entityIds = key;
    this._map.entities = ids;
  }

  _setPoint(slot, point) {
    this._points[slot] = point;
    this._results[slot] = [];
    this._picking = null;
    this._render();
    this._drawMap();
    this._query();
  }

  _onClick(ev) {
    const el = ev.target.closest("[data-action]");
    if (!el) return;
    const { action, slot } = el.dataset;
    if (action === "search") this._search(slot);
    else if (action === "pick") {
      this._picking = this._picking === slot ? null : slot;
      this._render();
    } else if (action === "result") {
      const place = this._results[slot][Number(el.dataset.index)];
      this._queries[slot] = place.place_name;
      this._setPoint(slot, {
        label: place.place_name,
        location: [place.latitude, place.longitude],
      });
    } else if (action === "mode") {
      this._mode = el.dataset.mode;
      this._render();
      this._query();
    }
  }

  _onChange(ev) {
    const slot = ev.target.dataset.entity;
    if (!slot || !ev.target.value) return;
    const state = this._hass.states[ev.target.value];
    if (!state) return;
    this._setPoint(slot, {
      label: state.attributes.friendly_name || state.entity_id,
      entityId: state.entity_id,
      location: [state.attributes.latitude, state.attributes.longitude],
    });
  }

  _onMapClicked(location) {
    if (!this._picking) return;
    this._setPoint(this._picking, { label: this._t.selected, location });
  }

  _onMarkerMoved(slot, location) {
    if (!this._points[slot]) return;
    // A dragged point is a plain coordinate now, even if it started as an entity.
    this._points[slot] = { label: this._t.selected, location };
    this._queries[slot] = "";
    this._render();
    clearTimeout(this._requeryTimer);
    this._requeryTimer = setTimeout(() => this._query(), REQUERY_DELAY);
  }

  async _callService(service, data) {
    const result = await this._hass.callWS({
      type: "call_service",
      domain: "naver_map",
      service,
      service_data: data,
      return_response: true,
    });
    return result.response;
  }

  async _search(slot) {
    const query = (this._queries[slot] || "").trim();
    if (!query) return;
    this._error = null;
    try {
      const response = await this._callService("search_place", { query });
      this._results[slot] = response.results;
    } catch (err) {
      this._results[slot] = [];
      this._error = err.message || String(err);
    }
    this._render();
  }

  async _query() {
    const { origin, destination } = this._points;
    if (!origin || !destination) return;
    const pointInput = (point) =>
      point.entityId || { latitude: point.location[0], longitude: point.location[1] };
    const requestId = ++this._requestId;
    this._loading = true;
    this._error = null;
    this._render();
    try {
      const route = await this._callService("get_directions", {
        origin: pointInput(origin),
        destination: pointInput(destination),
        mode: this._mode,
        include_geometry: true,
      });
      if (requestId !== this._requestId) return; // a newer lookup superseded this one
      this._route = route;
    } catch (err) {
      if (requestId !== this._requestId) return;
      this._route = null;
      this._error = err.message || String(err);
    }
    this._loading = false;
    this._render();
    this._drawMap();
  }

  _drawMap() {
    if (!this._map) return;
    const t = this._t;
    this._map.editableLocations = ["origin", "destination"]
      .filter((slot) => this._points[slot])
      .map((slot) => ({
        id: slot,
        location: this._points[slot].location,
        title: `${t[slot]}: ${this._points[slot].label}`,
        color: COLORS[slot],
        element: this._markerElement(slot),
        elementSize: 20,
        locationEditable: true,
      }));
    const line = this._routeLine();
    if (line.length) {
      // ha-map labels each path point with a time; spread the ETA along the line.
      const start = Date.now();
      const total = (this._route.duration || 0) * 1000;
      this._map.paths = [
        {
          name: t.modes[this._route.mode] || this._route.mode,
          color: COLORS.route,
          points: line.map((point, i) => ({
            point,
            timestamp: new Date(start + (total * i) / Math.max(line.length - 1, 1)),
          })),
        },
      ];
      this._map.fitBounds(line, { pad: 0.15 });
    } else {
      this._map.paths = [];
      const marks = ["origin", "destination"]
        .filter((slot) => this._points[slot])
        .map((slot) => this._points[slot].location);
      if (marks.length) this._map.fitBounds(marks, { pad: 0.5, zoom: 15 });
    }
  }

  // A colored dot, cached so ha-map sees the same element and keeps the marker.
  _markerElement(slot) {
    this._markers ||= {};
    if (!this._markers[slot]) {
      const dot = document.createElement("div");
      dot.style.cssText = `width:20px;height:20px;box-sizing:border-box;border-radius:50%;
        border:3px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4);background:${COLORS[slot]};cursor:grab`;
      this._markers[slot] = dot;
    }
    return this._markers[slot];
  }

  // Route geometry when available, else straight segments through the legs.
  _routeLine() {
    if (!this._route) return [];
    if (this._route.geometry?.length) return this._route.geometry;
    const legs = this._route.legs || [];
    if (!legs.length) return [];
    return [
      [legs[0].from_latitude, legs[0].from_longitude],
      ...legs.map((leg) => [leg.to_latitude, leg.to_longitude]),
    ];
  }

  _formatDuration(seconds) {
    const t = this._t;
    const minutes = Math.round(seconds / 60);
    const hours = Math.floor(minutes / 60);
    return hours ? `${hours}${t.hour} ${minutes % 60}${t.minute}` : `${minutes}${t.minute}`;
  }

  _formatDistance(meters) {
    return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${meters} m`;
  }

  _renderSlot(slot, entities) {
    const t = this._t;
    const point = this._points[slot];
    const results = this._results[slot]
      .map(
        (place, index) => `
        <li><button class="result" data-action="result" data-slot="${slot}" data-index="${index}">
          <b>${escapeHtml(place.place_name)}</b>
          <small>${escapeHtml(place.road_address || place.address)}</small>
        </button></li>`
      )
      .join("");
    const options = entities
      .map(
        (s) =>
          `<option value="${escapeHtml(s.entity_id)}" ${point?.entityId === s.entity_id ? "selected" : ""}>${escapeHtml(s.attributes.friendly_name || s.entity_id)}</option>`
      )
      .join("");
    return `
      <section class="slot">
        <div class="slot-head">
          <span class="dot" style="background:${COLORS[slot]}"></span>
          <b>${t[slot]}</b>
          <span class="chosen">${escapeHtml(point?.label || "")}</span>
        </div>
        <div class="row">
          <input data-query="${slot}" placeholder="${escapeHtml(t.searchPlaceholder)}" value="${escapeHtml(this._queries[slot])}">
          <button data-action="search" data-slot="${slot}">${t.search}</button>
        </div>
        <div class="row">
          <select data-entity="${slot}"><option value="">${t.entity}</option>${options}</select>
          <button data-action="pick" data-slot="${slot}" class="${this._picking === slot ? "active" : ""}">${t.pickOnMap}</button>
        </div>
        ${results ? `<ul class="results">${results}</ul>` : ""}
      </section>`;
  }

  _renderResult() {
    const t = this._t;
    if (this._loading) return `<p class="muted">${t.loading}</p>`;
    if (this._error) return `<p class="error">${escapeHtml(this._error)}</p>`;
    const route = this._route;
    if (!route) return "";
    const rows = [];
    if (route.duration == null) {
      rows.push(`<p class="muted">${t.noEta}</p>`);
    } else {
      const arrival = new Date(route.arrival_time).toLocaleTimeString(this._hass.language, {
        hour: "2-digit",
        minute: "2-digit",
      });
      rows.push(`<dl>
        <dt>${t.duration}</dt><dd>${this._formatDuration(route.duration)}</dd>
        <dt>${t.distance}</dt><dd>${this._formatDistance(route.distance)}</dd>
        <dt>${t.arrival}</dt><dd>${arrival}</dd>
        ${route.transfers != null ? `<dt>${t.transfers}</dt><dd>${route.transfers}</dd>` : ""}
        ${route.fare != null ? `<dt>${t.fare}</dt><dd>${route.fare.toLocaleString()} ${t.won}</dd>` : ""}
      </dl>`);
    }
    if (!route.geometry?.length) rows.push(`<p class="muted">${t.straightLine}</p>`);
    rows.push(
      `<a class="open" href="${escapeHtml(route.route_url)}" target="_blank" rel="noopener noreferrer">${t.openInNaver}</a>`
    );
    return `<section class="result-box">${rows.join("")}</section>`;
  }

  _render() {
    if (!this._sheet || !this._hass) return;
    const t = this._t;
    this._root.querySelector(".title").textContent = t.title;
    const entities = this._locatedEntities();
    const modes = MODES.map(
      (mode) =>
        `<button data-action="mode" data-mode="${mode}" class="${mode === this._mode ? "active" : ""}">${t.modes[mode]}</button>`
    ).join("");
    this._sheet.innerHTML = `
      ${this._renderSlot("origin", entities)}
      ${this._renderSlot("destination", entities)}
      ${this._picking ? `<p class="hint">${t.pickingHint}</p>` : ""}
      <div class="modes">${modes}</div>
      ${this._renderResult()}`;
  }
}

const STYLE = `
  :host { display: block; height: 100vh; height: 100dvh; background: var(--primary-background-color); color: var(--primary-text-color); }
  .layout { display: grid; height: 100%; grid-template-columns: 380px 1fr; grid-template-rows: var(--header-height, 56px) 1fr;
    grid-template-areas: "header header" "sheet map"; }
  .header { grid-area: header; display: flex; align-items: center; gap: 8px; padding: 0 12px;
    background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, #fff);
    font-size: 20px; }
  .sheet { grid-area: sheet; overflow-y: auto; padding: 12px; box-sizing: border-box;
    border-right: 1px solid var(--divider-color); display: flex; flex-direction: column; gap: 12px; }
  .map { grid-area: map; position: relative; min-height: 0; }
  .map ha-map { display: block; height: 100%; }
  :host(.narrow) .layout { grid-template-columns: 1fr; grid-template-rows: var(--header-height, 56px) 50% 1fr;
    grid-template-areas: "header" "map" "sheet"; }
  :host(.narrow) .sheet { border-right: none; border-top: 1px solid var(--divider-color); }
  .slot { display: flex; flex-direction: column; gap: 6px; }
  .slot-head { display: flex; align-items: center; gap: 6px; }
  .chosen { color: var(--secondary-text-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .dot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
  .row { display: flex; gap: 6px; }
  input, select { flex: 1; min-width: 0; padding: 8px; border-radius: 6px; border: 1px solid var(--divider-color);
    background: var(--card-background-color); color: var(--primary-text-color); font: inherit; }
  button { padding: 8px 10px; border-radius: 6px; border: 1px solid var(--divider-color); cursor: pointer;
    background: var(--card-background-color); color: var(--primary-text-color); font: inherit; }
  button.active { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
  .modes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
  .results { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
  .result { width: 100%; text-align: left; display: flex; flex-direction: column; gap: 2px; }
  .result small { color: var(--secondary-text-color); }
  .result-box { padding: 12px; border-radius: 8px; background: var(--card-background-color); }
  dl { display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; margin: 0 0 8px; }
  dt { color: var(--secondary-text-color); }
  dd { margin: 0; }
  .open { display: inline-block; color: var(--primary-color); }
  .muted, .hint { color: var(--secondary-text-color); margin: 0; }
  .error { color: var(--error-color); margin: 0; }
  .notice { padding: 24px; color: var(--secondary-text-color); }
`;

customElements.define("naver-map-panel", NaverMapPanel);
