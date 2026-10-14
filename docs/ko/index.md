# 네이버 지도 — Home Assistant 통합

> Home Assistant **2026.10.0.dev202609290227 이상**이 필요합니다. LLM 도구는 `llm.ToolResult`를 반환하며 기존 응답 필드는 `data`에 유지됩니다.

> 영어 문서가 원본입니다 — [English](../en/index.md).

네이버 검색 API, NAVER Cloud Platform Maps, 네이버 지도 웹/내부 API로 **장소 검색**, **주변 검색**,
**주소 좌표 변환**, **길찾기**(네이버 지도 링크 + 소요시간)를 제공하는 Home Assistant 커스텀 통합입니다. 한국 사용자용.

> **지도 타일 교체는 지원하지 않습니다.** 경로 패널은 Home Assistant 기본 지도(OpenStreetMap 타일) 위에 그리며, 타일을 바꾸거나 HA 프런트엔드 지도를 패치하지 않습니다.

## 기능

- **`search_place`** — 키워드 장소 검색. 상위 5건의 좌표·주소·지도 링크를 반환합니다.
- **`search_nearby`** — 중심 지점(엔티티 또는 좌표) 주변을 카테고리 또는 키워드로 검색. 거리순 정렬, 각 결과에 `distance` 포함.
- **`geocode_address`** — 주소를 WGS84 좌표로 변환. 가장 일치하는 결과의 지번·도로명 주소, 우편번호, 지도 링크를 반환합니다.
- **`get_directions`** — 네이버 지도 경로 링크 + 구간별 지점 + 자동차·대중교통·도보·자전거 소요시간/도착 예정 시각. 지점은 엔티티(person / device_tracker / zone / …) 또는 좌표.
- **경로 패널** — 사이드바 **Naver Map** 패널에서 장소를 검색하고, Home Assistant 기본 지도 위에 경로선을 그리며 소요시간·거리·(대중교통) 환승·요금을 보여줍니다.
- **Assist / AI 도구 지원** — 같은 기능을 AI 대화 에이전트용 LLM 도구 API로도 노출하며, 결과 카드를 시각적으로 표시합니다.
- **한국어·영어** UI 번역.

## 설치 (HACS)

