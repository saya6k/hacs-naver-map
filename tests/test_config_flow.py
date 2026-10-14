"""Tests for the Naver Map config flow."""

from __future__ import annotations

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.translation import async_get_translations

from custom_components.naver_map.const import DOMAIN, GEOCODE_URL
from tests.const import ENTRY_DATA
from tests.vendor.aiohttp_mock import AiohttpClientMocker
from tests.vendor.ha_common import MockConfigEntry

# What entries made before the search keys were dropped may still hold.
LEGACY_DATA = {**ENTRY_DATA, "client_id": "search-id", "client_secret": "search-secret"}


async def _submit(hass: HomeAssistant, data: dict = ENTRY_DATA) -> dict:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    return await hass.config_entries.flow.async_configure(result["flow_id"], data)


async def test_user_flow_creates_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The NCP keys alone pass validation (one geocode call) and create the entry."""
    aioclient_mock.get(GEOCODE_URL, json={"status": "OK", "addresses": []})

    result = await _submit(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Naver Map"
    assert result["data"] == ENTRY_DATA
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][3]["x-ncp-apigw-api-key-id"] == "ncp-id"


async def test_user_form_asks_only_for_the_ncp_keys(hass: HomeAssistant) -> None:
    """The form has the two NCP fields only; the key is a password input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    fields = {str(key): value for key, value in result["data_schema"].schema.items()}

    assert set(fields) == {"ncp_key_id", "ncp_key"}
    assert fields["ncp_key"].config["type"] == "password"


@pytest.mark.parametrize(
    ("geocode_kwargs", "error"),
    [
        ({"status": 401}, "invalid_ncp_auth"),
        ({"exc": aiohttp.ClientError("boom")}, "cannot_connect"),
        ({"exc": TimeoutError()}, "cannot_connect"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, geocode_kwargs: dict, error: str
) -> None:
    """A rejected key or a network error maps to its form error."""
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


async def test_reconfigure_replaces_the_keys(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Reconfigure validates and stores new NCP keys."""
    aioclient_mock.get(GEOCODE_URL, json={"status": "OK", "addresses": []})
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    new = {"ncp_key_id": "new-id", "ncp_key": "new-key"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], new)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert dict(entry.data) == new


async def test_forms_link_to_the_ncp_console_and_say_what_needs_no_keys(
    hass: HomeAssistant,
) -> None:
    """Both forms pass the NCP console URL; their text lists the APIs and keyless routes."""
    user = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id="other")
    entry.add_to_hass(hass)
    reconfigure = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    translations = await async_get_translations(hass, "ko", "config", [DOMAIN])

    for result in (user, reconfigure):
        assert result["description_placeholders"] == {
            "ncp_url": "https://console.ncloud.com/maps/application"
        }
    for step in ("user", "reconfigure"):
        text = translations[f"component.{DOMAIN}.config.step.{step}.description"]
        assert "{ncp_url}" in text
        assert "Geocoding" in text
        assert "Directions 5" in text
        assert "Reverse" not in text  # no longer needed
        assert "대중교통" in text  # transit/walk/bicycle need no keys
        assert "Developers" not in text


async def test_entry_from_before_drops_the_search_keys(hass: HomeAssistant) -> None:
    """Entries saved with the old Naver Developers keys are migrated to the NCP keys only."""
    entry = MockConfigEntry(domain=DOMAIN, data=LEGACY_DATA, unique_id=DOMAIN, minor_version=1)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert dict(entry.data) == ENTRY_DATA
    assert entry.minor_version == 2
