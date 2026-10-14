"""Constants for the naver_map LLM API tools."""

from __future__ import annotations

SOURCE = "naver_map"

API_PROMPT = (
    "You can use these tools to search places and get directions in Korea via "
    "Naver Map. Use naver_map__search_place for a keyword search, ranked "
    "around near (default home; pass the user's person when they ask for "
    "something near them). Use naver_map__search_nearby to search around a specific center "
    "point (an entity_id like a zone/person/device_tracker, or a "
    "latitude/longitude), passing exactly one of category or query. Use "
    "naver_map__geocode_address to convert an address string to coordinates. "
    "Use naver_map__get_directions for a route between an origin and "
    "destination (each an entity_id or latitude/longitude), with optional "
    "waypoints in order; pick mode 'car', 'transit' (public transit), 'walk', "
    "or 'bicycle'. duration/distance/arrival_time may be null when the "
    "best-effort route lookup fails — the route_url link is still valid. "
    "When the user refers to one of their own places (\"my favorite cafe\", "
    "a folder name), call naver_map__get_saved_places first and use its "
    "coordinates or entity_id. Use naver_map__get_place_details (by place_id, "
    "or query near a point) for opening status, reviews, and photos. "
    "Cards are already shown for search/nearby results, so keep narration "
    "brief."
)
