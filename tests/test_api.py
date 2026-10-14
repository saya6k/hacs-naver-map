"""Tests for the Naver API clients (official search/NCP + best-effort internal routes)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.naver_map.api import (
    InvalidApiKey,
    NaverMapRouteApi,
    NaverPlaceApi,
    NcpMapsApi,
    RouteResult,
    TransitResult,
)
from custom_components.naver_map.const import (
    BIKE_ROUTE_URL,
    BUS_ARRIVALS_URL,
    DRIVING_URL,
    GEOCODE_URL,
    INSTANT_SEARCH_URL,
    PLACE_SUMMARY_URL,
    SUBWAY_ARRIVALS_URL,
    TRANSIT_ROUTE_URL,
    WALK_ROUTE_URL,
)
from custom_components.naver_map.helpers import ResolvedPoint
from tests.const import (
    ADDRESS_ITEM,
    BUS_ARRIVALS_RESPONSE,
    CAPTCHA_RESPONSE,
    INSTANT_SEARCH_RESPONSE,
    PLACE_SUMMARY_RESPONSE,
    SUBWAY_ARRIVALS_RESPONSE,
)
from tests.vendor.aiohttp_mock import AiohttpClientMocker, AiohttpClientMockResponse

ORIGIN = ResolvedPoint(name="출발지", latitude=37.4979, longitude=127.0276)
DESTINATION = ResolvedPoint(name="도착지", latitude=37.5006, longitude=127.0364)
VIA = ResolvedPoint(name="경유지1", latitude=37.499, longitude=127.03)


def _maps_api(hass: HomeAssistant) -> NcpMapsApi:
    return NcpMapsApi(async_get_clientsession(hass), "ncp-id", "ncp-key")


def _route_api(hass: HomeAssistant) -> NaverMapRouteApi:
    return NaverMapRouteApi(async_get_clientsession(hass))



def _car(duration_ms: int, distance: int, toll: int, fuel: int) -> dict:
    """One Directions 5 route, as it appears under an option key."""
    return {
        "summary": {
            "duration": duration_ms,
            "distance": distance,
            "tollFare": toll,
            "fuelPrice": fuel,
        }
    }

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

    routes = await _maps_api(hass).async_get_driving_routes(ORIGIN, DESTINATION, [VIA, VIA])

    assert routes == [RouteResult(duration=600, distance=4200, labels=("best",))]
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
async def test_driving_route_failure_degrades_to_no_routes(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_kwargs: dict
) -> None:
    """Any driving lookup failure returns no routes instead of raising."""
    aioclient_mock.get(DRIVING_URL, **mock_kwargs)

    assert await _maps_api(hass).async_get_driving_routes(ORIGIN, DESTINATION, []) == []


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

    routes = await _route_api(hass).async_get_transit_routes(ORIGIN, DESTINATION)

    assert routes == [TransitResult(duration=3000, distance=24700, transfers=1, fare=3200)]
    _method, url, _data, headers = aioclient_mock.mock_calls[0]
    assert url.query == {"start": "127.0276,37.4979", "goal": "127.0364,37.5006"}
    assert headers["Referer"] == "https://map.naver.com/"


async def test_transit_route_without_paths_degrades_to_none(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A transit response with no paths returns no routes."""
    aioclient_mock.get(TRANSIT_ROUTE_URL, json={"status": "NO_RESULT", "paths": []})

    assert await _route_api(hass).async_get_transit_routes(ORIGIN, DESTINATION) == []


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


