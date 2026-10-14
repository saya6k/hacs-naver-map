"""Clients for the Naver Search API, NCP Maps API, and Naver Map internal routes."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any

import aiohttp

from .const import (
    BIKE_ROUTE_URL,
    DRIVING_URL,
    GEOCODE_URL,
    LOCAL_SEARCH_URL,
    MAX_SEARCH_RESULTS,
    REVERSE_GEOCODE_URL,
    ROUTE_API_HEADERS,
    TRANSIT_ROUTE_URL,
    WALK_ROUTE_URL,
)
from .helpers import ResolvedPoint

_LOGGER = logging.getLogger(__name__)

# Any of these means a route lookup could not be read; the ETA fields degrade
# to null while the route link is still returned.
_ROUTE_ERRORS = (
    aiohttp.ClientError,
    TimeoutError,
    KeyError,
    IndexError,
    TypeError,
    ValueError,
)


class NaverApiError(Exception):
    """Base error for Naver API calls."""


class InvalidApiKey(NaverApiError):
    """The credentials were rejected (HTTP 401)."""


async def _async_get_json(
    session: aiohttp.ClientSession,
    url: str,
    params: dict[str, str | int],
    headers: dict[str, str],
) -> Any:
    """GET a JSON endpoint, mapping HTTP 401 to InvalidApiKey."""
    async with asyncio.timeout(10):
        resp = await session.get(url, params=params, headers=headers)
    if resp.status == HTTPStatus.UNAUTHORIZED:
        raise InvalidApiKey
    resp.raise_for_status()
    return await resp.json(content_type=None)


class NaverSearchApi:
    """Async client for the Naver Developers local search endpoint."""

    def __init__(
        self, session: aiohttp.ClientSession, client_id: str, client_secret: str
    ) -> None:
        """Store the shared session and the Naver Developers credentials."""
        self._session = session
        self._headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        }

    async def async_search_local(self, query: str) -> list[dict[str, Any]]:
        """Search places by keyword and return raw local.json items (max 5)."""
        data = await _async_get_json(
            self._session,
            LOCAL_SEARCH_URL,
            {"query": query, "display": MAX_SEARCH_RESULTS},
            self._headers,
        )
        return list(data["items"])


# A route line as [lat, lng] points (WGS84), or None when it could not be read.
type RoutePath = list[tuple[float, float]] | None
# Turn-by-turn (or, for transit, per-ride) steps, or None when they could not be read.
type RouteSteps = list[dict[str, Any]] | None

# Transit step times are naive Korea Standard Time (no DST).
_KST = timezone(timedelta(hours=9))
_TAG = re.compile(r"<[^>]+>")


@dataclass(slots=True, frozen=True)
class RouteResult:
    """A resolved route's duration (seconds), distance (meters), and line."""

    duration: int
    distance: int
    path: RoutePath = None
    steps: RouteSteps = None


@dataclass(slots=True, frozen=True)
class TransitResult:
    """A public-transit route's duration/distance plus transfers, fare, and line."""

    duration: int
    distance: int
    transfers: int
    fare: int
    path: RoutePath = None
    steps: RouteSteps = None


def _read_optional[T](
    label: str, part: str, parse: Callable[[Any], list[T]], data: Any
) -> list[T] | None:
    """Parse an optional route part best-effort: a failure drops only that part, not the ETA."""
    try:
        parsed = parse(data)
        if not parsed:
            raise ValueError(f"empty {part}")
    except _ROUTE_ERRORS as err:
        _LOGGER.warning("Naver %s route %s unreadable, left out: %s", label, part, err)
        return None
    return parsed


def _read_path(
    label: str, parse: Callable[[Any], list[tuple[float, float]]], data: Any
) -> RoutePath:
    return _read_optional(label, "geometry", parse, data)


def _read_steps(
    label: str, parse: Callable[[Any], list[dict[str, Any]]], data: Any
) -> RouteSteps:
    return _read_optional(label, "steps", parse, data)


def _driving_steps(data: Any) -> list[dict[str, Any]]:
    """Directions 5 `guide`: instructions with distance (m) and duration (ms)."""
    return [
        {
            "instruction": guide["instructions"],
            "distance": int(guide["distance"]),
            "duration": int(guide["duration"]) // 1000,
        }
        for guide in data["guide"]
    ]


