"""Constants for the Naver Map integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "naver_map"

# Display name for the llm.API registration. Kept here (component root) rather
# than in llm/const.py: the API shell (llm_registration.py) must not import
# anything from the llm/ package, or it would defeat HA's lazy platform
# loading (see llm_registration.py's module docstring).
API_NAME: Final = "Naver Map"

# Config entry keys for the NAVER Cloud Platform Maps credentials. The Naver
# Developers search credentials use HA's CONF_CLIENT_ID / CONF_CLIENT_SECRET.
CONF_NCP_KEY_ID: Final = "ncp_key_id"
CONF_NCP_KEY: Final = "ncp_key"

# Naver Developers Search API (headers X-Naver-Client-Id / X-Naver-Client-Secret).
LOCAL_SEARCH_URL: Final = "https://openapi.naver.com/v1/search/local.json"

# NAVER Cloud Platform Maps API (headers x-ncp-apigw-api-key-id / x-ncp-apigw-api-key).
GEOCODE_URL: Final = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"
REVERSE_GEOCODE_URL: Final = "https://maps.apigw.ntruss.com/map-reversegeocode/v2/gc"
DRIVING_URL: Final = "https://maps.apigw.ntruss.com/map-direction/v1/driving"

# Naver Map web URLs (no API key required, open map.naver.com pages)
MAP_SEARCH_LINK_BASE: Final = "https://map.naver.com/p/search"
DIRECTIONS_LINK_BASE: Final = "https://map.naver.com/p/directions"

# Naver Map internal route API (undocumented; needs Referer + browser UA, no API key).
# best-effort only: may change or block without notice, so ETA data degrades to null.
# pubtrans (not the web app's newer /transit) still carries per-path distance and fare.
TRANSIT_ROUTE_URL: Final = "https://map.naver.com/p/api/directions/pubtrans"
WALK_ROUTE_URL: Final = "https://map.naver.com/p/api/directions/walk"
BIKE_ROUTE_URL: Final = "https://map.naver.com/p/api/directions/bike"
# Naver Map internal place API (same headers): autocomplete yields place ids,
# the summary yields business hours, review counts, photos, and service flags.
# The full place search (allSearch) is CAPTCHA-gated and deliberately unused.
INSTANT_SEARCH_URL: Final = "https://map.naver.com/p/api/search/instant-search"
PLACE_SUMMARY_URL: Final = "https://map.naver.com/p/api/place/summary"
PLACE_LINK_BASE: Final = "https://map.naver.com/p/entry/place"
# Realtime arrivals (same headers): bus per stop id, subway per per-line station id.
BUS_ARRIVALS_URL: Final = "https://map.naver.com/p/api/pubtrans/realtime/bus/arrivals"
SUBWAY_ARRIVALS_URL: Final = "https://pts.map.naver.com/api/realtime/subways"
SUBWAY_ARRIVAL_COUNT: Final = 3  # trains per direction
ROUTE_API_HEADERS: Final = {
    "Referer": "https://map.naver.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Directions travel modes exposed to users
MODE_CAR: Final = "car"
MODE_TRANSIT: Final = "transit"
MODE_WALK: Final = "walk"
MODE_BICYCLE: Final = "bicycle"
DIRECTIONS_MODES: Final = (MODE_CAR, MODE_TRANSIT, MODE_WALK, MODE_BICYCLE)
# Mode token in the map.naver.com/p/directions URL path
DIRECTIONS_LINK_MODES: Final = {
    MODE_CAR: "car",
    MODE_TRANSIT: "transit",
    MODE_WALK: "walk",
    MODE_BICYCLE: "bike",
}

# Frontend user-data key under which the panel keeps each user's saved places
# (favorites and filed zones, in folders); read by the saved-places LLM tool.
SAVED_PLACES_KEY: Final = "naver_map_saved"

MAX_WAYPOINTS: Final = 5  # Directions 5 limit
MAX_SEARCH_RESULTS: Final = 5  # local.json `display` cap

# Nearby search (search_nearby): center point + category or keyword within a radius.
# local.json has no coordinate parameters, so the center is reverse-geocoded to a
# region name that prefixes the keyword, and results are filtered by distance.
DEFAULT_NEARBY_RADIUS: Final = 1000  # meters
MAX_NEARBY_RADIUS: Final = 20000  # meters
# Friendly category slugs exposed to users, mapped to the Korean keyword searched.
CATEGORY_KEYWORDS: Final = {
    "supermarket": "대형마트",
    "convenience_store": "편의점",
    "daycare": "어린이집",
    "school": "학교",
    "academy": "학원",
    "parking": "주차장",
    "gas_station": "주유소",
    "subway_station": "지하철역",
    "bank": "은행",
    "cultural_facility": "문화시설",
    "real_estate": "부동산",
    "public_institution": "공공기관",
    "tourist_attraction": "관광명소",
    "accommodation": "숙박",
    "restaurant": "맛집",
    "cafe": "카페",
    "hospital": "병원",
    "pharmacy": "약국",
}
