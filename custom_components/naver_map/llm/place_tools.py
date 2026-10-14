"""Place search LLM tools (search_place, search_nearby)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import llm

from custom_components.naver_map.const import CATEGORY_KEYWORDS, MAX_NEARBY_RADIUS
from custom_components.naver_map.services import (
    ATTR_CATEGORY,
    ATTR_CENTER,
    ATTR_QUERY,
    ATTR_RADIUS,
    async_search_nearby,
    async_search_place,
)

from .base_tool import BaseNaverTool
from .render import grid_results
from .schema import POINT_INPUT

# Naver green
_PLACE_ACCENT = "#03c75a"


def _place_card_items(
    results: list[dict[str, Any]],
) -> list[tuple[str, list[tuple[str, str]], dict[str, Any] | None]]:
    items: list[tuple[str, list[tuple[str, str]], dict[str, Any] | None]] = []
    for r in results:
        lines: list[tuple[str, str]] = [("주소", r.get("road_address") or r["address"])]
        if r.get("category_name"):
            lines.append(("분류", r["category_name"]))
        if "distance" in r:
            lines.append(("거리", f"{r['distance']}m"))
        extra = {"place_url": r.get("place_url"), "map_url": r.get("map_url")}
        items.append((r["place_name"], lines, extra))
    return items


class SearchPlaceTool(BaseNaverTool):
    """Keyword search anywhere on Naver Map (not centered on a point)."""

    name = "naver_map__search_place"
    title = "Search place"
    description = (
        "Search Naver Map for places by keyword, anywhere (not centered on a "
        "point). Returns up to 5 matches with coordinates, address, and a "
        "map link."
    )
    parameters = vol.Schema({vol.Required("query"): cv.string})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        results = await async_search_place(self.clients, tool_input.tool_args["query"])
        return self.envelope(
            places=results,
            results=grid_results(_place_card_items(results), accent=_PLACE_ACCENT),
            instruction=(
                "Cards with each place are already shown. Narrate briefly — "
                "name and address of the top match or two — don't repeat "
                "every field."
            ),
        )


class SearchNearbyTool(BaseNaverTool):
    """Category or keyword search within a radius of a center point."""

    name = "naver_map__search_nearby"
    title = "Search nearby"
    description = (
        "Search Naver Map for places of a category or keyword within a "
        "radius of a center point (an entity_id like a zone/person/"
        "device_tracker, or a latitude/longitude). Pass exactly one of "
        "category or query. Returns up to 10 matches ordered by distance."
    )
    parameters = vol.Schema(
        {
            vol.Required("center"): POINT_INPUT,
            vol.Optional("category"): vol.In(CATEGORY_KEYWORDS),
            vol.Optional("query"): cv.string,
            vol.Optional("radius"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=MAX_NEARBY_RADIUS)
            ),
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        args = tool_input.tool_args
        center, results = await async_search_nearby(
            hass,
            self.clients,
            {
                ATTR_CENTER: args.get("center"),
                ATTR_CATEGORY: args.get("category"),
                ATTR_QUERY: args.get("query"),
                ATTR_RADIUS: args.get("radius"),
            },
        )
        return self.envelope(
            center={
                "name": center.name,
                "latitude": center.latitude,
                "longitude": center.longitude,
            },
            places=results,
            results=grid_results(_place_card_items(results), accent=_PLACE_ACCENT),
            instruction=(
                "Cards with each nearby place are already shown. Mention "
                "name and distance for the closest match or two, briefly."
            ),
        )
