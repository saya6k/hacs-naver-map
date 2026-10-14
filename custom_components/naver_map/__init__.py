"""The Naver Map integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.llm import async_register_api

from .api import NaverMapRouteApi, NaverPlaceApi, NcpMapsApi
from .const import CONF_NCP_KEY, CONF_NCP_KEY_ID, DOMAIN
from .llm_registration import NaverMapAPI
from .panel import async_register_panel, async_unregister_panel
from .services import NaverClients, async_setup_services, async_unload_services


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Drop the Naver Developers search keys that entries before 1.2 stored."""
    if entry.version == 1 and entry.minor_version < 2:
        data = {key: entry.data[key] for key in (CONF_NCP_KEY_ID, CONF_NCP_KEY)}
        hass.config_entries.async_update_entry(entry, data=data, minor_version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Naver Map from a config entry."""
    session = async_get_clientsession(hass)
    clients = NaverClients(
        maps=NcpMapsApi(session, entry.data[CONF_NCP_KEY_ID], entry.data[CONF_NCP_KEY]),
        route=NaverMapRouteApi(session),
        place=NaverPlaceApi(session),
    )
    unregister_llm = async_register_api(hass, NaverMapAPI(hass))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "clients": clients,
        "unregister_llm": unregister_llm,
    }
    async_setup_services(hass, clients)
    await async_register_panel(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Naver Map config entry."""
    store = hass.data[DOMAIN].pop(entry.entry_id, None)
    if store is not None:
        store["unregister_llm"]()
    async_unload_services(hass)
    async_unregister_panel(hass)
    return True
