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
    LOCAL_SEARCH_URL,
    REVERSE_GEOCODE_URL,
    TRANSIT_ROUTE_URL,
    WALK_ROUTE_URL,
)
from tests.const import ADDRESS_ITEM, ENTRY_DATA, REGION_RESPONSE, STARBUCKS_ITEM
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
