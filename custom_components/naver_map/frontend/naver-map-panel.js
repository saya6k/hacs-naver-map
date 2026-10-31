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
  edit: "mdi:pencil",
  done: "mdi:check",
  folder: "mdi:folder",
  folderOpen: "mdi:folder-open",
  folderNew: "mdi:folder-plus-outline",
  drag: "mdi:drag",
  zone: "mdi:map-marker-radius",
  car: "mdi:car",
  transit: "mdi:bus",
  walk: "mdi:walk",
  bicycle: "mdi:bike",
  swap: "mdi:swap-vertical",
  entity: "mdi:account-box-outline",
  pick: "mdi:map-marker-radius",
  locate: "mdi:crosshairs-gps",
  tiles: "mdi:layers",
  search: "mdi:magnify",
  open: "mdi:open-in-new",
  hours: "mdi:clock-outline",
  refresh: "mdi:refresh",
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
// Saved places are each user's own favorites, kept with folders in the user's
// frontend data (any user, synced across their devices). Zones appear in the
// same tree. An administrator can turn a favorite into a passive zone: an HA
// entity that automations and get_directions can use and presence ignores.
const SAVED_KEY = "naver_map_saved";
const SAVED_ZONE = { icon: "mdi:star", radius: 50, passive: true };
const SAME_PLACE_DEG = 0.0005; // ~50 m: the same name this close is the same place
const PERSIST_DELAY = 400; // ms; batches rapid edits into one user-data write
const REALTIME_MAX_AGE = 60000; // ms; arrivals are re-read on selection after this
const LOCATE_TIMEOUT = 8000; // ms to wait for the device position
const START_ZOOM = 15;
// Naver Map tiles laid over the base map (OpenStreetMap), from the CDN the
// Naver Maps JS SDK reads: undocumented and keyless, so it may change or block
// without notice. Its TileJSON names the current tile version.
const NAVER_TILES = {
  storageKey: "naver_map_tiles", // localStorage, per browser: "1" while on
  id: "naver-tiles",
  tileJson: (dark) =>
    `https://map.pstatic.net/nrb/styles/${dark ? "dbasic" : "basic"}` +
    `${window.devicePixelRatio > 1 ? "@2x" : ""}.json?fmt=png`,
  attribution: '&copy; <a href="https://map.naver.com/">NAVER Corp.</a>',
};
// Bottom-sheet snaps on phone widths. "min" fits the open tab's controls
// exactly (measured), "peek" shows results with the map still in view, and
// "full" leaves a strip of map so the handle stays reachable.
const SHEET = {
  minFloor: 96, // px, when there is nothing to measure yet
  peekRatio: 0.42, // of the height the map and sheet share
  peekExtra: 160, // px of results peek shows at least, below the controls
  peekCap: 0.6,
  mapStrip: 72, // px of map left above a full sheet
  foldBelow: 0.6, // dragged under this share of "min" folds the sheet away
};
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
    savedEmpty: "Save places from the Places tab with ☆ Save.",
    edit: "Edit",
    done: "Done",
    newFolder: "New folder",
    folderName: "Folder name",
    deleteFolder: "Delete folder (its places move out)",
    moveTo: "Move to",
    noFolder: "No folder",
    makeZone: "Make HA zone",
    zone: "Zone",
    favorites: "Favorites",
    entities: "Entities",
    items: (n) => `${n}`,
    dragHint: "Drag ≡ to reorder or drop onto a folder",
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
      toll_free: "Toll-free",
    },
    toll: (won) => (won ? `Tolls ${won.toLocaleString()} KRW` : "No tolls"),
    fuel: (won) => `Fuel ${won.toLocaleString()} KRW`,
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
    naverTiles: "Naver Map tiles",
    noNearby: "Nothing found nearby",
    loadingDetails: "Loading place details…",
    detailsUnavailable: "Place details unavailable",
    visitorReviews: (n) => `${n.toLocaleString()} visitor reviews`,
    blogReviews: (n) => `${n.toLocaleString()} blog reviews`,
    flags: { booking: "Booking", order: "Order", delivery: "Delivery", naver_pay: "Naver Pay" },
    stops: (n) => `${n} stop${n === 1 ? "" : "s"}`,
    realtime: "Live",
    arrivingSoon: "Arriving",
    inMinutes: (n) => `${n} min`,
    stopsAway: (n) => `${n} stop${n === 1 ? "" : "s"} away`,
    noRealtime: "No live info",
    notRunning: "Not running",
    refresh: "Refresh live arrivals",
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
    savedEmpty: "장소 검색에서 ☆ 저장을 누르면 여기에 모입니다.",
    edit: "편집",
    done: "완료",
    newFolder: "새 폴더",
    folderName: "폴더 이름",
    deleteFolder: "폴더 삭제(안의 장소는 밖으로)",
    moveTo: "이동",
    noFolder: "폴더 없음",
    makeZone: "HA 구역으로",
    zone: "구역",
    favorites: "즐겨찾기",
    entities: "엔티티",
    items: (n) => `${n}`,
    dragHint: "≡를 끌어 순서를 바꾸거나 폴더 위에 놓으세요",
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
      toll_free: "무료도로",
    },
    toll: (won) => (won ? `통행료 ${won.toLocaleString()}원` : "통행료 없음"),
    fuel: (won) => `유류비 ${won.toLocaleString()}원`,
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
    naverTiles: "네이버 지도 타일",
    noNearby: "주변에서 찾지 못했습니다",
    loadingDetails: "장소 정보를 불러오는 중…",
    detailsUnavailable: "장소 정보를 불러오지 못했습니다",
    visitorReviews: (n) => `방문자 리뷰 ${n.toLocaleString()}`,
    blogReviews: (n) => `블로그 리뷰 ${n.toLocaleString()}`,
    flags: { booking: "예약", order: "주문", delivery: "배달", naver_pay: "네이버페이" },
    stops: (n) => `${n}개 정류장`,
    realtime: "실시간",
    arrivingSoon: "곧 도착",
    inMinutes: (n) => `${n}분`,
    stopsAway: (n) => `${n}정거장 전`,
    noRealtime: "실시간 정보 없음",
    notRunning: "운행 종료",
    refresh: "실시간 도착 새로고침",
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

