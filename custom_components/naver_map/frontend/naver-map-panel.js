// Naver Map sidebar panel: search places, pick origin/destination, and draw the
// naver_map.get_directions route on Home Assistant's own <ha-map> (OSM tiles via
// core's map_tiles proxy). Plain custom element, no build step.
//
// Layout follows the Naver Map app: on phone widths the map sits above a
// draggable bottom sheet with a bottom tab bar; from tablet width a side panel
// with an icon rail sits next to the map.
//
// Panel strings live in the dictionary below, chosen by hass.language: panel
// JS is outside the backend translations/ files, which only cover services.

const MODES = ["car", "transit", "walk", "bicycle"];
const TABS = ["place", "route", "saved"];
const ICONS = {
  place: "mdi:magnify",
  route: "mdi:directions",
  saved: "mdi:star",
  save: "mdi:star-outline",
  delete: "mdi:delete-outline",
  car: "mdi:car",
  transit: "mdi:bus",
  walk: "mdi:walk",
  bicycle: "mdi:bike",
  swap: "mdi:swap-vertical",
  entity: "mdi:account-box-outline",
  pick: "mdi:map-marker-radius",
  locate: "mdi:crosshairs-gps",
  search: "mdi:magnify",
  open: "mdi:open-in-new",
  hours: "mdi:clock-outline",
  reviews: "mdi:comment-text-outline",
};
const PLACE_FLAGS = ["booking", "order", "delivery", "naver_pay"];
// Category shortcuts under the search bar (naver_map.search_nearby categories),
// in the order the Naver Map app shows its own.
const NEARBY_CATEGORIES = {
  restaurant: "mdi:silverware-fork-knife",
  cafe: "mdi:coffee",
  convenience_store: "mdi:store-24-hour",
  supermarket: "mdi:cart",
  pharmacy: "mdi:pill",
  hospital: "mdi:hospital-box",
  gas_station: "mdi:gas-station",
  parking: "mdi:parking",
  bank: "mdi:bank",
  subway_station: "mdi:subway-variant",
  accommodation: "mdi:bed",
  tourist_attraction: "mdi:camera",
};
const NEARBY_RADIUS = 1000; // m
const MAX_PHOTOS = 3;
const ENTITY_DOMAINS = ["person", "zone", "device_tracker"];
const REQUERY_DELAY = 800; // ms; marker drags re-query Directions 5, a paid API
const COMPACT_WIDTH = 600; // px of panel width; below this the phone layout is used
const COLORS = {
  origin: "#03c75a",
  destination: "#e5484d",
  route: "#03c75a",
  place: "#1e6fff",
  activePlace: "#ff7a00",
  here: "#1a73e8",
};
// Saving a place creates a passive zone: an ordinary HA entity that maps,
// automations and get_directions can use, and that presence detection ignores.
const SAVED_ZONE = { icon: "mdi:star", radius: 50, passive: true };
const SAME_PLACE_DEG = 0.0005; // ~50 m: a zone this close with the same name is the saved place
const LOCATE_TIMEOUT = 8000; // ms to wait for the device position
const START_ZOOM = 15;
// Bottom-sheet snap heights on phone widths, as fractions of the panel height
// (min is a fixed height that keeps the handle and the first row visible).
const SHEET_MIN_PX = 132;
const SHEET_SNAPS = { peek: 0.45, full: 0.88 };
// Transit vehicle-type filters; the key is the route's sorted vehicle types.
const TRANSIT_FILTERS = ["all", "bus", "subway", "bus+subway"];
const TRANSIT_SORTS = {
  best: () => 0, // Naver's order
  minimum_duration: (a, b) => a.duration - b.duration,
  minimum_transfer: (a, b) => a.transfers - b.transfers || a.duration - b.duration,
  minimum_walking: (a, b) =>
    (a.walking_duration ?? Infinity) - (b.walking_duration ?? Infinity) ||
    a.duration - b.duration,
};

