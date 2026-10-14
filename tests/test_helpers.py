"""Tests for point-input resolution (helpers.resolve_point / resolve_waypoint)."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.naver_map.helpers import (
    ResolvedPoint,
    resolve_point,
    resolve_waypoint,
)


async def test_resolve_entity_with_coordinates(hass: HomeAssistant) -> None:
    """An entity with latitude/longitude resolves to its coords and friendly name."""
    hass.states.async_set(
        "device_tracker.my_phone",
        "home",
        {"latitude": 37.5665, "longitude": 126.978, "friendly_name": "내 폰"},
    )

    point = resolve_point(hass, role="출발지", value="device_tracker.my_phone")

    assert point == ResolvedPoint(name="내 폰", latitude=37.5665, longitude=126.978)


async def test_resolve_entity_without_coordinates(hass: HomeAssistant) -> None:
    """An entity lacking coordinate attributes raises an error naming the entity."""
    hass.states.async_set("sensor.no_location", "on", {"friendly_name": "센서"})

    with pytest.raises(ServiceValidationError) as err:
        resolve_point(hass, role="출발지", value="sensor.no_location")

    assert err.value.translation_key == "entity_missing_coordinates"
    assert err.value.translation_placeholders == {"entity_id": "sensor.no_location"}


async def test_resolve_entity_not_found(hass: HomeAssistant) -> None:
    """An unknown entity_id raises an error naming the entity."""
    with pytest.raises(ServiceValidationError) as err:
        resolve_point(hass, role="도착지", value="zone.nowhere")

    assert err.value.translation_key == "entity_not_found"
    assert err.value.translation_placeholders == {"entity_id": "zone.nowhere"}


async def test_resolve_location_dict(hass: HomeAssistant) -> None:
    """A location mapping resolves with the role as its name."""
    point = resolve_point(hass, role="출발지", value={"latitude": 37.5, "longitude": 127.0})

    assert point == ResolvedPoint(name="출발지", latitude=37.5, longitude=127.0)


async def test_resolve_location_ignores_radius(hass: HomeAssistant) -> None:
    """A radius component in the location mapping is ignored."""
    point = resolve_point(
        hass,
        role="도착지",
        value={"latitude": 37.4, "longitude": 127.1, "radius": 100},
    )

    assert point == ResolvedPoint(name="도착지", latitude=37.4, longitude=127.1)


@pytest.mark.parametrize(
    "value",
    [
        {"latitude": 37.5},
        {"latitude": "abc", "longitude": 127.0},
        [37.5, 127.0],
        42,
    ],
)
async def test_resolve_location_invalid(hass: HomeAssistant, value: object) -> None:
    """A non-entity value without numeric latitude and longitude raises an error."""
    with pytest.raises(ServiceValidationError) as err:
        resolve_point(hass, role="출발지", value=value)

    assert err.value.translation_key == "invalid_location"
    assert err.value.translation_placeholders["role"] == "출발지"


async def test_resolve_missing_value(hass: HomeAssistant) -> None:
    """Omitting the point value raises an error naming the role."""
    with pytest.raises(ServiceValidationError) as err:
        resolve_point(hass, role="도착지")

    assert err.value.translation_key == "point_input_missing"
    assert err.value.translation_placeholders == {"role": "도착지"}


async def test_resolve_waypoint_entity(hass: HomeAssistant) -> None:
    """A waypoint given as an entity_id resolves from its attributes."""
    hass.states.async_set(
        "zone.office",
        "zoning",
        {"latitude": 37.4, "longitude": 127.1, "friendly_name": "회사"},
    )

    point = resolve_waypoint(hass, "zone.office", index=1)

    assert point == ResolvedPoint(name="회사", latitude=37.4, longitude=127.1)


async def test_resolve_waypoint_location(hass: HomeAssistant) -> None:
    """A waypoint given as a location mapping resolves with a numbered name."""
    point = resolve_waypoint(hass, {"latitude": 37.39, "longitude": 127.11}, index=2)

    assert point == ResolvedPoint(name="경유지2", latitude=37.39, longitude=127.11)


@pytest.mark.parametrize("value", [{"latitude": 37.5}, [], 42])
async def test_resolve_waypoint_invalid(hass: HomeAssistant, value: object) -> None:
    """A waypoint that is neither an entity_id nor a valid location raises an error."""
    with pytest.raises(ServiceValidationError) as err:
        resolve_waypoint(hass, value, index=1)

    assert err.value.translation_key == "invalid_location"
    assert err.value.translation_placeholders["role"] == "경유지1"
