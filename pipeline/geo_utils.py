"""대한민국 주요 비즈니스 권역 및 지리공간(GIS) 유틸리티 모듈"""

import math
import os
from typing import Dict, Tuple, Optional, Any
import requests
from dotenv import load_dotenv

load_dotenv()

# 대한민국 10대 핵심 비즈니스 & 오피스 권역 정의 (위도, 경도)
NATIONWIDE_HUBS: Dict[str, Dict[str, Any]] = {
    "판교": {
        "name": "판교테크노밸리",
        "lat": 37.3947,
        "lng": 127.1112,
        "desc": "IT/게임/바이오 벤처의 중심지 (판교역/유스페이스/H스퀘어)",
    },
    "강남": {
        "name": "강남 / 역삼 / 선릉",
        "lat": 37.4979,
        "lng": 127.0276,
        "desc": "테헤란로 스타트업 및 금융/대기업 밀집 지역 (강남역/역삼역)",
    },
    "여의도": {
        "name": "여의도 금융지구",
        "lat": 37.5215,
        "lng": 126.9242,
        "desc": "증권/금융/방송 및 IFC몰, 더현대 중심가 (여의도역)",
    },
    "을지로": {
        "name": "을지로 / 광화문 / 종로",
        "lat": 37.5663,
        "lng": 126.9827,
        "desc": "전통의 CBD 중심 비즈니스 및 힙지로 상권 (을지로입구/광화문)",
    },
    "성수": {
        "name": "성수 / 뚝섬 / 건대",
        "lat": 37.5445,
        "lng": 127.0560,
        "desc": "트렌디한 소셜 벤처, 디자인, 팝업 및 F&B 핫플레이스 (성수역)",
    },
    "마곡": {
        "name": "마곡 R&D 밸리",
        "lat": 37.5601,
        "lng": 126.8255,
        "desc": "LG, 코오롱 등 대규모 R&D 연구단지 (마곡나루역/발산역)",
    },
    "가산": {
        "name": "가산 / 구로디지털단지",
        "lat": 37.4815,
        "lng": 126.8826,
        "desc": "G밸리 IT/제조/지식산업센터 집적지 (가산디지털단지역)",
    },
    "송도": {
        "name": "송도국제도시",
        "lat": 37.3895,
        "lng": 126.6534,
        "desc": "바이오 클러스터 및 글로벌 비즈니스 단지 (인천대입구역)",
    },
    "부산": {
        "name": "부산 서면 / 해운대 센텀",
        "lat": 35.1578,
        "lng": 129.0593,
        "desc": "동남권 최대 비즈니스 및 해양·관광 중심가 (서면역/센텀시티)",
    },
    "대전": {
        "name": "대전 둔산 / 대덕연구단지",
        "lat": 36.3504,
        "lng": 127.3845,
        "desc": "정부청사 및 R&D 연구기관 집적 행정·과학 허브 (시청역/유성온천)",
    },
}


def calculate_haversine_distance(
    lat1: float, lng1: float, lat2: float, lng2: float
) -> float:
    """
    하버사인(Haversine) 공식을 사용하여 두 위도/경도 좌표 간의 구면 거리(미터 단위)를 계산합니다.
    """
    R = 6371000.0  # 지구 반지름 (미터)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 1)


def geocode_keyword(query: str) -> Optional[Tuple[float, float, str]]:
    """
    카카오 로컬 API를 통해 검색 키워드(예: '삼성역', '부산 센텀')의 위도/경도 및 대표 장소명을 조회합니다.
    API 키가 없거나 실패 시 사전 정의된 허브에서 매칭을 시도합니다.
    """
    query_clean = query.strip()
    if not query_clean:
        return None

    # 1. 사전 정의 허브에서 부분 일치 확인
    for key, info in NATIONWIDE_HUBS.items():
        if key in query_clean or query_clean in key or query_clean in info["name"]:
            return info["lat"], info["lng"], info["name"]

    # 2. 카카오 로컬 API를 통한 실시간 지오코딩
    key = os.getenv("KAKAO_KEY", "").strip()
    if key and "your_" not in key:
        url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        headers = {"Authorization": f"KakaoAK {key}"}
        try:
            res = requests.get(
                url, headers=headers, params={"query": query_clean, "size": 1}, timeout=5
            )
            if res.status_code == 200:
                docs = res.json().get("documents", [])
                if docs:
                    doc = docs[0]
                    return float(doc["y"]), float(doc["x"]), doc["place_name"]
        except Exception:
            pass

    return None
