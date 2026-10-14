"""Tests for the naver_map services."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from custom_components.naver_map.const import (
    BIKE_ROUTE_URL,
    DOMAIN,
    DRIVING_URL,
    GEOCODE_URL,
    INSTANT_SEARCH_URL,
    LOCAL_SEARCH_URL,
    PLACE_SUMMARY_URL,
    REVERSE_GEOCODE_URL,
    TRANSIT_ROUTE_URL,
    WALK_ROUTE_URL,
)
from tests.const import (
    ADDRESS_ITEM,
    CAPTCHA_RESPONSE,
    ENTRY_DATA,
    INSTANT_SEARCH_RESPONSE,
    PLACE_SUMMARY_RESPONSE,
    REGION_RESPONSE,
    STARBUCKS_ITEM,
)
from tests.vendor.aiohttp_mock import AiohttpClientMocker
from tests.vendor.ha_common import MockConfigEntry

# STARBUCKS_ITEM sits at (37.3945, 127.1112); this center is ~110 m south of it.
CENTER = {"latitude": 37.3935, "longitude": 127.1112}
FAR_ITEM = {**STARBUCKS_ITEM, "title": "스타벅스 정자점", "mapy": "373595000"}  # ~3.9 km
NEAR_ITEM = {**STARBUCKS_ITEM, "title": "스타벅스 삼평점", "mapy": "373937000"}  # ~20 m


@pytest.fixture(autouse=True)
async def setup_integration(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> MockConfigEntry:
    """Set up a naver_map config entry (after HTTP is mocked) so services are registered."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _call(hass: HomeAssistant, service: str, data: dict) -> dict:
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True
    )


async def test_search_place_returns_results(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_place maps every local.json item to the place schema."""
    aioclient_mock.get(LOCAL_SEARCH_URL, json={"items": [STARBUCKS_ITEM, FAR_ITEM]})

    response = await _call(hass, "search_place", {"query": "스타벅스"})

    assert [r["place_name"] for r in response["results"]] == ["스타벅스 판교점", "스타벅스 정자점"]
    assert response["results"][0]["latitude"] == 37.3945
    assert aioclient_mock.mock_calls[0][3]["X-Naver-Client-Id"] == "search-id"


async def test_search_place_no_results(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An empty result set raises a no_results validation error naming the query."""
    aioclient_mock.get(LOCAL_SEARCH_URL, json={"items": []})

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "search_place", {"query": "없는장소"})

    assert err.value.translation_key == "no_results"
    assert err.value.translation_placeholders == {"query": "없는장소"}


async def test_search_place_api_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An HTTP failure surfaces as the api_error HomeAssistantError."""
    aioclient_mock.get(LOCAL_SEARCH_URL, status=500)

    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, "search_place", {"query": "스타벅스"})

    assert err.value.translation_key == "api_error"


async def test_search_nearby_prefixes_region_filters_and_sorts(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The keyword is prefixed with the center's region; far results drop, near sort first."""
    aioclient_mock.get(REVERSE_GEOCODE_URL, json=REGION_RESPONSE)
    aioclient_mock.get(
        LOCAL_SEARCH_URL, json={"items": [STARBUCKS_ITEM, FAR_ITEM, NEAR_ITEM]}
    )

    response = await _call(
        hass, "search_nearby", {"center": CENTER, "category": "cafe", "radius": 500}
    )

    assert [r["place_name"] for r in response["results"]] == ["스타벅스 삼평점", "스타벅스 판교점"]
    assert [r["distance"] for r in response["results"]] == [22, 111]
    search_url = aioclient_mock.mock_calls[1][1]
    assert search_url.query["query"] == "성남시 분당구 삼평동 카페"


