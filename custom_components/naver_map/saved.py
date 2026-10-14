"""Read a user's saved places, which the sidebar panel keeps in frontend user data.

The panel writes ``{"version": 1, "tree": [...]}``: folders (one level, with
``children``) and leaves that are either a favorite (``kind: "place"`` with its
own coordinates) or a filed zone (``kind: "zone"``, resolved from its state).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.frontend.storage import async_user_store
from homeassistant.core import HomeAssistant

from .const import SAVED_PLACES_KEY


def _leaf(hass: HomeAssistant, leaf: dict[str, Any], folder: str | None) -> dict[str, Any] | None:
    if leaf.get("kind") == "zone":
        state = hass.states.get(leaf.get("entity_id", ""))
        if state is None:
            return None  # the zone was deleted since it was filed
        return {
            "name": state.attributes.get("friendly_name") or state.entity_id,
            "folder": folder,
            "latitude": state.attributes.get("latitude"),
            "longitude": state.attributes.get("longitude"),
            "entity_id": state.entity_id,
        }
    if leaf.get("kind") != "place":
        return None
    place: dict[str, Any] = {
        "name": leaf.get("name"),
        "folder": folder,
        "latitude": leaf.get("latitude"),
        "longitude": leaf.get("longitude"),
    }
    for key in ("address", "place_id"):
        if leaf.get(key):
            place[key] = leaf[key]
    return place


async def async_saved_places(hass: HomeAssistant, user_id: str | None) -> list[dict[str, Any]]:
    """Return one user's saved places in panel order, flattened with folder names."""
    if not user_id:
        return []
    store = await async_user_store(hass, user_id)
    tree = (store.data.get(SAVED_PLACES_KEY) or {}).get("tree") or []
    places = []
    for node in tree:
        if node.get("kind") == "folder":
            leaves = [(child, node.get("name")) for child in node.get("children") or []]
        else:
            leaves = [(node, None)]
        for leaf, folder in leaves:
            if (place := _leaf(hass, leaf, folder)) is not None:
                places.append(place)
    return places
