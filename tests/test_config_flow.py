"""Tests for the Naver Map config flow."""

from __future__ import annotations

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.translation import async_get_translations

from custom_components.naver_map.const import (
    CONF_NCP_KEY,
    CONF_NCP_KEY_ID,
    DOMAIN,
    GEOCODE_URL,
    LOCAL_SEARCH_URL,
)
from tests.const import ENTRY_DATA
from tests.vendor.aiohttp_mock import AiohttpClientMocker
from tests.vendor.ha_common import MockConfigEntry

NCP_ONLY = {CONF_NCP_KEY_ID: "ncp-id", CONF_NCP_KEY: "ncp-key"}


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


async def test_user_flow_without_search_keys_creates_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The search keys are optional: NCP keys alone create the entry (only NCP is checked)."""
    aioclient_mock.get(GEOCODE_URL, json={"status": "OK", "addresses": []})

    result = await _submit(hass, NCP_ONLY)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == NCP_ONLY
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize("partial", [{"client_id": "search-id"}, {"client_secret": "x"}])
async def test_user_flow_rejects_half_a_search_key_pair(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, partial: dict
) -> None:
    """A Client ID without its secret (or the reverse) is an error, before any call."""
    result = await _submit(hass, {**NCP_ONLY, **partial})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "search_keys_incomplete"}
    assert aioclient_mock.call_count == 0


async def test_user_form_explains_what_skipping_search_keys_loses(hass: HomeAssistant) -> None:
    """The form's translations say what leaving the search keys empty gives up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    translations = await async_get_translations(hass, "ko", "config", [DOMAIN])
    prefix = f"component.{DOMAIN}.config.step.user"

    assert result["step_id"] == "user"
    assert "비공식" in translations[f"{prefix}.description"]
    assert "선택" in translations[f"{prefix}.data_description.client_id"]


async def test_reconfigure_adds_and_removes_search_keys(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Reconfigure replaces the credentials, so search keys can be added or dropped later."""
    aioclient_mock.get(LOCAL_SEARCH_URL, json={"items": []})
    aioclient_mock.get(GEOCODE_URL, json={"status": "OK", "addresses": []})
    entry = MockConfigEntry(domain=DOMAIN, data=NCP_ONLY, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    for data in (ENTRY_DATA, NCP_ONLY):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        )
        assert result["step_id"] == "reconfigure"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], data)

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert dict(entry.data) == data


async def test_secret_fields_are_masked(hass: HomeAssistant) -> None:
    """The NCP key and the client secret use password inputs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    fields = {str(key): value for key, value in result["data_schema"].schema.items()}

    for name in ("ncp_key", "client_secret"):
        assert fields[name].config["type"] == "password", name
