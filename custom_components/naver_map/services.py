"""Service handlers for the Naver Map integration."""

from __future__ import annotations

import logging
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
    NaverPlaceApi,
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
    MAX_SEARCH_RESULTS,
    MAX_WAYPOINTS,
    MODE_BICYCLE,
    MODE_CAR,
    MODE_TRANSIT,
    MODE_WALK,
)
from .formatters import (
    address_result,
    bus_arrival_result,
    instant_place_result,
    place_details_result,
    place_result,
    route_url,
    subway_arrival_results,
)
from .helpers import ResolvedPoint, resolve_point, resolve_waypoint

SERVICE_SEARCH_PLACE = "search_place"
SERVICE_SEARCH_NEARBY = "search_nearby"
SERVICE_GEOCODE_ADDRESS = "geocode_address"
SERVICE_GET_DIRECTIONS = "get_directions"
SERVICE_GET_PLACE_DETAILS = "get_place_details"
SERVICE_GET_TRANSIT_ARRIVALS = "get_transit_arrivals"

ATTR_QUERY = "query"
ATTR_CENTER = "center"
ATTR_CATEGORY = "category"
ATTR_RADIUS = "radius"
ATTR_ORIGIN = "origin"
ATTR_DESTINATION = "destination"
ATTR_WAYPOINTS = "waypoints"
ATTR_MODE = "mode"
ATTR_PLACE_ID = "place_id"
ATTR_NEAR = "near"
ATTR_TYPE = "type"
ATTR_STOP_ID = "stop_id"
ATTR_ROUTE_IDS = "route_ids"
ATTR_DIRECTION = "direction"
TRANSIT_BUS = "bus"
TRANSIT_SUBWAY = "subway"
ATTR_INCLUDE_GEOMETRY = "include_geometry"
ATTR_INCLUDE_STEPS = "include_steps"
ATTR_INCLUDE_ALTERNATIVES = "include_alternatives"

NEARBY_CENTER_ROLE = "중심 지점"
NEAR_ROLE = "기준 지점"

_LOGGER = logging.getLogger(__name__)

_API_ERRORS = (NaverApiError, aiohttp.ClientError, TimeoutError)
# The place endpoints are undocumented: an unexpected (e.g. CAPTCHA-gated) answer
# shows up as a missing key or bad value rather than an HTTP error.
_PLACE_ERRORS = (*_API_ERRORS, KeyError, IndexError, TypeError, ValueError)

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

GET_PLACE_DETAILS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_PLACE_ID): cv.string,
        vol.Optional(ATTR_QUERY): cv.string,
        vol.Optional(ATTR_NEAR): POINT_INPUT,
    }
)

GET_TRANSIT_ARRIVALS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TYPE): vol.In([TRANSIT_BUS, TRANSIT_SUBWAY]),
        vol.Required(ATTR_STOP_ID): vol.Coerce(str),
        vol.Optional(ATTR_ROUTE_IDS): vol.All(cv.ensure_list, [vol.Coerce(str)]),
        vol.Optional(ATTR_DIRECTION): vol.In(["up", "down"]),
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
        vol.Optional(ATTR_INCLUDE_ALTERNATIVES, default=False): cv.boolean,
    }
)


@dataclass(slots=True, frozen=True)
class NaverClients:
    """The API clients one config entry builds and the services/LLM tools share."""

    search: NaverSearchApi | None  # None without the optional search keys
    maps: NcpMapsApi
    route: NaverMapRouteApi
    place: NaverPlaceApi


def _api_error() -> HomeAssistantError:
    return HomeAssistantError(translation_domain=DOMAIN, translation_key="api_error")


def _no_results(query: str) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="no_results",
        translation_placeholders={"query": query},
    )


