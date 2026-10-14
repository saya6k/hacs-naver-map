"""Services when the optional Naver Developers search keys are left out."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.naver_map.const import (
    CONF_NCP_KEY,
    CONF_NCP_KEY_ID,
    DOMAIN,
    INSTANT_SEARCH_URL,
    LOCAL_SEARCH_URL,
    TRANSIT_ROUTE_URL,
)
from tests.const import INSTANT_SEARCH_RESPONSE
from tests.vendor.aiohttp_mock import AiohttpClientMocker
from tests.vendor.ha_common import MockConfigEntry


@pytest.fixture(autouse=True)
async def setup_integration(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Set up an entry with only the NCP keys."""
    hass.config.latitude, hass.config.longitude = 37.4979, 127.0276
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NCP_KEY_ID: "ncp-id", CONF_NCP_KEY: "ncp-key"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _call(hass: HomeAssistant, service: str, data: dict) -> dict:
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True
    )


async def test_search_place_uses_autocomplete_around_home(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Without search keys, a keyword search asks Naver Map's autocomplete near home."""
    aioclient_mock.get(INSTANT_SEARCH_URL, json=INSTANT_SEARCH_RESPONSE)

    response = await _call(hass, "search_place", {"query": "스타벅스 강남"})

    assert [r["place_name"] for r in response["results"]] == [
        "스타벅스 강남R점",
        "스타벅스 강남역점",
    ]
    assert response["results"][0]["place_id"] == "1086067689"
    assert aioclient_mock.mock_calls[0][1].query["coords"] == "37.4979,127.0276"
    assert all(LOCAL_SEARCH_URL not in str(call[1]) for call in aioclient_mock.mock_calls)


async def test_search_place_blocked_autocomplete_is_api_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """With no official search to fall back on, a failed autocomplete is api_error."""
    aioclient_mock.get(INSTANT_SEARCH_URL, status=500)

    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, "search_place", {"query": "스타벅스"})

    assert err.value.translation_key == "api_error"


async def test_search_nearby_has_no_official_fallback(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A failed nearby autocomplete is api_error instead of the local.json fallback."""
    aioclient_mock.get(INSTANT_SEARCH_URL, status=500)

    with pytest.raises(HomeAssistantError) as err:
        await _call(
            hass,
            "search_nearby",
            {"center": {"latitude": 37.4979, "longitude": 127.0276}, "category": "cafe"},
        )

    assert err.value.translation_key == "api_error"
    assert aioclient_mock.call_count == 1


async def test_transit_directions_need_no_search_keys(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Transit (like walk and bicycle) routes use Naver Map's web routes, not the search keys."""
    aioclient_mock.get(
        TRANSIT_ROUTE_URL,
        json={"paths": [{"duration": 50, "distance": 24700, "fare": 3200, "transferCount": 1}]},
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
    assert response["fare"] == 3200
