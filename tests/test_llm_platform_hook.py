"""Tests for the naver_map `llm/` platform hook (async_get_tools)."""

from __future__ import annotations

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.llm import LLMContext

from custom_components.naver_map.const import DOMAIN
from custom_components.naver_map.llm import async_get_tools
from tests.const import ENTRY_DATA
from tests.vendor.ha_common import MockConfigEntry


def _llm_context() -> LLMContext:
    return LLMContext(
        platform="test", context=Context(), language="ko", assistant="test", device_id=None
    )


async def _setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_async_get_tools_returns_tools_for_naver_map_api(hass: HomeAssistant) -> None:
    """The hook returns naver_map's tools + prompt for our own api_id with a loaded entry."""
    await _setup_integration(hass)

    result = async_get_tools(hass, _llm_context(), DOMAIN)

    assert result is not None
    assert {t.name for t in result.tools} == {
        "naver_map__search_place",
        "naver_map__search_nearby",
        "naver_map__geocode_address",
        "naver_map__get_directions",
        "naver_map__get_place_details",
        "naver_map__get_saved_places",
    }
    assert result.prompt


async def test_async_get_tools_returns_none_for_other_api_id(hass: HomeAssistant) -> None:
    """The hook opts out for any api_id other than naver_map's own."""
    await _setup_integration(hass)

    assert async_get_tools(hass, _llm_context(), "assist") is None


async def test_async_get_tools_returns_none_without_a_loaded_entry(hass: HomeAssistant) -> None:
    """The hook returns None when no naver_map config entry is loaded."""
    assert async_get_tools(hass, _llm_context(), DOMAIN) is None
