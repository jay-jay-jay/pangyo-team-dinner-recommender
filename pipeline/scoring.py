"""우선순위 기반 회식장소 스코어링 모듈"""

from typing import Dict, Any
import pandas as pd


def safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def score_row(
    row: pd.Series,
    budget: int,
    headcount: int,
    weights: Dict[str, float],
) -> float:
    """
    각 음식점의 조건 적합도 점수(0~100점)를 계산합니다.

    Args:
        row: 식당 정보 행
        budget: 1인 목표 예산 (원)
        headcount: 회식 인원수
        weights: 우선순위 가중치 딕셔너리 {'price': ..., 'room': ..., 'access': ..., 'rating': ...}
    """
    # 1. 가격 적합도 (목표 예산과 차이가 적을수록 만점)
    price = safe_float(row.get("price_per_person"), default=float(budget))
    price_score = max(0.0, 1.0 - abs(price - budget) / max(budget, 1))

    # 2. 룸 / 단체석 수용 적합도
    raw_room = row.get("has_private_room", False)
    if isinstance(raw_room, str):
        has_room = raw_room.strip().lower() in ("true", "1", "yes", "y", "t")
    else:
        has_room = bool(raw_room)

    group_max = safe_int(row.get("group_seating_max"), default=0)

    if has_room and group_max >= headcount:
        room_score = 1.0
    elif has_room or group_max >= headcount:
        room_score = 0.5
    else:
        room_score = 0.1

    # 3. 접근성 점수 (판교역 기준 거리, 3km 밖은 0점)
    dist = safe_float(row.get("distance_m_from_hub"), default=1000.0)
    access_score = max(0.0, 1.0 - min(dist / 3000.0, 1.0))

    # 4. 신뢰도 점수 (평점 60% + 리뷰수 40%)
    rating = safe_float(row.get("rating"), default=4.0)
    review_cnt = safe_float(row.get("review_count"), default=50.0)
    rating_score = (rating / 5.0) * 0.6 + min(review_cnt / 100.0, 1.0) * 0.4

    # 총점 계산 (가중합 정규화, 100점 만점 환산)
    total_w = (
        weights.get("price", 0.35)
        + weights.get("room", 0.30)
        + weights.get("access", 0.20)
        + weights.get("rating", 0.15)
    )
    if total_w == 0:
        total_w = 1.0

    raw_score = (
        weights.get("price", 0.35) * price_score
        + weights.get("room", 0.30) * room_score
        + weights.get("access", 0.20) * access_score
        + weights.get("rating", 0.15) * rating_score
    ) / total_w

    return round(raw_score * 100, 1)
