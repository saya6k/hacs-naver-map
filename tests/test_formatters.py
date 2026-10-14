"""Tests for the response formatters and map.naver.com link builders."""

from __future__ import annotations

from custom_components.naver_map.formatters import address_result, place_result, route_url
from custom_components.naver_map.helpers import ResolvedPoint
from tests.const import ADDRESS_ITEM, STARBUCKS_ITEM


def test_place_result_strips_tags_and_scales_coordinates() -> None:
    """Title highlight tags are removed and mapx/mapy (deg * 1e7) become degrees."""
    assert place_result(STARBUCKS_ITEM) == {
        "place_name": "스타벅스 판교점",
        "latitude": 37.3945,
        "longitude": 127.1112,
        "address": "경기도 성남시 분당구 삼평동 681",
        "road_address": "경기도 성남시 분당구 판교역로 4",
        "category_name": "카페,디저트>카페",
        "place_url": "https://www.starbucks.co.kr/",
        "map_url": "https://map.naver.com/p/search/%EC%8A%A4%ED%83%80%EB%B2%85%EC%8A%A4%20%ED%8C%90%EA%B5%90%EC%A0%90",
    }


def test_place_result_unescapes_entities_and_omits_empty_link() -> None:
    """HTML entities in titles are decoded; an empty `link`/`category` is omitted."""
    item = {**STARBUCKS_ITEM, "title": "A&amp;B <b>카페</b>", "link": "", "category": ""}

    result = place_result(item)

    assert result["place_name"] == "A&B 카페"
    assert "place_url" not in result
    assert "category_name" not in result


def test_address_result_extracts_postal_code() -> None:
    """The geocode item maps to lot/road address, postal code, and coordinates."""
    result = address_result(ADDRESS_ITEM)

    assert result["latitude"] == 37.3595316
    assert result["longitude"] == 127.1052133
    assert result["address"] == ADDRESS_ITEM["jibunAddress"]
    assert result["road_address"] == ADDRESS_ITEM["roadAddress"]
    assert result["zone_no"] == "13561"
    assert result["map_url"].startswith("https://map.naver.com/p/search/")


def test_address_result_without_postal_code() -> None:
    """A missing POSTAL_CODE element yields zone_no None."""
    item = {**ADDRESS_ITEM, "addressElements": []}

    assert address_result(item)["zone_no"] is None


def test_route_url_encodes_points_like_map_naver_com() -> None:
    """Coordinates are base62(deg * 1e7 + 2e9) and the layout is start/goal/via/mode."""
    origin = ResolvedPoint(name="집", latitude=37.5666103, longitude=126.9783882)
    goal = ResolvedPoint(name="회사, 본관", latitude=37.3945, longitude=127.1112)

    url = route_url([origin, goal], "bicycle")

    # 126.9783882 -> 1269783882 + 2000000000 = 3269783882 -> base62 "3zhG9I"
    assert url.startswith("https://map.naver.com/p/directions/3zhG9I,2AM3hd,")
    assert ",%EC%A7%91,,PLACE_POI/" in url
    assert ",%ED%9A%8C%EC%82%AC%20%20%EB%B3%B8%EA%B4%80,,PLACE_POI/" in url
    assert url.endswith("/-/bike")


def test_route_url_joins_waypoints_with_colon() -> None:
    """Waypoints sit between destination and mode, `:`-joined."""
    a = ResolvedPoint(name="a", latitude=37.0, longitude=127.0)
    b = ResolvedPoint(name="b", latitude=37.1, longitude=127.1)
    c = ResolvedPoint(name="c", latitude=37.2, longitude=127.2)
    d = ResolvedPoint(name="d", latitude=37.3, longitude=127.3)

    path = route_url([a, b, c, d], "car").removeprefix("https://map.naver.com/p/directions/")
    start, goal, via, mode = path.split("/")

    assert start.endswith(",a,,PLACE_POI")
    assert goal.endswith(",d,,PLACE_POI")
    assert [p.split(",")[2] for p in via.split(":")] == ["b", "c"]
    assert mode == "car"
