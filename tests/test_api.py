"""Tests for the Naver API clients (official search/NCP + best-effort internal routes)."""

from __future__ import annotations

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.naver_map.api import (
    InvalidApiKey,
    NaverMapRouteApi,
    NaverSearchApi,
    NcpMapsApi,
    RouteResult,
    TransitResult,
)
from custom_components.naver_map.const import (
    BIKE_ROUTE_URL,
    DRIVING_URL,
    GEOCODE_URL,
    LOCAL_SEARCH_URL,
    REVERSE_GEOCODE_URL,
    TRANSIT_ROUTE_URL,
    WALK_ROUTE_URL,
)
from custom_components.naver_map.helpers import ResolvedPoint
from tests.const import ADDRESS_ITEM, REGION_RESPONSE, STARBUCKS_ITEM
from tests.vendor.aiohttp_mock import AiohttpClientMocker

ORIGIN = ResolvedPoint(name="출발지", latitude=37.4979, longitude=127.0276)
DESTINATION = ResolvedPoint(name="도착지", latitude=37.5006, longitude=127.0364)
VIA = ResolvedPoint(name="경유지1", latitude=37.499, longitude=127.03)


def _search_api(hass: HomeAssistant) -> NaverSearchApi:
    return NaverSearchApi(async_get_clientsession(hass), "search-id", "search-secret")


def _maps_api(hass: HomeAssistant) -> NcpMapsApi:
    return NcpMapsApi(async_get_clientsession(hass), "ncp-id", "ncp-key")


def _route_api(hass: HomeAssistant) -> NaverMapRouteApi:
    return NaverMapRouteApi(async_get_clientsession(hass))


