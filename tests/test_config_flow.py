"""Tests for the Naver Map config flow."""

from __future__ import annotations

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.naver_map.const import DOMAIN, GEOCODE_URL, LOCAL_SEARCH_URL
from tests.const import ENTRY_DATA
from tests.vendor.aiohttp_mock import AiohttpClientMocker
from tests.vendor.ha_common import MockConfigEntry


async def _submit(hass: HomeAssistant) -> dict:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    return await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)


async def test_user_flow_creates_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Both credential pairs pass validation and the entry is created."""
    aioclient_mock.get(LOCAL_SEARCH_URL, json={"items": []})
    aioclient_mock.get(GEOCODE_URL, json={"status": "OK", "addresses": []})

    result = await _submit(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Naver Map"
    assert result["data"] == ENTRY_DATA
    assert aioclient_mock.mock_calls[0][3]["X-Naver-Client-Id"] == "search-id"
    assert aioclient_mock.mock_calls[1][3]["x-ncp-apigw-api-key-id"] == "ncp-id"


@pytest.mark.parametrize(
    ("search_kwargs", "geocode_kwargs", "error"),
    [
        ({"status": 401}, {"json": {"addresses": []}}, "invalid_search_auth"),
        ({"json": {"items": []}}, {"status": 401}, "invalid_ncp_auth"),
        ({"exc": aiohttp.ClientError("boom")}, {"json": {"addresses": []}}, "cannot_connect"),
        ({"json": {"items": []}}, {"exc": TimeoutError()}, "cannot_connect"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    search_kwargs: dict,
    geocode_kwargs: dict,
    error: str,
) -> None:
    """Each failing credential pair or network error maps to its form error."""
    aioclient_mock.get(LOCAL_SEARCH_URL, **search_kwargs)
    aioclient_mock.get(GEOCODE_URL, **geocode_kwargs)

    result = await _submit(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_user_flow_aborts_when_already_configured(hass: HomeAssistant) -> None:
    """Only a single Naver Map entry is allowed (manifest single_config_entry)."""
    MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