1. HACS → 통합 → ⋮ → **사용자 지정 저장소** — 이 저장소 URL을 카테고리 **Integration**으로 추가.
2. **Naver Map** 설치.
3. Home Assistant 재시작.
4. 설정 → 기기 및 서비스 → **통합 추가** → "Naver Map" 검색.
5. 두 종류의 인증 정보를 입력([설정](#설정) 참고). 각각 1회 호출로 검증합니다.

## 수동 설치

`custom_components/naver_map/`을 HA 설정 폴더의 `custom_components/`에 복사한 뒤 재시작하세요.

## 설정

설정 흐름에서 두 종류의 인증 정보를 받습니다. 항목은 하나만 등록할 수 있습니다.

| 인증 정보 | 발급처 | 용도 |
|---|---|---|
| **Client ID / Client Secret** | [Naver Developers](https://developers.naver.com/apps/) → 애플리케이션 등록 → **검색** API 선택 | `search_place`, `search_nearby` |
| **API Key ID / API Key** | [NAVER Cloud Platform](https://console.ncloud.com/maps/application) → Maps → Application, **Geocoding**·**Reverse Geocoding**·**Directions 5** 활성화 | `geocode_address`, `search_nearby`(지역 조회), `get_directions`(자동차) |

NCP Maps는 월 무료 제공량이 있는 유료 서비스입니다. 최신 요금은 NCP 콘솔에서 확인하세요.

## 경로 패널

통합을 추가하면 사이드바에 **Naver Map** 항목이 생깁니다(관리자가 아닌 사용자도 사용 가능).

1. **출발**과 **도착**을 지정합니다: 장소를 검색해 결과를 고르거나, person / zone / device_tracker 엔티티를 선택하거나, **지도에서 선택**을 누른 뒤 지도를 클릭합니다.
2. **자동차**, **대중교통**, **도보**, **자전거** 중 하나를 고릅니다.
3. 지도에 경로선이 그려지고 소요 시간·거리·도착 예정 시각(대중교통은 환승·요금 포함)과 네이버 지도에서 같은 경로를 여는 링크가 표시됩니다. 마커를 끌어 지점을 옮기면 잠시 뒤 경로를 다시 조회합니다.

경로선을 가져오지 못하면 지점 사이를 직선으로 잇습니다. 패널 문구는 사용자 언어(한국어 또는 영어)를 따릅니다.

## 서비스

모든 서비스는 응답을 반환하므로 `response_variable`로 받으세요.

### `naver_map.search_place`

```yaml
action: naver_map.search_place
data:
  query: 네이버 그린팩토리
response_variable: found
# found.results[]: place_name / latitude / longitude / address / road_address /
#                  map_url / category_name / place_url(홈페이지, 있을 때만)
```

### `naver_map.search_nearby`

중심 지점 주변을 카테고리 **또는** 키워드(둘 중 정확히 하나)로 검색합니다. 각 결과에 `distance`(미터)가 포함됩니다.

```yaml
# 집 반경 1km 카페
action: naver_map.search_nearby
data:
  center: zone.home
  category: cafe       # 아래 목록에서 선택
  radius: 1000
response_variable: cafes
```

```yaml
# 좌표 주변 키워드 검색
action: naver_map.search_nearby
data:
  center:
    latitude: 37.5665
    longitude: 126.978
  query: 스타벅스
  radius: 500
response_variable: nearby
```

카테고리(18종): `cafe`, `restaurant`, `convenience_store`, `supermarket`, `hospital`, `pharmacy`, `subway_station`, `bank`, `gas_station`, `parking`, `academy`, `school`, `daycare`, `cultural_facility`, `real_estate`, `public_institution`, `tourist_attraction`, `accommodation`. UI에서는 현지화된 이름(카페, 맛집, …)으로 표시되며, 각각 한국어 키워드로 검색됩니다.

동작 방식: 네이버 지역 검색 API는 좌표를 받지 않으므로 중심 지점을 역지오코딩해 행정구역(예: `성남시 분당구 삼평동`)을 구하고, 그 지역 안에서 키워드를 검색한 뒤 `radius` 밖의 결과를 제외합니다. 검색 API는 1회 최대 5건만 반환하므로 주변 검색 결과도 **최대 5건**이며, 반경 밖 결과가 있으면 더 적어집니다.

### `naver_map.geocode_address`

주소를 좌표로 변환합니다. 가장 일치하는 결과 하나를 반환하며, 찾지 못하면 오류가 발생합니다.

```yaml
action: naver_map.geocode_address
data:
  query: 경기도 성남시 분당구 불정로 6
response_variable: geo
# geo: latitude / longitude / address(지번) / road_address / zone_no / map_url
```

### `naver_map.get_directions`

```yaml
action: naver_map.get_directions
data:
  origin: person.me                 # 엔티티 …
  destination:                      # … 또는 좌표
    latitude: 37.3595
    longitude: 127.1052
  waypoints:                        # 선택, 최대 5개
    - zone.office
  mode: car                         # car | transit | walk | bicycle
  include_geometry: false           # true면 경로선을 geometry로 추가
response_variable: route
# route: route_url / mode / duration(초) / distance(m) / arrival_time / legs[]
#        (include_geometry 시 + geometry: [[위도, 경도], …] 또는 null)
```

전체 필드는 `custom_components/naver_map/services.yaml`을 참고하세요.

## Assist 지원

같은 네 가지 기능이 LLM 도구 API(`naver_map__search_place`, `naver_map__search_nearby`, `naver_map__geocode_address`, `naver_map__get_directions`)로도 등록되어, AI 기반 Assist 파이프라인(예: Google Generative AI Conversation, OpenAI Conversation)이 자연어로 호출할 수 있습니다. 대화 에이전트 옵션의 노출 LLM API에서 **Naver Map**을 선택하세요. 장소·주변 검색 결과는 카드를 지원하는 Assist 화면(예: voice-satellite 대시보드)에 시각 카드로도 표시됩니다.

MCP 클라이언트는 대화 에이전트 설정과 무관하게 `/api/mcp/naver_map`(관리자 권한 토큰 필요)으로 직접 접근할 수도 있습니다.

## 참고 및 제한 사항

- **자동차 소요시간**은 NCP Directions 5(공식)에서 가져옵니다. **대중교통·도보·자전거** 소요시간은 네이버 지도의 비공개 내부 경로 API에서 가져오며, 예고 없이 바뀌거나 차단될 수 있습니다. 실패 시 `duration` / `distance` / `arrival_time`은 `null`이 되지만 경로 링크(`route_url`)는 항상 반환됩니다.
- **`mode: transit`**은 경유지를 지원하지 않으며 응답에 `transfers`·`fare`가 추가됩니다.
- **경유지가 있는 `mode: bicycle`**은 링크만 제공합니다(소요시간 `null`).
- **경로 패널**: 자동차 모드에서 경로가 바뀔 때마다 유료 NCP API인 Directions 5를 호출합니다. 마커 드래그는 디바운스되며 자동 반복 조회는 하지 않습니다. 패널 URL로 바로 들어오면 프런트엔드 내부 기능으로 HA 지도 구성요소를 불러오므로 프런트엔드 업데이트로 깨질 수 있으며, 그때는 지도 대신 안내 문구를 표시합니다.
- **지도 타일 교체 없음** — 상단 안내 참고.

## 개발

실제 Home Assistant로 테스트할 수 있는 devcontainer를 제공합니다. VS Code Dev Containers 확장으로 폴더를 연 뒤 실행하세요:

```bash
scripts/develop
```

HA는 컨테이너 안에서 8123 포트를 사용하며, 호스트 네트워크의 운영 HA와 구분되도록 컨테이너 호스트명은 `hacs-naver-map-dev`입니다. 린트와 테스트는 `scripts/test`로 실행합니다.

## 라이선스

[MIT](../../LICENSE)
