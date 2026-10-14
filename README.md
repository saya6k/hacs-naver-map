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

> **Map-tile replacement is not supported.** This integration provides services and LLM tools only; it does not patch the HA frontend map.

## Features

- **`search_place`** — keyword place search, returns the top 5 results with coordinates, addresses, and map links.
- **`search_nearby`** — search around a center point (entity or coordinates) by category or keyword, ordered by distance, with a `distance` field on each result.
- **`geocode_address`** — convert an address into WGS84 coordinates, returning the best match with its jibun/road address, postal code, and a map link.
- **`get_directions`** — Naver Map route link + per-leg points + travel time / arrival time for car, transit, walk, and bicycle. Points are entities (person / device_tracker / zone / …) or coordinates.
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

The config flow takes two credential pairs. Only one entry is supported.

| Credential | Where to get it | Used for |
|---|---|---|
| **Client ID / Client Secret** | [Naver Developers](https://developers.naver.com/apps/) → Application → register with the **검색 (Search)** API | `search_place`, `search_nearby` |
| **API Key ID / API Key** | [NAVER Cloud Platform](https://console.ncloud.com/maps/application) → Maps → Application, with **Geocoding**, **Reverse Geocoding**, and **Directions 5** enabled | `geocode_address`, `search_nearby` (region lookup), `get_directions` (car) |

NCP Maps is a paid service with a monthly free quota; check the current pricing in the NCP console.

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

How it works: the Naver local search API takes no coordinates, so the center is reverse-geocoded to its district (e.g. `성남시 분당구 삼평동`), the keyword is searched within that district, and results outside `radius` are dropped. The search API returns at most 5 places per call, so a nearby search returns **up to 5** results — fewer when some fall outside the radius.

### `naver_map.geocode_address`

Convert an address into coordinates. Returns the single best match (raises an error if the address isn't found).

```yaml
action: naver_map.geocode_address
data:
  query: 경기도 성남시 분당구 불정로 6
response_variable: geo
# geo: latitude / longitude / address(jibun) / road_address / zone_no / map_url
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
response_variable: route
# route: route_url / mode / duration(s) / distance(m) / arrival_time / legs[]
```

See `custom_components/naver_map/services.yaml` for all fields.

## Assist support

The same four actions are also registered as an LLM tool API (`naver_map__search_place`, `naver_map__search_nearby`, `naver_map__geocode_address`, `naver_map__get_directions`), so an AI-backed Assist pipeline (e.g. Google Generative AI Conversation, OpenAI Conversation) can call them from natural language. Enable it in the conversation agent's options by selecting **Naver Map** under the exposed LLM APIs. Place and nearby-search results also render as visual cards on cards-capable Assist surfaces (e.g. voice-satellite dashboards).

MCP clients can also reach the API directly at `/api/mcp/naver_map` (requires an admin-scoped token), independent of any conversation agent's configured API list.

## Notes and limitations

- **Car travel time** comes from NCP Directions 5 (official). **Transit, walk, and bicycle** travel times come from Naver Map's undocumented internal route API, which may change or be blocked. On any failure `duration` / `distance` / `arrival_time` degrade to `null` while the route link (`route_url`) is always returned.
- **`mode: transit`** does not support waypoints and adds `transfers` and `fare` to the response.
- **`mode: bicycle` with waypoints** is link-only (`null` travel time).
- **No map-tile replacement** — see the note near the top.

## Development

A devcontainer is provided for testing against a real Home Assistant install. Open the folder in VS Code with the Dev Containers extension and run:

```bash
scripts/develop
```

HA binds port 8123 inside the container, whose hostname is `hacs-naver-map-dev` so it's distinguishable from any production HA on the host network. Run the lint + test suite with `scripts/test`.

## License

[MIT](LICENSE)
