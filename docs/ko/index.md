# 네이버 지도 — Home Assistant 통합

> Home Assistant **2026.10.0.dev202609290227** 이상이 필요합니다.

> 영어 문서가 원본입니다 — [English](../en/index.md).

NAVER Cloud Platform Maps와 네이버 지도 웹/내부 API로 **장소 검색**, **주변 검색**,
**주소 좌표 변환**, **길찾기**(네이버 지도 링크 + 소요시간)를 제공하는 Home Assistant 커스텀 통합입니다. 한국 사용자용.

> **지도 타일:** 경로 패널은 Home Assistant 기본 지도(OpenStreetMap 타일) 위에 그립니다. 패널의 레이어 버튼으로 그 위에 네이버 지도 타일을 덮을 수 있으며, 패널에만 적용되고 다른 Home Assistant 지도는 바뀌지 않습니다. [경로 패널](#경로-패널) 참고.

## 기능

- **`search_place`** — 키워드 장소 검색. 상위 5건의 좌표·주소·지도 링크를 반환합니다.
- **`search_nearby`** — 중심 지점(엔티티 또는 좌표) 주변을 카테고리 또는 키워드로 검색. 거리순 정렬, 각 결과에 `distance`(가능하면 네이버 플레이스 `place_id`도) 포함.
- **`geocode_address`** — 주소를 WGS84 좌표로 변환. 가장 일치하는 결과의 지번·도로명 주소, 우편번호, 지도 링크를 반환합니다.
- **`get_place_details`** — 네이버 플레이스 요약: 영업 상태, 리뷰 수, 사진, 예약·주문 여부, 장소 링크.
- **`get_transit_arrivals`** — 버스 정류장·지하철역 실시간 도착(노선별 다음 차량, 남은 시간·정류장).
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

설정 흐름에서 NAVER Cloud Platform 키 한 쌍만 받습니다. 항목은 하나만 등록할 수 있으며, 키는 나중에 **재구성**에서 바꿀 수 있습니다.

| 인증 정보 | 발급처 | 용도 |
|---|---|---|
| **API Key ID / API Key** | [NAVER Cloud Platform](https://console.ncloud.com/maps/application) → Maps → Application, **Geocoding**·**Directions 5** 활성화 | `geocode_address`, `get_directions`(자동차) |

그 밖의 기능은 키가 필요 없습니다. 키워드·주변 검색, 대중교통·도보·자전거 길찾기, 플레이스 정보, 실시간 도착은 네이버 지도 웹(비공식)을 사용하므로, 네이버가 이를 바꾸거나 막으면 동작하지 않을 수 있습니다. 설정 화면에도 같은 내용과 NCP 콘솔 링크가 표시됩니다.

NCP Maps는 월 무료 제공량이 있는 유료 서비스입니다(작성 시점 기준 예: Directions 5 월 6만 회, Geocoding 월 300만 회). 최신 요금은 NCP 콘솔에서 확인하세요. 자동차 길찾기나 주소 변환이 실패하면 [NCP 서비스 상태](https://www.ncloud.com/serviceStatus/)를 확인하세요.

## 경로 패널

통합을 추가하면 사이드바에 **Naver Map** 항목이 생깁니다(관리자가 아닌 사용자도 사용 가능). 탭이 세 개 있습니다.

패널은 지도만 보이는 상태로 열립니다. 탭을 누르면 열리고, 열린 탭을 한 번 더 누르면 완전히 접힙니다(경로선 등 지도에 표시된 것은 유지). 휴대폰 폭에서는 탭이 조작부만 보이는 높이의 하단 시트로 열리고, 결과가 나오면 높아지며, 끌어서 더 높이거나 아래로 내려 접을 수 있습니다. 태블릿·데스크톱에서는 지도 옆 사이드 패널로 열립니다.

**장소 검색** — 장소를 검색하거나, 카테고리(음식점·카페·편의점·약국 등)를 누르면 내 위치(내 person 위치, 없으면 집) 1km 안의 장소가 나옵니다. 모든 결과가 거리와 함께 지도에 표시됩니다. 결과를 고르면 그 위치로 확대하고 네이버 플레이스 요약(사진, 영업 상태, 리뷰 수, 예약·주문 여부)을 보여주며, 네이버 지도에서 열거나 **출발** / **도착**을 눌러 **길찾기** 탭으로 보낼 수 있습니다.

**저장** — Home Assistant 사용자별로 따로 보관되는 내 즐겨찾기입니다(내 기기 간 동기화, 관리자 권한 불필요). 검색 결과에서 **저장**을 누르고, 즐겨찾기를 누르면 네이버 플레이스 요약을 보거나 출발지·도착지로 쓸 수 있습니다(길찾기 탭의 지점 선택 목록에도 즐겨찾기가 나옵니다). Home Assistant 구역도 같은 목록에 나옵니다. **편집**을 누르면 폴더를 만들고, ≡를 끌어 폴더에 넣거나 순서를 바꾸고, 폴더 메뉴로 옮기고, 이름을 바꾸거나 삭제할 수 있습니다. 구역의 이름 변경·삭제는 모든 사용자에게 적용되므로 관리자만 할 수 있고, 관리자는 즐겨찾기를 자동화와 `get_directions`에 쓸 수 있는 수동(passive) 구역(재실 감지에는 쓰이지 않음)으로 바꿀 수도 있습니다.

**길찾기**

1. **출발**과 **도착**을 지정합니다: 장소를 검색해 결과를 고르거나, person / zone / device_tracker 엔티티를 선택하거나, **지도에서 선택**을 누른 뒤 지도를 클릭합니다. 바꾸기 버튼으로 출발·도착을 맞바꿀 수 있습니다.
2. **자동차**, **대중교통**, **도보**, **자전거** 중 하나를 고릅니다.
3. 지도에 경로선이 그려지고 소요 시간·거리·도착 예정 시각(대중교통은 환승·요금 포함)과 네이버 지도에서 같은 경로를 여는 링크가 표시됩니다. 마커를 끌어 지점을 옮기면 잠시 뒤 경로를 다시 조회합니다.
4. **대중교통**은 네이버가 제안하는 모든 경로를 **최적**·**최소시간**·**최소환승**·**최소도보** 표시와 함께 보여주며, 버스/지하철 필터, 정렬, 시각, 환승, 도보 시간, 요금, 노선 색 막대를 제공합니다. 선택한 경로는 지도에 그려지고 승차 구간(노선, 방면, 승·하차 정류장, 정류장 수, 시각, 승차 정류장의 **실시간 도착**과 새로고침 버튼)과 도보 구간을 보여줍니다.
5. **자동차**는 최적·최소시간·무료도로 경로를 보여주며(Directions 5 한 번 호출), 각각 통행료와 유류비가 표시됩니다. 선택한 경로는 지도에 그려지고 회전 안내가 나옵니다. 도보·자전거의 **상세 경로**에는 회전 안내가 표시됩니다.

지도는 브라우저가 위치를 알려주면 현재 위치(파란 점)에서 시작합니다. 이때 HA가 HTTPS로 접속돼 있어야 하고 위치 권한이 필요하며, Android 컴패니언 앱의 웹뷰는 위치를 알려주지 않습니다. 현재 위치를 못 받으면 내 person 위치, 그것도 없으면 집에서 시작합니다. 위치 버튼으로 다시 가운데로 맞출 수 있고, 카테고리 검색도 같은 위치를 기준으로 합니다.

그 위의 레이어 버튼을 누르면 지도 위에 **네이버 지도 타일**을 덮습니다(다크 모드에서는 네이버 다크 타일). 다시 누르면 OpenStreetMap으로 돌아갑니다. 선택은 브라우저별로 기억되며 기본값은 꺼짐입니다. 타일은 네이버 지도 웹이 쓰는 CDN(비공식, 키 없음)에서 받으므로 네이버가 이를 바꾸거나 막으면 불러오지 못할 수 있고, 그런 자리에는 OpenStreetMap이 그대로 보입니다. WebGL2를 지원하지 않는 기기에서는 버튼이 표시되지 않습니다.

휴대폰·태블릿(Home Assistant 컴패니언 앱 포함)에서는 네이버 지도 링크가 네이버 지도 앱으로 열리며, Android에서 앱이 없으면 Play 스토어가 열립니다. 데스크톱에서는 map.naver.com이 열립니다.

경로선을 가져오지 못하면 지점 사이를 직선으로 잇습니다. 패널 문구는 사용자 언어(한국어 또는 영어)를 따릅니다.

## 서비스

모든 서비스는 응답을 반환하므로 `response_variable`로 받으세요.

### `naver_map.search_place`

네이버 지도 앱처럼 `near`(엔티티 또는 좌표, 기본값: 집) 근처 장소가 먼저 나옵니다.

```yaml
action: naver_map.search_place
data:
  query: 네이버 그린팩토리
  near: person.me                   # 선택, 기본값은 집
response_variable: found
# found.results[]: place_name / latitude / longitude / distance(m) / address /
#                  road_address / map_url / category_name / place_id 또는 place_url
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

동작 방식: 네이버 지도의 (비공개) 자동완성에 중심 좌표 주변의 키워드를 물어 `place_id`가 있는 장소를 **최대 10건** 받고, `radius` 밖의 결과를 제외합니다. 조회가 실패(예: 차단)하면 오류가 납니다.

### `naver_map.geocode_address`

주소를 좌표로 변환합니다. 가장 일치하는 결과 하나를 반환하며, 찾지 못하면 오류가 발생합니다.

```yaml
action: naver_map.geocode_address
data:
  query: 경기도 성남시 분당구 불정로 6
response_variable: geo
# geo: latitude / longitude / address(지번) / road_address / zone_no / map_url
```

### `naver_map.get_place_details`

장소 이름(올바른 지점을 고르기 위한 기준 지점과 함께) 또는 장소 ID로 네이버 플레이스 요약을 조회합니다. 네이버 지도의 비공개 웹 API를 사용하는 best-effort 기능입니다.

```yaml
action: naver_map.get_place_details
data:
  query: 스타벅스 강남R점            # … 또는 place_id: "1086067689"
  near:                             # 선택, 기본값은 집
    latitude: 37.4979
    longitude: 127.0276
response_variable: place
# place: place_id / place_name / category / address / road_address / latitude / longitude /
#        business_hours(영업 상태) / visitor_review_count / blog_review_count / images[] /
#        booking / order / delivery / naver_pay / place_url
```

### `naver_map.get_transit_arrivals`

버스 정류장이나 지하철역(역 ID는 노선별)의 실시간 도착 정보입니다. ID는 `get_directions` 대중교통 단계의 `stop_id`·`route_ids`·`way`에서 가져옵니다. 네이버 지도의 비공개 웹 API를 사용하는 best-effort 기능입니다.

```yaml
action: naver_map.get_transit_arrivals
data:
  type: bus                         # bus | subway
  stop_id: "106041"
  route_ids: ["6025"]               # 선택: 이 노선만
  # direction: up                   # 지하철 전용: up | down
response_variable: realtime
# realtime.arrivals[]: route_id / line / color / direction / running / (지하철) way /
#   vehicles[]: arrival_time / remaining_time(초) / (버스) remaining_stops / congestion /
#               low_floor / (지하철) headsign / express / last
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
  include_steps: false              # true면 회전 안내/승차 구간을 steps로 추가
  include_alternatives: false       # 자동차·대중교통: true면 제안 경로 전체를 추가
response_variable: route
# route: route_url / mode / duration(초) / distance(m) / arrival_time / legs[]
#        (include_geometry 시 + geometry: [[위도, 경도], …] 또는 null)
#        (include_steps 시 + steps: [{instruction, distance, duration, …}] 또는 null;
#         대중교통은 type, lines, color, headsign, from, to, stops, 시각과
#         get_transit_arrivals용 stop_id / route_ids / way 추가)
#        (include_alternatives 시 + alternatives — 자동차: [{duration, distance, arrival_time,
#         toll_fare, fuel_price, labels(best/minimum_duration/toll_free), …}], 대중교통: [{duration, distance, transfers, fare,
#         walking_duration, departure_time, arrival_time, vehicle_types, labels, …}])
```

전체 필드는 `custom_components/naver_map/services.yaml`을 참고하세요.

## Assist 지원

같은 기능이 LLM 도구 API(`naver_map__search_place`, `naver_map__search_nearby`, `naver_map__geocode_address`, `naver_map__get_directions`, `naver_map__get_place_details`, 그리고 요청한 사용자의 패널 저장 장소를 읽는 `naver_map__get_saved_places` — "자주 가는 카페까지 얼마나 걸려?" 같은 질문이 가능)로도 등록되어, AI 기반 Assist 파이프라인(예: Google Generative AI Conversation, OpenAI Conversation)이 자연어로 호출할 수 있습니다. 대화 에이전트 옵션의 노출 LLM API에서 **Naver Map**을 선택하세요. 장소·주변 검색 결과는 카드를 지원하는 Assist 화면(예: voice-satellite 대시보드)에 시각 카드로도 표시됩니다.

저장 장소는 Home Assistant 사용자별이라, 음성 위성처럼 로그인한 사용자가 없는 요청에서는 `naver_map__get_saved_places`가 아무것도 반환하지 않습니다. 구역은 엔티티이므로 그런 경우에도 쓸 수 있습니다.

MCP 클라이언트는 대화 에이전트 설정과 무관하게 `/api/mcp/naver_map`(관리자 권한 토큰 필요)으로 직접 접근할 수도 있습니다.

## 참고 및 제한 사항

- **자동차 소요시간**은 NCP Directions 5(공식)에서 가져옵니다. **대중교통·도보·자전거** 소요시간은 네이버 지도의 비공개 내부 경로 API에서 가져오며, 예고 없이 바뀌거나 차단될 수 있습니다. 실패 시 `duration` / `distance` / `arrival_time`은 `null`이 되지만 경로 링크(`route_url`)는 항상 반환됩니다.
- **장소 상세 정보**는 네이버 지도의 비공개 웹 API에서 가져옵니다(전체 장소 검색은 캡차로 보호되어 사용하지 않음). 네이버가 연속 요청을 제한하므로 요약은 1시간 캐시하며, 메뉴·전체 영업시간·전화번호·리뷰 본문은 제공되지 않습니다.
- **`mode: transit`**은 경유지를 지원하지 않으며 응답에 `transfers`·`fare`가 추가됩니다.
- **경유지가 있는 `mode: bicycle`**은 링크만 제공합니다(소요시간 `null`).
- **경로선과 세부 단계**는 소요시간과 같은 조회에서 가져오므로 같은 제약을 따르며, 각각 따로 `null`이 될 수 있습니다.
- **경로 패널**: 자동차 모드에서 경로가 바뀔 때마다 유료 NCP API인 Directions 5를 호출합니다. 마커 드래그는 디바운스되며 자동 반복 조회는 하지 않습니다. 패널 URL로 바로 들어오면 프런트엔드 내부 기능으로 HA 지도 구성요소를 불러오므로 프런트엔드 업데이트로 깨질 수 있으며, 그때는 지도 대신 안내 문구를 표시합니다.
- 패널의 **네이버 지도 타일**은 비공식이며 Home Assistant 지도 구성요소의 내부에 접근합니다. 프런트엔드 업데이트로 이것이 바뀌면 레이어 버튼이 사라지고 패널은 OpenStreetMap을 유지합니다. 다른 Home Assistant 지도는 바뀌지 않습니다.

## 개발

실제 Home Assistant로 테스트할 수 있는 devcontainer를 제공합니다. VS Code Dev Containers 확장으로 폴더를 연 뒤 실행하세요:

```bash
scripts/develop
```

HA는 컨테이너 안에서 8123 포트를 사용하며, 호스트 네트워크의 운영 HA와 구분되도록 컨테이너 호스트명은 `hacs-naver-map-dev`입니다. 린트와 테스트는 `scripts/test`로 실행합니다.

## 라이선스

[MIT](../../LICENSE)
