## 이 문서의 목적

Antigravity IDE + GitHub + PowerShell + Streamlit + 크롤링 조합으로 연습 중인 "판교테크노밸리 회식장소 추천 앱"을 실제로 구현하기 위한 데이터셋 확보 방법과 전체 개발 절차를 정리한다. 우선순위 기준은 사용자가 지정한 순서를 따른다.

1. 가격대 / 1인 예산
2. 단체석·룸 유무
3. 판교역·주요 오피스 접근성
4. 평점·리뷰수(신뢰도)

수집 방식은 **공식 API 우선** 원칙을 따르고, 공식 API가 없는 사이트(식신, 캐치테이블, 네이버지도)는 보조 수단으로만 제한적으로 다룬다.

---

## 1. 전체 아키텍처

```
[Antigravity IDE]  코드 작성 (에이전트 보조)
        │
        ▼
[GitHub]            버전 관리 · .env 등 민감정보 제외
        │
        ▼
[PowerShell]         venv 생성 · 패키지 설치 · 스크립트 실행
        │
        ▼
[수집 스크립트 (Python)]
   ├─ 카카오 로컬 API  → 기본 POI, 좌표, 카테고리
   ├─ 네이버 지역/블로그 검색 API → 보조 정보, 리뷰 텍스트
   ├─ 공공데이터포털 → 인허가 정보(좌석수, 주차, 정확 주소)
   └─ (보조, 소량 수동) 식신 / 캐치테이블 / 네이버지도
        │
        ▼
[데이터 정제·통합]  중복 제거 · 거리 계산 · 스키마 통일 → CSV/SQLite
        │
        ▼
[Streamlit 앱]       필터 UI · 우선순위 가중치 조정 · 지도 · 추천 카드
```

Antigravity IDE는 코드 생성과 리팩터링을 에이전트에게 맡기고, PowerShell은 `venv` 활성화와 `streamlit run` 실행을 담당하고, GitHub는 커밋 단위로 "수집 스크립트 → 정제 → UI" 단계를 나눠 올리는 용도로 쓰면 실습 흐름이 자연스럽다.

---

## 2. 사이트별 데이터 수집 전략

| 소스 | 공식 API | 상태 | 활용 방식 |
|---|---|---|---|
| 카카오맵(로컬 API) | 있음 (키워드 장소 검색) | 무료 쿼터 제공, 첫 앱만 무료 | **주력.** 판교 지역 음식점 좌표·카테고리·전화번호·도로명주소 대량 수집 |
| 네이버 검색 API(지역/블로그) | 있음 | 무료 쿼터 제공 | 보조. 블로그 리뷰 존재 여부·리뷰 텍스트로 신뢰도 정보 보완 |
| 공공데이터포털 / 경기데이터드림 | 있음 (인허가 데이터) | 무료 | 보조. 좌석수, 주차장 여부, 정확한 인허가 주소 등 정형 데이터 보완 |
| 식신(siksinhot) | 없음 | 봇 차단 정책 확인됨 | **자동 대량 수집 지양.** 참고 링크만 결과 카드에 노출, 사람이 직접 확인하는 용도로만 사용 |
| 캐치테이블 | 없음(비공식) | SPA + 예약 특화, ToS 상 재게시 제한 소지 | **자동 대량 수집 지양.** "예약 가능 여부"는 캐치테이블 링크로 연결만 하고 자체 DB화하지 않음 |
| 네이버지도 | 지도 자체 크롤링은 별도 API 없이는 위험 | 이용약관·저작권 이슈 소지 | 지도 위젯은 임베드(iframe/스크립트)로만 사용, 업체 리스트 대량 스크래핑은 하지 않음 |

---

## 3. 데이터 스키마 설계

| 필드 | 설명 | 주 출처 |
|---|---|---|
| `restaurant_id` | 고유 ID | 자체 생성 |
| `name` | 상호명 | 카카오 로컬 API |
| `category` | 한식/일식/고깃집 등 | 카카오 로컬 API |
| `address_road` | 도로명 주소 | 카카오 로컬 API / 공공데이터 |
| `lat`, `lng` | 좌표 | 카카오 로컬 API |
| `distance_m_from_hub` | 기준점(판교역 등)까지 거리 | 좌표 기반 계산(haversine) |
| `price_per_person` | 1인 예상 예산(원) | 네이버 블로그 리뷰 텍스트 파싱 또는 수동 태깅 |
| `has_private_room` | 룸 유무(Boolean) | 네이버 블로그/수동 태깅 |
| `group_seating_max` | 단체 수용 인원 | 공공데이터(좌석수) 또는 수동 태깅 |
| `parking_available` | 주차 가능 여부 | 공공데이터 / 카카오 상세정보 |
| `rating` | 평점 | 네이버 지역정보(있는 경우) |
| `review_count` | 리뷰수 | 네이버 블로그 검색 결과수로 근사 |
| `phone` | 전화번호 | 카카오 로컬 API |
| `place_url` | 원본 링크(카카오맵/식신/캐치테이블) | 각 소스 |
| `source` | 데이터 출처 태그 | 자체 |
| `last_updated` | 수집 시각 | 자체 |

---

## 4. 수집 파이프라인 구현

### 4-1. 카카오 로컬 API — 기본 POI 수집