async def async_search_place(
    hass: HomeAssistant, clients: NaverClients, query: str
) -> list[dict[str, Any]]:
    """Keyword-search places and return place results.

    With the search keys this is the official local.json search. Without them
    it is Naver Map's (unofficial) autocomplete, ranked around home.
    """
    if clients.search is None:
        try:
            places = await clients.place.async_instant_search(
                query, hass.config.latitude, hass.config.longitude
            )
        except _PLACE_ERRORS as err:
            _LOGGER.warning("Naver place autocomplete failed (no search keys): %r", err)
            raise _api_error() from err
        if not places:
            raise _no_results(query)
        return [instant_place_result(place) for place in places[:MAX_SEARCH_RESULTS]]
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

    Naver Map's autocomplete takes the center's coordinates and returns up to
    10 nearby places with their place ids. If that undocumented endpoint fails,
    the official local.json search is used instead: it takes no coordinates, so
    the center is reverse-geocoded to a region name that prefixes the keyword.
    Either way results outside ``radius`` are dropped and the rest ordered by
    distance. ``data`` holds ``ATTR_CENTER``, exactly one of
    ``ATTR_CATEGORY``/``ATTR_QUERY``, and optionally ``ATTR_RADIUS``.
    """
    category = data.get(ATTR_CATEGORY)
    query = data.get(ATTR_QUERY)
    if bool(category) == bool(query):
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="nearby_input")
    center = resolve_point(hass, role=NEARBY_CENTER_ROLE, value=data.get(ATTR_CENTER))
    radius = data.get(ATTR_RADIUS) or DEFAULT_NEARBY_RADIUS
    keyword = CATEGORY_KEYWORDS[category] if category else query
    try:
        places = await clients.place.async_instant_search(
            keyword, center.latitude, center.longitude
        )
        candidates = [instant_place_result(place) for place in places]
    except _PLACE_ERRORS as err:
        if clients.search is None:
            _LOGGER.warning("Naver nearby autocomplete failed (no search keys): %r", err)
            raise _api_error() from err
        _LOGGER.warning("Naver nearby autocomplete failed, using local search: %r", err)
        try:
            region = await clients.maps.async_region_name(center.longitude, center.latitude)
            items = await clients.search.async_search_local(
                f"{region} {keyword}" if region else keyword
            )
        except _API_ERRORS as api_err:
            raise _api_error() from api_err
        candidates = [place_result(item) for item in items]
    results = []
    for result in candidates:
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


def _pick_place(places: list[dict[str, Any]], query: str) -> dict[str, Any]:
    """The nearest exactly named place, else Naver's first suggestion."""
    wanted = query.replace(" ", "")
    exact = [place for place in places if place.get("title", "").replace(" ", "") == wanted]
    if exact:
        return min(exact, key=lambda place: float(place.get("dist", float("inf"))))
    return places[0]


async def async_get_place_details(
    hass: HomeAssistant, clients: NaverClients, data: Mapping[str, Any]
) -> dict[str, Any]:
    """Look up a place's Naver Place summary by place_id, or by name near a point.

    ``data`` holds exactly one of ``ATTR_PLACE_ID``/``ATTR_QUERY``; a query is
    autocompleted around ``ATTR_NEAR`` (an entity or location), defaulting to
    the home location.
    """
    place_id = data.get(ATTR_PLACE_ID)
    query = data.get(ATTR_QUERY)
    if bool(place_id) == bool(query):
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="place_input")
    if data.get(ATTR_NEAR):
        near = resolve_point(hass, role=NEAR_ROLE, value=data[ATTR_NEAR])
        latitude, longitude = near.latitude, near.longitude
    else:
        latitude, longitude = hass.config.latitude, hass.config.longitude
    try:
        if query:
            places = await clients.place.async_instant_search(query, latitude, longitude)
            if not places:
                raise _no_results(query)
            place_id = _pick_place(places, query)["id"]
        return place_details_result(await clients.place.async_get_place_summary(place_id))
    except _PLACE_ERRORS as err:
        _LOGGER.warning("Naver place lookup failed (the endpoint may be blocked): %r", err)
        raise _api_error() from err


async def async_get_transit_arrivals(
    clients: NaverClients, data: Mapping[str, Any]
) -> dict[str, Any]:
    """Return realtime arrivals at a bus stop or a subway station (one line).

    The ids come from get_directions transit steps (``stop_id``/``route_ids``/
    ``way``). ``ATTR_ROUTE_IDS`` keeps only those lines and, for the subway,
    ``ATTR_DIRECTION`` only that direction.
    """
    stop_id = data[ATTR_STOP_ID]
    try:
        if data[ATTR_TYPE] == TRANSIT_BUS:
            items = await clients.route.async_get_bus_arrivals(stop_id)
            arrivals = [bus_arrival_result(item) for item in items]
        else:
            items = await clients.route.async_get_subway_arrivals(stop_id)
            now = dt_util.now()
            arrivals = [entry for item in items for entry in subway_arrival_results(item, now)]
    except _PLACE_ERRORS as err:
        _LOGGER.warning("Naver realtime arrivals lookup failed: %r", err)
        raise _api_error() from err
    if route_ids := data.get(ATTR_ROUTE_IDS):
        arrivals = [entry for entry in arrivals if entry["route_id"] in route_ids]
    if direction := data.get(ATTR_DIRECTION):
        arrivals = [entry for entry in arrivals if entry.get("way", direction) == direction]
    return {"arrivals": arrivals}


