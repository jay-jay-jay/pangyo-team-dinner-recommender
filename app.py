import datetime
import os
from typing import Any
import pandas as pd
import streamlit as st
import pydeck as pdk
from pipeline.scoring import score_row, safe_float, safe_int

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="판교테크노밸리 회식장소 추천",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. GBSA (경기도경제과학진흥원) 브랜드 톤 컬러 팔레트
GBSA_COLORS = {
    "primary_blue": "#0B4F9E",  # 메인 네이비 블루
    "sky_blue": "#2E86DE",      # 서브 강조 블루
    "accent_cyan": "#00A8FF",    # 하이라이트 하늘색
    "sky_tint": "#F1F7FD",      # 카드 배경색
    "card_border": "#D2E3F4",   # 카드 테두리
    "badge_bg": "#E1EFFE",      # 배지 배경
    "badge_text": "#1E429F",    # 배지 글자색
    "text_dark": "#2C3E50",     # 제목/본문 진한 색
    "text_muted": "#576574",    # 보조 설명 텍스트
}

# 3. 커스텀 CSS 적용
st.markdown(
    f"""
    <style>
        /* 메인 타이틀 배너 */
        .main-header {{
            background: linear-gradient(135deg, {GBSA_COLORS['primary_blue']} 0%, {GBSA_COLORS['sky_blue']} 100%);
            color: white;
            padding: 24px 28px;
            border-radius: 12px;
            margin-bottom: 24px;
            box-shadow: 0 4px 12px rgba(11, 79, 158, 0.15);
        }}
        .main-header h1 {{
            color: white !important;
            margin: 0;
            font-size: 1.85rem;
            font-weight: 700;
        }}
        .main-header p {{
            color: #E0F2FE;
            margin: 6px 0 0 0;
            font-size: 0.95rem;
        }}

        /* 카드 배지 */
        .custom-badge {{
            display: inline-block;
            background-color: {GBSA_COLORS['badge_bg']};
            color: {GBSA_COLORS['badge_text']};
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 0.8rem;
            font-weight: 600;
            margin-right: 5px;
        }}
        .score-badge {{
            display: inline-block;
            background-color: #E8F5E9;
            color: #2E7D32;
            padding: 3px 10px;
            border-radius: 5px;
            font-size: 0.82rem;
            font-weight: 700;
            margin-right: 5px;
        }}
        .rank-badge {{
            display: inline-block;
            background: linear-gradient(135deg, {GBSA_COLORS['primary_blue']}, {GBSA_COLORS['sky_blue']});
            color: white;
            padding: 3px 10px;
            border-radius: 15px;
            font-size: 0.82rem;
            font-weight: 700;
        }}
        .warn-badge {{
            display: inline-block;
            background-color: #FFF0F0;
            color: #E74C3C;
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 0.78rem;
            font-weight: 600;
        }}
        .open-badge {{
            display: inline-block;
            background-color: #EBFBF2;
            color: #27AE60;
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 0.78rem;
            font-weight: 600;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# 4. 데이터 로드 함수
def load_data() -> pd.DataFrame:
    csv_path = "data/restaurants.csv"
    if not os.path.exists(csv_path):
        st.error("데이터 파일(`data/restaurants.csv`)을 찾을 수 없습니다.")
        return pd.DataFrame()

    df = pd.read_csv(csv_path, encoding="utf-8")
    df["price_per_person"] = pd.to_numeric(df["price_per_person"], errors="coerce").fillna(30000).astype(int)
    df["distance_m_from_hub"] = pd.to_numeric(df["distance_m_from_hub"], errors="coerce").fillna(500.0).astype(float)
    df["group_seating_max"] = pd.to_numeric(df["group_seating_max"], errors="coerce").fillna(20).astype(int)
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").fillna(4.0).astype(float)
    df["review_count"] = pd.to_numeric(df["review_count"], errors="coerce").fillna(50).astype(int)
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    return df


df_raw = load_data()

# 5. 요일 계산 함수 (0=월, 6=일)
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]


def check_open_status(closed_days_str: Any, target_date: datetime.date) -> str:
    if pd.isna(closed_days_str) or not str(closed_days_str).strip():
        return "정보없음"
    closed_list = [d.strip() for d in str(closed_days_str).split(",")]
    target_weekday = WEEKDAY_KR[target_date.weekday()]
    if target_weekday in closed_list:
        return "휴무"
    return "영업"


# 6. 상단 헤더
st.markdown(
    """
    <div class="main-header">
        <h1>🏢 판교테크노밸리 맞춤형 회식장소 추천</h1>
        <p>예산, 인원수, 룸/단체석, 판교역 접근성, 신뢰도 리뷰를 종합 분석하여 최적의 회식 장소를 추천합니다.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# 7. 사이드바 - 조건 및 우선순위 필터링
with st.sidebar:
    st.header("🎯 회식 조건 설정")

    # 1) 회식 날짜
    selected_date = st.date_input(
        "📅 회식 예정일",
        value=datetime.date.today(),
        help="선택한 요일의 정기 휴무 정보를 반영합니다.",
    )
    weekday_name = WEEKDAY_KR[selected_date.weekday()]
    formatted_date_str = f"{selected_date.year}년 {selected_date.month}월 {selected_date.day}일"
    st.caption(f"선택일: **{formatted_date_str} ({weekday_name}요일)**")

    st.markdown("---")

    # 2) 메뉴 카테고리
    cuisine_choice = st.radio(
        "🍽️ 메뉴 카테고리",
        options=["전체", "한식", "중식", "일식", "양식"],
        horizontal=True,
    )

    # 3) 예산 및 인원
    budget = st.slider("💰 1인 목표 예산 (원)", 10000, 100000, 40000, step=5000)
    headcount = st.slider("👥 회식 인원수 (명)", 2, 40, 8)

    st.markdown("---")

    # 4) 우선순위 가중치 조정
    with st.expander("⚖️ 우선순위 가중치 커스텀", expanded=False):
        st.caption("원하는 기준의 비중을 높이면 추천 순위에 더 많이 반영됩니다.")
        w_price = st.slider("1️⃣ 가격대 적합도", 0.0, 1.0, 0.35, step=0.05)
        w_room = st.slider("2️⃣ 룸 / 단체석 확보", 0.0, 1.0, 0.30, step=0.05)
        w_access = st.slider("3️⃣ 판교역 접근성(거리)", 0.0, 1.0, 0.20, step=0.05)
        w_rating = st.slider("4️⃣ 평점 및 리뷰 신뢰도", 0.0, 1.0, 0.15, step=0.05)

    weights = {
        "price": w_price,
        "room": w_room,
        "access": w_access,
        "rating": w_rating,
    }

# 8. 데이터 필터링 및 스코어 계산
if not df_raw.empty:
    df = df_raw.copy()

    # 1) 메뉴 카테고리 필터
    if cuisine_choice != "전체":
        df = df[df["cuisine_type"] == cuisine_choice]

    # 2) 휴무일 계산 및 필터
    df["open_status"] = df["closed_days"].apply(
        lambda cd: check_open_status(cd, selected_date)
    )
    df = df[df["open_status"] != "휴무"]

    # 3) 스코어 계산 및 정렬
    df["match_score"] = df.apply(
        lambda r: score_row(r, budget=budget, headcount=headcount, weights=weights),
        axis=1,
    )
    df = df.sort_values(by="match_score", ascending=False).reset_index(drop=True)

    # 9. 상단 요약 메트릭 카드
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📋 추천 후보 식당", f"{len(df)} 곳")
    with col2:
        top_name = df.iloc[0]["name"] if not df.empty else "-"
        st.metric("🥇 1위 추천 장소", top_name)
    with col3:
        st.metric("👥 설정 인원 / 1인 예산", f"{headcount}명 / {budget:,}원")
    with col4:
        st.metric("📅 회식 요일", f"{weekday_name}요일")

    st.markdown("<br>", unsafe_allow_html=True)

    # 10. 탭 화면 구성
    tab1, tab2, tab3 = st.tabs(["🏆 맞춤 추천 순위 (카드 뷰)", "🗺️ 위치 지도 보기", "📊 전체 데이터 표"])

    # --- TAB 1: 추천 카드 뷰 ---
    with tab1:
        if df.empty:
            st.warning("선택하신 조건에 부합하는 식당이 없습니다. 사이드바 필터를 변경해 보세요.")
        else:
            for rank, (_, row) in enumerate(df.iterrows(), start=1):
                with st.container(border=True):
                    # 상단 배지 영역
                    b_col1, b_col2 = st.columns([4, 1])
                    with b_col1:
                        cuisine_tag = row.get("cuisine_type", "기타")
                        cat_tag = row.get("category", "")
                        score_val = safe_float(row.get("match_score"), 0.0)
                        status_val = row.get("open_status", "영업")

                        status_html = ""
                        if status_val == "정보없음":
                            status_html = '<span class="warn-badge">⚠️ 휴무일 확인 필요</span>'
                        elif status_val == "영업":
                            status_html = '<span class="open-badge">✅ 정상영업</span>'

                        st.markdown(
                            f'<span class="custom-badge">{cuisine_tag}</span>'
                            f'<span class="custom-badge">{cat_tag}</span>'
                            f'<span class="score-badge">적합도 {score_val:.1f}점</span>'
                            f'{status_html}',
                            unsafe_allow_html=True,
                        )
                    with b_col2:
                        st.markdown(f'<div style="text-align:right;"><span class="rank-badge">추천 {rank}위</span></div>', unsafe_allow_html=True)

                    # 식당명
                    st.subheader(f"🍴 {row.get('name', '식당명')}")

                    # 식당 세부 정보
                    has_room_val = bool(row.get("has_private_room", False))
                    room_txt = "🚪 단독 룸 보유" if has_room_val else "테이블석"
                    max_seats_val = safe_int(row.get("group_seating_max"), 20)
                    price_val = safe_int(row.get("price_per_person"), 30000)
                    dist_val = safe_float(row.get("distance_m_from_hub"), 500.0)
                    rating_val = safe_float(row.get("rating"), 4.0)
                    review_val = safe_int(row.get("review_count"), 50)
                    phone_val = row.get("phone", "-")
                    address_val = row.get("address_road", "")

                    c_info1, c_info2 = st.columns([3, 1])
                    with c_info1:
                        st.markdown(
                            f"📍 **주소:** {address_val} *(판교역에서 약 **{dist_val:.0f}m**)*  \n"
                            f"💵 **1인 예상 예산:** **{price_val:,}원** &nbsp;|&nbsp; 👥 **공간:** {room_txt} *(최대 {max_seats_val}명 단체 가능)*  \n"
                            f"⭐ **평점:** {rating_val:.1f}점 &nbsp;|&nbsp; 📝 **리뷰:** {review_val:,}건 &nbsp;|&nbsp; 📞 **전화:** `{phone_val}`"
                        )
                    with c_info2:
                        place_url = row.get("place_url", "https://map.kakao.com")
                        st.link_button("🗺️ 카카오맵 상세", url=place_url, use_container_width=True)

    # --- TAB 2: 인터랙티브 지도 보기 (좌표, 주소, 툴팁) ---
    with tab2:
        st.subheader("📍 판교 회식 후보지 인터랙티브 지도")
        st.caption("지도 위의 점에 마우스를 올리면 **식당명, 도로명 주소, 위도/경도 좌표, 예상 가격**이 툴팁으로 표시됩니다.")

        valid_geo_df = df.dropna(subset=["lat", "lng"]).copy()
        if not valid_geo_df.empty:
            # 툴팁용 텍스트 필드 생성
            valid_geo_df["lat_str"] = valid_geo_df["lat"].apply(lambda v: f"{v:.5f}")
            valid_geo_df["lng_str"] = valid_geo_df["lng"].apply(lambda v: f"{v:.5f}")
            valid_geo_df["price_str"] = valid_geo_df["price_per_person"].apply(lambda v: f"{v:,}원")
            valid_geo_df["rating_str"] = valid_geo_df["rating"].apply(lambda v: f"{v:.1f}점")

            # Pydeck 레이어 구성 (판교역 중심)
            view_state = pdk.ViewState(
                latitude=37.3965,
                longitude=127.1115,
                zoom=14.2,
                pitch=20,
            )

            layer = pdk.Layer(
                "ScatterplotLayer",
                data=valid_geo_df,
                get_position=["lng", "lat"],
                get_radius=50,
                get_fill_color=[11, 79, 158, 210],
                get_line_color=[255, 255, 255],
                line_width_min_pixels=2,
                pickable=True,
                auto_highlight=True,
            )

            tooltip = {
                "html": """
                <div style="font-family: sans-serif; padding: 6px 10px; background-color: #0B4F9E; color: white; border-radius: 8px; font-size: 13px;">
                    <b style="font-size: 15px; color: #64B5F6;">{name}</b> <span style="background: rgba(255,255,255,0.2); padding: 2px 6px; border-radius: 4px; font-size: 11px;">{cuisine_type}</span><br/>
                    📍 <b>도로명주소:</b> {address_road}<br/>
                    🌐 <b>좌표(위도/경도):</b> ({lat_str}, {lng_str})<br/>
                    💵 <b>1인 예산:</b> {price_str} &nbsp;|&nbsp; ⭐ <b>평점:</b> {rating_str}
                </div>
                """,
                "style": {"zIndex": "10000"},
            }

            st.pydeck_chart(
                pdk.Deck(
                    layers=[layer],
                    initial_view_state=view_state,
                    tooltip=tooltip,
                    map_style="road",
                )
            )

            # 지도 하단: 주소 & 좌표 상세 목록 테이블
            st.markdown("#### 📌 후보 식당별 상세 좌표 및 주소 안내")
            st.dataframe(
                valid_geo_df[
                    [
                        "name",
                        "cuisine_type",
                        "address_road",
                        "lat",
                        "lng",
                        "distance_m_from_hub",
                        "phone",
                    ]
                ].rename(
                    columns={
                        "name": "식당명",
                        "cuisine_type": "메뉴",
                        "address_road": "도로명 주소",
                        "lat": "위도 (Latitude)",
                        "lng": "경도 (Longitude)",
                        "distance_m_from_hub": "판교역 거리(m)",
                        "phone": "전화번호",
                    }
                ),
                use_container_width=True,
            )
        else:
            st.info("지도에 표시할 위치 좌표가 없습니다.")

    # --- TAB 3: 전체 데이터 표 ---
    with tab3:
        st.subheader("📋 추천 데이터 전체 비교")
        display_df = df[
            [
                "name",
                "cuisine_type",
                "match_score",
                "price_per_person",
                "has_private_room",
                "group_seating_max",
                "distance_m_from_hub",
                "rating",
                "review_count",
                "phone",
                "address_road",
            ]
        ].copy().rename(
            columns={
                "name": "식당명",
                "cuisine_type": "메뉴",
                "match_score": "적합도(점)",
                "price_per_person": "1인예산(원)",
                "has_private_room": "룸유무",
                "group_seating_max": "최대좌석",
                "distance_m_from_hub": "판교역거리(m)",
                "rating": "평점",
                "review_count": "리뷰수",
                "phone": "전화번호",
                "address_road": "도로명주소",
            }
        )
        st.dataframe(display_df, use_container_width=True)

else:
    st.info("데이터를 불러오는 중입니다...")
