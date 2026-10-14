// Naver Map sidebar panel: search places, pick origin/destination, and draw the
// naver_map.get_directions route on Home Assistant's own <ha-map> (OSM tiles via
// core's map_tiles proxy). Plain custom element, no build step.
//
// Panel strings live in the dictionary below, chosen by hass.language: panel
// JS is outside the backend translations/ files, which only cover services.

const MODES = ["car", "transit", "walk", "bicycle"];
const ENTITY_DOMAINS = ["person", "zone", "device_tracker"];
const REQUERY_DELAY = 800; // ms; marker drags re-query Directions 5, a paid API
const COLORS = {
  origin: "#03c75a",
  destination: "#e5484d",
  route: "#03c75a",
  place: "#1e6fff",
  activePlace: "#ff7a00",
};

const STRINGS = {
  en: {
    title: "Naver Map",
    tabs: { place: "Places", route: "Directions" },
    setOrigin: "Set as origin",
    setDestination: "Set as destination",
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
    steps: "Route details",
    stops: (n) => `${n} stop${n === 1 ? "" : "s"}`,
    bound: (headsign) => `toward ${headsign}`,
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
    tabs: { place: "장소 검색", route: "길찾기" },
    setOrigin: "출발지로",
    setDestination: "도착지로",
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
    steps: "상세 경로",
    stops: (n) => `${n}개 정류장`,
    bound: (headsign) => `${headsign} 방면`,
    loading: "경로를 찾는 중…",
    mapUnavailable: "지도 구성요소가 아직 로드되지 않았습니다. 개요 대시보드를 한 번 연 뒤 다시 와 주세요.",
    selected: "지도에서 선택한 지점",
    hour: "시간",
    minute: "분",
    won: "원",
  },
};

const APP_PACKAGE = "com.nhn.android.nmap";
// Travel mode token in the Naver Map app's nmap://route/<mode> URLs.
const APP_ROUTE_MODES = { car: "car", transit: "public", walk: "walk", bicycle: "bicycle" };
const HEX_COLOR = /^#[0-9a-f]{3,8}$/i;
const MAX_LINES = 3; // bus rides can list many interchangeable lines

const escapeHtml = (text) =>
  String(text ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );

function mobilePlatform() {
  const ua = navigator.userAgent;
  if (/Android/i.test(ua)) return "android";
  // iPadOS reports a Mac user agent; touch support tells them apart.
  if (/iPhone|iPad|iPod/i.test(ua) || (/Macintosh/i.test(ua) && navigator.maxTouchPoints > 1)) {
    return "ios";
  }
  return null;
}