async def test_search_nearby_by_query_without_region(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """With no region for the center, the bare query is searched."""
    aioclient_mock.get(REVERSE_GEOCODE_URL, json={"status": {"code": 3}, "results": []})
    aioclient_mock.get(LOCAL_SEARCH_URL, json={"items": [STARBUCKS_ITEM]})

    response = await _call(hass, "search_nearby", {"center": CENTER, "query": "스타벅스"})

    assert len(response["results"]) == 1
    assert aioclient_mock.mock_calls[1][1].query["query"] == "스타벅스"


async def test_search_nearby_all_outside_radius(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """When every result is outside the radius, no_results is raised."""
    aioclient_mock.get(REVERSE_GEOCODE_URL, json=REGION_RESPONSE)
    aioclient_mock.get(LOCAL_SEARCH_URL, json={"items": [FAR_ITEM]})

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "search_nearby", {"center": CENTER, "query": "스타벅스"})

    assert err.value.translation_key == "no_results"


@pytest.mark.parametrize(
    "extra", [{}, {"category": "cafe", "query": "스타벅스"}], ids=["neither", "both"]
)
async def test_search_nearby_requires_exactly_one_of_category_or_query(
    hass: HomeAssistant, extra: dict
) -> None:
    """Passing neither or both of category/query is rejected."""
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "search_nearby", {"center": CENTER, **extra})

    assert err.value.translation_key == "nearby_input"


