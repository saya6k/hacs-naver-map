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

# map.naver.com instant-search (autocomplete), trimmed to the fields we read.
INSTANT_SEARCH_RESPONSE = {
    "ac": ["강남역 스타벅스"],
    "place": [
        {
            "id": "1086067689",
            "title": "스타벅스 강남R점",
            "x": "127.028439",
            "y": "37.497711",
            "dist": 0.0769,
            "ctg": "카페",
            "roadAddress": "서울특별시 강남구 강남대로 390 (역삼동)",
            "review": {"count": "8266"},
        },
        {
            "id": "1234",
            "title": "스타벅스 강남역점",
            "x": "127.0270",
            "y": "37.4990",
            "dist": 0.2,
            "ctg": "카페",
        },
    ],
}

# map.naver.com place/summary/{id}, trimmed.
PLACE_SUMMARY_RESPONSE = {
    "data": {
        "placeDetail": {
            "id": "1086067689",
            "name": "스타벅스 강남R점",
            "coordinate": {"longitude": 127.028439, "latitude": 37.497711},
            "labels": {
                "booking": False,
                "delivery": False,
                "nPay": True,
                "talktalk": False,
                "order": True,
            },
            "category": {"category": "카페"},
            "address": {
                "address": "서울 강남구 역삼동 825",
                "roadAddress": "서울 강남구 강남대로 390 (역삼동)",
            },
            "businessHours": {"description": "22:00에 영업 종료"},
            "visitorReviews": {"score": None, "displayText": "방문자 리뷰 8,266"},
            "blogReviews": {"total": 1064},
            "images": {
                "images": [
                    {"origin": "https://ldb-phinf.pstatic.net/a.png"},
                    {"origin": "https://ldb-phinf.pstatic.net/b.jpg"},
                ]
            },
        }
    }
}

# What instant-search returns when Naver gates it behind a CAPTCHA.
CAPTCHA_RESPONSE = {"result": {"place": None, "ncaptcha": {"confirmRules": "CE_EMPTY_TOKEN"}}}

# map.naver.com realtime bus arrivals at one stop, trimmed.
BUS_ARRIVALS_RESPONSE = [
    {
        "stopId": 106041,
        "id": 6025,
        "name": "917",
        "type": {"name": "일반", "color": "#87C700"},
        "direction": "논현역",
        "arrival": {
            "status": "RUNNING",
            "referenceTime": "2026-10-14T17:27:44+09:00",
            "buses": [
                {
                    "lowFloor": True,
                    "remainingTime": 120,
                    "remainingStop": 2,
                    "congestion": {"code": "RELAXED", "desc": "여유"},
                    "last": False,
                },
                {
                    "lowFloor": False,
                    "remainingTime": 900,
                    "remainingStop": 9,
                    "congestion": None,
                    "last": True,
                },
            ],
        },
    },
    {
        "stopId": 106041,
        "id": 20037433,
        "name": "3100N",
        "type": {"name": "간선", "color": "#386de8"},
        "direction": "논현역",
        "arrival": {"status": "END", "buses": [], "referenceTime": "2026-10-14T17:27:44+09:00"},
    },
]

# pts.map.naver.com realtime subway arrivals at one station (one line), trimmed.
SUBWAY_ARRIVALS_RESPONSE = [
    {
        "stationId": 222,
        "routeType": {"id": 202, "name": "2호선", "color": "#3cb44a"},
        "upWay": "외선순환",
        "downWay": "내선순환",
        "upWays": [
            {
                "laneId": 2,
                "headsign": "외선순환",
                "arrivalTimeZ": "2099-01-01T08:00:00+09:00",
                "operation": {"type": "NORMAL", "name": "일반"},
                "lastTrip": False,
            }
        ],
        "downWays": [
            {
                "laneId": 2,
                "headsign": "성수",
                "arrivalTimeZ": "2099-01-01T08:05:00+09:00",
                "operation": {"type": "EXPRESS", "name": "급행"},
                "lastTrip": True,
            }
        ],
    }
]
