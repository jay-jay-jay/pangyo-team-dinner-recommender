"""카카오 로컬 API를 사용한 전국 음식점 데이터 수집 및 지오코딩 모듈"""

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

load_dotenv()

KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category.json"


def get_headers() -> Dict[str, str]:
    """카카오 API 인증 헤더를 반환합니다."""
    key = os.getenv("KAKAO_KEY", "").strip()
    if not key or "your_" in key:
        raise ValueError(
            "[안내] .env 파일에 유효한 KAKAO_KEY가 아직 설정되지 않았습니다.\n"
            "Kakao Developers(https://developers.kakao.com)에서 REST API 키를 발급받아 .env에 입력하시면 실제 데이터를 수집할 수 있습니다."
        )
    return {"Authorization": f"KakaoAK {key}"}


def search_restaurants_nationwide(
    query: str,
    x: float,
    y: float,
    radius: int = 1500,
    max_pages: int = 3,
) -> List[Dict[str, Any]]:
    """
    임의의 위도/경도(x=lng, y=lat) 반경 내 음식점을 검색합니다.

    Args:
        query: 검색할 키워드 (예: '강남역 회식', '서면 고깃집')
        x: 경도 (Longitude)
        y: 위도 (Latitude)
        radius: 검색 반경 (미터 단위, 기본 1500m)
        max_pages: 최대 조회 페이지 수

    Returns:
        수집된 식당 목록
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
            "category_group_code": "FD6",  # 음식점 카테고리
            "x": str(x),
            "y": str(y),
            "radius": radius,
            "page": page,
            "sort": "distance",
        }
        try:
            res = requests.get(KEYWORD_URL, headers=headers, params=params, timeout=10)
            if res.status_code != 200:
                break

            data = res.json()
            docs = data.get("documents", [])
            if not docs:
                break

            results.extend(docs)
            if data.get("meta", {}).get("is_end", True):
                break

            time.sleep(0.2)
        except Exception:
            break

    return results