def _walk_steps(data: Any) -> list[dict[str, Any]]:
    """walk `legs[].steps[]`: `turnDesc` turns (blank ones skipped), duration in seconds."""
    return [
        {
            "instruction": step["turnDesc"],
            "distance": int(step["distance"]),
            "duration": int(step["duration"]),
        }
        for leg in data["legs"]
        for step in leg["steps"]
        if step.get("turnDesc")
    ]


def _bike_steps(data: Any) -> list[dict[str, Any]]:
    """bike `legs[].steps[]`: HTML `guide.instructions`; marker steps have no `content`."""
    return [
        {
            "instruction": _TAG.sub("", step["guide"]["instructions"]),
            "distance": int(step["summary"]["distance"]),
            "duration": int(step["summary"]["duration"]),
        }
        for leg in data["legs"]
        for step in leg["steps"]
        if step["guide"].get("content")
    ]


def _kst(value: str) -> str:
    return datetime.fromisoformat(value).replace(tzinfo=_KST).isoformat()


def _transit_steps(data: Any) -> list[dict[str, Any]]:
    """pubtrans `legs[].steps[]`: walks and rides (duration in minutes, naive KST times)."""
    steps = []
    for leg in data["legs"]:
        for raw in leg["steps"]:
            step: dict[str, Any] = {
                "type": "walk" if raw["type"] == "WALKING" else raw["type"].lower(),
                "instruction": raw["instruction"],
                "distance": int(raw["distance"]),
                "duration": int(raw["duration"]) * 60,
                "departure_time": _kst(raw["departureTime"]),
                "arrival_time": _kst(raw["arrivalTime"]),
            }
            if routes := raw.get("routes"):
                stations = raw["stations"]
                # Several bus lines can serve the same ride; any of them works.
                step["lines"] = [route["name"] for route in routes]
                step["color"] = routes[0]["type"].get("color")
                step["headsign"] = raw.get("headsign")
                step["from"] = stations[0]["name"]
                step["to"] = stations[-1]["name"]
                step["stops"] = len(stations) - 1
            steps.append(step)
    return steps


def _lng_lat_pairs(data: Any) -> list[tuple[float, float]]:
    """Directions 5 `path`: [[lng, lat], ...]."""
    return [(float(lat), float(lng)) for lng, lat in data["path"]]


def _step_path_strings(data: Any) -> list[tuple[float, float]]:
    """walk/bike `legs[].steps[].path`: "lng,lat lng,lat" strings (null/empty skip)."""
    path = []
    for leg in data["legs"]:
        for step in leg["steps"]:
            for pair in (step.get("path") or "").split():
                lng, lat = pair.split(",")
                path.append((float(lat), float(lng)))
    return path


def _step_points(data: Any) -> list[tuple[float, float]]:
    """pubtrans `legs[].steps[].points`: [{x: lng, y: lat}, ...] (missing skip)."""
    return [
        (float(point["y"]), float(point["x"]))
        for leg in data["legs"]
        for step in leg["steps"]
        for point in step.get("points") or []
    ]


def _coord(point: ResolvedPoint) -> str:
    """Format a point as the `lng,lat` pair Naver endpoints expect."""
    return f"{point.longitude},{point.latitude}"


