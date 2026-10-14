"""Tests for the naver_map llm.API shell (NaverMapAPI) and its tools."""

from __future__ import annotations

import pytest
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from custom_components.naver_map.const import (
    DOMAIN,
    DRIVING_URL,
    GEOCODE_URL,
    LOCAL_SEARCH_URL,
    REVERSE_GEOCODE_URL,
)
from tests.const import ADDRESS_ITEM, ENTRY_DATA, REGION_RESPONSE, STARBUCKS_ITEM
from tests.vendor.aiohttp_mock import AiohttpClientMocker
from tests.vendor.ha_common import MockConfigEntry


async def _setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the `llm` integration plus a naver_map config entry."""
    await async_setup_component(hass, "llm", {})
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _llm_context() -> llm.LLMContext:
    return llm.LLMContext(
        platform="test", context=Context(), language="ko", assistant="test", device_id=None
    )


async def _get_api_instance(hass: HomeAssistant) -> llm.APIInstance:
    api = next(a for a in llm.async_get_apis(hass) if a.id == DOMAIN)
    return await api.async_get_api_instance(_llm_context())


async def test_llm_api_registered_with_stable_id(hass: HomeAssistant) -> None:
    """Setting up the entry registers a NaverMapAPI under the stable "naver_map" id."""
    await _setup_integration(hass)

    assert any(a.id == DOMAIN for a in llm.async_get_apis(hass))


async def test_llm_api_instance_has_four_tools_plus_get_date_time(hass: HomeAssistant) -> None:
    """The aggregated instance has naver_map's 4 tools plus the llm integration's GetDateTime."""
    await _setup_integration(hass)

    instance = await _get_api_instance(hass)

    assert {t.name for t in instance.tools} == {
        "naver_map__search_place",
        "naver_map__search_nearby",
        "naver_map__geocode_address",
        "naver_map__get_directions",
        "llm__GetDateTime",
    }
    assert instance.api_prompt


async def test_llm_api_unregistered_on_unload(hass: HomeAssistant) -> None:
    """Unloading the entry unregisters the NaverMapAPI."""
    entry = await _setup_integration(hass)
    assert any(a.id == DOMAIN for a in llm.async_get_apis(hass))

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not any(a.id == DOMAIN for a in llm.async_get_apis(hass))


async def test_search_place_tool_returns_places_and_cards(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_place returns the formatted place list plus one card per result."""
    await _setup_integration(hass)
    aioclient_mock.get(LOCAL_SEARCH_URL, json={"items": [STARBUCKS_ITEM]})
    instance = await _get_api_instance(hass)

    tool = next(tool for tool in instance.tools if tool.name == "naver_map__search_place")
    result = await tool.async_call(
        hass,
        llm.ToolInput(tool_name=tool.name, tool_args={"query": "판교 스타벅스"}),
        _llm_context(),
    )

    assert isinstance(result, llm.ToolResult)
    assert not result.error
    assert result.data["source"] == "naver_map"
    assert result.data["places"][0]["place_name"] == "스타벅스 판교점"
    assert len(result.data["results"]) == 1
    assert result.data["results"][0]["title"] == "스타벅스 판교점"
    assert result.data["results"][0]["image_url"].startswith("data:image/svg+xml;base64,")


