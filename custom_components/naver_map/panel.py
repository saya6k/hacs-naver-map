"""The Naver Map sidebar panel: serves the panel JS module and registers it."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import async_get_integration

from .const import DOMAIN

PANEL_URL_PATH = "naver-map"
PANEL_ELEMENT = "naver-map-panel"
STATIC_URL = f"/{DOMAIN}_static"
FRONTEND_DIR = Path(__file__).parent / "frontend"
_DATA_STATIC_REGISTERED = f"{DOMAIN}_static_registered"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Serve the frontend directory and add the sidebar panel."""
    # aiohttp routes can't be removed, so the static path outlives entry reloads.
    if not hass.data.get(_DATA_STATIC_REGISTERED):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False)]
        )
        hass.data[_DATA_STATIC_REGISTERED] = True
    integration = await async_get_integration(hass, DOMAIN)
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_ELEMENT,
        sidebar_title="Naver Map",
        sidebar_icon="mdi:map-marker-path",
        module_url=f"{STATIC_URL}/{PANEL_ELEMENT}.js?v={integration.version}",
        embed_iframe=False,
        # The panel keeps its tab bar and controls clear of the safe areas itself;
        # HA's default padding would push the full-height panel past the screen.
        handle_safe_area=True,
        require_admin=False,
    )


@callback
def async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar panel."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
