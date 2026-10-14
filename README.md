# Naver Map — Home Assistant Integration

> Requires Home Assistant **2026.10.0.dev202609290227 or later**. LLM tools return `llm.ToolResult`, preserving existing response fields in `data`.

[![Built with Claude Code](https://img.shields.io/badge/Built%20with%20Claude%20Code-D97757?style=for-the-badge&logo=claude&logoColor=white)](https://claude.ai/code)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-41BDF5?style=for-the-badge&logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=white)](https://hacs.xyz/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Shell](https://img.shields.io/badge/Shell-4EAA25?style=for-the-badge&logo=gnubash&logoColor=white)](https://www.gnu.org/software/bash/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/saya6k)

Naver Map for Home Assistant — **place search**, **nearby search**, **geocoding**, and **directions** (Naver Map link plus travel time) built on the Naver Search API, NAVER Cloud Platform Maps, and Naver Map's web/internal APIs. For Korean users.

> **Map-tile replacement is not supported.** The route panel draws on Home Assistant's built-in map (OpenStreetMap tiles); the integration does not replace tiles or patch the HA frontend map.

## Features

- **`search_place`** — keyword place search, returns the top 5 results with coordinates, addresses, and map links.
- **`search_nearby`** — search around a center point (entity or coordinates) by category or keyword, ordered by distance, with a `distance` field (and the Naver Place `place_id` when available) on each result.
- **`geocode_address`** — convert an address into WGS84 coordinates, returning the best match with its jibun/road address, postal code, and a map link.
- **`get_place_details`** — a place's Naver Place summary: business-hours status, review counts, photos, booking/order availability, and a link to the place.
- **`get_transit_arrivals`** — realtime arrivals at a bus stop or subway station (next vehicles per line, remaining time and stops).
- **`get_directions`** — Naver Map route link + per-leg points + travel time / arrival time for car, transit, walk, and bicycle. Points are entities (person / device_tracker / zone / …) or coordinates.
- **Route panel** — a **Naver Map** sidebar panel that searches places, draws the route line on Home Assistant's built-in map, and shows travel time, distance, and (transit) transfers/fare.
- **Assist / AI tool support** — the same actions are exposed as an LLM tool API for AI-backed conversation agents, with visual result cards.
- **Korean and English** UI translations.

## Installation (HACS)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=saya6k&repository=hacs-naver-map&category=integration)

1. HACS → Integrations → ⋮ → **Custom repositories** — add this repo URL with category **Integration**.
2. Install **Naver Map**.
3. Restart Home Assistant.
4. Settings → Devices & Services → **Add integration** → search "Naver Map".
5. Enter both credential pairs (see [Configuration](#configuration)). Each pair is validated with one call.

## Manual installation

Copy `custom_components/naver_map/` into your HA config's `custom_components/` folder and restart.

## Configuration

The config flow asks for the NAVER Cloud Platform keys (required) and, optionally, Naver Developers search keys. Only one entry is supported; change the keys later with **Reconfigure**.

| Credential | Where to get it | Used for |
|---|---|---|
| **API Key ID / API Key** (required) | [NAVER Cloud Platform](https://console.ncloud.com/maps/application) → Maps → Application, with **Geocoding**, **Reverse Geocoding**, and **Directions 5** enabled | `geocode_address`, `get_directions` (car), region lookup for the `search_nearby` fallback |
| **Client ID / Client Secret** (optional) | [Naver Developers](https://developers.naver.com/apps/) → Application → register with the **검색 (Search)** API | Official keyword search for `search_place`, and the `search_nearby` fallback |

**Without the search keys**, keyword and nearby search rely only on Naver Map's unofficial web autocomplete: if Naver blocks or changes it, both stop, with no official search API to fall back on, and keyword results are ranked around your home rather than nationwide. Everything else works the same. The setup form says this too.

NCP Maps is a paid service with a monthly free quota (e.g. Directions 5: 60,000 and Geocoding: 3,000,000 calls a month at the time of writing); check the current pricing in the NCP console. If car directions or geocoding fail, check the [NCP service status](https://www.ncloud.com/serviceStatus/).

## Route panel

Adding the integration puts a **Naver Map** entry in the sidebar (all users, not only admins). It has three tabs.

The panel opens on the map alone: tap a tab to open it, and tap the open tab again to fold it away (the map keeps what it shows, e.g. a route line). On phone widths the tab opens as a bottom sheet just tall enough for its controls, grows when results arrive, and can be dragged taller, or down to fold it; on tablets and desktops it opens as a side panel next to the map.

**Places** — search a place, or tap a category (restaurants, cafes, convenience stores, pharmacies, …) to list places within 1 km of you (your person's location, else home); every result is marked on the map with its distance. Pick a result to zoom to it and see its Naver Place summary (photos, opening status, review counts, booking/order availability), open it in Naver Map, or send it to the **Directions** tab with **Origin** / **Destination**.

**Saved** — your own favorites, kept per Home Assistant user (synced across your devices; no administrator needed): tap **Save** on a search result; tap a favorite for its Naver Place summary, or use it as an origin or destination (favorites are also listed in the Directions tab's point picker). Home Assistant zones appear in the same list. Tap **Edit** to make folders, drag places (by ≡) into folders or reorder them, move them with the folder menu, and rename or delete them. Renaming or deleting a zone changes it for everyone, so only administrators can; they can also turn a favorite into a passive zone (ignored by presence detection) for automations and `get_directions`.

**Directions**

1. Set the **origin** and **destination**: search a place and pick a result, choose a person / zone / device_tracker entity, or press **Pick on map** and click the map. The swap button exchanges them.
2. Choose **Car**, **Transit**, **Walk**, or **Bicycle**.
3. The route line is drawn on the map with the travel time, distance, and arrival time (plus transfers and fare for transit), and a link opens the same route in Naver Map. Drag a marker to adjust a point; the route is looked up again after a short pause.
4. **Transit** lists every route Naver suggests, marked **Best**, **Fastest**, **Fewest transfers**, or **Least walking**, with a bus / subway filter, a sort, times, transfers, walking time, fare, and a line-colored bar of the rides. The selected route is drawn on the map and shows each ride (line, direction, boarding and alighting stops, stop count, times, and **live arrivals** at the boarding stop, with a refresh button) and walk.
5. **Route details** for car, walk, and bicycle list the turn-by-turn steps.

The map opens at your current location (a blue dot) when the browser shares it — this needs Home Assistant over HTTPS and location permission; the Android companion app's web view does not share it. Otherwise it opens at your person's location, else home. The location button re-centers the map, and the category shortcuts search around the same point.

On phones and tablets (including the Home Assistant companion apps) the Naver Map links open the Naver Map app; on Android a missing app opens the Play Store. On desktop they open map.naver.com.

When the route line can't be read, the panel connects the points with straight segments. The panel text follows the user's language (Korean or English).

## Services

Every service returns a response, so capture it with `response_variable`.

### `naver_map.search_place`

```yaml
action: naver_map.search_place
data:
  query: 네이버 그린팩토리
response_variable: found
# found.results[]: place_name / latitude / longitude / address / road_address /
#                  map_url / category_name / place_url (homepage, when present)
```

### `naver_map.search_nearby`

Search around a center by a category **or** a keyword (exactly one). Each result includes `distance` (meters).

```yaml
# Cafes within 1 km of home
action: naver_map.search_nearby
data:
  center: zone.home
  category: cafe       # pick from the list below
  radius: 1000
response_variable: cafes
```

```yaml
# Keyword search around coordinates
action: naver_map.search_nearby
data:
  center:
    latitude: 37.5665
    longitude: 126.978
  query: 스타벅스
  radius: 500
response_variable: nearby
```

Categories (18 total): `cafe`, `restaurant`, `convenience_store`, `supermarket`, `hospital`, `pharmacy`, `subway_station`, `bank`, `gas_station`, `parking`, `academy`, `school`, `daycare`, `cultural_facility`, `real_estate`, `public_institution`, `tourist_attraction`, `accommodation`. In the UI these show as localized labels (카페, 맛집, …); each is searched as a Korean keyword.

How it works: Naver Map's (undocumented) autocomplete is asked for the keyword around the center's coordinates, which yields **up to 10** places with their `place_id`; results outside `radius` are dropped. If that lookup fails, it falls back to the official local search API: that API takes no coordinates, so the center is reverse-geocoded to its district (e.g. `성남시 분당구 삼평동`) and the keyword is searched within it, returning **up to 5** results.

### `naver_map.geocode_address`

Convert an address into coordinates. Returns the single best match (raises an error if the address isn't found).

```yaml
action: naver_map.geocode_address
data:
  query: 경기도 성남시 분당구 불정로 6
response_variable: geo
# geo: latitude / longitude / address(jibun) / road_address / zone_no / map_url
```

### `naver_map.get_place_details`

Look up a place's Naver Place summary by name (near a point, to pick the right branch) or by place ID. Best effort: it uses Naver Map's undocumented web API.

```yaml
action: naver_map.get_place_details
data:
  query: 스타벅스 강남R점            # … or place_id: "1086067689"
  near:                             # optional; defaults to home
    latitude: 37.4979
    longitude: 127.0276
response_variable: place
# place: place_id / place_name / category / address / road_address / latitude / longitude /
#        business_hours (status line) / visitor_review_count / blog_review_count / images[] /
#        booking / order / delivery / naver_pay / place_url
```

### `naver_map.get_transit_arrivals`

Realtime arrivals at a bus stop or a subway station (station IDs are per line). Take the IDs from a `get_directions` transit step (`stop_id`, `route_ids`, `way`). Best effort: it uses Naver Map's undocumented web API.

```yaml
action: naver_map.get_transit_arrivals
data:
  type: bus                         # bus | subway
  stop_id: "106041"
  route_ids: ["6025"]               # optional: only these lines
  # direction: up                   # subway only: up | down
response_variable: realtime
# realtime.arrivals[]: route_id / line / color / direction / running / (subway) way /
#   vehicles[]: arrival_time / remaining_time(s) / (bus) remaining_stops / congestion /
#               low_floor / (subway) headsign / express / last
```

### `naver_map.get_directions`

```yaml
action: naver_map.get_directions
data:
  origin: person.me                 # an entity …
  destination:                      # … or coordinates
    latitude: 37.3595
    longitude: 127.1052
  waypoints:                        # optional, up to 5
    - zone.office
  mode: car                         # car | transit | walk | bicycle
  include_geometry: false           # true adds the route line as geometry
  include_steps: false              # true adds turn-by-turn / per-ride steps
  include_alternatives: false       # transit: true lists every suggested route
response_variable: route
# route: route_url / mode / duration(s) / distance(m) / arrival_time / legs[]
#        (+ geometry: [[latitude, longitude], …] or null with include_geometry)
#        (+ steps: [{instruction, distance, duration, …}] or null with include_steps;
#         transit steps add type, lines, color, headsign, from, to, stops, times,
#         and stop_id / route_ids / way for get_transit_arrivals)
#        (+ alternatives (transit): [{duration, distance, transfers, fare, walking_duration,
#         departure_time, arrival_time, vehicle_types, labels, …}] with include_alternatives)
```

See `custom_components/naver_map/services.yaml` for all fields.

## Assist support

The same actions are also registered as an LLM tool API (`naver_map__search_place`, `naver_map__search_nearby`, `naver_map__geocode_address`, `naver_map__get_directions`, `naver_map__get_place_details`, plus `naver_map__get_saved_places` for the requesting user's saved places from the panel — so "how long to my favorite cafe?" works), so an AI-backed Assist pipeline (e.g. Google Generative AI Conversation, OpenAI Conversation) can call them from natural language. Enable it in the conversation agent's options by selecting **Naver Map** under the exposed LLM APIs. Place and nearby-search results also render as visual cards on cards-capable Assist surfaces (e.g. voice-satellite dashboards).

Saved places are per Home Assistant user, so `naver_map__get_saved_places` returns nothing for requests without a signed-in user, such as voice satellites; zones still work there as entities.

MCP clients can also reach the API directly at `/api/mcp/naver_map` (requires an admin-scoped token), independent of any conversation agent's configured API list.

## Notes and limitations

- **Car travel time** comes from NCP Directions 5 (official). **Transit, walk, and bicycle** travel times come from Naver Map's undocumented internal route API, which may change or be blocked. On any failure `duration` / `distance` / `arrival_time` degrade to `null` while the route link (`route_url`) is always returned.
- **Place details** come from Naver Map's undocumented web API (its full place search is CAPTCHA-protected and not used). Naver throttles bursts, so summaries are cached for an hour; the menu, full opening hours, phone number, and review text are not available.
- **`mode: transit`** does not support waypoints and adds `transfers` and `fare` to the response.
- **`mode: bicycle` with waypoints** is link-only (`null` travel time).
- **Route geometry and steps** come from the same lookups as the travel time, so they share its limits and degrade to `null` independently.
- **Route panel**: every route change in car mode calls Directions 5, a paid NCP API; marker drags are debounced, and nothing is looked up automatically. The panel loads Home Assistant's map component through frontend internals when its URL is opened directly, so a frontend update can break it; it then shows a notice instead of the map.
- **No map-tile replacement** — see the note near the top.

## Development

A devcontainer is provided for testing against a real Home Assistant install. Open the folder in VS Code with the Dev Containers extension and run:

```bash
scripts/develop
```

HA binds port 8123 inside the container, whose hostname is `hacs-naver-map-dev` so it's distinguishable from any production HA on the host network. Run the lint + test suite with `scripts/test`.

## License

[MIT](LICENSE)
