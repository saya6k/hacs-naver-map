"""Shared config data and canned Naver API payloads for the tests."""

from __future__ import annotations

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET

from custom_components.naver_map.const import CONF_NCP_KEY, CONF_NCP_KEY_ID

ENTRY_DATA = {
    CONF_CLIENT_ID: "search-id",
    CONF_CLIENT_SECRET: "search-secret",
    CONF_NCP_KEY_ID: "ncp-id",
    CONF_NCP_KEY: "ncp-key",
}

STARBUCKS_ITEM = {
    "title": "<b>스타벅스</b> 판교점",
    "link": "https://www.starbucks.co.kr/",
    "category": "카페,디저트>카페",
    "description": "",
    "telephone": "",
    "address": "경기도 성남시 분당구 삼평동 681",
    "roadAddress": "경기도 성남시 분당구 판교역로 4",
    "mapx": "1271112000",
    "mapy": "373945000",
}

ADDRESS_ITEM = {
    "roadAddress": "경기도 성남시 분당구 불정로 6 NAVER그린팩토리",
    "jibunAddress": "경기도 성남시 분당구 정자동 178-1 NAVER그린팩토리",
    "englishAddress": "6, Buljeong-ro, Bundang-gu, Seongnam-si, Gyeonggi-do, Republic of Korea",
    "addressElements": [
        {"types": ["SIDO"], "longName": "경기도", "shortName": "경기도", "code": ""},
        {"types": ["POSTAL_CODE"], "longName": "13561", "shortName": "", "code": ""},
    ],
    "x": "127.1052133",
    "y": "37.3595316",
    "distance": 0.0,
}

REGION_RESPONSE = {
    "status": {"code": 0, "name": "ok", "message": "done"},
    "results": [
        {
            "name": "legalcode",
            "region": {
                "area1": {"name": "경기도"},
                "area2": {"name": "성남시 분당구"},
                "area3": {"name": "삼평동"},
                "area4": {"name": ""},
            },
        }
    ],
}