async def test_search_place_tool_no_results(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_place raises a validation error when nothing matches."""
    await _setup_integration(hass)
    aioclient_mock.get(LOCAL_SEARCH_URL, json={"items": []})
    instance = await _get_api_instance(hass)

    with pytest.raises(ServiceValidationError) as err:
        await instance.async_call_tool(
            llm.ToolInput(
                tool_name="naver_map__search_place", tool_args={"query": "존재하지않는장소"}
            )
        )

    assert err.value.translation_key == "no_results"


async def test_search_nearby_tool_by_category(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_nearby resolves an entity center and searches by category."""
    await _setup_integration(hass)
    hass.states.async_set(
        "zone.home", "zoning", {"latitude": 37.3935, "longitude": 127.1112, "friendly_name": "집"}
    )
    aioclient_mock.get(REVERSE_GEOCODE_URL, json=REGION_RESPONSE)
    aioclient_mock.get(LOCAL_SEARCH_URL, json={"items": [STARBUCKS_ITEM]})
    instance = await _get_api_instance(hass)

    result = await instance.async_call_tool(
        llm.ToolInput(
            tool_name="naver_map__search_nearby",
            tool_args={"center": "zone.home", "category": "cafe", "radius": 500},
        )
    )

    assert result.data["places"][0]["place_name"] == "스타벅스 판교점"
    assert result.data["places"][0]["distance"] == 111
    assert result.data["center"]["name"] == "집"


async def test_search_nearby_tool_requires_exactly_one_of_category_or_query(
    hass: HomeAssistant,
) -> None:
    """search_nearby rejects a call with neither (or both) category and query."""
    await _setup_integration(hass)
    instance = await _get_api_instance(hass)

    with pytest.raises(ServiceValidationError) as err:
        await instance.async_call_tool(
            llm.ToolInput(
                tool_name="naver_map__search_nearby",
                tool_args={"center": {"latitude": 37.5, "longitude": 127.0}},
            )
        )

    assert err.value.translation_key == "nearby_input"


async def test_geocode_address_tool_returns_result_and_card(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """geocode_address returns the best-match coordinate result plus a card."""
    await _setup_integration(hass)
    aioclient_mock.get(GEOCODE_URL, json={"status": "OK", "addresses": [ADDRESS_ITEM]})
    instance = await _get_api_instance(hass)

    result = await instance.async_call_tool(
        llm.ToolInput(tool_name="naver_map__geocode_address", tool_args={"query": "판교역로 4"})
    )

    assert result.data["latitude"] == 37.3595316
    assert result.data["zone_no"] == "13561"
    assert result.data["featured_image"].startswith("data:image/svg+xml;base64,")


async def test_get_directions_tool_builds_route(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """get_directions resolves coordinate points and returns the route link."""
    await _setup_integration(hass)
    aioclient_mock.get(DRIVING_URL, status=500, json={"code": 3})
    instance = await _get_api_instance(hass)

    result = await instance.async_call_tool(
        llm.ToolInput(
            tool_name="naver_map__get_directions",
            tool_args={
                "origin": {"latitude": 37.5, "longitude": 127.0},
                "destination": {"latitude": 37.4, "longitude": 127.1},
            },
        )
    )

    assert result.data["mode"] == "car"
    assert result.data["duration"] is None
    assert result.data["route_url"].startswith("https://map.naver.com/p/directions/")


async def test_get_directions_tool_never_returns_geometry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The LLM tool omits route geometry and steps even when the lookup returns them."""
    await _setup_integration(hass)
    aioclient_mock.get(
        DRIVING_URL,
        json={
            "code": 0,
            "route": {
                "traoptimal": [
                    {
                        "summary": {"duration": 600000, "distance": 4200},
                        "path": [[127.0, 37.5], [127.1, 37.4]],
                        "guide": [{"instructions": "우회전", "distance": 300, "duration": 60000}],
                    }
                ]
            },
        },
    )
    instance = await _get_api_instance(hass)

    result = await instance.async_call_tool(
        llm.ToolInput(
            tool_name="naver_map__get_directions",
            tool_args={
                "origin": {"latitude": 37.5, "longitude": 127.0},
                "destination": {"latitude": 37.4, "longitude": 127.1},
            },
        )
    )

    assert result.data["duration"] == 600
    assert "geometry" not in result.data
    assert "steps" not in result.data
    assert "alternatives" not in result.data


async def test_get_directions_tool_rejects_too_many_waypoints(hass: HomeAssistant) -> None:
    """get_directions raises a validation error for more than 5 waypoints."""
    await _setup_integration(hass)
    instance = await _get_api_instance(hass)

    with pytest.raises(ServiceValidationError) as err:
        await instance.async_call_tool(
            llm.ToolInput(
                tool_name="naver_map__get_directions",
                tool_args={
                    "origin": {"latitude": 37.5, "longitude": 127.0},
                    "destination": {"latitude": 37.4, "longitude": 127.1},
                    "waypoints": [{"latitude": 37.0 + i, "longitude": 127.0} for i in range(6)],
                },
            )
        )

    assert err.value.translation_key == "too_many_waypoints"


async def test_tools_declare_external_read_only_metadata(hass: HomeAssistant) -> None:
    await _setup_integration(hass)
    instance = await _get_api_instance(hass)
    for tool in instance.tools:
        if not tool.name.startswith("naver_map__"):
            continue
        assert tool.integration == DOMAIN
        assert tool.title
        assert tool.annotations == llm.ToolAnnotations(
            read_only=True, destructive=False, idempotent=True, open_world=True
        )