Kakao Developers에서 앱을 만들고 REST API 키를 발급받는다. 판교역 좌표(대략 위도 37.3947, 경도 127.1112)를 기준으로 반경 검색을 돌린다.

```python
import requests
import time

KAKAO_KEY = "여기에_REST_API_키"
HEADERS = {"Authorization": f"KakaoAK {KAKAO_KEY}"}
URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

PANGYO_STATION = (37.3947, 127.1112)  # (lat, lng)

def search_restaurants(query, x, y, radius=1500):
    results = []
    for page in range(1, 4):  # 페이지당 최대 15건, 최대 45건
        params = {
            "query": query,
            "category_group_code": "FD6",  # 음식점 카테고리
            "x": x, "y": y,
            "radius": radius,
            "page": page,
            "sort": "distance",
        }
        res = requests.get(URL, headers=HEADERS, params=params)
        data = res.json()
        docs = data.get("documents", [])
        if not docs:
            break
        results.extend(docs)
        if data["meta"]["is_end"]:
            break
        time.sleep(0.2)
    return results

queries = ["판교 회식", "판교 고깃집", "판교 한식", "판교 일식", "판교 단체석"]
all_rows = []
for q in queries:
    all_rows += search_restaurants(q, PANGYO_STATION[1], PANGYO_STATION[0])
```

### 4-2. 거리 계산(접근성 점수용)

```python
from math import radians, sin, cos, sqrt, atan2

def haversine(lat1, lng1, lat2, lng2):
    R = 6371000  # meters
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))
```

### 4-3. 네이버 검색 API — 리뷰 신뢰도 보완

```python
import requests

NAVER_ID = "Client_ID"
NAVER_SECRET = "Client_Secret"
HEADERS = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}

def naver_blog_review_count(name, address_hint="판교"):
    url = "https://openapi.naver.com/v1/search/blog.json"
    params = {"query": f"{address_hint} {name} 회식", "display": 1}
    res = requests.get(url, headers=HEADERS, params=params)
    return res.json().get("total", 0)
```

### 4-4. 공공데이터 보완(선택)
공공데이터포털 또는 경기데이터드림에서 "일반음식점 인허가" 데이터를 내려받아 좌석수·주차장 여부 등을 결합.

### 4-5. 통합 및 저장
세 출처를 상호명 유사도로 병합하고 `data/restaurants.csv`로 저장.

---

## 5. 우선순위 기반 추천 스코어링

| 기준 | 가중치(초기값) | 정규화 방법 |
|---|---|---|
| 가격대 적합도 | 35% | 사용자가 입력한 목표 예산과의 차이가 작을수록 높은 점수 |
| 룸/단체석 유무 | 30% | `has_private_room` True + `group_seating_max` ≥ 인원수 → 만점, 둘 중 하나만 충족 시 절반 |
| 접근성(거리) | 20% | `distance_m_from_hub`를 0~1로 min-max 정규화 후 역수 처리(가까울수록 고득점) |
| 평점/리뷰수 | 15% | 평점과 리뷰수를 각각 정규화해 평균 |

```python
def score_row(row, budget, headcount, weights):
    price_score = max(0, 1 - abs(row.price_per_person - budget) / budget)
    room_score = 1.0 if row.has_private_room and row.group_seating_max >= headcount else (
        0.5 if row.has_private_room or row.group_seating_max >= headcount else 0
    )
    access_score = 1 - min(row.distance_m_from_hub / 3000, 1)  # 3km 밖은 0점
    rating_score = (row.rating / 5) * 0.6 + min(row.review_count / 100, 1) * 0.4

    return (
        weights["price"] * price_score
        + weights["room"] * room_score
        + weights["access"] * access_score
        + weights["rating"] * rating_score
    )
```

---

## 6. Streamlit 앱 — GBSA 색상 톤 적용

```python
GBSA_COLORS = {
    "primary_blue": "#0B4F9E",   # 메인 블루
    "sky_blue": "#4FA8DE",       # 서브 강조
    "sky_tint": "#EAF4FC",       # 카드/배경 은은한 하늘색
    "white": "#FFFFFF",
    "gray_text": "#3A4552",      # 본문 텍스트
    "gray_border": "#D9E1E8",    # 구분선, 카드 테두리
}
```

---

## 10. 추가 기능: 참석 가능 날짜 필터 + 메뉴 카테고리 필터

### 10-1. 스키마 확장
- `cuisine_type`: 한식 / 중식 / 일식 / 양식 / 기타
- `closed_days`: 정기 휴무 요일 (예: `일`, `월,일`)

### 10-2. 메뉴 카테고리 자동 분류
```python
CUISINE_KEYWORDS = {
    "한식": ["한식", "고기", "삼겹살", "국밥", "찌개", "곱창", "냉면", "한정식", "족발", "보쌈", "닭갈비"],
    "중식": ["중식", "중국요리", "짬뽕", "탕수육", "마라"],
    "일식": ["일식", "스시", "초밥", "라멘", "이자카야", "우동", "돈카츠"],
    "양식": ["양식", "이탈리안", "파스타", "스테이크", "피자", "브런치"],
}

def classify_cuisine(category_name: str) -> str:
    for cuisine, keywords in CUISINE_KEYWORDS.items():
        if any(k in category_name for k in keywords):
            return cuisine
    return "기타"
```