class NcpMapsApi:
    """Async client for NAVER Cloud Platform Maps (geocode, reverse geocode, driving)."""

    def __init__(self, session: aiohttp.ClientSession, key_id: str, key: str) -> None:
        """Store the shared session and the NCP API key pair."""
        self._session = session
        self._headers = {
            "x-ncp-apigw-api-key-id": key_id,
            "x-ncp-apigw-api-key": key,
        }

    async def async_geocode(self, query: str) -> list[dict[str, Any]]:
        """Geocode an address string and return raw `addresses` items."""
        data = await _async_get_json(
            self._session, GEOCODE_URL, {"query": query}, self._headers
        )
        return list(data["addresses"])

    async def async_region_name(self, longitude: float, latitude: float) -> str | None:
        """Reverse-geocode a point to a `시/군/구 읍/면/동` name, or None if none."""
        data = await _async_get_json(
            self._session,
            REVERSE_GEOCODE_URL,
            {"coords": f"{longitude},{latitude}", "orders": "legalcode", "output": "json"},
            self._headers,
        )
        results = data.get("results") or []
        if not results:
            return None
        region = results[0]["region"]
        names = [region[area]["name"] for area in ("area2", "area3") if region.get(area)]
        return " ".join(name for name in names if name) or None

    async def async_get_driving_route(
        self,
        origin: ResolvedPoint,
        destination: ResolvedPoint,
        waypoints: list[ResolvedPoint],
    ) -> RouteResult | None:
        """Query Directions 5 for a car route, or None if the lookup fails."""
        params: dict[str, str | int] = {
            "start": _coord(origin),
            "goal": _coord(destination),
            "option": "traoptimal",
        }
        if waypoints:
            params["waypoints"] = "|".join(_coord(p) for p in waypoints)
        try:
            async with asyncio.timeout(10):
                resp = await self._session.get(DRIVING_URL, params=params, headers=self._headers)
            # Route failures (e.g. code 2 "not near a road") come back as HTTP 400
            # with a JSON body, so read the body before judging the status.
            data = await resp.json(content_type=None)
            if data.get("code") != 0:
                raise ValueError(f"code={data.get('code')} {data.get('message')}")
            route = data["route"]["traoptimal"][0]
            summary = route["summary"]
            return RouteResult(
                duration=int(summary["duration"]) // 1000,
                distance=int(summary["distance"]),
                path=_read_path("driving", _lng_lat_pairs, route),
                steps=_read_steps("driving", _driving_steps, route),
            )
        except _ROUTE_ERRORS as err:
            _LOGGER.warning("Naver driving route lookup failed, ETA unavailable: %s", err)
            return None


class NaverMapRouteApi:
    """Best-effort client for map.naver.com internal route endpoints (no API key)."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Store the shared session."""
        self._session = session

    async def _async_get(self, url: str, params: dict[str, str]) -> Any:
        async with asyncio.timeout(10):
            resp = await self._session.get(url, params=params, headers=ROUTE_API_HEADERS)
        resp.raise_for_status()
        return await resp.json(content_type=None)

    async def async_get_transit_route(
        self, origin: ResolvedPoint, destination: ResolvedPoint
    ) -> TransitResult | None:
        """Query the transit endpoint for the top-ranked route, or None on failure."""
        try:
            data = await self._async_get(
                TRANSIT_ROUTE_URL, {"start": _coord(origin), "goal": _coord(destination)}
            )
            path = data["paths"][0]
            return TransitResult(
                duration=int(path["duration"]) * 60,  # minutes
                distance=int(path["distance"]),
                transfers=int(path["transferCount"]),
                fare=int(path["fare"]),
                path=_read_path("transit", _step_points, path),
                steps=_read_steps("transit", _transit_steps, path),
            )
        except _ROUTE_ERRORS as err:
            _LOGGER.warning("Naver transit route lookup failed, ETA unavailable: %s", err)
            return None

    async def async_get_walk_route(self, points: list[ResolvedPoint]) -> RouteResult | None:
        """Query the walk endpoint through all points in order, or None on failure."""
        try:
            data = await self._async_get(
                WALK_ROUTE_URL, {"o": "all", "l": ";".join(_coord(p) for p in points)}
            )
            route = data["routes"][0]
            summary = route["summary"]
            return RouteResult(
                duration=int(summary["duration"]),
                distance=int(summary["distance"]),
                path=_read_path("walk", _step_path_strings, route),
                steps=_read_steps("walk", _walk_steps, route),
            )
        except _ROUTE_ERRORS as err:
            _LOGGER.warning("Naver walk route lookup failed, ETA unavailable: %s", err)
            return None

    async def async_get_bike_route(
        self, origin: ResolvedPoint, destination: ResolvedPoint
    ) -> RouteResult | None:
        """Query the bike endpoint for a direct route, or None on failure."""
        try:
            # The bike endpoint rejects bare coordinates; it needs the `,name=` suffix.
            data = await self._async_get(
                BIKE_ROUTE_URL,
                {
                    "start": f"{_coord(origin)},name={origin.name}",
                    "destination": f"{_coord(destination)},name={destination.name}",
                },
            )
            route = data["routes"][0]
            summary = route["summary"]
            return RouteResult(
                duration=int(summary["duration"]),
                distance=int(summary["distance"]),
                path=_read_path("bike", _step_path_strings, route),
                steps=_read_steps("bike", _bike_steps, route),
            )
        except _ROUTE_ERRORS as err:
            _LOGGER.warning("Naver bike route lookup failed, ETA unavailable: %s", err)
            return None
