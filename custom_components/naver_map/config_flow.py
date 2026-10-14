"""Config flow for the Naver Map integration."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import InvalidApiKey, NcpMapsApi
from .const import CONF_NCP_KEY, CONF_NCP_KEY_ID, DOMAIN

# The NAVER Cloud Platform Maps keys are the only credentials: keyword and
# nearby search, transit/walk/bicycle routes, place details, and live arrivals
# all use Naver Map's (unofficial) web endpoints, which take no keys.
STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NCP_KEY_ID): str,
        vol.Required(CONF_NCP_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

# Where the keys are issued; passed into the form text as a placeholder
# (translation strings must not contain URLs themselves).
KEY_LINKS = {"ncp_url": "https://console.ncloud.com/maps/application"}

# Any address works for validating the key; we only care about the HTTP status.
VALIDATION_ADDRESS = "분당구 불정로 6"


class NaverMapConfigFlow(ConfigFlow, domain=DOMAIN):
    """Collect and validate the NCP Maps credentials."""

    VERSION = 1
    # 1.2 dropped the optional Naver Developers search keys (see async_migrate_entry).
    MINOR_VERSION = 2

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
            description_placeholders=KEY_LINKS,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Replace the credentials."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            if error := await self._async_validate(user_input):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input or dict(entry.data)
            ),
            errors=errors,
            description_placeholders=KEY_LINKS,
        )

    async def _async_validate(self, data: dict[str, Any]) -> str | None:
        """Make one geocode call with the keys; return an error key or None."""
        maps = NcpMapsApi(
            async_get_clientsession(self.hass), data[CONF_NCP_KEY_ID], data[CONF_NCP_KEY]
        )
        try:
            await maps.async_geocode(VALIDATION_ADDRESS)
        except InvalidApiKey:
            return "invalid_ncp_auth"
        except (aiohttp.ClientError, TimeoutError):
            return "cannot_connect"
        return None
