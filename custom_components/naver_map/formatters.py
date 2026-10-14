"""Map Naver API responses to the integration's response schema.

Shared by the services and the LLM tools so both surfaces return identical
place/address shapes and links.
"""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

from .const import DIRECTIONS_LINK_BASE, DIRECTIONS_LINK_MODES, MAP_SEARCH_LINK_BASE
from .helpers import ResolvedPoint

_TAG = re.compile(r"<[^>]+>")

# map.naver.com packs each coordinate as base62(round(deg * 1e7) + 200 * 1e7).
_BASE62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_COORD_SCALE = 10**7
_COORD_OFFSET = 200 * _COORD_SCALE


def _strip_tags(text: str) -> str:
    """Drop the <b> highlight tags and HTML entities local.json puts in titles."""
    return html.unescape(_TAG.sub("", text))


def map_url(name: str) -> str:
    """Build a map.naver.com search link for a place or address."""
    return f"{MAP_SEARCH_LINK_BASE}/{quote(name, safe='')}"


def place_result(item: dict[str, Any]) -> dict[str, Any]:
    """Map a local.json item to the place response schema."""
    name = _strip_tags(item["title"])
    result: dict[str, Any] = {
        "place_name": name,
        # mapx/mapy are WGS84 degrees scaled by 1e7, as integer strings.
        "latitude": int(item["mapy"]) / _COORD_SCALE,
        "longitude": int(item["mapx"]) / _COORD_SCALE,
        "address": item["address"],
        "road_address": item["roadAddress"],
        "map_url": map_url(name),
    }
    if item.get("category"):
        result["category_name"] = item["category"]
    # `link` is the business's own homepage and is often empty.
    if item.get("link"):
        result["place_url"] = item["link"]
    return result


def address_result(item: dict[str, Any]) -> dict[str, Any]:
    """Map an NCP geocode `addresses` item to the geocode_address response schema."""
    address = item["jibunAddress"] or item["roadAddress"]
    zone_no = next(
        (
            element["longName"]
            for element in item.get("addressElements", [])
            if "POSTAL_CODE" in element.get("types", [])
        ),
        None,
    )
    return {
        "latitude": float(item["y"]),
        "longitude": float(item["x"]),
        "address": address,
        "road_address": item["roadAddress"] or None,
        "zone_no": zone_no or None,
        "map_url": map_url(address),
    }


def _encode_coord(value: float) -> str:
    n = round(value * _COORD_SCALE) + _COORD_OFFSET
    out = ""
    while n > 0:
        n, rem = divmod(n, 62)
        out = _BASE62[rem] + out
    return out or _BASE62[0]


def _link_point(point: ResolvedPoint) -> str:
    # Segment layout is `x,y,name,id,type`; commas would break it, so drop them.
    name = quote(point.name.replace(",", " "), safe="")
    return (
        f"{_encode_coord(point.longitude)},{_encode_coord(point.latitude)},"
        f"{name},,PLACE_POI"
    )


def route_url(points: Sequence[ResolvedPoint], mode: str) -> str:
    """Build a map.naver.com directions link: origin, destination, ':'-joined vias, mode."""
    origin, *vias, destination = points
    via = ":".join(_link_point(p) for p in vias) or "-"
    return (
        f"{DIRECTIONS_LINK_BASE}/{_link_point(origin)}/{_link_point(destination)}"
        f"/{via}/{DIRECTIONS_LINK_MODES[mode]}"
    )