async def test_geocode_address_returns_best_match(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """geocode_address returns the first NCP geocode match."""
    aioclient_mock.get(GEOCODE_URL, json={"status": "OK", "addresses": [ADDRESS_ITEM]})

    response = await _call(hass, "geocode_address", {"query": "불정로 6"})

    assert response["zone_no"] == "13561"
    assert response["latitude"] == 37.3595316
    assert aioclient_mock.mock_calls[0][3]["x-ncp-apigw-api-key"] == "ncp-key"


async def test_geocode_address_no_results(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An address with no match raises no_results."""
    aioclient_mock.get(GEOCODE_URL, json={"status": "OK", "addresses": []})

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "geocode_address", {"query": "없는주소"})

    assert err.value.translation_key == "no_results"


async def test_get_directions_car_populates_eta_and_link(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Car mode uses Directions 5 and returns link, legs, duration, and arrival time."""
    aioclient_mock.get(
        DRIVING_URL,
        json={
            "code": 0,
            "route": {"traoptimal": [{"summary": {"duration": 900000, "distance": 12000}}]},
        },
    )
    hass.states.async_set(
        "zone.office", "0", {"latitude": 37.4, "longitude": 127.1, "friendly_name": "회사"}
    )
    before = dt_util.now()

    response = await _call(
        hass,
        "get_directions",
        {
            "origin": {"latitude": 37.5665, "longitude": 126.978},
            "destination": "zone.office",
            "waypoints": [{"latitude": 37.5, "longitude": 127.0}],
        },
    )

    assert response["mode"] == "car"
    assert response["duration"] == 900
    assert response["distance"] == 12000
    arrival = dt_util.parse_datetime(response["arrival_time"])
    assert before + timedelta(seconds=900) <= arrival
    assert response["route_url"].startswith("https://map.naver.com/p/directions/")
    assert response["route_url"].endswith("/car")
    assert [(leg["from"], leg["to"]) for leg in response["legs"]] == [
        ("출발지", "경유지1"),
        ("경유지1", "회사"),
    ]
    assert aioclient_mock.mock_calls[0][1].query["waypoints"] == "127.0,37.5"


async def test_get_directions_car_failure_keeps_link(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A failed driving lookup leaves ETA fields null but still returns the link."""
    aioclient_mock.get(DRIVING_URL, status=500, json={"code": 3})

    response = await _call(
        hass,
        "get_directions",
        {
            "origin": {"latitude": 37.5665, "longitude": 126.978},
            "destination": {"latitude": 37.4, "longitude": 127.1},
        },
    )

    assert response["duration"] is None
    assert response["distance"] is None
    assert response["arrival_time"] is None
    assert response["route_url"].endswith("/-/car")


async def test_get_directions_transit_adds_transfers_and_fare(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Transit mode adds transfers and fare from the internal transit endpoint."""
    aioclient_mock.get(
        TRANSIT_ROUTE_URL,
        json={"paths": [{"duration": 50, "distance": 24700, "fare": 3200, "transferCount": 0}]},
    )

    response = await _call(
        hass,
        "get_directions",
        {
            "origin": {"latitude": 37.5665, "longitude": 126.978},
            "destination": {"latitude": 37.3945, "longitude": 127.1112},
            "mode": "transit",
        },
    )

    assert response["duration"] == 3000
    assert response["transfers"] == 0
    assert response["fare"] == 3200
    assert response["route_url"].endswith("/transit")


async def test_get_directions_transit_rejects_waypoints(hass: HomeAssistant) -> None:
    """Transit mode does not accept waypoints."""
    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass,
            "get_directions",
            {
                "origin": {"latitude": 37.5, "longitude": 127.0},
                "destination": {"latitude": 37.4, "longitude": 127.1},
                "waypoints": [{"latitude": 37.45, "longitude": 127.05}],
                "mode": "transit",
            },
        )

    assert err.value.translation_key == "transit_no_waypoints"


async def test_get_directions_rejects_more_than_five_waypoints(hass: HomeAssistant) -> None:
    """More than five waypoints is rejected before any lookup."""
    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass,
            "get_directions",
            {
                "origin": {"latitude": 37.5, "longitude": 127.0},
                "destination": {"latitude": 37.4, "longitude": 127.1},
                "waypoints": [{"latitude": 37.45, "longitude": 127.05}] * 6,
            },
        )

    assert err.value.translation_key == "too_many_waypoints"
    assert err.value.translation_placeholders == {"count": "6", "max": "5"}


async def test_get_directions_walk_routes_through_waypoints(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Walk mode sends every point to the walk endpoint and returns its ETA."""
    aioclient_mock.get(
        WALK_ROUTE_URL, json={"routes": [{"summary": {"duration": 1047, "distance": 876}}]}
    )

    response = await _call(
        hass,
        "get_directions",
        {
            "origin": {"latitude": 37.4979, "longitude": 127.0276},
            "destination": {"latitude": 37.5006, "longitude": 127.0364},
            "waypoints": [{"latitude": 37.499, "longitude": 127.03}],
            "mode": "walk",
        },
    )

    assert response["duration"] == 1047
    assert aioclient_mock.mock_calls[0][1].query["l"].count(";") == 2
    assert response["route_url"].endswith("/walk")


async def test_get_directions_bicycle_populates_eta(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Bicycle mode without waypoints uses the bike endpoint; the link mode is `bike`."""
    aioclient_mock.get(
        BIKE_ROUTE_URL, json={"routes": [{"summary": {"duration": 208, "distance": 821}}]}
    )

    response = await _call(
        hass,
        "get_directions",
        {
            "origin": {"latitude": 37.4979, "longitude": 127.0276},
            "destination": {"latitude": 37.5006, "longitude": 127.0364},
            "mode": "bicycle",
        },
    )

    assert response["duration"] == 208
    assert response["route_url"].endswith("/-/bike")


async def test_get_directions_bicycle_with_waypoints_skips_eta(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Bicycle mode with waypoints is link-only (no lookup is made)."""
    response = await _call(
        hass,
        "get_directions",
        {
            "origin": {"latitude": 37.4979, "longitude": 127.0276},
            "destination": {"latitude": 37.5006, "longitude": 127.0364},
            "waypoints": [{"latitude": 37.499, "longitude": 127.03}],
            "mode": "bicycle",
        },
    )

    assert response["duration"] is None
    assert aioclient_mock.call_count == 0


async def test_services_removed_on_unload(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Unloading the entry removes every naver_map service."""
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.async_services_for_domain(DOMAIN)


async def test_get_directions_geometry_only_when_requested(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """include_geometry=true adds `geometry` as [lat, lng] lists; it is absent by default."""
    aioclient_mock.get(
        DRIVING_URL,
        json={
            "code": 0,
            "route": {
                "traoptimal": [
                    {
                        "summary": {"duration": 900000, "distance": 12000},
                        "path": [[126.978, 37.5665], [127.1, 37.4]],
                    }
                ]
            },
        },
    )
    data = {
        "origin": {"latitude": 37.5665, "longitude": 126.978},
        "destination": {"latitude": 37.4, "longitude": 127.1},
    }

    default = await _call(hass, "get_directions", data)
    with_geometry = await _call(hass, "get_directions", {**data, "include_geometry": True})

    assert "geometry" not in default
    assert with_geometry["geometry"] == [[37.5665, 126.978], [37.4, 127.1]]


async def test_get_directions_geometry_null_without_lookup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Bicycle with waypoints makes no lookup, so a requested geometry is null."""
    response = await _call(
        hass,
        "get_directions",
        {
            "origin": {"latitude": 37.4979, "longitude": 127.0276},
            "destination": {"latitude": 37.5006, "longitude": 127.0364},
            "waypoints": [{"latitude": 37.499, "longitude": 127.03}],
            "mode": "bicycle",
            "include_geometry": True,
        },
    )

    assert response["geometry"] is None


async def test_get_directions_steps_only_when_requested(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """include_steps=true adds `steps`; it is absent by default."""
    aioclient_mock.get(
        DRIVING_URL,
        json={
            "code": 0,
            "route": {
                "traoptimal": [
                    {
                        "summary": {"duration": 900000, "distance": 12000},
                        "guide": [{"instructions": "우회전", "distance": 300, "duration": 60000}],
                    }
                ]
            },
        },
    )
    data = {
        "origin": {"latitude": 37.5665, "longitude": 126.978},
        "destination": {"latitude": 37.4, "longitude": 127.1},
    }

    default = await _call(hass, "get_directions", data)
    with_steps = await _call(hass, "get_directions", {**data, "include_steps": True})

    assert "steps" not in default
    assert with_steps["steps"] == [{"instruction": "우회전", "distance": 300, "duration": 60}]


async def test_get_directions_transit_alternatives_only_when_requested(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """include_alternatives lists every transit route; the top level stays the first one."""
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
                    "vehicleTypes": ["SUBWAY"],
                    "pathLabels": [{"labelCode": "BEST"}],
                    "legs": [{"steps": [{"points": [{"x": 127.0, "y": 37.5}]}]}],
                },
                {
                    "duration": 50,
                    "distance": 9000,
                    "fare": 1500,
                    "transferCount": 0,
                    "vehicleTypes": ["BUS"],
                    "pathLabels": [{"labelCode": "MINIMUM_TRANSFER"}],
                },
            ]
        },
    )
    data = {
        "origin": {"latitude": 37.5665, "longitude": 126.978},
        "destination": {"latitude": 37.3945, "longitude": 127.1112},
        "mode": "transit",
    }

    default = await _call(hass, "get_directions", data)
    response = await _call(
        hass, "get_directions", {**data, "include_alternatives": True, "include_geometry": True}
    )

    assert "alternatives" not in default
    assert response["duration"] == 2160
    first, second = response["alternatives"]
    assert first["labels"] == ["best"]
    assert first["geometry"] == [[37.5, 127.0]]
    assert first["walking_duration"] == 720
    assert second == {
        "duration": 3000,
        "distance": 9000,
        "transfers": 0,
        "fare": 1500,
        "walking_duration": None,
        "departure_time": None,
        "arrival_time": None,
        "vehicle_types": ["bus"],
        "labels": ["minimum_transfer"],
        "geometry": None,
    }


async def test_get_directions_alternatives_null_for_other_modes(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Only transit has alternative routes; other modes report null."""
    aioclient_mock.get(
        WALK_ROUTE_URL, json={"routes": [{"summary": {"duration": 1047, "distance": 876}}]}
    )

    response = await _call(
        hass,
        "get_directions",
        {
            "origin": {"latitude": 37.4979, "longitude": 127.0276},
            "destination": {"latitude": 37.5006, "longitude": 127.0364},
            "mode": "walk",
            "include_alternatives": True,
        },
    )

    assert response["alternatives"] is None


PLACE_DETAILS = {
    "place_id": "1086067689",
    "place_name": "스타벅스 강남R점",
    "category": "카페",
    "address": "서울 강남구 역삼동 825",
    "road_address": "서울 강남구 강남대로 390 (역삼동)",
    "latitude": 37.497711,
    "longitude": 127.028439,
    "business_hours": "22:00에 영업 종료",
    "visitor_review_count": 8266,
    "blog_review_count": 1064,
    "images": ["https://ldb-phinf.pstatic.net/a.png", "https://ldb-phinf.pstatic.net/b.jpg"],
    "booking": False,
    "order": True,
    "delivery": False,
    "naver_pay": True,
    "place_url": "https://map.naver.com/p/entry/place/1086067689",
}


async def test_get_place_details_by_query_matches_name_near_point(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A query resolves to the exactly named place near `near`, then its summary."""
    aioclient_mock.get(INSTANT_SEARCH_URL, json=INSTANT_SEARCH_RESPONSE)
    aioclient_mock.get(f"{PLACE_SUMMARY_URL}/1086067689", json=PLACE_SUMMARY_RESPONSE)

    response = await _call(
        hass,
        "get_place_details",
        {"query": "스타벅스 강남R점", "near": {"latitude": 37.4979, "longitude": 127.0276}},
    )

    assert response == PLACE_DETAILS
    assert aioclient_mock.mock_calls[0][1].query["coords"] == "37.4979,127.0276"


async def test_get_place_details_query_defaults_to_home_and_first_result(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Without `near` the home location is used; with no exact name, Naver's first pick."""
    hass.config.latitude, hass.config.longitude = 37.5665, 126.978
    aioclient_mock.get(INSTANT_SEARCH_URL, json=INSTANT_SEARCH_RESPONSE)
    aioclient_mock.get(f"{PLACE_SUMMARY_URL}/1086067689", json=PLACE_SUMMARY_RESPONSE)

    response = await _call(hass, "get_place_details", {"query": "강남 스타벅스"})

    assert response["place_id"] == "1086067689"
    assert aioclient_mock.mock_calls[0][1].query["coords"] == "37.5665,126.978"


async def test_get_place_details_by_place_id(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A place_id skips the autocomplete lookup."""
    aioclient_mock.get(f"{PLACE_SUMMARY_URL}/1086067689", json=PLACE_SUMMARY_RESPONSE)

    response = await _call(hass, "get_place_details", {"place_id": "1086067689"})

    assert response == PLACE_DETAILS
    assert aioclient_mock.call_count == 1


async def test_get_place_details_requires_exactly_one_of_query_or_place_id(
    hass: HomeAssistant,
) -> None:
    """Neither (or both) of query/place_id is a validation error."""
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "get_place_details", {})

    assert err.value.translation_key == "place_input"


async def test_get_place_details_no_match(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An autocomplete answer without places raises no_results."""
    aioclient_mock.get(INSTANT_SEARCH_URL, json={"ac": [], "place": []})

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "get_place_details", {"query": "없는장소"})

    assert err.value.translation_key == "no_results"


async def test_get_place_details_blocked_lookup_is_api_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A CAPTCHA-gated (or otherwise unreadable) lookup raises api_error."""
    aioclient_mock.get(INSTANT_SEARCH_URL, json=CAPTCHA_RESPONSE)

    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, "get_place_details", {"query": "스타벅스"})

    assert err.value.translation_key == "api_error"