const realtimeKey = (step) => `${step.type}:${step.stop_id}:${step.way || ""}`;
const PLACE_LINK = "https://map.naver.com/p/entry/place";
const mapSearchUrl = (name) => `https://map.naver.com/p/search/${encodeURIComponent(name)}`;

// A saved favorite in the shape of a search result (for details and links).
const leafPlace = (leaf) => ({
  place_name: leaf.name,
  latitude: leaf.latitude,
  longitude: leaf.longitude,
  ...(leaf.place_id ? { place_id: leaf.place_id } : {}),
});

// crypto.randomUUID needs a secure context, which HA over plain http lacks.
const newId = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
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
    this._realtime = {}; // get_transit_arrivals results by boarding stop
    this._confirmRemove = null; // saved node id waiting for a second tap
    this._saved = null; // favorites tree from user data; null until loaded
    this._editing = false;
    this._activeSaved = null; // saved favorite whose details are shown
    this._drag = null;
    this._here = null; // device position [lat, lng], when the browser shares it
    this._sheet = "min";
    this._open = false; // the panel starts folded: map only, no tab content
    this._naverTiles = false;
    try {
      this._naverTiles = localStorage.getItem(NAVER_TILES.storageKey) === "1";
    } catch {
      // Storage blocked: the tiles start off.
    }
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
    if (first) this._loadSaved();
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
      <div class="layout closed">
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
    this._setUpDrag(this._content);
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

  // Snap heights for the open tab, from what is on screen right now.
  _sheetHeights() {
    const nav = this._root.querySelector(".nav").offsetHeight;
    const shared = this._layout.clientHeight - nav; // map + sheet
    const handle = this._root.querySelector(".handle").offsetHeight;
    const head = this._content.querySelector(".sheet-head")?.offsetHeight;
    // handle + content padding (4 top, 12 below the controls)
    const min = Math.max(SHEET.minFloor, head ? Math.ceil(handle + 4 + head + 12) : 0);
    const full = Math.max(min, shared - SHEET.mapStrip);
    const peek = Math.min(
      full,
      Math.max(min + SHEET.peekExtra, Math.min(shared * SHEET.peekRatio, shared * SHEET.peekCap))
    );
    return { min, peek: Math.round(peek), full };
  }

  // Phone layout: the sheet height decides how much map stays visible above it.
  _applySheet(px) {
    if (!this._compact) {
      this._layout.style.removeProperty("--sheet-h");
      return;
    }
    if (!this._open) {
      this._layout.style.setProperty("--sheet-h", "0px");
      return;
    }
    this._layout.style.setProperty("--sheet-h", `${px ?? this._sheetHeights()[this._sheet]}px`);
  }

  // The snap a tab opens at: just its controls, or results when it has some.
  _defaultSheet() {
    const hasResults = {
      place: this._places.length > 0,
      route: Boolean(this._route),
      saved: this._savedLeaves().length > 0,
    };
    return hasResults[this._tab] ? "peek" : "min";
  }

  _openTab(tab) {
    this._tab = tab;
    this._open = true;
    this._picking = null;
    this._error = null;
    this._layout.classList.remove("closed");
    this._sheet = this._defaultSheet();
    this._render();
    this._drawMap();
  }

  // Fold the tab away entirely; the map keeps what it shows.
  _closeTab() {
    this._open = false;
    this._picking = null;
    this._layout.classList.add("closed");
    this._render();
    this._applySheet();
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
      start = {
        y: ev.clientY,
        h: this._root.querySelector(".sheet").offsetHeight,
        heights: this._sheetHeights(),
        moved: false,
      };
      handle.setPointerCapture(ev.pointerId);
      this._layout.classList.add("dragging");
    });
    handle.addEventListener("pointermove", (ev) => {
      if (!start) return;
      const dy = start.y - ev.clientY;
      if (Math.abs(dy) > 4) start.moved = true;
      this._applySheet(Math.min(start.heights.full, Math.max(0, start.h + dy)));
    });
    const end = () => {
      if (!start) return;
      const height = this._root.querySelector(".sheet").offsetHeight;
      const { heights } = start;
      const order = ["min", "peek", "full"];
      let state;
      if (!start.moved) {
        // A tap steps through the snaps: min → peek → full → peek.
        state = this._sheet === "full" ? "peek" : order[order.indexOf(this._sheet) + 1];
      } else if (height < heights.min * SHEET.foldBelow) {
        state = null; // dragged well below the controls: fold away
      } else {
        state = order.reduce((best, s) =>
          Math.abs(heights[s] - height) < Math.abs(heights[best] - height) ? s : best
        );
      }
      start = null;
      this._layout.classList.remove("dragging");
      if (state === null) {
        this._closeTab();
        return;
      }
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
    // Fired each time ha-map has (re)built its engine, e.g. after a WebGL loss.
    map.addEventListener("editing-available-changed", () => this._attachNaverTiles());
    container.appendChild(map);
    const tiles = document.createElement("button");
    tiles.className = "tiles";
    tiles.title = this._t.naverTiles;
    tiles.innerHTML = icon("tiles");
    tiles.hidden = true; // until there is a MapLibre map to lay them on
    tiles.addEventListener("click", () => this._toggleNaverTiles());
    container.appendChild(tiles);
    this._tilesButton = tiles;
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

  // The MapLibre map inside <ha-map>, or null on its Leaflet fallback (no
  // WebGL2). ha-map has no public way to add a layer, so this reads its
  // internals; if the frontend changes them the tiles just never appear.
  _glMap() {
    const gl = this._map?._engine?._map;
    return typeof gl?.getStyle === "function" && typeof gl?.addLayer === "function" ? gl : null;
  }

  _attachNaverTiles() {
    const gl = this._glMap();
    this._tilesButton.hidden = !gl;
    if (!gl || gl === this._tilesMap) return;
    this._tilesMap = gl;
    // A style change (theme switch) drops the layer; put it back once it settles.
    const sync = () => this._syncNaverTiles();
    gl.on("styledata", sync);
    gl.on("idle", sync);
    sync();
  }

  _toggleNaverTiles() {
    this._naverTiles = !this._naverTiles;
    try {
      if (this._naverTiles) localStorage.setItem(NAVER_TILES.storageKey, "1");
      else localStorage.removeItem(NAVER_TILES.storageKey);
    } catch {
      // Not remembered; still applies to this map.
    }
    this._syncNaverTiles();
  }

  // One raster layer over the base map and under what the panel draws (zones,
  // route, markers: GeoJSON sources). Where Naver tiles fail to load the base
  // map shows through, and turning them off only removes the layer.
  _syncNaverTiles() {
    this._tilesButton.classList.toggle("on", this._naverTiles);
    this._tilesButton.setAttribute("aria-pressed", String(this._naverTiles));
    const gl = this._glMap();
    // Its own add/move calls fire styledata again.
    if (!gl || this._syncingTiles) return;
    this._syncingTiles = true;
    const { id } = NAVER_TILES;
    const dark = Boolean(this._hass?.themes?.darkMode);
    try {
      if (gl.getSource(id) && (!this._naverTiles || this._naverTilesDark !== dark)) {
        if (gl.getLayer(id)) gl.removeLayer(id);
        gl.removeSource(id);
      }
      if (!this._naverTiles) return;
      if (!gl.getSource(id)) {
        gl.addSource(id, {
          type: "raster",
          url: NAVER_TILES.tileJson(dark),
          tileSize: 256,
          attribution: NAVER_TILES.attribution,
        });
        this._naverTilesDark = dark;
      }
      if (!gl.getLayer(id)) gl.addLayer({ id, type: "raster", source: id });
      const layers = gl.getStyle().layers;
      const drawn = (layer) => gl.getSource(layer.source)?.type === "geojson";
      const at = layers.findIndex((layer) => layer.id === id);
      const misplaced = layers.some(
        (layer, i) => layer.id !== id && (i < at ? drawn(layer) : !drawn(layer))
      );
      if (misplaced) {
        gl.moveLayer(id);
        layers.filter(drawn).forEach((layer) => gl.moveLayer(layer.id));
      }
    } catch {
      // The style is still loading; the next styledata/idle tries again.
    } finally {
      this._syncingTiles = false;
    }
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
    this._map.paths = [];
    const leaves = this._savedLeaves();
    this._map.editableLocations = [
      ...this._hereMarkers(),
      ...leaves
        .filter((leaf) => leaf.kind === "place")
        .map((leaf) => ({
          id: `saved-${leaf.id}`,
          location: [leaf.latitude, leaf.longitude],
          title: leaf.name,
          element: this._markerElement("activePlace", leaf.id),
          elementSize: 20,
        })),
    ];
    const points = leaves.map((leaf) => this._leafLocation(leaf)).filter(Boolean);
    if (points.length) this._map.fitBounds(points, { pad: 0.3, zoom: 15 });
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

  // --- favorites tree ------------------------------------------------------

  async _loadSaved() {
    try {
      const result = await this._hass.callWS({ type: "frontend/get_user_data", key: SAVED_KEY });
      this._saved = result?.value?.tree || [];
    } catch (err) {
      console.warn("[naver-map-panel] could not load saved places:", err);
      this._saved = [];
    }
    if (this._tab !== "route") {
      this._render();
      this._drawMap();
    }
  }

  // The stored tree, with removed zones dropped and zones not filed yet appended.
  _savedTree() {
    const zones = this._savedZones();
    const known = new Set(zones.map((s) => s.entity_id));
    const keep = (leaf) => leaf.kind !== "zone" || known.has(leaf.entity_id);
    const tree = (this._saved || [])
      .map((node) =>
        node.kind === "folder" ? { ...node, children: node.children.filter(keep) } : node
      )
      .filter((node) => node.kind === "folder" || keep(node));
    const filed = new Set(
      tree.flatMap((node) => (node.kind === "folder" ? node.children : [node]))
        .filter((leaf) => leaf.kind === "zone")
        .map((leaf) => leaf.entity_id)
    );
    for (const state of zones) {
      if (!filed.has(state.entity_id)) {
        tree.push({ kind: "zone", id: `zone:${state.entity_id}`, entity_id: state.entity_id });
      }
    }
    return tree;
  }

  _savedLeaves() {
    return this._savedTree().flatMap((node) => (node.kind === "folder" ? node.children : [node]));
  }

  // Apply an edit to the (reconciled) tree and write it to the user's data.
  _updateSaved(mutate) {
    const tree = structuredClone(this._savedTree());
    mutate(tree);
    this._saved = tree;
    this._render();
    this._drawMap();
    clearTimeout(this._persistTimer);
    this._persistTimer = setTimeout(() => {
      this._hass
        .callWS({ type: "frontend/set_user_data", key: SAVED_KEY, value: { version: 1, tree } })
        .catch((err) => {
          this._error = err.message || String(err);
          this._render();
        });
    }, PERSIST_DELAY);
  }

  _leafName(leaf) {
    if (leaf.kind === "place") return leaf.name;
    const state = this._hass.states[leaf.entity_id];
    return state?.attributes.friendly_name || leaf.entity_id;
  }

  _leafLocation(leaf) {
    if (leaf.kind === "place") return [leaf.latitude, leaf.longitude];
    const state = this._hass.states[leaf.entity_id];
    return state ? [state.attributes.latitude, state.attributes.longitude] : null;
  }

  // Find a node: { list, index, node } where list is the root or a folder's children.
  static _locate(tree, id) {
    for (let i = 0; i < tree.length; i++) {
      if (tree[i].id === id) return { list: tree, index: i, node: tree[i] };
      if (tree[i].kind === "folder") {
        const j = tree[i].children.findIndex((child) => child.id === id);
        if (j >= 0) return { list: tree[i].children, index: j, node: tree[i].children[j] };
      }
    }
    return null;
  }

  // Move a node before/after another, or into a folder. Folders stay one level deep.
  _moveSaved(id, targetId, position) {
    if (id === targetId) return;
    this._updateSaved((tree) => {
      const from = NaverMapPanel._locate(tree, id);
      if (!from) return;
      let target = NaverMapPanel._locate(tree, targetId);
      if (!target) return;
      if (from.node.kind === "folder" && (position === "into" || target.list !== tree)) {
        // A folder dropped on a folder's contents goes next to that folder instead.
        const parent = tree.find((n) => n.kind === "folder" && n.children.includes(target.node));
        target = parent ? NaverMapPanel._locate(tree, parent.id) : target;
        if (position === "into") position = "after";
      }
      from.list.splice(from.index, 1);
      if (position === "into") {
        target.node.open = true;
        target.node.children.push(from.node);
        return;
      }
      const at = target.list.indexOf(target.node);
      target.list.splice(position === "before" ? at : at + 1, 0, from.node);
    });
  }

  _isSaved(place) {
    return (
      this._savedZoneFor(place) ||
      this._savedLeaves().some(
        (leaf) =>
          leaf.kind === "place" &&
          ((place.place_id && leaf.place_id === place.place_id) ||
            (leaf.name === place.place_name &&
              Math.abs(leaf.latitude - place.latitude) < SAME_PLACE_DEG &&
              Math.abs(leaf.longitude - place.longitude) < SAME_PLACE_DEG))
      )
    );
  }

  _savePlace(place) {
    this._updateSaved((tree) =>
      tree.push({
        kind: "place",
        id: newId(),
        name: place.place_name,
        latitude: place.latitude,
        longitude: place.longitude,
        ...(place.place_id ? { place_id: place.place_id } : {}),
        ...(place.road_address || place.address
          ? { address: place.road_address || place.address }
          : {}),
      })
    );
  }

  // Zones created in the UI (or here) are listed by zone/list; YAML zones and
  // home are not, and cannot be changed from the panel.
  async _zoneId(entityId) {
    const state = this._hass.states[entityId];
    const zones = await this._hass.callWS({ type: "zone/list" });
    return zones.find(
      (z) =>
        z.name === state.attributes.friendly_name &&
        Math.abs(z.latitude - state.attributes.latitude) < 1e-6 &&
        Math.abs(z.longitude - state.attributes.longitude) < 1e-6
    )?.id;
  }

  async _zoneCall(work) {
    try {
      await work();
    } catch (err) {
      this._error = err.message || String(err);
      this._render();
    }
  }

  // Delete needs a second tap: a favorite leaves the list, a zone is deleted.
  _removeSaved(id) {
    if (this._confirmRemove !== id) {
      this._confirmRemove = id;
      this._render();
      return;
    }
    this._confirmRemove = null;
    const found = NaverMapPanel._locate(this._savedTree(), id);
    if (!found) return;
    if (found.node.kind === "zone") {
      this._zoneCall(async () => {
        const zoneId = await this._zoneId(found.node.entity_id);
        if (zoneId) await this._hass.callWS({ type: "zone/delete", zone_id: zoneId });
      });
      return;
    }
    this._updateSaved((tree) => {
      const at = NaverMapPanel._locate(tree, id);
      if (!at) return;
      at.list.splice(at.index, 1, ...(at.node.kind === "folder" ? at.node.children : []));
    });
  }

  _renameSaved(id, name) {
    const trimmed = name.trim();
    if (!trimmed) return;
    const found = NaverMapPanel._locate(this._savedTree(), id);
    if (found?.node.kind === "zone") {
      this._zoneCall(async () => {
        const zoneId = await this._zoneId(found.node.entity_id);
        if (zoneId) await this._hass.callWS({ type: "zone/update", zone_id: zoneId, name: trimmed });
      });
      return;
    }
    this._updateSaved((tree) => {
      const at = NaverMapPanel._locate(tree, id);
      if (at) at.node.name = trimmed;
    });
  }

  // A favorite becomes a passive zone in the same spot of the tree.
  _favoriteToZone(id) {
    const found = NaverMapPanel._locate(this._savedTree(), id);
    if (found?.node.kind !== "place") return;
    const leaf = found.node;
    this._zoneCall(async () => {
      const zone = await this._hass.callWS({
        type: "zone/create",
        name: leaf.name,
        latitude: leaf.latitude,
        longitude: leaf.longitude,
        ...SAVED_ZONE,
      });
      const entityId = `zone.${zone.id}`;
      this._updateSaved((tree) => {
        const at = NaverMapPanel._locate(tree, id);
        if (at) at.list[at.index] = { kind: "zone", id: `zone:${entityId}`, entity_id: entityId };
      });
    });
  }

  // Drag by the ≡ handle (mouse or touch): the row under the pointer becomes
  // the drop target, before/after it or, for a folder's middle, into it.
  _setUpDrag(content) {
    content.addEventListener("pointerdown", (ev) => {
      const handle = ev.target.closest(".drag-handle");
      if (!handle || !this._editing) return;
      ev.preventDefault();
      handle.setPointerCapture(ev.pointerId);
      this._drag = { id: handle.dataset.id, target: null };
      handle.closest(".node").classList.add("dragging");
    });
    content.addEventListener("pointermove", (ev) => {
      if (!this._drag) return;
      const row = this._root.elementFromPoint(ev.clientX, ev.clientY)?.closest(".node-row");
      content.querySelectorAll(".drop-before, .drop-after, .drop-into").forEach((el) =>
        el.classList.remove("drop-before", "drop-after", "drop-into")
      );
      // Keep the list scrolling while dragging near its edges.
      const box = content.getBoundingClientRect();
      if (ev.clientY < box.top + 40) content.scrollBy(0, -12);
      else if (ev.clientY > box.bottom - 40) content.scrollBy(0, 12);
      if (!row || row.dataset.id === this._drag.id) {
        this._drag.target = null;
        return;
      }
      const rect = row.getBoundingClientRect();
      const y = (ev.clientY - rect.top) / rect.height;
      const isFolder = row.dataset.kind === "folder";
      const position = isFolder && y > 0.25 && y < 0.75 ? "into" : y < 0.5 ? "before" : "after";
      row.classList.add(`drop-${position}`);
      this._drag.target = { id: row.dataset.id, position };
    });
    const end = () => {
      if (!this._drag) return;
      const { id, target } = this._drag;
      this._drag = null;
      if (target) this._moveSaved(id, target.id, target.position);
      else this._render();
    };
    content.addEventListener("pointerup", end);
    content.addEventListener("pointercancel", end);
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
        // The open tab's button folds it; any other opens that tab.
        if (this._open && this._tab === el.dataset.tab) this._closeTab();
        else this._openTab(el.dataset.tab);
        break;
      case "place-search":
        this._searchPlaces();
        break;
      case "place-save":
        this._savePlace(this._places[index]);
        break;
      case "saved-use":
      case "saved-select": {
        const found = NaverMapPanel._locate(this._savedTree(), el.dataset.id);
        if (!found) break;
        const leaf = found.node;
        const location = this._leafLocation(leaf);
        if (!location) break;
        if (action === "saved-select") {
          this._map?.fitBounds([location], { zoom: 16 });
          // Favorites are Naver places: show their summary, as in the Places tab.
          this._activeSaved = leaf.kind === "place" && this._activeSaved !== leaf.id ? leaf.id : null;
          if (this._activeSaved) this._loadDetails(leafPlace(leaf));
          this._render();
          break;
        }
        const label = this._leafName(leaf);
        this._openTab("route");
        this._queries[slot] = label;
        this._setPoint(slot, {
          label,
          location,
          ...(leaf.kind === "zone" ? { entityId: leaf.entity_id } : {}),
        });
        break;
      }
      case "saved-remove":
        this._removeSaved(el.dataset.id);
        break;
      case "saved-zone":
        this._favoriteToZone(el.dataset.id);
        break;
      case "saved-edit":
        this._editing = !this._editing;
        this._confirmRemove = null;
        this._render();
        break;
      case "folder-new":
        this._updateSaved((tree) =>
          tree.unshift({ kind: "folder", id: newId(), name: this._t.newFolder, open: true, children: [] })
        );
        break;
      case "folder-toggle":
        this._updateSaved((tree) => {
          const at = NaverMapPanel._locate(tree, el.dataset.id);
          if (at) at.node.open = !at.node.open;
        });
        break;
      case "nearby":
        this._searchNearby(el.dataset.category);
        break;
      case "place-select":
        this._selectPlace(index);
        break;
      case "place-use": {
        const place = this._places[index];
        this._openTab("route");
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
        this._loadRealtime();
        break;
      case "realtime-refresh":
        this._loadRealtime({ force: true });
        break;
    }
  }

  _onChange(ev) {
    const { rename, move } = ev.target.dataset;
    if (rename) {
      this._renameSaved(rename, ev.target.value);
      return;
    }
    if (move) {
      const into = ev.target.value;
      if (into) this._moveSaved(move, into, "into");
      else {
        // Out of its folder: right after that folder.
        const tree = this._savedTree();
        const folder = tree.find((n) => n.kind === "folder" && n.children.some((c) => c.id === move));
        if (folder) this._moveSaved(move, folder.id, "after");
      }
      return;
    }
    if (ev.target.dataset.sort) {
      this._transitSort = ev.target.value;
      this._selectFirstVisibleAlternative();
      return;
    }
    const slot = ev.target.dataset.entity;
    if (!slot || !ev.target.value) return;
    if (ev.target.value.startsWith("fav:")) {
      const found = NaverMapPanel._locate(this._savedTree(), ev.target.value.slice(4));
      if (!found) return;
      const leaf = found.node;
      this._queries[slot] = leaf.name;
      this._setPoint(slot, {
        label: leaf.name,
        favoriteId: leaf.id,
        location: [leaf.latitude, leaf.longitude],
      });
      return;
    }
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
      this._places = (
        await this._callService("search_place", { query, near: this._startLocation().input })
      ).results;
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
    if (this._tab !== "route") this._render();
  }

  async _search(slot) {
    const query = (this._queries[slot] || "").trim();
    if (!query) return;
    this._error = null;
    try {
      const response = await this._callService("search_place", {
        query,
        near: this._startLocation().input,
      });
      this._results[slot] = response.results;
      if (this._sheet === "min") this._sheet = "peek"; // room for the matches
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
        include_alternatives: this._mode === "transit" || this._mode === "car",
      });
      if (requestId !== this._requestId) return; // a newer lookup superseded this one
      this._route = route;
      if (this._sheet === "min") this._sheet = "peek";
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
    this._loadRealtime();
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
    this._loadRealtime();
  }

  // Live arrivals at the boarding stops of the transit route on screen. Read
  // only when a route is shown or refreshed, one stop at a time, and reused
  // for a minute, to stay gentle with Naver's undocumented endpoint.
  async _loadRealtime({ force = false } = {}) {
    const shown = this._shownRoute();
    if (this._route?.mode !== "transit" || !shown?.steps) return;
    for (const step of shown.steps.filter((s) => s.stop_id)) {
      const key = realtimeKey(step);
      const cached = this._realtime[key];
      if (cached?.loading) continue;
      if (!force && cached?.at && Date.now() - cached.at < REALTIME_MAX_AGE) continue;
      this._realtime[key] = { ...cached, loading: true };
      try {
        const response = await this._callService("get_transit_arrivals", {
          type: step.type,
          stop_id: step.stop_id,
          route_ids: step.route_ids,
          ...(step.type === "subway" && step.way ? { direction: step.way } : {}),
        });
        this._realtime[key] = { arrivals: response.arrivals, at: Date.now() };
      } catch (err) {
        this._realtime[key] = { error: err.message || String(err), at: Date.now() };
      }
      if (this._tab === "route") this._render();
    }
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
        `<button data-action="tab" data-tab="${tab}" class="nav-tab ${this._open && tab === this._tab ? "active" : ""}" title="${t.tabs[tab]}" aria-expanded="${this._open && tab === this._tab}">
          ${icon(tab)}<span>${t.tabs[tab]}</span>
        </button>`
    ).join("");
    const renderers = {
      place: () => this._renderPlaceTab(),
      route: () => this._renderRouteTab(),
      saved: () => this._renderSavedTab(),
    };
    this._content.innerHTML = this._open ? renderers[this._tab]() : "";
    // The controls' height may have changed ("min" fits them).
    if (!this._layout.classList.contains("dragging")) this._applySheet();
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
      <div class="sheet-head">
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
      </div>
      ${this._error ? `<p class="error">${escapeHtml(this._error)}</p>` : ""}
      ${places ? `<ul class="list">${places}</ul>` : ""}`;
  }

  _renderSaveButton(place, index) {
    const t = this._t;
    if (this._isSaved(place)) {
      return `<span class="chip saved">${icon("saved")}${t.savedLabel}</span>`;
    }
    return `<button class="chip" data-action="place-save" data-index="${index}">${icon("save")}${t.save}</button>`;
  }

  _renderSavedTab() {
    const t = this._t;
    if (this._saved === null) return `<p class="muted">…</p>`;
    const tree = this._savedTree();
    const folders = tree.filter((n) => n.kind === "folder");
    const editing = this._editing;
    const toolbar = `
      <div class="sheet-head">
      <div class="saved-toolbar">
        ${editing ? `<button class="chip" data-action="folder-new">${icon("folderNew")}${t.newFolder}</button>` : ""}
        <span class="spacer"></span>
        <button class="chip ${editing ? "active" : ""}" data-action="saved-edit">${icon(editing ? "done" : "edit")}${editing ? t.done : t.edit}</button>
      </div>
      ${editing ? `<small>${t.dragHint}</small>` : ""}
      </div>`;
    const nodes = tree
      .map((node) =>
        node.kind === "folder" ? this._renderFolder(node, folders) : this._renderLeaf(node, folders, null)
      )
      .join("");
    const empty = tree.some((n) => n.kind === "folder" || n.kind === "place")
      ? ""
      : `<p class="muted">${t.savedEmpty}</p>`;
    return `
      ${toolbar}
      ${this._error ? `<p class="error">${escapeHtml(this._error)}</p>` : ""}
      <ul class="list tree">${nodes}</ul>
      ${empty}`;
  }

  _renderFolder(folder, folders) {
    const t = this._t;
    const head = this._editing
      ? `<span class="drag-handle" data-id="${folder.id}">${icon("drag")}</span>
         ${icon("folder")}
         <input class="rename" data-rename="${folder.id}" value="${escapeHtml(folder.name)}" aria-label="${t.folderName}">
         ${this._removeButton(folder.id, t.deleteFolder)}`
      : `<button class="plain folder-head" data-action="folder-toggle" data-id="${folder.id}">
           ${icon(folder.open ? "folderOpen" : "folder")}<b>${escapeHtml(folder.name)}</b>
           <small>${t.items(folder.children.length)}</small>
         </button>`;
    const children =
      folder.open || this._editing
        ? `<ul class="list children">${folder.children.map((leaf) => this._renderLeaf(leaf, folders, folder)).join("")}</ul>`
        : "";
    return `
      <li class="node folder">
        <div class="node-row folder-row" data-id="${folder.id}" data-kind="folder">${head}</div>
        ${children}
      </li>`;
  }

  _removeButton(id, title) {
    const t = this._t;
    const confirming = this._confirmRemove === id;
    return `<button class="icon-btn small ${confirming ? "danger" : ""}" data-action="saved-remove" data-id="${id}" title="${confirming ? t.confirmRemove : title || t.remove}">${icon("delete")}</button>${confirming ? `<small class="danger-text">${t.confirmRemove}</small>` : ""}`;
  }

  _renderLeaf(leaf, folders, folder) {
    const t = this._t;
    const isAdmin = this._hass.user?.is_admin;
    const name = this._leafName(leaf);
    const location = this._leafLocation(leaf);
    const start = this._startLocation().location;
    const meters = location ? Math.round(distanceMeters(start, location)) : null;
    const zoneState = leaf.kind === "zone" ? this._hass.states[leaf.entity_id] : null;
    const leafIcon =
      leaf.kind === "zone" ? zoneState?.attributes.icon || ICONS.zone : "mdi:star";
    // Zones are renamed/removed for everyone, so only administrators may, and
    // only UI-created ones (home and YAML zones are read-only).
    const zoneEditable = isAdmin && zoneState?.attributes.editable && leaf.entity_id !== "zone.home";
    if (this._editing) {
      const moveOptions = [
        `<option value="">${t.noFolder}</option>`,
        ...folders.map(
          (f) => `<option value="${f.id}" ${f === folder ? "selected" : ""}>${escapeHtml(f.name)}</option>`
        ),
      ].join("");
      const canRename = leaf.kind === "place" || zoneEditable;
      return `
        <li class="node leaf">
          <div class="node-row card" data-id="${leaf.id}" data-kind="${leaf.kind}">
            <span class="drag-handle" data-id="${leaf.id}">${icon("drag")}</span>
            <ha-icon class="zone-icon" icon="${escapeHtml(leafIcon)}"></ha-icon>
            ${
              canRename
                ? `<input class="rename" data-rename="${leaf.id}" value="${escapeHtml(name)}">`
                : `<b class="leaf-name">${escapeHtml(name)}</b>`
            }
            <select class="move" data-move="${leaf.id}" title="${t.moveTo}" aria-label="${t.moveTo}">${moveOptions}</select>
            ${leaf.kind === "place" && isAdmin ? `<button class="icon-btn small" data-action="saved-zone" data-id="${leaf.id}" title="${t.makeZone}">${icon("zone")}</button>` : ""}
            ${leaf.kind === "place" || zoneEditable ? this._removeButton(leaf.id) : ""}
          </div>
        </li>`;
    }
    return `
      <li class="node leaf">
        <div class="node-row card place ${leaf.id === this._activeSaved ? "active" : ""}" data-id="${leaf.id}" data-kind="${leaf.kind}">
          <button class="plain" data-action="saved-select" data-id="${leaf.id}">
            <b><ha-icon class="zone-icon" icon="${escapeHtml(leafIcon)}"></ha-icon>${escapeHtml(name)}${leaf.kind === "zone" ? ` <span class="label">${t.zone}</span>` : ""}</b>
            <small>${[meters != null ? this._formatDistance(meters) : null, leaf.address && escapeHtml(leaf.address)].filter(Boolean).join(" · ")}</small>
          </button>
          ${leaf.id === this._activeSaved ? this._renderDetails(leafPlace(leaf)) : ""}
          <div class="actions">
            <button class="chip" data-action="saved-use" data-slot="origin" data-id="${leaf.id}">
              <span class="dot" style="background:${COLORS.origin}"></span>${t.setOrigin}</button>
            <button class="chip" data-action="saved-use" data-slot="destination" data-id="${leaf.id}">
              <span class="dot" style="background:${COLORS.destination}"></span>${t.setDestination}</button>
            ${
              leaf.kind === "place"
                ? this._openLink(
                    this._details[placeKey(leafPlace(leaf))]?.place_url ||
                      (leaf.place_id ? `${PLACE_LINK}/${leaf.place_id}` : mapSearchUrl(leaf.name)),
                    appUrl("place", { lat: leaf.latitude, lng: leaf.longitude, name: leaf.name })
                  )
                : ""
            }
          </div>
        </div>
      </li>`;
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
      <div class="sheet-head">
      <div class="points">
        <div class="point-rows">
          ${this._renderSlot("origin", entities)}
          ${this._renderSlot("destination", entities)}
        </div>
        <button class="icon-btn swap" data-action="swap" title="${t.swap}">${icon("swap")}</button>
      </div>
      <div class="modes">${modes}</div>
      ${this._picking ? `<p class="hint">${t.pickingHint}</p>` : ""}
      </div>
      ${this._renderSlotResults("origin")}
      ${this._renderSlotResults("destination")}
      ${this._renderResult()}`;
  }

  _renderSlot(slot, entities) {
    const t = this._t;
    const point = this._points[slot];
    const entityOptions = entities
      .map(
        (s) =>
          `<option value="${escapeHtml(s.entity_id)}" ${point?.entityId === s.entity_id ? "selected" : ""}>${escapeHtml(s.attributes.friendly_name || s.entity_id)}</option>`
      )
      .join("");
    // Favorites first, labelled with their folder, then the entities.
    const favoriteOptions = this._savedTree()
      .flatMap((node) =>
        node.kind === "folder" ? node.children.map((leaf) => [leaf, node.name]) : [[node, null]]
      )
      .filter(([leaf]) => leaf.kind === "place")
      .map(
        ([leaf, folder]) =>
          `<option value="fav:${leaf.id}" ${point?.favoriteId === leaf.id ? "selected" : ""}>${escapeHtml(folder ? `${folder} › ${leaf.name}` : leaf.name)}</option>`
      )
      .join("");
    const options =
      (favoriteOptions ? `<optgroup label="${t.favorites}">${favoriteOptions}</optgroup>` : "") +
      `<optgroup label="${t.entities}">${entityOptions}</optgroup>`;
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
    if (route.alternatives?.length && route.mode === "transit") return this._renderTransit(route);
    if (route.alternatives?.length) {
      const cards = route.alternatives
        .map((alt, index) => this._renderAlternative(route, alt, index))
        .join("");
      return `<ul class="list">${cards}</ul>`;
    }
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
    if (route.mode !== "transit") {
      // Car: Directions 5's best / fastest / toll-free routes with their costs.
      const facts = [
        this._formatDistance(alt.distance),
        alt.toll_fare != null ? t.toll(alt.toll_fare) : null,
        alt.fuel_price != null ? t.fuel(alt.fuel_price) : null,
      ]
        .filter(Boolean)
        .join(" · ");
      return `
        <li class="card alternative ${active ? "active" : ""}">
          <button class="plain" data-action="alternative" data-index="${index}">
            ${labels ? `<div class="labels">${labels}</div>` : ""}
            <div class="headline"><span class="big">${this._formatDuration(alt.duration)}</span><small>${t.arrives(this._formatTime(alt.arrival_time))}</small></div>
            <small>${facts}</small>
          </button>
          ${active ? `${this._renderSteps({ ...alt, mode: route.mode })}${this._routeAppLink(route)}` : ""}
        </li>`;
    }
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

  // "Live 140 Arriving (1 stop away) · 7 min (3 stops away)" under a ride.
  _renderRealtime(step) {
    const t = this._t;
    if (!step.stop_id) return "";
    const live = this._realtime[realtimeKey(step)];
    const refresh = `<button class="icon-btn small" data-action="realtime-refresh" title="${t.refresh}">${icon("refresh")}</button>`;
    if (!live || (live.loading && !live.arrivals)) {
      return `<div class="live"><span class="live-tag">${t.realtime}</span><small>…</small></div>`;
    }
    if (live.error || !live.arrivals?.length) {
      return `<div class="live"><span class="live-tag">${t.realtime}</span><small>${t.noRealtime}</small>${refresh}</div>`;
    }
    const now = Date.now();
    const vehicle = (v) => {
      const minutes = Math.max(0, Math.round((new Date(v.arrival_time).getTime() - now) / 60000));
      const when = minutes < 1 ? t.arrivingSoon : t.inMinutes(minutes);
      return v.remaining_stops != null ? `${when} (${t.stopsAway(v.remaining_stops)})` : when;
    };
    const rows = live.arrivals
      .map((line) => {
        const next = line.vehicles.length
          ? line.vehicles.slice(0, 2).map(vehicle).join(" · ")
          : t.notRunning;
        const name = live.arrivals.length > 1 || step.type === "bus" ? `<b>${escapeHtml(line.line)}</b> ` : "";
        return `<div>${name}${escapeHtml(next)}</div>`;
      })
      .join("");
    return `<div class="live"><span class="live-tag">${t.realtime}</span><div class="live-rows">${rows}</div>${refresh}</div>`;
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
          ${this._renderRealtime(step)}
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
  .sheet-head { display: flex; flex-direction: column; gap: 12px; flex: none; }
  /* Folded: no tab content; the map takes the space. */
  .layout.closed { grid-template-columns: var(--rail-w) 0 minmax(0, 1fr); }
  .layout.closed .sheet { display: none; }
  .map { grid-area: map; position: relative; min-height: 0; }
  .map ha-map { display: block; height: 100%; }
  .locate, .tiles { position: absolute; right: 12px; bottom: 28px; z-index: 1; width: 44px; height: 44px;
    border-radius: 50%; border: none; display: flex; align-items: center; justify-content: center;
    background: var(--card-background-color); color: var(--primary-color); box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3); }
  .tiles { bottom: 84px; }
  .tiles[hidden] { display: none; }
  .tiles.on { background: var(--primary-color); color: var(--text-primary-color, #fff); }

  /* Phone: map above a draggable bottom sheet, bottom tab bar */
  :host(.compact) .layout, :host(.compact) .layout.closed { grid-template-columns: minmax(0, 1fr);
    grid-template-rows: 1fr var(--sheet-h, 45%) calc(var(--nav-h) + var(--safe-area-inset-bottom, 0px)); grid-template-areas: "map" "sheet" "nav"; }
  :host(.compact) .layout:not(.dragging) { transition: grid-template-rows 0.2s ease; }
  :host(.compact) .layout.closed { grid-template-rows: 1fr 0 calc(var(--nav-h) + var(--safe-area-inset-bottom, 0px)); }
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
  .saved-toolbar { display: flex; align-items: center; gap: 6px; }
  .spacer { flex: 1; }
  .tree, .children { gap: 6px; }
  .children { margin-left: 18px; padding-left: 8px; border-left: 2px solid var(--divider-color); }
  .node-row { display: flex; align-items: center; gap: 6px; }
  .node-row.card { padding: 8px 10px; }
  .node-row.card.place { flex-direction: column; align-items: stretch; padding: 12px; gap: 8px; }
  .node-row.card.place.active { outline: 2px solid ${COLORS.activePlace}; }
  .folder-row { padding: 6px 4px; border-radius: 8px; }
  .folder-head { flex-direction: row; align-items: center; gap: 6px; }
  .folder-head ha-icon { color: var(--primary-color); }
  .rename { flex: 1; padding: 6px 8px; }
  .move { max-width: 34%; padding: 6px; font-size: 13px; }
  .leaf-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .drag-handle { display: flex; padding: 4px; cursor: grab; touch-action: none; color: var(--secondary-text-color); }
  .node.dragging > .node-row { opacity: 0.4; }
  .drop-before { box-shadow: inset 0 3px 0 var(--primary-color); }
  .drop-after { box-shadow: inset 0 -3px 0 var(--primary-color); }
  .drop-into { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.15); outline: 2px dashed var(--primary-color); }
  .icon-btn.danger { color: var(--error-color); }
  .danger-text { color: var(--error-color); }
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
  .live { display: flex; align-items: flex-start; gap: 6px; margin-top: 4px; font-size: 13px; }
  .live-tag { flex: none; padding: 0 6px; border-radius: 4px; font-size: 11px; font-weight: 700; line-height: 18px;
    color: #fff; background: var(--error-color, #db4437); }
  .live-rows { flex: 1; display: flex; flex-direction: column; gap: 2px; color: var(--error-color, #db4437); }
  .live-rows b { color: var(--primary-text-color); }
  .icon-btn.small { width: 24px; height: 24px; }
  .icon-btn.small ha-icon { --mdc-icon-size: 16px; }
  .badge { display: inline-block; padding: 1px 8px; border-radius: 10px; background: var(--line-color);
    color: #fff; font-weight: 600; font-size: 13px; }
`;

customElements.define("naver-map-panel", NaverMapPanel);
