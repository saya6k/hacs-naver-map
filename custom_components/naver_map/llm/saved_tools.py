"""Saved places and place details LLM tools."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import llm

from custom_components.naver_map.saved import async_saved_places
from custom_components.naver_map.services import (
    ATTR_NEAR,
    ATTR_PLACE_ID,
    ATTR_QUERY,
    async_get_place_details,
)

from .base_tool import BaseNaverTool
from .render import grid_results
from .schema import POINT_INPUT

_PLACE_ACCENT = "#03c75a"


class GetSavedPlacesTool(BaseNaverTool):
    """The requesting user's saved places from the Naver Map panel."""

    name = "naver_map__get_saved_places"
    title = "Get saved places"
    description = (
        "List the user's saved places (favorites and filed zones from the Naver "
        "Map panel), each with its folder, latitude/longitude, and, when known, "
        "address, Naver place_id, or zone entity_id. Optionally filter by a "
        "query that matches a place or folder name. Use the coordinates or "
        "entity_id with naver_map__get_directions, and place_id with "
        "naver_map__get_place_details."
    )
    parameters = vol.Schema({vol.Optional("query"): cv.string})
    # Reads Home Assistant's own data; no Naver call.
    annotations = llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        user_id = llm_context.context.user_id if llm_context.context else None
        places = await async_saved_places(hass, user_id)
        if query := (tool_input.tool_args.get("query") or "").strip():
            places = [
                place
                for place in places
                if query in (place["name"] or "") or query in (place["folder"] or "")
            ]
        if not user_id:
            instruction = (
                "Saved places are per user and this request has no signed-in "
                "user (e.g. a voice satellite), so none are available."
            )
        elif not places:
            instruction = "No saved place matched; say so."
        else:
            instruction = "Pick the place the user means; don't read out every field."
        return self.envelope(places=places, instruction=instruction)


class GetPlaceDetailsTool(BaseNaverTool):
    """Naver Place summary of a place by place_id, or by name near a point."""

    name = "naver_map__get_place_details"
    title = "Get place details"
    description = (
        "Get a place's Naver Place summary: business-hours status, visitor and "
        "blog review counts, photos, booking/order/delivery availability, and a "
        "Naver Map link. Pass place_id (e.g. from naver_map__get_saved_places "
        "or naver_map__search_nearby), or query with an optional near point "
        "(entity_id or latitude/longitude) to pick the right branch."
    )
    parameters = vol.Schema(
        {
            vol.Optional("place_id"): cv.string,
            vol.Optional("query"): cv.string,
            vol.Optional("near"): POINT_INPUT,
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        args = tool_input.tool_args
        place = await async_get_place_details(
            hass,
            self.clients,
            {
                ATTR_PLACE_ID: args.get("place_id"),
                ATTR_QUERY: args.get("query"),
                ATTR_NEAR: args.get("near"),
            },
        )
        lines = [("주소", place["road_address"] or place["address"] or "")]
        if place["business_hours"]:
            lines.append(("영업", place["business_hours"]))
        if place["visitor_review_count"] is not None:
            lines.append(("리뷰", f"방문자 {place['visitor_review_count']:,}"))
        card = (place["place_name"], lines, {"place_url": place["place_url"]})
        return self.envelope(
            place=place,
            results=grid_results([card], accent=_PLACE_ACCENT),
            instruction=(
                "A card with the place is already shown. Mention the business-"
                "hours status and review counts briefly."
            ),
        )
