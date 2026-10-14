"""Config flow for the Naver Map integration."""

from __future__ import annotations

from functools import partial
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import InvalidApiKey, NaverSearchApi, NcpMapsApi
from .const import CONF_NCP_KEY, CONF_NCP_KEY_ID, DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
        vol.Required(CONF_NCP_KEY_ID): str,
        vol.Required(CONF_NCP_KEY): str,
    }
)

# Any query works for validating the credentials; we only care about the HTTP status.
VALIDATION_QUERY = "네이버"
VALIDATION_ADDRESS = "분당구 불정로 6"


class NaverMapConfigFlow(ConfigFlow, domain=DOMAIN):
    """Collect and validate the Naver Developers and NCP Maps credentials."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the credentials form."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if error := await self._async_validate(user_input):
                errors["base"] = error
            else:
                return self.async_create_entry(title="Naver Map", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, user_input),
            errors=errors,
        )

    async def _async_validate(self, user_input: dict[str, Any]) -> str | None:
        """Make one call with each credential pair; return an error key or None."""
        session = async_get_clientsession(self.hass)
        search = NaverSearchApi(
            session, user_input[CONF_CLIENT_ID], user_input[CONF_CLIENT_SECRET]
        )
        maps = NcpMapsApi(session, user_input[CONF_NCP_KEY_ID], user_input[CONF_NCP_KEY])
        for call, auth_error in (
            (partial(search.async_search_local, VALIDATION_QUERY), "invalid_search_auth"),
            (partial(maps.async_geocode, VALIDATION_ADDRESS), "invalid_ncp_auth"),
        ):
            try:
                await call()
            except InvalidApiKey:
                return auth_error
            except (aiohttp.ClientError, TimeoutError):
                return "cannot_connect"
        return None
