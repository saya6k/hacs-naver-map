"""Shared pytest fixtures for the Naver Map integration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp.resolver import AsyncResolver
from homeassistant import core as ha
from homeassistant import loader
from homeassistant.components.http.server import HomeAssistantHTTP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame

from tests.vendor.aiohttp_mock import AiohttpClientMocker, mock_aiohttp_client
from tests.vendor.ha_common import async_test_home_assistant


@pytest.fixture(autouse=True)
async def mock_zeroconf_resolver() -> AsyncGenerator[None]:
    """Avoid real DNS/zeroconf resolution in tests (vendored fixture behavior from phacc)."""
    with patch(
        "homeassistant.helpers.aiohttp_client._async_make_resolver",
        return_value=AsyncResolver(),
    ):
        yield


@pytest.fixture(autouse=True)
def reset_hass_threading_local_object() -> Generator[None]:
    """Reset the _Hass threading.local object for every test (as HA core's conftest does).

    Otherwise it keeps the last test's hass alive until interpreter shutdown,
    where tearing down its config entries' cached orjson Fragments segfaults.
    """
    yield
    ha._hass.__dict__.clear()


@pytest.fixture(autouse=True)
def mock_http_server() -> Generator[None]:
    """Keep the http component (a panel dependency) from binding a real port."""
    with (
        patch.object(HomeAssistantHTTP, "async_bind", AsyncMock()),
        patch.object(HomeAssistantHTTP, "start", AsyncMock()),
        patch.object(HomeAssistantHTTP, "stop", AsyncMock()),
    ):
        yield


@pytest.fixture
async def hass(tmp_path) -> AsyncGenerator[HomeAssistant]:
    """Create a test instance of Home Assistant (vendored harness, see tests/vendor/)."""
    async with async_test_home_assistant(
        asyncio.get_running_loop(), config_dir=str(tmp_path)
    ) as test_hass:
        # HA core's own `hass` fixture does this; without it any `frame.report_usage`
        # call reached during a test raises RuntimeError("Frame helper not set up").
        frame.async_setup(test_hass)
        yield test_hass
        await test_hass.async_stop(force=True)
        frame.async_setup(None)


@pytest.fixture
def aioclient_mock() -> Generator[AiohttpClientMocker]:
    """Fixture to mock aioclient calls."""
    with mock_aiohttp_client() as mock_session:
        yield mock_session


@pytest.fixture
def enable_custom_integrations(hass: HomeAssistant) -> None:
    """Enable custom integrations defined in custom_components/."""
    hass.data.pop(loader.DATA_CUSTOM_COMPONENTS)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of the naver_map custom integration in tests."""