// Naver Map app link (nmap:// URL scheme) on phones and tablets, or null on
// desktop. Android gets an intent:// URL so a missing app opens Play Store.
function appUrl(action, params) {
  const platform = mobilePlatform();
  if (!platform) return null;
  const query = Object.entries({ ...params, appname: location.origin })
    .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
    .join("&");
  return platform === "android"
    ? `intent://${action}?${query}#Intent;scheme=nmap;package=${APP_PACKAGE};end`
    : `nmap://${action}?${query}`;
}

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
    this._tab = "place";
    this._placeQuery = "";
    this._places = [];
    this._activePlace = null;
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
      const { query } = ev.target.dataset;
      if (query === "place") this._placeQuery = ev.target.value;
      else if (query) this._queries[query] = ev.target.value;
    });
    this._sheet.addEventListener("keydown", (ev) => {
      const { query } = ev.target.dataset;
      if (ev.key !== "Enter" || !query) return;
      if (query === "place") this._searchPlaces();
      else this._search(query);
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
    map.addEventListener("editable-location-clicked", (ev) => {
      if (this._tab === "place") this._selectPlace(Number(ev.detail.id.replace("place-", "")));
    });
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
    if (action === "tab") {
      this._tab = el.dataset.tab;
      this._picking = null;
      this._render();
      this._drawMap();
    } else if (action === "place-search") this._searchPlaces();
    else if (action === "place-select") this._selectPlace(Number(el.dataset.index));
    else if (action === "place-use") {
      const place = this._places[Number(el.dataset.index)];
      this._tab = "route";
      this._queries[slot] = place.place_name;
      this._setPoint(slot, { label: place.place_name, location: [place.latitude, place.longitude] });
    } else if (action === "search") this._search(slot);
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
    if (this._tab !== "route" || !this._picking) return;
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

  async _searchPlaces() {
    const query = this._placeQuery.trim();
    if (!query) return;
    this._error = null;
    this._activePlace = null;
    try {
      this._places = (await this._callService("search_place", { query })).results;
    } catch (err) {
      this._places = [];
      this._error = err.message || String(err);
    }
    this._render();
    this._drawMap();
  }

  _selectPlace(index) {
    this._activePlace = index;
    this._render();
    this._drawMap();
    const place = this._places[index];
    this._map?.fitBounds([[place.latitude, place.longitude]], { zoom: 16 });
    this._sheet.querySelector(`[data-place="${index}"]`)?.scrollIntoView({ block: "nearest" });
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
        include_steps: true,
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
    if (this._tab === "place") {
      this._drawPlaces();
      return;
    }
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

  _drawPlaces() {
    this._map.paths = [];
    this._map.editableLocations = this._places.map((place, index) => ({
      id: `place-${index}`,
      location: [place.latitude, place.longitude],
      title: place.place_name,
      element: this._markerElement(index === this._activePlace ? "activePlace" : "place", index),
      elementSize: 20,
      activatable: true,
    }));
    if (this._places.length && this._activePlace == null) {
      this._map.fitBounds(
        this._places.map((place) => [place.latitude, place.longitude]),
        { pad: 0.3, zoom: 16 }
      );
    }
  }

  // A colored dot, cached per marker so ha-map sees the same element and keeps it.
  _markerElement(color, key = color) {
    this._markers ||= {};
    const id = `${color}:${key}`;
    if (!this._markers[id]) {
      const dot = document.createElement("div");
      dot.style.cssText = `width:20px;height:20px;box-sizing:border-box;border-radius:50%;
        border:3px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4);background:${COLORS[color]};cursor:pointer`;
      this._markers[id] = dot;
    }
    return this._markers[id];
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

  // Times are shown in Home Assistant's time zone, like the rest of the frontend.
  _formatTime(iso) {
    return new Date(iso).toLocaleTimeString(this._hass.language, {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: this._hass.config?.time_zone,
    });
  }

  // App links replace the page, so only web links open a new tab.
  _openLink(webUrl, app) {
    const href = app || webUrl;
    const target = app ? "" : ' target="_blank" rel="noopener noreferrer"';
    return `<a class="open" href="${escapeHtml(href)}"${target}>${this._t.openInNaver}</a>`;
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
      const arrival = this._formatTime(route.arrival_time);
      rows.push(`<dl>
        <dt>${t.duration}</dt><dd>${this._formatDuration(route.duration)}</dd>
        <dt>${t.distance}</dt><dd>${this._formatDistance(route.distance)}</dd>
        <dt>${t.arrival}</dt><dd>${arrival}</dd>
        ${route.transfers != null ? `<dt>${t.transfers}</dt><dd>${route.transfers}</dd>` : ""}
        ${route.fare != null ? `<dt>${t.fare}</dt><dd>${route.fare.toLocaleString()} ${t.won}</dd>` : ""}
      </dl>`);
    }
    if (!route.geometry?.length) rows.push(`<p class="muted">${t.straightLine}</p>`);
    rows.push(this._renderSteps(route));
    const { origin, destination } = this._points;
    rows.push(
      this._openLink(
        route.route_url,
        appUrl(`route/${APP_ROUTE_MODES[route.mode]}`, {
          slat: origin.location[0],
          slng: origin.location[1],
          sname: origin.label,
          dlat: destination.location[0],
          dlng: destination.location[1],
          dname: destination.label,
        })
      )
    );
    return `<section class="result-box">${rows.join("")}</section>`;
  }

  _renderPlaceTab() {
    const t = this._t;
    const places = this._places
      .map(
        (place, index) => `
        <li class="place ${index === this._activePlace ? "active" : ""}" data-place="${index}">
          <button class="result" data-action="place-select" data-index="${index}">
            <b>${escapeHtml(place.place_name)}</b>
            ${place.category_name ? `<small>${escapeHtml(place.category_name)}</small>` : ""}
            <small>${escapeHtml(place.road_address || place.address)}</small>
          </button>
          <div class="row">
            <button data-action="place-use" data-slot="origin" data-index="${index}">${t.setOrigin}</button>
            <button data-action="place-use" data-slot="destination" data-index="${index}">${t.setDestination}</button>
            ${this._openLink(
              place.map_url,
              appUrl("place", { lat: place.latitude, lng: place.longitude, name: place.place_name })
            )}
          </div>
        </li>`
      )
      .join("");
    return `
      <div class="row">
        <input data-query="place" placeholder="${escapeHtml(t.searchPlaceholder)}" value="${escapeHtml(this._placeQuery)}">
        <button data-action="place-search">${t.search}</button>
      </div>
      ${this._error ? `<p class="error">${escapeHtml(this._error)}</p>` : ""}
      ${places ? `<ul class="results">${places}</ul>` : ""}`;
  }

  _renderSteps(route) {
    const t = this._t;
    const steps = route.steps;
    if (!steps?.length) return "";
    if (route.mode !== "transit") {
      const items = steps
        .map(
          (step) =>
            `<li>${escapeHtml(step.instruction)}${step.distance ? ` <small>${this._formatDistance(step.distance)}</small>` : ""}</li>`
        )
        .join("");
      return `<details class="steps"><summary>${t.steps} (${steps.length})</summary><ol>${items}</ol></details>`;
    }
    const items = steps
      .map((step) => {
        const time = `${this._formatTime(step.departure_time)}–${this._formatTime(step.arrival_time)}`;
        if (!step.lines) {
          return `<li class="walk-step">${escapeHtml(step.instruction)} <small>${this._formatDuration(step.duration)}</small></li>`;
        }
        const color = HEX_COLOR.test(step.color || "") ? step.color : "var(--primary-color)";
        const lines =
          step.lines.slice(0, MAX_LINES).join(", ") +
          (step.lines.length > MAX_LINES ? ` +${step.lines.length - MAX_LINES}` : "");
        return `<li class="ride" style="--line-color:${color}">
          <span class="badge">${escapeHtml(lines)}</span>
          ${step.headsign ? `<small>${escapeHtml(t.bound(step.headsign))}</small>` : ""}
          <div>${escapeHtml(step.from)} → ${escapeHtml(step.to)} <small>${t.stops(step.stops)}</small></div>
          <small>${time} · ${this._formatDuration(step.duration)}</small>
        </li>`;
      })
      .join("");
    return `<details class="steps" open><summary>${t.steps}</summary><ol class="transit">${items}</ol></details>`;
  }

  _render() {
    if (!this._sheet || !this._hass) return;
    const t = this._t;
    this._root.querySelector(".title").textContent = t.title;
    const tabs = ["place", "route"]
      .map(
        (tab) =>
          `<button data-action="tab" data-tab="${tab}" class="tab ${tab === this._tab ? "active" : ""}">${t.tabs[tab]}</button>`
      )
      .join("");
    if (this._tab === "place") {
      this._sheet.innerHTML = `<div class="tabs">${tabs}</div>${this._renderPlaceTab()}`;
      return;
    }
    const entities = this._locatedEntities();
    const modes = MODES.map(
      (mode) =>
        `<button data-action="mode" data-mode="${mode}" class="${mode === this._mode ? "active" : ""}">${t.modes[mode]}</button>`
    ).join("");
    this._sheet.innerHTML = `
      <div class="tabs">${tabs}</div>
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
  .tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .place { display: flex; flex-direction: column; gap: 4px; padding: 6px; border-radius: 8px; }
  .place.active { background: var(--secondary-background-color); }
  .place .open { align-self: center; }
  .modes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
  .results { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
  .result { width: 100%; text-align: left; display: flex; flex-direction: column; gap: 2px; }
  .result small { color: var(--secondary-text-color); }
  .result-box { padding: 12px; border-radius: 8px; background: var(--card-background-color); }
  dl { display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; margin: 0 0 8px; }
  dt { color: var(--secondary-text-color); }
  dd { margin: 0; }
  .open { display: inline-block; color: var(--primary-color); }
  .steps { margin-bottom: 8px; }
  .steps summary { cursor: pointer; color: var(--secondary-text-color); }
  .steps ol { margin: 8px 0 0; padding-left: 20px; display: flex; flex-direction: column; gap: 4px; }
  .steps small { color: var(--secondary-text-color); }
  .steps ol.transit { list-style: none; padding-left: 0; gap: 8px; }
  .ride { border-left: 4px solid var(--line-color); padding-left: 8px; }
  .walk-step { border-left: 4px dotted var(--divider-color); padding-left: 8px; color: var(--secondary-text-color); }
  .badge { display: inline-block; padding: 1px 8px; border-radius: 10px; background: var(--line-color);
    color: #fff; font-weight: 600; font-size: 13px; }
  .muted, .hint { color: var(--secondary-text-color); margin: 0; }
  .error { color: var(--error-color); margin: 0; }
  .notice { padding: 24px; color: var(--secondary-text-color); }
`;

customElements.define("naver-map-panel", NaverMapPanel);