async def async_get_directions(
    hass: HomeAssistant, clients: NaverClients, data: Mapping[str, Any]
) -> dict[str, Any]:
    """Resolve origin/destination/waypoints and build a directions response.

    ``data`` holds ``ATTR_ORIGIN``/``ATTR_DESTINATION``/``ATTR_WAYPOINTS``/
    ``ATTR_MODE`` (waypoints and mode must already have their defaults
    applied). Shared by the get_directions service and the get_directions
    LLM tool. ``ATTR_INCLUDE_GEOMETRY`` adds the route line as ``geometry``
    ([lat, lng] lists) and ``ATTR_INCLUDE_STEPS`` the turn-by-turn or per-ride
    ``steps`` (each null when unavailable). ``ATTR_INCLUDE_ALTERNATIVES`` lists
    every transit route Naver returned (the first is the top-level one) as
    ``alternatives``, null for other modes. The LLM tool sets none of them,
    since they would flood the model context.
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
    transit_routes: list[TransitResult] = []
    if mode == MODE_CAR:
        route = await clients.maps.async_get_driving_route(points[0], points[-1], points[1:-1])
    elif mode == MODE_TRANSIT:
        transit_routes = await clients.route.async_get_transit_routes(points[0], points[-1])
        route = transit_routes[0] if transit_routes else None
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
    response.update(_route_extras(route, data))
    if data.get(ATTR_INCLUDE_ALTERNATIVES):
        response["alternatives"] = (
            [_transit_alternative(transit, data) for transit in transit_routes]
            if transit_routes
            else None
        )
    return response


def _route_extras(
    route: RouteResult | TransitResult | None, data: Mapping[str, Any]
) -> dict[str, Any]:
    """The requested optional parts of a route: `geometry` and/or `steps`."""
    extras: dict[str, Any] = {}
    if data.get(ATTR_INCLUDE_GEOMETRY):
        extras["geometry"] = (
            [list(point) for point in route.path] if route and route.path else None
        )
    if data.get(ATTR_INCLUDE_STEPS):
        extras["steps"] = route.steps if route else None
    return extras


def _transit_alternative(route: TransitResult, data: Mapping[str, Any]) -> dict[str, Any]:
    """One transit route of the `alternatives` list."""
    return {
        "duration": route.duration,
        "distance": route.distance,
        "transfers": route.transfers,
        "fare": route.fare,
        "walking_duration": route.walking_duration,
        "departure_time": route.departure_time,
        "arrival_time": route.arrival_time,
        "vehicle_types": list(route.vehicle_types),
        "labels": list(route.labels),
        **_route_extras(route, data),
    }


async def _async_handle_search_place(
    hass: HomeAssistant, clients: NaverClients, call: ServiceCall
) -> ServiceResponse:
    return {"results": await async_search_place(hass, clients, call.data[ATTR_QUERY])}


async def _async_handle_search_nearby(
    hass: HomeAssistant, clients: NaverClients, call: ServiceCall
) -> ServiceResponse:
    _center, results = await async_search_nearby(hass, clients, call.data)
    return {"results": results}


async def _async_handle_geocode_address(
    clients: NaverClients, call: ServiceCall
) -> ServiceResponse:
    return await async_geocode_address(clients, call.data[ATTR_QUERY])


async def _async_handle_get_place_details(
    hass: HomeAssistant, clients: NaverClients, call: ServiceCall
) -> ServiceResponse:
    return await async_get_place_details(hass, clients, call.data)


async def _async_handle_get_transit_arrivals(
    clients: NaverClients, call: ServiceCall
) -> ServiceResponse:
    return await async_get_transit_arrivals(clients, call.data)


async def _async_handle_get_directions(
    hass: HomeAssistant, clients: NaverClients, call: ServiceCall
) -> ServiceResponse:
    return await async_get_directions(hass, clients, call.data)


@callback
def async_setup_services(hass: HomeAssistant, clients: NaverClients) -> None:
    """Register the naver_map services against the given API clients."""
    for service, handler, schema in (
        (
            SERVICE_SEARCH_PLACE,
            partial(_async_handle_search_place, hass, clients),
            SEARCH_PLACE_SCHEMA,
        ),
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
        (
            SERVICE_GET_PLACE_DETAILS,
            partial(_async_handle_get_place_details, hass, clients),
            GET_PLACE_DETAILS_SCHEMA,
        ),
        (
            SERVICE_GET_TRANSIT_ARRIVALS,
            partial(_async_handle_get_transit_arrivals, clients),
            GET_TRANSIT_ARRIVALS_SCHEMA,
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
    hass.services.async_remove(DOMAIN, SERVICE_GET_PLACE_DETAILS)
    hass.services.async_remove(DOMAIN, SERVICE_GET_TRANSIT_ARRIVALS)