async def test_search_local_sends_credentials_and_returns_items(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """local.json is called with the client headers and display=5."""
    aioclient_mock.get(LOCAL_SEARCH_URL, json={"items": [STARBUCKS_ITEM]})

    items = await _search_api(hass).async_search_local("스타벅스")

    assert items == [STARBUCKS_ITEM]
    _method, url, _data, headers = aioclient_mock.mock_calls[0]
    assert url.query == {"query": "스타벅스", "display": "5"}
    assert headers["X-Naver-Client-Id"] == "search-id"
    assert headers["X-Naver-Client-Secret"] == "search-secret"


async def test_search_local_401_raises_invalid_api_key(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A rejected search credential raises InvalidApiKey."""
    aioclient_mock.get(LOCAL_SEARCH_URL, status=401)

    with pytest.raises(InvalidApiKey):
        await _search_api(hass).async_search_local("스타벅스")


async def test_geocode_sends_ncp_headers_and_returns_addresses(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """geocode is called with the NCP key headers and returns `addresses`."""
    aioclient_mock.get(GEOCODE_URL, json={"status": "OK", "addresses": [ADDRESS_ITEM]})

    items = await _maps_api(hass).async_geocode("불정로 6")

    assert items == [ADDRESS_ITEM]
    headers = aioclient_mock.mock_calls[0][3]
    assert headers["x-ncp-apigw-api-key-id"] == "ncp-id"
    assert headers["x-ncp-apigw-api-key"] == "ncp-key"


async def test_geocode_401_raises_invalid_api_key(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A rejected NCP key raises InvalidApiKey."""
    aioclient_mock.get(GEOCODE_URL, status=401)

    with pytest.raises(InvalidApiKey):
        await _maps_api(hass).async_geocode("불정로 6")


async def test_region_name_joins_area2_and_area3(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Reverse geocoding yields the `시/군/구 읍/면/동` prefix for keyword searches."""
    aioclient_mock.get(REVERSE_GEOCODE_URL, json=REGION_RESPONSE)

    name = await _maps_api(hass).async_region_name(127.1112, 37.3945)

    assert name == "성남시 분당구 삼평동"
    url = aioclient_mock.mock_calls[0][1]
    assert url.query["coords"] == "127.1112,37.3945"
    assert url.query["orders"] == "legalcode"


async def test_region_name_none_without_results(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A point with no region (e.g. at sea) yields None."""
    aioclient_mock.get(
        REVERSE_GEOCODE_URL, json={"status": {"code": 3, "name": "no results"}, "results": []}
    )

    assert await _maps_api(hass).async_region_name(130.0, 35.0) is None


async def test_driving_route_parses_ms_duration_and_joins_waypoints(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Directions 5 duration (ms) becomes seconds; waypoints are `|`-joined lng,lat."""
    aioclient_mock.get(
        DRIVING_URL,
        json={
            "code": 0,
            "route": {"traoptimal": [{"summary": {"duration": 600500, "distance": 4200}}]},
        },
    )

    route = await _maps_api(hass).async_get_driving_route(ORIGIN, DESTINATION, [VIA, VIA])

    assert route == RouteResult(duration=600, distance=4200)
    url = aioclient_mock.mock_calls[0][1]
    assert url.query["start"] == "127.0276,37.4979"
    assert url.query["goal"] == "127.0364,37.5006"
    assert url.query["waypoints"] == "127.03,37.499|127.03,37.499"


@pytest.mark.parametrize(
    "mock_kwargs",
    [
        {"status": 400, "json": {"code": 2, "message": "출발지 또는 도착지가 도로 주변이 아님"}},
        {"status": 401, "json": {"error": {"errorCode": "200"}}},
        {"exc": aiohttp.ClientError("boom")},
        {"exc": TimeoutError()},
    ],
)
async def test_driving_route_failure_degrades_to_none(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_kwargs: dict
) -> None:
    """Any driving lookup failure returns None instead of raising."""
    aioclient_mock.get(DRIVING_URL, **mock_kwargs)

    assert await _maps_api(hass).async_get_driving_route(ORIGIN, DESTINATION, []) is None


async def test_transit_route_parses_top_path(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The first transit path's minutes become seconds, plus transfers and fare."""
    aioclient_mock.get(
        TRANSIT_ROUTE_URL,
        json={
            "status": "CITY",
            "paths": [{"duration": 50, "distance": 24700, "fare": 3200, "transferCount": 1}],
        },
    )

    route = await _route_api(hass).async_get_transit_route(ORIGIN, DESTINATION)

    assert route == TransitResult(duration=3000, distance=24700, transfers=1, fare=3200)
    _method, url, _data, headers = aioclient_mock.mock_calls[0]
    assert url.query == {"start": "127.0276,37.4979", "goal": "127.0364,37.5006"}
    assert headers["Referer"] == "https://map.naver.com/"


async def test_transit_route_without_paths_degrades_to_none(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A transit response with no paths returns None."""
    aioclient_mock.get(TRANSIT_ROUTE_URL, json={"status": "NO_RESULT", "paths": []})

    assert await _route_api(hass).async_get_transit_route(ORIGIN, DESTINATION) is None


async def test_walk_route_passes_all_points_in_order(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The walk endpoint gets every point `;`-joined in `l`, and the summary is parsed."""
    aioclient_mock.get(
        WALK_ROUTE_URL, json={"routes": [{"summary": {"duration": 1047, "distance": 876}}]}
    )

    route = await _route_api(hass).async_get_walk_route([ORIGIN, VIA, DESTINATION])

    assert route == RouteResult(duration=1047, distance=876)
    url = aioclient_mock.mock_calls[0][1]
    assert url.query["o"] == "all"
    assert url.query["l"] == "127.0276,37.4979;127.03,37.499;127.0364,37.5006"


async def test_walk_route_error_body_degrades_to_none(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The walk endpoint's 200 + `error` body (e.g. too far to walk) returns None."""
    aioclient_mock.get(
        WALK_ROUTE_URL, json={"code": 0, "error": "도보 길찾기 결과를 제공할 수 없습니다."}
    )

    assert await _route_api(hass).async_get_walk_route([ORIGIN, DESTINATION]) is None


async def test_bike_route_sends_named_points(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The bike endpoint gets `lng,lat,name=...` start/destination and the summary is parsed."""
    aioclient_mock.get(
        BIKE_ROUTE_URL, json={"routes": [{"summary": {"duration": 208, "distance": 821}}]}
    )

    route = await _route_api(hass).async_get_bike_route(ORIGIN, DESTINATION)

    assert route == RouteResult(duration=208, distance=821)
    url = aioclient_mock.mock_calls[0][1]
    assert url.query["start"] == "127.0276,37.4979,name=출발지"
    assert url.query["destination"] == "127.0364,37.5006,name=도착지"


async def test_bike_route_error_body_degrades_to_none(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The bike endpoint's `error` body returns None."""
    aioclient_mock.get(BIKE_ROUTE_URL, json={"error": {"error_code": 2}})

    assert await _route_api(hass).async_get_bike_route(ORIGIN, DESTINATION) is None