const STRINGS = {
  en: {
    tabs: { place: "Places", route: "Directions", saved: "Saved" },
    save: "Save",
    savedLabel: "Saved",
    remove: "Remove",
    confirmRemove: "Tap again to remove",
    savedEmpty: "Save places from the Places tab with ☆ Save. They become Home Assistant zones.",
    savedEmptyUser: "Places an administrator saves (as zones) appear here.",
    setOrigin: "Origin",
    setDestination: "Destination",
    origin: "Origin",
    destination: "Destination",
    search: "Search",
    searchPlaceholder: "Search a place",
    originPlaceholder: "Search an origin",
    destinationPlaceholder: "Search a destination",
    entity: "Choose an entity",
    pickOnMap: "Pick on map",
    swap: "Swap origin and destination",
    pickingHint: "Click the map to set the point",
    modes: { car: "Car", transit: "Transit", walk: "Walk", bicycle: "Bicycle" },
    filters: { all: "All", bus: "Bus", subway: "Subway", "bus+subway": "Bus+Subway" },
    sorts: {
      best: "Best",
      minimum_duration: "Fastest",
      minimum_transfer: "Fewest transfers",
      minimum_walking: "Least walking",
    },
    labels: {
      best: "Best",
      minimum_duration: "Fastest",
      minimum_transfer: "Fewest transfers",
      minimum_walking: "Least walking",
    },
    distance: "Distance",
    arrival: "Arrival",
    arrives: (time) => `Arrives ${time}`,
    transfers: (n) => (n ? `${n} transfer${n === 1 ? "" : "s"}` : "No transfers"),
    walking: (time) => `Walk ${time}`,
    noEta: "No travel time available",
    noRoutes: "No routes for this filter",
    straightLine: "Route line unavailable; showing straight segments",
    openInNaver: "Open in Naver Map",
    steps: "Route details",
    categories: {
      restaurant: "Restaurants",
      cafe: "Cafes",
      convenience_store: "Convenience",
      supermarket: "Supermarkets",
      pharmacy: "Pharmacies",
      hospital: "Hospitals",
      gas_station: "Gas",
      parking: "Parking",
      bank: "Banks",
      subway_station: "Subway",
      accommodation: "Stays",
      tourist_attraction: "Sights",
    },
    nearbyOf: (name) => `Within 1 km of ${name}`,
    home: "Home",
    currentLocation: "Current location",
    locate: "Go to my location",
    noNearby: "Nothing found nearby",
    loadingDetails: "Loading place details…",
    detailsUnavailable: "Place details unavailable",
    visitorReviews: (n) => `${n.toLocaleString()} visitor reviews`,
    blogReviews: (n) => `${n.toLocaleString()} blog reviews`,
    flags: { booking: "Booking", order: "Order", delivery: "Delivery", naver_pay: "Naver Pay" },
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
    tabs: { place: "장소 검색", route: "길찾기", saved: "저장" },
    save: "저장",
    savedLabel: "저장됨",
    remove: "삭제",
    confirmRemove: "한 번 더 누르면 삭제",
    savedEmpty: "장소 검색에서 ☆ 저장을 누르면 여기에 모입니다. 저장한 장소는 Home Assistant 구역(zone)이 됩니다.",
    savedEmptyUser: "관리자가 저장한 장소(구역)가 여기에 표시됩니다.",
    setOrigin: "출발",
    setDestination: "도착",
    origin: "출발",
    destination: "도착",
    search: "검색",
    searchPlaceholder: "장소, 주소 검색",
    originPlaceholder: "출발지 검색",
    destinationPlaceholder: "도착지 검색",
    entity: "엔티티 선택",
    pickOnMap: "지도에서 선택",
    swap: "출발지와 도착지 바꾸기",
    pickingHint: "지도를 클릭해 지점을 지정하세요",
    modes: { car: "자동차", transit: "대중교통", walk: "도보", bicycle: "자전거" },
    filters: { all: "전체", bus: "버스", subway: "지하철", "bus+subway": "버스+지하철" },
    sorts: {
      best: "최적순",
      minimum_duration: "최소시간순",
      minimum_transfer: "최소환승순",
      minimum_walking: "최소도보순",
    },
    labels: {
      best: "최적",
      minimum_duration: "최소시간",
      minimum_transfer: "최소환승",
      minimum_walking: "최소도보",
    },
    distance: "거리",
    arrival: "도착 예정",
    arrives: (time) => `${time} 도착`,
    transfers: (n) => (n ? `환승 ${n}회` : "환승 없음"),
    walking: (time) => `도보 ${time}`,
    noEta: "예상시간 없음",
    noRoutes: "이 조건의 경로가 없습니다",
    straightLine: "경로선을 가져오지 못해 직선으로 표시합니다",
    openInNaver: "네이버 지도에서 열기",
    steps: "상세 경로",
    categories: {
      restaurant: "음식점",
      cafe: "카페",
      convenience_store: "편의점",
      supermarket: "마트",
      pharmacy: "약국",
      hospital: "병원",
      gas_station: "주유소",
      parking: "주차장",
      bank: "은행",
      subway_station: "지하철역",
      accommodation: "숙소",
      tourist_attraction: "관광명소",
    },
    nearbyOf: (name) => `${name} 주변 1km`,
    home: "집",
    currentLocation: "현재 위치",
    locate: "현 위치로",
    noNearby: "주변에서 찾지 못했습니다",
    loadingDetails: "장소 정보를 불러오는 중…",
    detailsUnavailable: "장소 정보를 불러오지 못했습니다",
    visitorReviews: (n) => `방문자 리뷰 ${n.toLocaleString()}`,
    blogReviews: (n) => `블로그 리뷰 ${n.toLocaleString()}`,
    flags: { booking: "예약", order: "주문", delivery: "배달", naver_pay: "네이버페이" },
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

const icon = (name) => `<ha-icon icon="${ICONS[name]}"></ha-icon>`;

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

// Great-circle distance in meters between two [lat, lng] points.
function distanceMeters([lat1, lng1], [lat2, lng2]) {
  const rad = Math.PI / 180;
  const a =
    Math.sin(((lat2 - lat1) * rad) / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lng2 - lng1) * rad) / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.sqrt(a));
}

