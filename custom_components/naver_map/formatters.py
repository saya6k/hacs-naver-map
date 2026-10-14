"""Map Naver API responses to the integration's response schema.

Shared by the services and the LLM tools so both surfaces return identical
place/address shapes and links.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

from .const import (
    DIRECTIONS_LINK_BASE,
    DIRECTIONS_LINK_MODES,
    MAP_SEARCH_LINK_BASE,
    PLACE_LINK_BASE,
)
from .helpers import ResolvedPoint

_NON_DIGIT = re.compile(r"\D")

# map.naver.com packs each coordinate as base62(round(deg * 1e7) + 200 * 1e7).
_BASE62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_COORD_SCALE = 10**7
_COORD_OFFSET = 200 * _COORD_SCALE


def map_url(name: str) -> str:
    """Build a map.naver.com search link for a place or address."""
    return f"{MAP_SEARCH_LINK_BASE}/{quote(name, safe='')}"


def instant_place_result(item: dict[str, Any]) -> dict[str, Any]:
    """Map a map.naver.com autocomplete place to the place response schema (plus place_id)."""
    return {
        "place_name": item["title"],
        "latitude": float(item["y"]),
        "longitude": float(item["x"]),
        "address": item.get("jibunAddress") or "",
        "road_address": item.get("roadAddress") or "",
        "map_url": f"{PLACE_LINK_BASE}/{item['id']}",
        "category_name": item.get("ctg"),
        "place_id": item["id"],
    }


def _count(text: str | None) -> int | None:
    """Read a count out of display text such as "방문자 리뷰 8,266"."""
    digits = _NON_DIGIT.sub("", text or "")
    return int(digits) if digits else None


def place_details_result(detail: dict[str, Any]) -> dict[str, Any]:
    """Map a map.naver.com place summary (`placeDetail`) to the place details schema."""
    address = detail.get("address") or {}
    labels = detail.get("labels") or {}
    images = (detail.get("images") or {}).get("images") or []
    return {
        "place_id": detail["id"],
        "place_name": detail["name"],
        "category": (detail.get("category") or {}).get("category"),
        "address": address.get("address"),
        "road_address": address.get("roadAddress"),
        "latitude": float(detail["coordinate"]["latitude"]),
        "longitude": float(detail["coordinate"]["longitude"]),
        # A one-line status such as "22:00에 영업 종료"; full hours aren't in the summary.
        "business_hours": (detail.get("businessHours") or {}).get("description"),
        "visitor_review_count": _count((detail.get("visitorReviews") or {}).get("displayText")),
        "blog_review_count": (detail.get("blogReviews") or {}).get("total"),
        "images": [image["origin"] for image in images if image.get("origin")],
        "booking": bool(labels.get("booking")),
        "order": bool(labels.get("order")),
        "delivery": bool(labels.get("delivery")),
        "naver_pay": bool(labels.get("nPay")),
        "place_url": f"{PLACE_LINK_BASE}/{detail['id']}",
    }


def bus_arrival_result(item: dict[str, Any]) -> dict[str, Any]:
    """Map one line of a realtime bus arrivals answer to the arrivals schema."""
    arrival = item["arrival"]
    reference = datetime.fromisoformat(arrival["referenceTime"])
    return {
        "route_id": str(item["id"]),
        "line": item["name"],
        "color": (item.get("type") or {}).get("color"),
        "direction": item.get("direction"),
        "running": arrival["status"] == "RUNNING",
        "vehicles": [
            {
                "arrival_time": (reference + timedelta(seconds=bus["remainingTime"])).isoformat(),
                "remaining_time": int(bus["remainingTime"]),
                "remaining_stops": bus.get("remainingStop"),
                "congestion": (bus.get("congestion") or {}).get("desc"),
                "low_floor": bus.get("lowFloor"),
                "last": bool(bus.get("last")),
            }
            for bus in arrival["buses"]
        ],
    }


def _seconds_until(iso: str, now: datetime) -> int:
    return max(0, int((datetime.fromisoformat(iso) - now).total_seconds()))


def subway_arrival_results(item: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    """Map one line of a realtime subway arrivals answer to one entry per direction."""
    line = item["routeType"]
    results = []
    for way in ("up", "down"):
        trains = item[f"{way}Ways"]
        results.append(
            {
                "route_id": str(trains[0]["laneId"]) if trains else None,
                "line": line["name"],
                "color": line.get("color"),
                "direction": item.get(f"{way}Way"),
                "way": way,
                "running": bool(trains),
                "vehicles": [
                    {
                        "arrival_time": train["arrivalTimeZ"],
                        "remaining_time": _seconds_until(train["arrivalTimeZ"], now),
                        "headsign": train.get("headsign"),
                        "express": (train.get("operation") or {}).get("type", "NORMAL") != "NORMAL",
                        "last": bool(train.get("lastTrip")),
                    }
                    for train in trains
                ],
            }
        )
    return results


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
