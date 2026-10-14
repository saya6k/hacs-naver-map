"""geocode_address LLM tool."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import llm

from custom_components.naver_map.services import async_geocode_address

from .base_tool import BaseNaverTool
from .render import svg_card

_GEOCODE_ACCENT = "#a855f7"  # purple-500


class GeocodeAddressTool(BaseNaverTool):
    """Convert an address string to WGS84 coordinates."""

    name = "naver_map__geocode_address"
    title = "Geocode address"
    description = (
        "Convert a Korean address string to WGS84 coordinates, returning "
        "the best-match result's lot/road address, postal code, and a map "
        "link."
    )
    parameters = vol.Schema({vol.Required("query"): cv.string})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        result = await async_geocode_address(self.clients, tool_input.tool_args["query"])
        card = svg_card(
            result["address"],
            [
                ("도로명", result.get("road_address") or "-"),
                ("우편번호", result.get("zone_no") or "-"),
            ],
            accent=_GEOCODE_ACCENT,
        )
        return self.envelope(
            **result,
            featured_image=card,
            instruction="A card with the address is already shown; confirm it briefly.",
        )
