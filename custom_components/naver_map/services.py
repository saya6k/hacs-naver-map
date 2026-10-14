"""Service handlers for the Naver Map integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from itertools import pairwise
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util
from homeassistant.util.location import distance as geo_distance

from .api import (
    NaverApiError,
    NaverMapRouteApi,
    NaverSearchApi,
    NcpMapsApi,
    RouteResult,
    TransitResult,
)
from .const import (
    CATEGORY_KEYWORDS,
    DEFAULT_NEARBY_RADIUS,
    DIRECTIONS_MODES,
    DOMAIN,
    MAX_NEARBY_RADIUS,
    MAX_WAYPOINTS,
    MODE_BICYCLE,
    MODE_CAR,
    MODE_TRANSIT,
    MODE_WALK,
)
from .formatters import address_result, place_result, route_url
from .helpers import ResolvedPoint, resolve_point, resolve_waypoint

SERVICE_SEARCH_PLACE = "search_place"
SERVICE_SEARCH_NEARBY = "search_nearby"
SERVICE_GEOCODE_ADDRESS = "geocode_address"
SERVICE_GET_DIRECTIONS = "get_directions"

ATTR_QUERY = "query"
ATTR_CENTER = "center"
ATTR_CATEGORY = "category"
ATTR_RADIUS = "radius"
ATTR_ORIGIN = "origin"
ATTR_DESTINATION = "destination"
ATTR_WAYPOINTS = "waypoints"
ATTR_MODE = "mode"
ATTR_INCLUDE_GEOMETRY = "include_geometry"
ATTR_INCLUDE_STEPS = "include_steps"

NEARBY_CENTER_ROLE = "중심 지점"

_API_ERRORS = (NaverApiError, aiohttp.ClientError, TimeoutError)

SEARCH_PLACE_SCHEMA = vol.Schema({vol.Required(ATTR_QUERY): cv.string})
GEOCODE_ADDRESS_SCHEMA = vol.Schema({vol.Required(ATTR_QUERY): cv.string})

# A point is an entity_id (resolved from its lat/lon attributes) or a location mapping.
POINT_INPUT = vol.Any(cv.entity_id, dict)

SEARCH_NEARBY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CENTER): POINT_INPUT,
        vol.Optional(ATTR_CATEGORY): vol.In(CATEGORY_KEYWORDS),
        vol.Optional(ATTR_QUERY): cv.string,
        vol.Optional(ATTR_RADIUS, default=DEFAULT_NEARBY_RADIUS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_NEARBY_RADIUS)
        ),
    }
)

GET_DIRECTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ORIGIN): POINT_INPUT,
        vol.Optional(ATTR_DESTINATION): POINT_INPUT,
        vol.Optional(ATTR_WAYPOINTS, default=list): [POINT_INPUT],
        vol.Optional(ATTR_MODE, default=MODE_CAR): vol.In(DIRECTIONS_MODES),
        vol.Optional(ATTR_INCLUDE_GEOMETRY, default=False): cv.boolean,
        vol.Optional(ATTR_INCLUDE_STEPS, default=False): cv.boolean,
    }
)


@dataclass(slots=True, frozen=True)
class NaverClients:
    """The API clients one config entry builds and the services/LLM tools share."""

    search: NaverSearchApi
    maps: NcpMapsApi
    route: NaverMapRouteApi


def _api_error() -> HomeAssistantError:
    return HomeAssistantError(translation_domain=DOMAIN, translation_key="api_error")


def _no_results(query: str) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="no_results",
        translation_placeholders={"query": query},
    )


async def async_search_place(clients: NaverClients, query: str) -> list[dict[str, Any]]:
    """Keyword-search places anywhere and return place results."""
    try:
        items = await clients.search.async_search_local(query)
    except _API_ERRORS as err:
        raise _api_error() from err
    if not items:
        raise _no_results(query)
    return [place_result(item) for item in items]


async def async_search_nearby(
    hass: HomeAssistant, clients: NaverClients, data: Mapping[str, Any]
) -> tuple[ResolvedPoint, list[dict[str, Any]]]:
    """Search a category or keyword around a center and return (center, results).

    local.json takes no coordinates, so the center is reverse-geocoded to a
    region name that prefixes the keyword; results outside ``radius`` are
    dropped and the rest ordered by distance. ``data`` holds ``ATTR_CENTER``,
    exactly one of ``ATTR_CATEGORY``/``ATTR_QUERY``, and optionally ``ATTR_RADIUS``.
    """
    category = data.get(ATTR_CATEGORY)
    query = data.get(ATTR_QUERY)
    if bool(category) == bool(query):
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="nearby_input")
    center = resolve_point(hass, role=NEARBY_CENTER_ROLE, value=data.get(ATTR_CENTER))
    radius = data.get(ATTR_RADIUS) or DEFAULT_NEARBY_RADIUS
    keyword = CATEGORY_KEYWORDS[category] if category else query
    try:
        region = await clients.maps.async_region_name(center.longitude, center.latitude)
        items = await clients.search.async_search_local(
            f"{region} {keyword}" if region else keyword
        )
    except _API_ERRORS as err:
        raise _api_error() from err
    results = []
    for item in items:
        result = place_result(item)
        meters = geo_distance(
            center.latitude, center.longitude, result["latitude"], result["longitude"]
        )
        if meters is not None and meters <= radius:
            result["distance"] = round(meters)
            results.append(result)
    if not results:
        raise _no_results(keyword)
    results.sort(key=lambda r: r["distance"])
    return center, results


async def async_geocode_address(clients: NaverClients, query: str) -> dict[str, Any]:
    """Geocode an address string to the best-match coordinate result."""
    try:
        items = await clients.maps.async_geocode(query)
    except _API_ERRORS as err:
        raise _api_error() from err
    if not items:
        raise _no_results(query)
    return address_result(items[0])


async def async_get_directions(
    hass: HomeAssistant, clients: NaverClients, data: Mapping[str, Any]
) -> dict[str, Any]:
    """Resolve origin/destination/waypoints and build a directions response.

    ``data`` holds ``ATTR_ORIGIN``/``ATTR_DESTINATION``/``ATTR_WAYPOINTS``/
    ``ATTR_MODE`` (waypoints and mode must already have their defaults
    applied). Shared by the get_directions service and the get_directions
    LLM tool. ``ATTR_INCLUDE_GEOMETRY`` adds the route line as ``geometry``
    ([lat, lng] lists) and ``ATTR_INCLUDE_STEPS`` the turn-by-turn or per-ride
    ``steps`` (each null when unavailable); the LLM tool sets neither, since
    both would flood the model context.
    """
    waypoints = data[ATTR_WAYPOINTS]
    mode = data[ATTR_MODE]
    if len(waypoints) > MAX_WAYPOINTS:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="too_many_waypoints",
            translation_placeholders={
                "count": str(len(waypoints)),
                "max": str(MAX_WAYPOINTS),
            },
        )
    if mode == MODE_TRANSIT and waypoints:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="transit_no_waypoints"
        )
    points = [resolve_point(hass, role="출발지", value=data.get(ATTR_ORIGIN))]
    points.extend(
        resolve_waypoint(hass, value, index=index)
        for index, value in enumerate(waypoints, start=1)
    )
    points.append(resolve_point(hass, role="도착지", value=data.get(ATTR_DESTINATION)))
    route: RouteResult | TransitResult | None = None
    if mode == MODE_CAR:
        route = await clients.maps.async_get_driving_route(points[0], points[-1], points[1:-1])
    elif mode == MODE_TRANSIT:
        route = await clients.route.async_get_transit_route(points[0], points[-1])
    elif mode == MODE_WALK:
        route = await clients.route.async_get_walk_route(points)
    elif mode == MODE_BICYCLE and not waypoints:
        # The bike endpoint's waypoint format is unknown, so only direct routes get an ETA.
        route = await clients.route.async_get_bike_route(points[0], points[-1])
    legs = [
        {
            "from": a.name,
            "from_latitude": a.latitude,
            "from_longitude": a.longitude,
            "to": b.name,
            "to_latitude": b.latitude,
            "to_longitude": b.longitude,
        }
        for a, b in pairwise(points)
    ]
    response: dict[str, Any] = {
        "route_url": route_url(points, mode),
        "mode": mode,
        "duration": route.duration if route else None,
        "distance": route.distance if route else None,
        "arrival_time": (
            (dt_util.now() + timedelta(seconds=route.duration)).isoformat() if route else None
        ),
        "legs": legs,
    }
    if isinstance(route, TransitResult):
        response["transfers"] = route.transfers
        response["fare"] = route.fare
    if data.get(ATTR_INCLUDE_GEOMETRY):
        response["geometry"] = (
            [list(point) for point in route.path] if route and route.path else None
        )
    if data.get(ATTR_INCLUDE_STEPS):
        response["steps"] = route.steps if route else None
    return response


async def _async_handle_search_place(clients: NaverClients, call: ServiceCall) -> ServiceResponse:
    return {"results": await async_search_place(clients, call.data[ATTR_QUERY])}


async def _async_handle_search_nearby(
    hass: HomeAssistant, clients: NaverClients, call: ServiceCall
) -> ServiceResponse:
    _center, results = await async_search_nearby(hass, clients, call.data)
    return {"results": results}


async def _async_handle_geocode_address(
    clients: NaverClients, call: ServiceCall
) -> ServiceResponse:
    return await async_geocode_address(clients, call.data[ATTR_QUERY])


async def _async_handle_get_directions(
    hass: HomeAssistant, clients: NaverClients, call: ServiceCall
) -> ServiceResponse:
    return await async_get_directions(hass, clients, call.data)


@callback
def async_setup_services(hass: HomeAssistant, clients: NaverClients) -> None:
    """Register the naver_map services against the given API clients."""
    for service, handler, schema in (
        (SERVICE_SEARCH_PLACE, partial(_async_handle_search_place, clients), SEARCH_PLACE_SCHEMA),
        (
            SERVICE_SEARCH_NEARBY,
            partial(_async_handle_search_nearby, hass, clients),
            SEARCH_NEARBY_SCHEMA,
        ),
        (
            SERVICE_GEOCODE_ADDRESS,
            partial(_async_handle_geocode_address, clients),
            GEOCODE_ADDRESS_SCHEMA,
        ),
        (
            SERVICE_GET_DIRECTIONS,
            partial(_async_handle_get_directions, hass, clients),
            GET_DIRECTIONS_SCHEMA,
        ),
    ):
        hass.services.async_register(
            DOMAIN, service, handler, schema=schema, supports_response=SupportsResponse.ONLY
        )


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    """Remove the naver_map services."""
    hass.services.async_remove(DOMAIN, SERVICE_SEARCH_PLACE)
    hass.services.async_remove(DOMAIN, SERVICE_SEARCH_NEARBY)
    hass.services.async_remove(DOMAIN, SERVICE_GEOCODE_ADDRESS)
    hass.services.async_remove(DOMAIN, SERVICE_GET_DIRECTIONS)