const placeKey = (place) => `${place.place_name}|${place.latitude}|${place.longitude}`;
const vehicleKey = (route) => [...(route.vehicle_types || [])].sort().join("+");

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
    this._nearbyCategory = null;
    this._places = [];
    this._activePlace = null;
    this._details = {}; // naver_map.get_place_details results by place key
    this._points = { origin: null, destination: null };
    this._queries = { origin: "", destination: "" };
    this._results = { origin: [], destination: [] };
    this._mode = "car";
    this._route = null;
    this._transitFilter = "all";
    this._transitSort = "best";
    this._altIndex = 0; // index into this._route.alternatives
    this._error = null;
    this._loading = false;
    this._picking = null;
    this._requestId = 0;
    this._requeryTimer = null;
    this._entityIds = "";
    this._compact = false;
    this._zonesKey = "";
    this._confirmRemove = null; // zone entity_id waiting for a second tap
    this._here = null; // device position [lat, lng], when the browser shares it
    this._sheet = "peek";
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (this._map) {
      this._map.hass = hass;
      this._syncMapEntities();
    }
    if (this._menuButton) this._menuButton.hass = hass;
    // Saving or removing a place changes the zones; refresh what shows them.
    const zonesKey = this._savedZones()
      .map((s) => `${s.entity_id}:${s.attributes.friendly_name}`)
      .join(",");
    const zonesChanged = zonesKey !== this._zonesKey;
    this._zonesKey = zonesKey;
    if (first && this.isConnected) this._render();
    else if (zonesChanged && this._tab !== "route") {
      this._render();
      this._drawMap();
    }
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
        <nav class="nav"><span class="menu"></span><div class="nav-tabs"></div></nav>
        <section class="sheet">
          <div class="handle" title=""><span></span></div>
          <div class="content"></div>
        </section>
        <div class="map"></div>
      </div>`;
    this._layout = this._root.querySelector(".layout");
    this._content = this._root.querySelector(".content");
    for (const el of [this._content, this._root.querySelector(".nav-tabs")]) {
      el.addEventListener("click", (ev) => this._onClick(ev));
    }
    this._content.addEventListener("change", (ev) => this._onChange(ev));
    this._content.addEventListener("input", (ev) => {
      const { query } = ev.target.dataset;
      if (query === "place") this._placeQuery = ev.target.value;
      else if (query) this._queries[query] = ev.target.value;
    });
    this._content.addEventListener("keydown", (ev) => {
      const { query } = ev.target.dataset;
      if (ev.key !== "Enter" || !query) return;
      if (query === "place") this._searchPlaces();
      else this._search(query);
    });
    this._setUpSheetDrag(this._root.querySelector(".handle"));
    new ResizeObserver(() => this._onResize()).observe(this);
    customElements.whenDefined("ha-menu-button").then(() => {
      this._menuButton = document.createElement("ha-menu-button");
      this._menuButton.hass = this._hass;
      this._menuButton.narrow = this._narrow;
      this._root.querySelector(".menu").appendChild(this._menuButton);
    });
    this._setUpMap();
    if (this._hass) this._render();
  }

  // --- layout -------------------------------------------------------------

  _onResize() {
    const compact = this.clientWidth < COMPACT_WIDTH;
    if (compact !== this._compact) {
      this._compact = compact;
      this.classList.toggle("compact", compact);
    }
    this._applySheet();
  }

  // Phone layout: the sheet height decides how much map stays visible above it.
  _applySheet(px) {
    if (!this._compact) {
      this._layout.style.removeProperty("--sheet-h");
      return;
    }
    const height = this.clientHeight;
    const snapPx =
      this._sheet === "min" ? SHEET_MIN_PX : Math.round(height * SHEET_SNAPS[this._sheet]);
    this._layout.style.setProperty("--sheet-h", `${px ?? snapPx}px`);
  }

  _setSheet(state) {
    if (this._sheet === state) return;
    this._sheet = state;
    this._applySheet();
  }

  _setUpSheetDrag(handle) {
    let start = null;
    handle.addEventListener("pointerdown", (ev) => {
      if (!this._compact) return;
      start = { y: ev.clientY, h: this._root.querySelector(".sheet").offsetHeight, moved: false };
      handle.setPointerCapture(ev.pointerId);
      this._layout.classList.add("dragging");
    });
    handle.addEventListener("pointermove", (ev) => {
      if (!start) return;
      const dy = start.y - ev.clientY;
      if (Math.abs(dy) > 4) start.moved = true;
      const max = this.clientHeight * SHEET_SNAPS.full;
      this._applySheet(Math.min(max, Math.max(SHEET_MIN_PX, start.h + dy)));
    });
    const end = () => {
      if (!start) return;
      const height = this._root.querySelector(".sheet").offsetHeight;
      const order = ["min", "peek", "full"];
      let state;
      if (!start.moved) {
        // A tap steps through the snaps: min → peek → full → peek.
        state = this._sheet === "full" ? "peek" : order[order.indexOf(this._sheet) + 1];
      } else {
        const targets = {
          min: SHEET_MIN_PX,
          peek: this.clientHeight * SHEET_SNAPS.peek,
          full: this.clientHeight * SHEET_SNAPS.full,
        };
        state = order.reduce((best, s) =>
          Math.abs(targets[s] - height) < Math.abs(targets[best] - height) ? s : best
        );
      }
      start = null;
      this._layout.classList.remove("dragging");
      this._sheet = state;
      this._applySheet();
    };
    handle.addEventListener("pointerup", end);
    handle.addEventListener("pointercancel", end);
  }

  // --- map ----------------------------------------------------------------

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
    const locate = document.createElement("button");
    locate.className = "locate";
    locate.title = this._t.locate;
    locate.innerHTML = icon("locate");
    locate.addEventListener("click", () => this._locate());
    container.appendChild(locate);
    this._map = map;
    this._syncMapEntities();
    this._drawMap();
    this._locate({ initial: true });
  }

  // The device position, or null when the browser can't or won't share it
  // (geolocation needs HTTPS or localhost, and the user's permission).
  _deviceLocation() {
    if (!window.isSecureContext || !navigator.geolocation) return Promise.resolve(null);
    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve([pos.coords.latitude, pos.coords.longitude]),
        () => resolve(null),
        { enableHighAccuracy: true, timeout: LOCATE_TIMEOUT, maximumAge: 60000 }
      );
    });
  }

  // Where the panel starts and searches nearby: the device position, else the
  // signed-in user's person, else home.
  _startLocation() {
    if (this._here) {
      const [latitude, longitude] = this._here;
      return { input: { latitude, longitude }, location: this._here, name: this._t.currentLocation };
    }
    const userId = this._hass.user?.id;
    const person = Object.values(this._hass.states).find(
      (s) =>
        s.entity_id.startsWith("person.") &&
        s.attributes.user_id === userId &&
        typeof s.attributes.latitude === "number" &&
        typeof s.attributes.longitude === "number"
    );
    if (person) {
      return {
        input: person.entity_id,
        location: [person.attributes.latitude, person.attributes.longitude],
        name: person.attributes.friendly_name || person.entity_id,
      };
    }
    const { latitude, longitude } = this._hass.config;
    return { input: { latitude, longitude }, location: [latitude, longitude], name: this._t.home };
  }

  // Center the map on the start location. On first load, leave the view alone
  // if the user has already searched or picked points while it was resolving.
  async _locate({ initial = false } = {}) {
    this._here = (await this._deviceLocation()) || this._here;
    this._drawMap();
    const busy = this._places.length || this._points.origin || this._points.destination;
    if (initial && busy) return;
    this._map.fitBounds([this._startLocation().location], { zoom: START_ZOOM });
  }

  // A blue dot at the device position, shown on both tabs.
  _hereMarkers() {
    if (!this._here) return [];
    return [
      {
        id: "here",
        location: this._here,
        title: this._t.currentLocation,
        element: this._markerElement("here"),
        elementSize: 18,
      },
    ];
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

  _drawMap() {
    if (!this._map) return;
    if (this._tab === "saved") {
      this._drawSaved();
      return;
    }
    if (this._tab === "place") {
      this._drawPlaces();
      return;
    }
    const t = this._t;
    this._map.editableLocations = [
      ...this._hereMarkers(),
      ...["origin", "destination"]
        .filter((slot) => this._points[slot])
        .map((slot) => ({
          id: slot,
          location: this._points[slot].location,
          title: `${t[slot]}: ${this._points[slot].label}`,
          color: COLORS[slot],
          element: this._markerElement(slot),
          elementSize: 20,
          locationEditable: true,
        })),
    ];
    const line = this._routeLine();
    if (line.length) {
      // ha-map labels each path point with a time; spread the ETA along the line.
      const start = Date.now();
      const total = (this._shownRoute()?.duration || 0) * 1000;
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
    this._map.editableLocations = [
      ...this._hereMarkers(),
      ...this._places.map((place, index) => ({
        id: `place-${index}`,
        location: [place.latitude, place.longitude],
        title: place.place_name,
        element: this._markerElement(index === this._activePlace ? "activePlace" : "place", index),
        elementSize: 20,
        activatable: true,
      })),
    ];
    if (this._places.length && this._activePlace == null) {
      this._map.fitBounds(
        this._places.map((place) => [place.latitude, place.longitude]),
        { pad: 0.3, zoom: 16 }
      );
    }
  }

  _drawSaved() {
    const zones = this._savedZones();
    this._map.paths = [];
    this._map.editableLocations = this._hereMarkers();
    if (zones.length) {
      this._map.fitBounds(
        zones.map((s) => [s.attributes.latitude, s.attributes.longitude]),
        { pad: 0.3, zoom: 15 }
      );
    }
  }

  // Zones with coordinates: home first, then the rest by name.
  _savedZones() {
    return Object.values(this._hass?.states || {})
      .filter(
        (s) =>
          s.entity_id.startsWith("zone.") &&
          typeof s.attributes.latitude === "number" &&
          typeof s.attributes.longitude === "number"
      )
      .sort(
        (a, b) =>
          (b.entity_id === "zone.home") - (a.entity_id === "zone.home") ||
          (a.attributes.friendly_name || "").localeCompare(b.attributes.friendly_name || "")
      );
  }

  _savedZoneFor(place) {
    return this._savedZones().find(
      (s) =>
        s.attributes.friendly_name === place.place_name &&
        Math.abs(s.attributes.latitude - place.latitude) < SAME_PLACE_DEG &&
        Math.abs(s.attributes.longitude - place.longitude) < SAME_PLACE_DEG
    );
  }

  async _savePlace(place) {
    this._error = null;
    try {
      await this._hass.callWS({
        type: "zone/create",
        name: place.place_name,
        latitude: place.latitude,
        longitude: place.longitude,
        ...SAVED_ZONE,
      });
    } catch (err) {
      this._error = err.message || String(err);
      this._render();
    }
  }

  // Zones created in the UI (or here) are listed by zone/list; YAML zones and
  // home are not, and cannot be removed from the panel.
  async _removeSaved(entityId) {
    if (this._confirmRemove !== entityId) {
      this._confirmRemove = entityId;
      this._render();
      return;
    }
    this._confirmRemove = null;
    const state = this._hass.states[entityId];
    try {
      const zones = await this._hass.callWS({ type: "zone/list" });
      const zone = zones.find(
        (z) =>
          z.name === state.attributes.friendly_name &&
          Math.abs(z.latitude - state.attributes.latitude) < 1e-6 &&
          Math.abs(z.longitude - state.attributes.longitude) < 1e-6
      );
      if (zone) await this._hass.callWS({ type: "zone/delete", zone_id: zone.id });
    } catch (err) {
      this._error = err.message || String(err);
      this._render();
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

  // The route on screen: the chosen transit alternative, or the route itself.
  _shownRoute() {
    const route = this._route;
    if (!route) return null;
    return route.alternatives?.[this._altIndex] || route;
  }

  // Route geometry when available, else straight segments through the legs.
  _routeLine() {
    const shown = this._shownRoute();
    if (!shown) return [];
    if (shown.geometry?.length) return shown.geometry;
    const legs = this._route.legs || [];
    if (!legs.length) return [];
    return [
      [legs[0].from_latitude, legs[0].from_longitude],
      ...legs.map((leg) => [leg.to_latitude, leg.to_longitude]),
    ];
  }

  // --- actions ------------------------------------------------------------

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
    const index = Number(el.dataset.index);
    switch (action) {
      case "tab":
        this._tab = el.dataset.tab;
        this._picking = null;
        this._error = null;
        this._render();
        this._drawMap();
        break;
      case "place-search":
        this._searchPlaces();
        break;
      case "place-save":
        this._savePlace(this._places[index]);
        break;
      case "saved-use":
      case "saved-select": {
        const state = this._hass.states[el.dataset.entity];
        if (!state) break;
        const location = [state.attributes.latitude, state.attributes.longitude];
        if (action === "saved-select") {
          this._map?.fitBounds([location], { zoom: 16 });
          break;
        }
        const label = state.attributes.friendly_name || state.entity_id;
        this._tab = "route";
        this._queries[slot] = label;
        this._setPoint(slot, { label, entityId: state.entity_id, location });
        break;
      }
      case "saved-remove":
        this._removeSaved(el.dataset.entity);
        break;
      case "nearby":
        this._searchNearby(el.dataset.category);
        break;
      case "place-select":
        this._selectPlace(index);
        break;
      case "place-use": {
        const place = this._places[index];
        this._tab = "route";
        this._queries[slot] = place.place_name;
        this._setPoint(slot, {
          label: place.place_name,
          location: [place.latitude, place.longitude],
        });
        break;
      }
      case "search":
        this._search(slot);
        break;
      case "pick":
        this._picking = this._picking === slot ? null : slot;
        if (this._picking) this._setSheet("min");
        this._render();
        break;
      case "swap":
        this._swap();
        break;
      case "result": {
        const place = this._results[slot][index];
        this._queries[slot] = place.place_name;
        this._setPoint(slot, {
          label: place.place_name,
          location: [place.latitude, place.longitude],
        });
        break;
      }
      case "mode":
        this._mode = el.dataset.mode;
        this._render();
        this._query();
        break;
      case "filter":
        this._transitFilter = el.dataset.filter;
        this._selectFirstVisibleAlternative();
        break;
      case "alternative":
        this._altIndex = index;
        this._render();
        this._drawMap();
        break;
    }
  }

  _onChange(ev) {
    if (ev.target.dataset.sort) {
      this._transitSort = ev.target.value;
      this._selectFirstVisibleAlternative();
      return;
    }
    const slot = ev.target.dataset.entity;
    if (!slot || !ev.target.value) return;
    const state = this._hass.states[ev.target.value];
    if (!state) return;
    const label = state.attributes.friendly_name || state.entity_id;
    this._queries[slot] = label;
    this._setPoint(slot, {
      label,
      entityId: state.entity_id,
      location: [state.attributes.latitude, state.attributes.longitude],
    });
  }

  _swap() {
    const { origin, destination } = this._points;
    this._points = { origin: destination, destination: origin };
    this._queries = { origin: this._queries.destination, destination: this._queries.origin };
    this._render();
    this._drawMap();
    this._query();
  }

  _onMapClicked(location) {
    if (this._tab !== "route" || !this._picking) return;
    this._queries[this._picking] = "";
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

  async _searchPlaces() {
    const query = this._placeQuery.trim();
    if (!query) return;
    this._nearbyCategory = null;
    this._error = null;
    this._activePlace = null;
    try {
      this._places = (await this._callService("search_place", { query })).results;
    } catch (err) {
      this._places = [];
      this._error = err.message || String(err);
    }
    this._setSheet("peek");
    this._render();
    this._drawMap();
  }

  async _searchNearby(category) {
    this._nearbyCategory = category;
    this._placeQuery = "";
    this._error = null;
    this._activePlace = null;
    try {
      const response = await this._callService("search_nearby", {
        center: this._startLocation().input,
        category,
        radius: NEARBY_RADIUS,
      });
      this._places = response.results;
    } catch (err) {
      this._places = [];
      // search_nearby reports an empty area as an error; say so plainly.
      this._error = err.code === "service_validation_error" ? this._t.noNearby : err.message || String(err);
    }
    this._setSheet("peek");
    this._render();
    this._drawMap();
  }

  _selectPlace(index) {
    this._activePlace = index;
    this._loadDetails(this._places[index]);
    this._render();
    this._drawMap();
    const place = this._places[index];
    this._map?.fitBounds([[place.latitude, place.longitude]], { zoom: 16 });
    this._content.querySelector(`[data-place="${index}"]`)?.scrollIntoView({ block: "nearest" });
  }

  // One lookup per place picked (never automatic); results are kept for the session.
  async _loadDetails(place) {
    const key = placeKey(place);
    if (this._details[key]) return;
    this._details[key] = { loading: true };
    try {
      this._details[key] = await this._callService(
        "get_place_details",
        place.place_id
          ? { place_id: place.place_id }
          : {
              query: place.place_name,
              near: { latitude: place.latitude, longitude: place.longitude },
            }
      );
    } catch (err) {
      this._details[key] = { error: err.message || String(err) };
    }
    if (this._tab === "place") this._render();
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
        include_steps: true,
        include_alternatives: this._mode === "transit",
      });
      if (requestId !== this._requestId) return; // a newer lookup superseded this one
      this._route = route;
      this._altIndex = 0;
      this._transitFilter = "all";
    } catch (err) {
      if (requestId !== this._requestId) return;
      this._route = null;
      this._error = err.message || String(err);
    }
    this._loading = false;
    this._render();
    this._drawMap();
  }

  // Transit alternatives that pass the vehicle filter, in the chosen order,
  // each with its index into this._route.alternatives.
  _visibleAlternatives() {
    const alternatives = (this._route?.alternatives || []).map((route, index) => ({
      route,
      index,
    }));
    const sort = TRANSIT_SORTS[this._transitSort];
    return alternatives
      .filter(({ route }) => this._transitFilter === "all" || vehicleKey(route) === this._transitFilter)
      .sort((a, b) => sort(a.route, b.route) || a.index - b.index);
  }

  _selectFirstVisibleAlternative() {
    const [first] = this._visibleAlternatives();
    if (first) this._altIndex = first.index;
    this._render();
    this._drawMap();
  }

  // --- formatting -----------------------------------------------------------

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

  _formatDistance(meters) {
    return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${meters} m`;
  }

  // Web links open a new tab. App links differ per companion app: Android
  // intercepts intent: URLs only on same-frame navigation, while iOS hands a
  // custom scheme to the OS only for new-window (target=_blank) links.
  _openLink(webUrl, app, label = this._t.openInNaver) {
    const href = app || webUrl;
    const newTab = !app || mobilePlatform() === "ios";
    const target = newTab ? ' target="_blank" rel="noopener noreferrer"' : "";
    return `<a class="open" href="${escapeHtml(href)}"${target}>${icon("open")}<span>${label}</span></a>`;
  }

  // --- rendering ------------------------------------------------------------

  _render() {
    if (!this._content || !this._hass) return;
    const t = this._t;
    this._root.querySelector(".nav-tabs").innerHTML = TABS.map(
      (tab) =>
        `<button data-action="tab" data-tab="${tab}" class="nav-tab ${tab === this._tab ? "active" : ""}" title="${t.tabs[tab]}">
          ${icon(tab)}<span>${t.tabs[tab]}</span>
        </button>`
    ).join("");
    const renderers = {
      place: () => this._renderPlaceTab(),
      route: () => this._renderRouteTab(),
      saved: () => this._renderSavedTab(),
    };
    this._content.innerHTML = renderers[this._tab]();
  }

  _renderPlaceTab() {
    const t = this._t;
    const places = this._places
      .map(
        (place, index) => `
        <li class="card place ${index === this._activePlace ? "active" : ""}" data-place="${index}">
          <button class="plain" data-action="place-select" data-index="${index}">
            <b>${escapeHtml(place.place_name)}</b>
            ${
              place.category_name || place.distance != null
                ? `<small>${[
                    place.category_name && escapeHtml(place.category_name),
                    place.distance != null && this._formatDistance(place.distance),
                  ]
                    .filter(Boolean)
                    .join(" · ")}</small>`
                : ""
            }
            <small>${escapeHtml(place.road_address || place.address)}</small>
          </button>
          ${index === this._activePlace ? this._renderDetails(place) : ""}
          <div class="actions">
            <button class="chip" data-action="place-use" data-slot="origin" data-index="${index}">
              <span class="dot" style="background:${COLORS.origin}"></span>${t.setOrigin}</button>
            <button class="chip" data-action="place-use" data-slot="destination" data-index="${index}">
              <span class="dot" style="background:${COLORS.destination}"></span>${t.setDestination}</button>
            ${this._renderSaveButton(place, index)}
            ${this._openLink(
              this._details[placeKey(place)]?.place_url || place.map_url,
              appUrl("place", { lat: place.latitude, lng: place.longitude, name: place.place_name })
            )}
          </div>
        </li>`
      )
      .join("");
    return `
      <div class="searchbar">
        ${icon("search")}
        <input data-query="place" placeholder="${escapeHtml(t.searchPlaceholder)}" value="${escapeHtml(this._placeQuery)}" enterkeyhint="search">
        <button class="icon-btn" data-action="place-search" title="${t.search}">${icon("search")}</button>
      </div>
      <div class="chips categories">${Object.entries(NEARBY_CATEGORIES)
        .map(
          ([category, mdi]) =>
            `<button class="chip ${category === this._nearbyCategory ? "active" : ""}" data-action="nearby" data-category="${category}">
              <ha-icon icon="${mdi}"></ha-icon>${t.categories[category]}</button>`
        )
        .join("")}</div>
      ${this._nearbyCategory ? `<small>${escapeHtml(t.nearbyOf(this._startLocation().name))}</small>` : ""}
      ${this._error ? `<p class="error">${escapeHtml(this._error)}</p>` : ""}
      ${places ? `<ul class="list">${places}</ul>` : ""}`;
  }

  // Creating zones needs an administrator; others only see what is saved.
  _renderSaveButton(place, index) {
    const t = this._t;
    if (this._savedZoneFor(place)) {
      return `<span class="chip saved">${icon("saved")}${t.savedLabel}</span>`;
    }
    if (!this._hass.user?.is_admin) return "";
    return `<button class="chip" data-action="place-save" data-index="${index}">${icon("save")}${t.save}</button>`;
  }

  _renderSavedTab() {
    const t = this._t;
    const isAdmin = this._hass.user?.is_admin;
    const start = this._startLocation().location;
    const zones = this._savedZones();
    const custom = zones.filter((s) => s.entity_id !== "zone.home");
    const cards = zones
      .map((s) => {
        const meters = Math.round(
          distanceMeters(start, [s.attributes.latitude, s.attributes.longitude])
        );
        const removable = isAdmin && s.entity_id !== "zone.home" && s.attributes.editable;
        const confirming = this._confirmRemove === s.entity_id;
        return `
        <li class="card place">
          <button class="plain" data-action="saved-select" data-entity="${escapeHtml(s.entity_id)}">
            <b><ha-icon class="zone-icon" icon="${escapeHtml(s.attributes.icon || "mdi:map-marker")}"></ha-icon>${escapeHtml(s.attributes.friendly_name || s.entity_id)}</b>
            <small>${this._formatDistance(meters)}</small>
          </button>
          <div class="actions">
            <button class="chip" data-action="saved-use" data-slot="origin" data-entity="${escapeHtml(s.entity_id)}">
              <span class="dot" style="background:${COLORS.origin}"></span>${t.setOrigin}</button>
            <button class="chip" data-action="saved-use" data-slot="destination" data-entity="${escapeHtml(s.entity_id)}">
              <span class="dot" style="background:${COLORS.destination}"></span>${t.setDestination}</button>
            ${
              removable
                ? `<button class="chip ${confirming ? "danger" : ""}" data-action="saved-remove" data-entity="${escapeHtml(s.entity_id)}">${icon("delete")}${confirming ? t.confirmRemove : t.remove}</button>`
                : ""
            }
          </div>
        </li>`;
      })
      .join("");
    return `
      ${this._error ? `<p class="error">${escapeHtml(this._error)}</p>` : ""}
      <ul class="list">${cards}</ul>
      ${custom.length ? "" : `<p class="muted">${isAdmin ? t.savedEmpty : t.savedEmptyUser}</p>`}`;
  }

  // Naver Place summary of the selected place: photos, status, reviews, services.
  _renderDetails(place) {
    const t = this._t;
    const details = this._details[placeKey(place)];
    if (!details || details.loading) return `<p class="muted">${t.loadingDetails}</p>`;
    if (details.error) return `<p class="muted">${t.detailsUnavailable}</p>`;
    const photos = (details.images || [])
      .slice(0, MAX_PHOTOS)
      .map(
        (url) =>
          `<img src="${escapeHtml(url)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
      )
      .join("");
    const reviews = [
      details.visitor_review_count != null ? t.visitorReviews(details.visitor_review_count) : null,
      details.blog_review_count != null ? t.blogReviews(details.blog_review_count) : null,
    ].filter(Boolean);
    const flags = PLACE_FLAGS.filter((flag) => details[flag])
      .map((flag) => `<span class="label">${t.flags[flag]}</span>`)
      .join("");
    return `
      <div class="details">
        ${photos ? `<div class="photos">${photos}</div>` : ""}
        ${details.business_hours ? `<div class="fact">${icon("hours")}<span>${escapeHtml(details.business_hours)}</span></div>` : ""}
        ${reviews.length ? `<div class="fact">${icon("reviews")}<span>${reviews.join(" · ")}</span></div>` : ""}
        ${flags ? `<div class="labels">${flags}</div>` : ""}
      </div>`;
  }

  _renderRouteTab() {
    const t = this._t;
    const entities = this._locatedEntities();
    const modes = MODES.map(
      (mode) =>
        `<button data-action="mode" data-mode="${mode}" class="mode ${mode === this._mode ? "active" : ""}" title="${t.modes[mode]}">
          ${icon(mode)}<span>${t.modes[mode]}</span>
        </button>`
    ).join("");
    return `
      <div class="points">
        <div class="point-rows">
          ${this._renderSlot("origin", entities)}
          ${this._renderSlot("destination", entities)}
        </div>
        <button class="icon-btn swap" data-action="swap" title="${t.swap}">${icon("swap")}</button>
      </div>
      ${this._renderSlotResults("origin")}
      ${this._renderSlotResults("destination")}
      ${this._picking ? `<p class="hint">${t.pickingHint}</p>` : ""}
      <div class="modes">${modes}</div>
      ${this._renderResult()}`;
  }

  _renderSlot(slot, entities) {
    const t = this._t;
    const point = this._points[slot];
    const options = entities
      .map(
        (s) =>
          `<option value="${escapeHtml(s.entity_id)}" ${point?.entityId === s.entity_id ? "selected" : ""}>${escapeHtml(s.attributes.friendly_name || s.entity_id)}</option>`
      )
      .join("");
    const value = this._queries[slot] || point?.label || "";
    return `
      <div class="point-row">
        <span class="dot" style="background:${COLORS[slot]}"></span>
        <input data-query="${slot}" placeholder="${escapeHtml(t[`${slot}Placeholder`])}" value="${escapeHtml(value)}" enterkeyhint="search">
        <label class="icon-btn icon-select" title="${t.entity}">
          ${icon("entity")}
          <select data-entity="${slot}" aria-label="${t.entity}"><option value="">${t.entity}</option>${options}</select>
        </label>
        <button class="icon-btn ${this._picking === slot ? "active" : ""}" data-action="pick" data-slot="${slot}" title="${t.pickOnMap}">${icon("pick")}</button>
      </div>`;
  }

  _renderSlotResults(slot) {
    const results = this._results[slot];
    if (!results.length) return "";
    return `<ul class="list">${results
      .map(
        (place, index) => `
        <li><button class="card plain" data-action="result" data-slot="${slot}" data-index="${index}">
          <span class="dot" style="background:${COLORS[slot]}"></span>
          <b>${escapeHtml(place.place_name)}</b>
          <small>${escapeHtml(place.road_address || place.address)}</small>
        </button></li>`
      )
      .join("")}</ul>`;
  }

  _routeAppLink(route) {
    const { origin, destination } = this._points;
    return this._openLink(
      route.route_url,
      appUrl(`route/${APP_ROUTE_MODES[route.mode]}`, {
        slat: origin.location[0],
        slng: origin.location[1],
        sname: origin.label,
        dlat: destination.location[0],
        dlng: destination.location[1],
        dname: destination.label,
      })
    );
  }

  _renderResult() {
    const t = this._t;
    if (this._loading) return `<p class="muted">${t.loading}</p>`;
    if (this._error) return `<p class="error">${escapeHtml(this._error)}</p>`;
    const route = this._route;
    if (!route) return "";
    if (route.duration == null) {
      return `<div class="card"><p class="muted">${t.noEta}</p>${this._routeAppLink(route)}</div>`;
    }
    if (route.alternatives?.length) return this._renderTransit(route);
    return `
      <div class="card summary">
        <div class="big">${this._formatDuration(route.duration)}</div>
        <div class="sub">${this._formatDistance(route.distance)} · ${t.arrives(this._formatTime(route.arrival_time))}</div>
        ${route.geometry?.length ? "" : `<p class="muted">${t.straightLine}</p>`}
        ${this._renderSteps(route)}
        ${this._routeAppLink(route)}
      </div>`;
  }

  _renderTransit(route) {
    const t = this._t;
    const present = new Set(route.alternatives.map(vehicleKey));
    const filters = TRANSIT_FILTERS.filter((f) => f === "all" || present.has(f))
      .map(
        (f) =>
          `<button class="chip ${f === this._transitFilter ? "active" : ""}" data-action="filter" data-filter="${f}">${t.filters[f] || f}</button>`
      )
      .join("");
    const sorts = Object.keys(TRANSIT_SORTS)
      .map(
        (s) =>
          `<option value="${s}" ${s === this._transitSort ? "selected" : ""}>${t.sorts[s]}</option>`
      )
      .join("");
    const visible = this._visibleAlternatives();
    const cards = visible.length
      ? visible.map(({ route: alt, index }) => this._renderAlternative(route, alt, index)).join("")
      : `<p class="muted">${t.noRoutes}</p>`;
    return `
      <div class="toolbar">
        <div class="chips">${filters}</div>
        <select class="sort" data-sort="1">${sorts}</select>
      </div>
      <ul class="list">${cards}</ul>`;
  }

  _renderAlternative(route, alt, index) {
    const t = this._t;
    const active = index === this._altIndex;
    const labels = (alt.labels || [])
      .map((label) => `<span class="label">${t.labels[label] || escapeHtml(label)}</span>`)
      .join("");
    const times =
      alt.departure_time && alt.arrival_time
        ? `${this._formatTime(alt.departure_time)} – ${this._formatTime(alt.arrival_time)}`
        : "";
    const facts = [
      t.transfers(alt.transfers),
      alt.walking_duration != null ? t.walking(this._formatDuration(alt.walking_duration)) : null,
      `${alt.fare.toLocaleString()}${t.won}`,
    ]
      .filter(Boolean)
      .join(" · ");
    return `
      <li class="card alternative ${active ? "active" : ""}">
        <button class="plain" data-action="alternative" data-index="${index}">
          ${labels ? `<div class="labels">${labels}</div>` : ""}
          <div class="headline"><span class="big">${this._formatDuration(alt.duration)}</span><small>${times}</small></div>
          <small>${facts}</small>
          ${this._renderSegmentBar(alt)}
        </button>
        ${active ? `${this._renderSteps({ ...alt, mode: "transit" })}${this._routeAppLink(route)}` : ""}
      </li>`;
  }

  // A proportional bar of the walks and rides, colored by line.
  _renderSegmentBar(alt) {
    if (!alt.steps?.length) return "";
    const segments = alt.steps
      .map((step) => {
        const grow = Math.max(step.duration, 60);
        if (!step.lines) return `<span class="seg walk" style="flex-grow:${grow}"></span>`;
        const color = HEX_COLOR.test(step.color || "") ? step.color : "var(--primary-color)";
        return `<span class="seg ride" style="flex-grow:${grow};background:${color}">${escapeHtml(step.lines[0])}</span>`;
      })
      .join("");
    return `<div class="segbar">${segments}</div>`;
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
    return `<div class="steps"><ol class="transit">${items}</ol></div>`;
  }
}

const STYLE = `
  :host { display: block; height: 100vh; height: 100dvh; box-sizing: border-box;
    background: var(--primary-background-color); color: var(--primary-text-color); --rail-w: 72px; --nav-h: 60px;
    /* Registered with handle_safe_area: keep clear of notches here, and of the
       home indicator in the bottom tab bar (phone) or the sheet (wider). */
    padding: var(--safe-area-inset-top, 0px) var(--safe-area-inset-right, 0px) 0 var(--safe-area-inset-left, 0px); }
  ha-icon { --mdc-icon-size: 22px; }

  /* Tablet and wider: icon rail | side panel | map */
  .layout { position: relative; display: grid; height: 100%;
    grid-template-columns: var(--rail-w) clamp(320px, 32vw, 400px) minmax(0, 1fr); grid-template-areas: "nav sheet map"; }
  .nav { grid-area: nav; display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 8px 0;
    background: var(--card-background-color); border-right: 1px solid var(--divider-color); }
  .nav-tabs { display: flex; flex-direction: column; gap: 4px; }
  .nav-tab { display: flex; flex-direction: column; align-items: center; gap: 2px; width: 64px; padding: 8px 0;
    border: none; background: none; color: var(--secondary-text-color); font-size: 11px; cursor: pointer; border-radius: 12px; }
  .nav-tab.active { color: var(--primary-color); background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.12); }
  /* min-width: 0 keeps wide rows (e.g. the category chips) scrolling inside the sheet. */
  .sheet { grid-area: sheet; display: flex; flex-direction: column; min-height: 0; min-width: 0;
    border-right: 1px solid var(--divider-color); background: var(--primary-background-color); }
  .handle { display: none; }
  .content { flex: 1; overflow-y: auto; padding: 12px 12px calc(12px + var(--safe-area-inset-bottom, 0px));
    display: flex; flex-direction: column; gap: 12px; }
  .map { grid-area: map; position: relative; min-height: 0; }
  .map ha-map { display: block; height: 100%; }
  .locate { position: absolute; right: 12px; bottom: 28px; z-index: 1; width: 44px; height: 44px;
    border-radius: 50%; border: none; display: flex; align-items: center; justify-content: center;
    background: var(--card-background-color); color: var(--primary-color); box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3); }

  /* Phone: map above a draggable bottom sheet, bottom tab bar */
  :host(.compact) .layout { grid-template-columns: minmax(0, 1fr);
    grid-template-rows: 1fr var(--sheet-h, 45%) calc(var(--nav-h) + var(--safe-area-inset-bottom, 0px)); grid-template-areas: "map" "sheet" "nav"; }
  :host(.compact) .layout:not(.dragging) { transition: grid-template-rows 0.2s ease; }
  :host(.compact) .nav { flex-direction: row; justify-content: center; border-right: none;
    padding: 0 0 var(--safe-area-inset-bottom, 0px);
    border-top: 1px solid var(--divider-color); }
  :host(.compact) .nav-tabs { flex-direction: row; flex: 1; justify-content: space-around; }
  :host(.compact) .menu { position: absolute; top: 8px; right: 8px; z-index: 2; border-radius: 50%;
    background: var(--card-background-color); box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3); }
  :host(.compact:not(.narrow)) .menu { display: none; }
  :host(.compact) .sheet { border-right: none; border-radius: 16px 16px 0 0; box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.15);
    z-index: 1; margin-top: -16px; }
  :host(.compact) .handle { display: flex; justify-content: center; padding: 8px 0 4px; cursor: grab; touch-action: none; }
  .handle span { width: 40px; height: 4px; border-radius: 2px; background: var(--divider-color); }
  :host(.compact) .content { padding-top: 4px; padding-bottom: 12px; }

  input, select { min-width: 0; padding: 10px; border-radius: 8px; border: 1px solid var(--divider-color);
    background: var(--card-background-color); color: var(--primary-text-color); font: inherit; }
  button { font: inherit; color: inherit; cursor: pointer; }
  .plain { border: none; background: none; padding: 0; text-align: left; width: 100%;
    display: flex; flex-direction: column; gap: 2px; }
  .icon-btn { position: relative; display: inline-flex; align-items: center; justify-content: center; flex: none;
    width: 40px; height: 40px; border-radius: 50%; border: none; background: none; color: var(--secondary-text-color); }
  .icon-btn.active { color: var(--primary-color); background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.12); }
  .icon-select select { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
  .chip { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 16px;
    border: 1px solid var(--divider-color); background: var(--card-background-color); white-space: nowrap; }
  .chip.active { background: var(--primary-color); border-color: var(--primary-color); color: var(--text-primary-color, #fff); }
  .dot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
  .card { padding: 12px; border-radius: 12px; background: var(--card-background-color);
    box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0, 0, 0, 0.12)); }
  .list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
  small, .muted, .hint { color: var(--secondary-text-color); }
  .muted, .hint, .error { margin: 0; }
  .error { color: var(--error-color); }
  .notice { padding: 24px; color: var(--secondary-text-color); }

  .searchbar { display: flex; align-items: center; gap: 4px; padding: 0 4px 0 12px; border-radius: 24px;
    background: var(--card-background-color); box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2); }
  .searchbar input { flex: 1; border: none; background: none; }
  .searchbar > ha-icon { color: var(--secondary-text-color); }
  .place { display: flex; flex-direction: column; gap: 8px; }
  .place.active { outline: 2px solid ${COLORS.activePlace}; }
  .details { display: flex; flex-direction: column; gap: 6px; }
  .photos { display: grid; grid-template-columns: repeat(${MAX_PHOTOS}, 1fr); gap: 4px; }
  .photos img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 8px;
    background: var(--secondary-background-color); }
  .fact { display: flex; align-items: center; gap: 6px; font-size: 14px; }
  .fact ha-icon { --mdc-icon-size: 18px; color: var(--secondary-text-color); }
  .actions { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
  .chip ha-icon { --mdc-icon-size: 18px; }
  .chip.saved { color: var(--primary-color); border-color: var(--primary-color); }
  .chip.danger { color: var(--error-color); border-color: var(--error-color); }
  .zone-icon { --mdc-icon-size: 18px; color: var(--primary-color); margin-right: 4px; vertical-align: -3px; }
  .open { display: inline-flex; align-items: center; gap: 4px; color: var(--primary-color); text-decoration: none; font-size: 14px; }
  .open ha-icon { --mdc-icon-size: 18px; }

  .points { display: flex; align-items: center; gap: 4px; padding: 8px; border-radius: 12px;
    background: var(--card-background-color); box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0, 0, 0, 0.12)); }
  .point-rows { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
  .point-row { display: flex; align-items: center; gap: 4px; }
  .point-row input { flex: 1; border: none; background: var(--secondary-background-color); }
  .modes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; }
  .mode { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 8px 0; border-radius: 12px;
    border: none; background: none; color: var(--secondary-text-color); font-size: 12px; }
  .mode.active { color: var(--primary-color); background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.12); font-weight: 600; }

  .summary .big, .headline .big { font-size: 22px; font-weight: 700; }
  .summary { display: flex; flex-direction: column; gap: 6px; }
  .toolbar { display: flex; align-items: center; gap: 8px; }
  .chips { flex: 1; display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; }
  .categories { flex: none; margin: 0 -12px; padding: 0 12px 2px; }
  .categories ha-icon { --mdc-icon-size: 18px; }
  .categories .chip:not(.active) ha-icon { color: var(--primary-color); }
  .sort { padding: 6px 8px; border-radius: 16px; font-size: 13px; }
  .alternative { display: flex; flex-direction: column; gap: 8px; }
  .alternative.active { outline: 2px solid var(--primary-color); }
  .labels { display: flex; gap: 4px; }
  .label { padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: 600;
    color: var(--primary-color); background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.12); }
  .headline { display: flex; align-items: baseline; gap: 8px; }
  .segbar { display: flex; gap: 2px; height: 18px; margin-top: 6px; }
  .seg { min-width: 6px; border-radius: 9px; overflow: hidden; white-space: nowrap; text-overflow: clip;
    font-size: 11px; line-height: 18px; color: #fff; font-weight: 600; padding: 0 6px; box-sizing: border-box; }
  .seg.walk { background: var(--divider-color); padding: 0; }

  .steps summary { cursor: pointer; color: var(--secondary-text-color); }
  .steps ol { margin: 8px 0 0; padding-left: 20px; display: flex; flex-direction: column; gap: 4px; }
  .steps ol.transit { list-style: none; padding-left: 0; gap: 8px; margin: 0; }
  .ride { border-left: 4px solid var(--line-color); padding-left: 8px; }
  .walk-step { border-left: 4px dotted var(--divider-color); padding-left: 8px; color: var(--secondary-text-color); }
  .badge { display: inline-block; padding: 1px 8px; border-radius: 10px; background: var(--line-color);
    color: #fff; font-weight: 600; font-size: 13px; }
`;

customElements.define("naver-map-panel", NaverMapPanel);
