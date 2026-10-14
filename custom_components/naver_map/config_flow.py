"""Config flow for the Naver Map integration."""

from __future__ import annotations

from functools import partial
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import InvalidApiKey, NaverSearchApi, NcpMapsApi
from .const import CONF_NCP_KEY, CONF_NCP_KEY_ID, DOMAIN

# The NCP Maps keys are required. The Naver Developers search keys are
# optional: without them keyword search relies on Naver Map's unofficial web
# autocomplete alone (the form's description spells out what that gives up).
_SECRET = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NCP_KEY_ID): str,
        vol.Required(CONF_NCP_KEY): _SECRET,
        vol.Optional(CONF_CLIENT_ID): str,
        vol.Optional(CONF_CLIENT_SECRET): _SECRET,
    }
)

# Where the keys are issued; passed into the form text as placeholders
# (translation strings must not contain URLs themselves).
KEY_LINKS = {
    "ncp_url": "https://console.ncloud.com/maps/application",
    "developers_url": "https://developers.naver.com/apps/#/register?api=search",
}

# Any query works for validating the credentials; we only care about the HTTP status.
VALIDATION_QUERY = "네이버"
VALIDATION_ADDRESS = "분당구 불정로 6"


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """Drop empty optional fields so the entry only holds what was given."""
    return {key: value for key, value in user_input.items() if value}


class NaverMapConfigFlow(ConfigFlow, domain=DOMAIN):
    """Collect and validate the NCP Maps and (optional) Naver Developers credentials."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the credentials form."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _clean(user_input)
            if error := await self._async_validate(data):
                errors["base"] = error
            else:
                return self.async_create_entry(title="Naver Map", data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, user_input),
            errors=errors,
            description_placeholders=KEY_LINKS,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Replace the credentials, e.g. to add or drop the search keys later."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _clean(user_input)
            if error := await self._async_validate(data):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input or dict(entry.data)
            ),
            errors=errors,
            description_placeholders=KEY_LINKS,
        )

    async def _async_validate(self, data: dict[str, Any]) -> str | None:
        """Make one call with each given credential pair; return an error key or None."""
        if bool(data.get(CONF_CLIENT_ID)) != bool(data.get(CONF_CLIENT_SECRET)):
            return "search_keys_incomplete"
        session = async_get_clientsession(self.hass)
        checks = []
        if data.get(CONF_CLIENT_ID):
            search = NaverSearchApi(session, data[CONF_CLIENT_ID], data[CONF_CLIENT_SECRET])
            checks.append(
                (partial(search.async_search_local, VALIDATION_QUERY), "invalid_search_auth")
            )
        maps = NcpMapsApi(session, data[CONF_NCP_KEY_ID], data[CONF_NCP_KEY])
        checks.append((partial(maps.async_geocode, VALIDATION_ADDRESS), "invalid_ncp_auth"))
        for call, auth_error in checks:
            try:
                await call()
            except InvalidApiKey:
                return auth_error
            except (aiohttp.ClientError, TimeoutError):
                return "cannot_connect"
        return None