async def test_driving_route_parses_path_as_lat_lng(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Directions 5 `path` ([lng, lat] pairs) becomes [lat, lng] tuples."""
    aioclient_mock.get(
        DRIVING_URL,
        json={
            "code": 0,
            "route": {
                "traoptimal": [
                    {
                        "summary": {"duration": 600000, "distance": 4200},
                        "path": [[127.0276, 37.4979], [127.0364, 37.5006]],
                    }
                ]
            },
        },
    )

    [route] = await _maps_api(hass).async_get_driving_routes(ORIGIN, DESTINATION, [])

    assert route.path == [(37.4979, 127.0276), (37.5006, 127.0364)]


async def test_transit_route_parses_step_points(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Transit step `points` ({x: lng, y: lat}) are joined in order; steps without points skip."""
    aioclient_mock.get(
        TRANSIT_ROUTE_URL,
        json={
            "paths": [
                {
                    "duration": 50,
                    "distance": 24700,
                    "fare": 3200,
                    "transferCount": 1,
                    "legs": [
                        {
                            "steps": [
                                {"points": [{"x": 127.0276, "y": 37.4979}]},
                                {"type": "WALKING"},
                                {
                                    "points": [
                                        {"x": 127.03, "y": 37.499},
                                        {"x": 127.0364, "y": 37.5006},
                                    ]
                                },
                            ]
                        }
                    ],
                }
            ]
        },
    )

    [route] = await _route_api(hass).async_get_transit_routes(ORIGIN, DESTINATION)

    assert route.path == [(37.4979, 127.0276), (37.499, 127.03), (37.5006, 127.0364)]


async def test_walk_route_parses_step_path_strings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Walk step `path` strings ("lng,lat lng,lat") are joined; null/empty steps skip."""
    aioclient_mock.get(
        WALK_ROUTE_URL,
        json={
            "routes": [
                {
                    "summary": {"duration": 1047, "distance": 876},
                    "legs": [
                        {"steps": [{"path": None}, {"path": "127.0276,37.4979 127.03,37.499"}]},
                        {"steps": [{"path": ""}, {"path": "127.0364,37.5006"}]},
                    ],
                }
            ]
        },
    )

    route = await _route_api(hass).async_get_walk_route([ORIGIN, VIA, DESTINATION])

    assert route is not None
    assert route.path == [(37.4979, 127.0276), (37.499, 127.03), (37.5006, 127.0364)]


async def test_bike_route_parses_step_path_strings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Bike steps use the same space-separated path strings as walk."""
    aioclient_mock.get(
        BIKE_ROUTE_URL,
        json={
            "routes": [
                {
                    "summary": {"duration": 208, "distance": 821},
                    "legs": [{"steps": [{"path": "127.0276,37.4979 127.0364,37.5006"}]}],
                }
            ]
        },
    )

    route = await _route_api(hass).async_get_bike_route(ORIGIN, DESTINATION)

    assert route is not None
    assert route.path == [(37.4979, 127.0276), (37.5006, 127.0364)]


async def test_unreadable_geometry_keeps_eta_with_null_path(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog: pytest.LogCaptureFixture
) -> None:
    """A malformed path drops only the geometry (with a warning); duration/distance stay."""
    aioclient_mock.get(
        WALK_ROUTE_URL,
        json={
            "routes": [
                {
                    "summary": {"duration": 1047, "distance": 876},
                    "legs": [{"steps": [{"path": "not-a-coordinate"}]}],
                }
            ]
        },
    )

    route = await _route_api(hass).async_get_walk_route([ORIGIN, DESTINATION])

    assert route == RouteResult(duration=1047, distance=876, path=None)
    assert "geometry" in caplog.text


async def test_driving_route_parses_guide_steps(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Directions 5 `guide` entries become steps with seconds (from ms) and meters."""
    aioclient_mock.get(
        DRIVING_URL,
        json={
            "code": 0,
            "route": {
                "traoptimal": [
                    {
                        "summary": {"duration": 600000, "distance": 4200},
                        "path": [[127.0276, 37.4979], [127.0364, 37.5006]],
                        "guide": [
                            {
                                "pointIndex": 1,
                                "type": 3,
                                "instructions": "테헤란로 방면으로 우회전",
                                "distance": 300,
                                "duration": 60000,
                            },
                        ],
                    }
                ]
            },
        },
    )

    [route] = await _maps_api(hass).async_get_driving_routes(ORIGIN, DESTINATION, [])

    assert route.steps == [
        {"instruction": "테헤란로 방면으로 우회전", "distance": 300, "duration": 60}
    ]


async def test_transit_route_parses_ride_and_walk_steps(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Transit steps keep lines, color, headsign, stations, and KST times (minutes → s)."""
    aioclient_mock.get(
        TRANSIT_ROUTE_URL,
        json={
            "paths": [
                {
                    "duration": 30,
                    "distance": 9000,
                    "fare": 1500,
                    "transferCount": 0,
                    "legs": [
                        {
                            "steps": [
                                {
                                    "type": "WALKING",
                                    "instruction": "도보 75m",
                                    "distance": 75,
                                    "duration": 2,
                                    "departureTime": "2026-10-14T16:06:00",
                                    "arrivalTime": "2026-10-14T16:08:04",
                                    "routes": [],
                                    "stations": [],
                                },
                                {
                                    "type": "BUS",
                                    "instruction": "버스 승차",
                                    "distance": 2785,
                                    "duration": 10,
                                    "headsign": "옥수동회차지",
                                    "wayType": "UP",
                                    "departureTime": "2026-10-14T16:14:38",
                                    "arrivalTime": "2026-10-14T16:25:16",
                                    "routes": [
                                        {"id": 1808, "name": "421", "type": {"color": "#386de8"}},
                                        {"id": 500, "name": "400", "type": {"color": "#386de8"}},
                                    ],
                                    "stations": [
                                        {"id": 106041, "name": "강남역"},
                                        {"id": 1, "name": "논현역"},
                                        {"id": 2, "name": "신사역"},
                                    ],
                                },
                            ]
                        }
                    ],
                }
            ]
        },
    )

    [route] = await _route_api(hass).async_get_transit_routes(ORIGIN, DESTINATION)

    assert route.steps == [
        {
            "type": "walk",
            "instruction": "도보 75m",
            "distance": 75,
            "duration": 120,
            "departure_time": "2026-10-14T16:06:00+09:00",
            "arrival_time": "2026-10-14T16:08:04+09:00",
        },
        {
            "type": "bus",
            "instruction": "버스 승차",
            "distance": 2785,
            "duration": 600,
            "departure_time": "2026-10-14T16:14:38+09:00",
            "arrival_time": "2026-10-14T16:25:16+09:00",
            "lines": ["421", "400"],
            "color": "#386de8",
            "headsign": "옥수동회차지",
            "from": "강남역",
            "to": "신사역",
            "stops": 2,
            "stop_id": "106041",
            "route_ids": ["1808", "500"],
            "way": "up",
        },
    ]


async def test_walk_route_parses_turn_steps(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Walk steps with a `turnDesc` become steps; blank turns are skipped."""
    aioclient_mock.get(
        WALK_ROUTE_URL,
        json={
            "routes": [
                {
                    "summary": {"duration": 288, "distance": 201},
                    "legs": [
                        {
                            "steps": [
                                {"turnDesc": "", "distance": 0, "duration": 0, "path": None},
                                {
                                    "turnDesc": "강남역 10번 출구",
                                    "distance": 120,
                                    "duration": 213,
                                    "path": "127.0276,37.4979 127.0270,37.4987",
                                },
                            ]
                        }
                    ],
                }
            ]
        },
    )

    route = await _route_api(hass).async_get_walk_route([ORIGIN, DESTINATION])

    assert route is not None
    assert route.steps == [{"instruction": "강남역 10번 출구", "distance": 120, "duration": 213}]


async def test_bike_route_parses_guide_steps_without_markup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Bike `guide.instructions` lose their <b> tags; content-less marker steps are skipped."""
    aioclient_mock.get(
        BIKE_ROUTE_URL,
        json={
            "routes": [
                {
                    "summary": {"duration": 72, "distance": 321},
                    "legs": [
                        {
                            "steps": [
                                {
                                    "summary": {"distance": 0, "duration": 0},
                                    "guide": {"content": "", "instructions": "A"},
                                    "path": "",
                                },
                                {
                                    "summary": {"distance": 321, "duration": 72},
                                    "guide": {
                                        "content": "321m 이동",
                                        "instructions": "<b>테헤란로</b>를 따라 321m 이동",
                                    },
                                    "path": "127.0276,37.4979 127.0294,37.4984",
                                },
                            ]
                        }
                    ],
                }
            ]
        },
    )

    route = await _route_api(hass).async_get_bike_route(ORIGIN, DESTINATION)

    assert route is not None
    assert route.steps == [
        {"instruction": "테헤란로를 따라 321m 이동", "distance": 321, "duration": 72}
    ]


async def test_transit_routes_keep_every_path_with_labels(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Every transit path is returned in order with its labels, vehicle types, and times."""
    aioclient_mock.get(
        TRANSIT_ROUTE_URL,
        json={
            "paths": [
                {
                    "duration": 36,
                    "distance": 10000,
                    "fare": 1650,
                    "transferCount": 2,
                    "walkingDuration": 12,
                    "departureTime": "2026-10-14T16:04:30",
                    "arrivalTime": "2026-10-14T16:40:42",
                    "vehicleTypes": ["SUBWAY"],
                    "pathLabels": [
                        {"labelCode": "BEST", "labelText": "최적"},
                        {"labelCode": "MINIMUM_DURATION", "labelText": "최소시간"},
                    ],
                },
                {"duration": 50, "fare": 1500},  # unreadable: skipped
                {
                    "duration": 54,
                    "distance": 11000,
                    "fare": 1600,
                    "transferCount": 2,
                    "walkingDuration": 8,
                    "vehicleTypes": ["BUS", "SUBWAY"],
                    "pathLabels": [{"labelCode": "MINIMUM_WALKING", "labelText": "최소도보"}],
                },
            ]
        },
    )

    routes = await _route_api(hass).async_get_transit_routes(ORIGIN, DESTINATION)

    assert routes == [
        TransitResult(
            duration=2160,
            distance=10000,
            transfers=2,
            fare=1650,
            walking_duration=720,
            departure_time="2026-10-14T16:04:30+09:00",
            arrival_time="2026-10-14T16:40:42+09:00",
            vehicle_types=("subway",),
            labels=("best", "minimum_duration"),
        ),
        TransitResult(
            duration=3240,
            distance=11000,
            transfers=2,
            fare=1600,
            walking_duration=480,
            vehicle_types=("bus", "subway"),
            labels=("minimum_walking",),
        ),
    ]


def _place_api(hass: HomeAssistant) -> NaverPlaceApi:
    return NaverPlaceApi(async_get_clientsession(hass))


async def test_instant_search_sends_query_and_coords(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Autocomplete gets the query and `lat,lng` coords and returns its place list."""
    aioclient_mock.get(INSTANT_SEARCH_URL, json=INSTANT_SEARCH_RESPONSE)

    places = await _place_api(hass).async_instant_search("스타벅스 강남", 37.4979, 127.0276)

    assert [place["id"] for place in places] == ["1086067689", "1234"]
    _method, url, _data, headers = aioclient_mock.mock_calls[0]
    assert url.query["query"] == "스타벅스 강남"
    assert url.query["coords"] == "37.4979,127.0276"
    assert headers["Referer"] == "https://map.naver.com/"


async def test_instant_search_captcha_raises(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A CAPTCHA-gated answer has no place list and raises instead of looking empty."""
    aioclient_mock.get(INSTANT_SEARCH_URL, json=CAPTCHA_RESPONSE)

    with pytest.raises(KeyError):
        await _place_api(hass).async_instant_search("스타벅스", 37.4979, 127.0276)


async def test_place_summary_returns_detail(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The summary endpoint is called with the place id and yields `placeDetail`."""
    aioclient_mock.get(f"{PLACE_SUMMARY_URL}/1086067689", json=PLACE_SUMMARY_RESPONSE)

    detail = await _place_api(hass).async_get_place_summary("1086067689")

    assert detail["name"] == "스타벅스 강남R점"


async def test_place_summary_retries_once_after_rate_limit(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 429 (Naver throttles bursts) is retried once after a short pause."""
    url = f"{PLACE_SUMMARY_URL}/1086067689"
    statuses = iter([429, 200])

    async def respond(method, request_url, data):
        return AiohttpClientMockResponse(
            method, request_url, status=next(statuses), json=PLACE_SUMMARY_RESPONSE
        )

    aioclient_mock.get(url, side_effect=respond)
    with patch("custom_components.naver_map.api.asyncio.sleep", AsyncMock()) as sleep:
        detail = await _place_api(hass).async_get_place_summary("1086067689")

    assert detail["id"] == "1086067689"
    assert aioclient_mock.call_count == 2
    sleep.assert_awaited_once()


async def test_place_summary_rate_limited_twice_raises(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A second 429 is not retried again."""
    aioclient_mock.get(f"{PLACE_SUMMARY_URL}/1086067689", status=429)

    with (
        patch("custom_components.naver_map.api.asyncio.sleep", AsyncMock()),
        pytest.raises(aiohttp.ClientResponseError),
    ):
        await _place_api(hass).async_get_place_summary("1086067689")

    assert aioclient_mock.call_count == 2


async def test_place_summary_is_cached(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A place looked up again within the cache window makes no new request."""
    aioclient_mock.get(f"{PLACE_SUMMARY_URL}/1086067689", json=PLACE_SUMMARY_RESPONSE)
    api = _place_api(hass)

    await api.async_get_place_summary("1086067689")
    await api.async_get_place_summary("1086067689")

    assert aioclient_mock.call_count == 1


async def test_bus_arrivals_query_the_stop(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Realtime bus arrivals are requested per stop id."""
    aioclient_mock.get(BUS_ARRIVALS_URL, json=BUS_ARRIVALS_RESPONSE)

    arrivals = await _route_api(hass).async_get_bus_arrivals("106041")

    assert [item["name"] for item in arrivals] == ["917", "3100N"]
    assert aioclient_mock.mock_calls[0][1].query == {"stopId": "106041"}


async def test_subway_arrivals_query_the_station(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Realtime subway arrivals are requested per (per-line) station id."""
    aioclient_mock.get(SUBWAY_ARRIVALS_URL, json=SUBWAY_ARRIVALS_RESPONSE)

    arrivals = await _route_api(hass).async_get_subway_arrivals("222")

    assert arrivals[0]["routeType"]["name"] == "2호선"
    assert aioclient_mock.mock_calls[0][1].query == {"station": "222", "subwayArrivalCount": "3"}


async def test_driving_routes_ask_three_options_in_one_call(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """One Directions 5 call returns best, fastest, and toll-free routes, with costs."""
    aioclient_mock.get(
        DRIVING_URL,
        json={
            "code": 0,
            "route": {
                "traoptimal": [_car(900000, 12000, 1500, 1800)],
                "trafast": [_car(840000, 13000, 2400, 1900)],
                "traavoidtoll": [_car(1200000, 11000, 0, 1600)],
            },
        },
    )

    routes = await _maps_api(hass).async_get_driving_routes(ORIGIN, DESTINATION, [])

    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][1].query["option"] == "traoptimal:trafast:traavoidtoll"
    assert [(r.labels, r.duration, r.toll_fare, r.fuel_price) for r in routes] == [
        (("best",), 900, 1500, 1800),
        (("minimum_duration",), 840, 2400, 1900),
        (("toll_free",), 1200, 0, 1600),
    ]


async def test_driving_routes_merge_identical_options(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Options that pick the same route become one route carrying both labels."""
    same = {"summary": {"duration": 600000, "distance": 4200, "tollFare": 0, "fuelPrice": 700}}
    aioclient_mock.get(
        DRIVING_URL,
        json={
            "code": 0,
            "route": {"traoptimal": [same], "trafast": [same], "traavoidtoll": [same]},
        },
    )

    routes = await _maps_api(hass).async_get_driving_routes(ORIGIN, DESTINATION, [])

    assert [r.labels for r in routes] == [("best", "minimum_duration", "toll_free")]


async def test_driving_routes_merge_the_same_route_despite_timing_noise(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Options returning the same road (same distance, tolls, and line) merge even when
    their real-time durations differ by a few milliseconds."""
    path = [[127.0, 37.5], [127.1, 37.4]]
    best = {"summary": {"duration": 3323000, "distance": 34093, "tollFare": 0}, "path": path}
    free = {"summary": {"duration": 3323450, "distance": 34093, "tollFare": 0}, "path": path}
    aioclient_mock.get(
        DRIVING_URL, json={"code": 0, "route": {"traoptimal": [best], "traavoidtoll": [free]}}
    )

    routes = await _maps_api(hass).async_get_driving_routes(ORIGIN, DESTINATION, [])

    assert [r.labels for r in routes] == [("best", "toll_free")]
