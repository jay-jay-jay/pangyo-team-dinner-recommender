"""카카오 로컬 API를 사용한 판교 음식점 데이터 수집 모듈"""

import os
import sys
import time
from typing import List, Dict, Any, Optional
import requests
from dotenv import load_dotenv

# 윈도우 콘솔 한글 인코딩 안전 처리
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# .env 파일 로드
load_dotenv()

URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

# 판교역 기본 좌표 (위도, 경도)
PANGYO_LAT = 37.3947
PANGYO_LNG = 127.1112


def get_headers() -> Dict[str, str]:
    """카카오 API 인증 헤더를 반환합니다."""
    key = os.getenv("KAKAO_KEY")
    if not key or key.strip() == "" or "your_" in key:
        raise ValueError(
            "[안내] .env 파일에 유효한 KAKAO_KEY가 아직 설정되지 않았습니다.\n"
            "Kakao Developers(https://developers.kakao.com)에서 REST API 키를 발급받아 .env에 입력하시면 실제 데이터를 수집할 수 있습니다."
        )
    return {"Authorization": f"KakaoAK {key.strip()}"}


def search_restaurants(
    query: str,
    x: float = PANGYO_LNG,
    y: float = PANGYO_LAT,
    radius: int = 1500,
    max_pages: int = 3,
) -> List[Dict[str, Any]]:
    """
    카카오 로컬 키워드 검색 API로 특정 위치 주변의 음식점을 검색합니다.

    Args:
        query: 검색할 키워드 (예: '판교 회식', '판교 삼겹살')
        x: 경도 (Longitude) - 기본값: 판교역 경도 (127.1112)
        y: 위도 (Latitude) - 기본값: 판교역 위도 (37.3947)
        radius: 검색 반경 (미터 단위, 최대 20000, 기본값 1500m)
        max_pages: 가져올 최대 페이지 수 (페이지당 최대 15건, 기본값 3페이지 = 최대 45건)

    Returns:
        음식점 정보 딕셔너리 리스트
    """
    try:
        headers = get_headers()
    except ValueError as e:
        print(e)
        return []

    results = []
    for page in range(1, max_pages + 1):
        params = {
            "query": query,
            "category_group_code": "FD6",  # 음식점 카테고리 코드
            "x": str(x),
            "y": str(y),
            "radius": radius,
            "page": page,
            "sort": "distance",
        }
        try:
            res = requests.get(URL, headers=headers, params=params, timeout=10)
            if res.status_code != 200:
                print(f"[API 오류] 상태 코드 {res.status_code}: {res.text}")
                break

            data = res.json()
            docs = data.get("documents", [])
            if not docs:
                break

            results.extend(docs)

            # 마지막 페이지면 루프 종료
            if data.get("meta", {}).get("is_end", True):
                break

            time.sleep(0.2)  # API 과호출 방지용 딜레이

        except Exception as err:
            print(f"[네트워크 오류] 요청 실패: {err}")
            break

    return results


def collect_pangyo_restaurants(
    queries: Optional[List[str]] = None,
    x: float = PANGYO_LNG,
    y: float = PANGYO_LAT,
    radius: int = 1500,
) -> List[Dict[str, Any]]:
    """
    다양한 회식 관련 키워드로 검색하여 중복을 제거한 음식점 목록을 반환합니다.
    """
    if queries is None:
        queries = ["판교 회식", "판교 고깃집", "판교 한식", "판교 일식", "판교 중식", "판교 단체석"]

    all_restaurants = {}
    for q in queries:
        print(f"'{q}' 검색 중...")
        items = search_restaurants(q, x=x, y=y, radius=radius)
        for item in items:
            item_id = item.get("id")
            if item_id and item_id not in all_restaurants:
                all_restaurants[item_id] = item
        time.sleep(0.3)

    print(f"총 {len(all_restaurants)}개의 고유 음식점 수집 완료.")
    return list(all_restaurants.values())


if __name__ == "__main__":
    print("=== 카카오 로컬 API 검색 테스트 ===")
    sample = search_restaurants("판교 회식", x=PANGYO_LNG, y=PANGYO_LAT, max_pages=1)
    if sample:
        print(f"성공적으로 {len(sample)}건 검색됨:")
        for r in sample[:3]:
            print(f"- {r.get('place_name')} ({r.get('category_name')}) / 거리: {r.get('distance')}m")
    else:
        print("검색 결과가 없거나 API 키가 설정되지 않았습니다.")
