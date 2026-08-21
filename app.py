"""대한민국 전역 맞춤형 회식장소 추천 서비스 (Streamlit Application)"""

import datetime
import os
import urllib.parse
from typing import Any, Dict, Tuple
import pandas as pd
import pydeck as pdk
import streamlit as st

from pipeline.geo_utils import (
    NATIONWIDE_HUBS,
    calculate_haversine_distance,
    geocode_keyword,
)
from pipeline.scoring import safe_float, safe_int, score_row

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="대한민국 맞춤형 회식장소 추천 서비스",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. GBSA 및 모던 테크 디자인 CSS
st.markdown(
    """
<style>
    /* 기본 테마 컬러 정의 (GBSA 딥 네이비 & 비즈니스 블루) */
    :root {
        --primary-blue: #0B4F9E;
        --secondary-blue: #2E86DE;
        --accent-blue: #48DBFB;
        --soft-bg: #F0F4F8;
        --card-border: #D1D8E0;
    }

    /* 헤더 배너 스타일 */
    .header-box {
        background: linear-gradient(135deg, #0B4F9E 0%, #1B68C2 50%, #2E86DE 100%);
        padding: 24px 30px;
        border-radius: 12px;
        color: #ffffff;
        margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(11, 79, 158, 0.15);
    }
    .header-box h1 {
        color: #ffffff !important;
        font-size: 26px !important;
        font-weight: 700;
        margin: 0 0 8px 0 !important;
    }
    .header-box p {
        color: #E2E8F0 !important;
        font-size: 14px;
        margin: 0 !important;
    }

    /* 커스텀 배지 스타일 */
    .custom-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 16px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 6px;
        background-color: #E8F1FC;
        color: #0B4F9E;
        border: 1px solid #BFD9F8;
    }
    .region-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 16px;
        font-size: 12px;
        font-weight: 700;
        margin-right: 6px;
        background-color: #0B4F9E;
        color: #ffffff;
    }
    .score-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 16px;
        font-size: 12px;
        font-weight: 700;
        margin-right: 6px;
        background-color: #E6FBF5;
        color: #00875A;
        border: 1px solid #B3F5E3;
    }
    .warn-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 16px;
        font-size: 11px;
        font-weight: 600;
        background-color: #FFF4E5;
        color: #DE350B;
        border: 1px solid #FFD2B2;
    }
    .open-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 16px;
        font-size: 11px;
        font-weight: 600;
        background-color: #E3FCEF;
        color: #006644;
        border: 1px solid #ABF5D1;
    }
    .rank-badge {
        font-size: 13px;
        font-weight: 800;
        background-color: #0B4F9E;
        color: #ffffff;
        padding: 4px 12px;
        border-radius: 20px;
    }
</style>
""",
    unsafe_allow_html=True,
)


# 3. 데이터 로드 및 전처리
@st.cache_data
def load_restaurant_data() -> pd.DataFrame:
    csv_path = os.path.join(
        os.path.dirname(__file__), "data", "restaurants.csv"
    )
    if not os.path.exists(csv_path):
        st.error(f"데이터 파일이 존재하지 않습니다: {csv_path}")
        return pd.DataFrame()

    df = pd.read_csv(csv_path, encoding="utf-8")
    df["rating"] = df["rating"].apply(lambda v: safe_float(v, 4.0))
    df["review_count"] = df["review_count"].apply(lambda v: safe_int(v, 50))
    df["price_per_person"] = df["price_per_person"].apply(
        lambda v: safe_int(v, 30000)
    )
    df["group_seating_max"] = df["group_seating_max"].apply(
        lambda v: safe_int(v, 20)
    )
    df["lat"] = df["lat"].apply(lambda v: safe_float(v, 37.3947))
    df["lng"] = df["lng"].apply(lambda v: safe_float(v, 127.1112))
    df["closed_days"] = df["closed_days"].fillna("").astype(str)
    df["region"] = df["region"].fillna("기타").astype(str)
    return df


def main():
    raw_df = load_restaurant_data()
    if raw_df.empty:
        st.error("데이터셋을 로드할 수 없습니다.")
        return

    # 요일 매핑 딕셔너리
    weekday_kr = {
        0: "월",
        1: "화",
        2: "수",
        3: "목",
        4: "금",
        5: "토",
        6: "일",
    }
    weekday_names = {
        0: "월요일",
        1: "화요일",
        2: "수요일",
        3: "목요일",
        4: "금요일",
        5: "토요일",
        6: "일요일",
    }

    # ==========================
    # 사이드바: 회식 조건 입력
    # ==========================
    st.sidebar.header("🎯 회식 조건 및 위치 설정")

    # [1] 전국 위치 및 권역 설정
    st.sidebar.subheader("📍 1. 회식 지역 / 위치")
    loc_mode = st.sidebar.radio(
        "위치 선택 방식",
        ["🏢 주요 비즈니스 권역 선택", "🔍 지하철역/지명 직접 검색"],
        horizontal=False,
    )

    current_hub_name = "판교테크노밸리"
    current_hub_lat = 37.3947
    current_hub_lng = 127.1112
    filter_region_key = "전체"

    if loc_mode == "🏢 주요 비즈니스 권역 선택":
        hub_options = ["전체 (전국 통합 추천)"] + [
            f"{k} - {info['name']}" for k, info in NATIONWIDE_HUBS.items()
        ]
        selected_hub_str = st.sidebar.selectbox("비즈니스 권역 선택", hub_options, index=1)

        if selected_hub_str.startswith("전체"):
            filter_region_key = "전체"
            current_hub_name = "전국 중심 (판교 기준)"
        else:
            filter_region_key = selected_hub_str.split(" - ")[0]
            hub_data = NATIONWIDE_HUBS[filter_region_key]
            current_hub_name = hub_data["name"]
            current_hub_lat = hub_data["lat"]
            current_hub_lng = hub_data["lng"]
            st.sidebar.caption(f"💡 *{hub_data['desc']}*")
    else:
        custom_query = st.sidebar.text_input(
            "지하철역 또는 지명 입력",
            value="강남역",
            placeholder="예: 삼성역, 을지로입구, 해운대, 서면",
        )
        geo_res = geocode_keyword(custom_query)
        if geo_res:
            current_hub_lat, current_hub_lng, current_hub_name = geo_res
            filter_region_key = "전체"
            st.sidebar.success(f"📍 기준 위치: **{current_hub_name}**")
        else:
            st.sidebar.warning("입력하신 위치를 찾을 수 없어 기본(판교)으로 설정됩니다.")

    search_radius_m = st.sidebar.slider(
        "기준 위치 탐색 반경",
        min_value=500,
        max_value=5000,
        value=3000,
        step=500,
        format="%d m",
    )

    st.sidebar.markdown("---")

    # [2] 회식 후보 일정 다중 선택 (중복/복수 날짜 지원)
    st.sidebar.subheader("📅 2. 회식 후보 일정 (다중 선택)")
    today = datetime.date.today()

    # 향후 30일간의 날짜 목록 생성 (한국어 요일 포함)
    upcoming_dates = []
    date_map = {}
    for i in range(30):
        d = today + datetime.timedelta(days=i)
        w_kr = weekday_kr[d.weekday()]
        label = f"{d.strftime('%Y-%m-%d')} ({w_kr}요일)"
        upcoming_dates.append(label)
        date_map[label] = (d, w_kr)

    # 기본값: 이번 주/다음 주 목요일, 금요일 2개 날짜를 기본 후보로 선택
    default_selected = []
    for lbl in upcoming_dates[:14]:
        if "목요일" in lbl or "금요일" in lbl:
            default_selected.append(lbl)
            if len(default_selected) >= 2:
                break
    if not default_selected:
        default_selected = [upcoming_dates[0]]

    selected_date_labels = st.sidebar.multiselect(
        "회식 후보 날짜 (복수 선택 가능)",
        options=upcoming_dates,
        default=default_selected,
        help="여러 후보 날짜를 선택하시면 모든 후보일에 예약 가능한 식당을 분석합니다.",
    )

    if not selected_date_labels:
        selected_date_labels = [upcoming_dates[0]]
        st.sidebar.caption("⚠️ 최소 1개 이상의 날짜가 필요하여 오늘 날짜가 기본 선택되었습니다.")

    # 선택된 날짜 객체 및 요일 리스트
    selected_date_objs = [date_map[lbl] for lbl in selected_date_labels if lbl in date_map]
    date_summary_str = ", ".join([f"{d.month}/{d.day}({w})" for d, w in selected_date_objs[:3]])
    if len(selected_date_objs) > 3:
        date_summary_str += f" 외 {len(selected_date_objs)-3}일"

    st.sidebar.caption(f"선택된 후보일: **총 {len(selected_date_objs)}개 일자** ({date_summary_str})")

    filter_strict_open = st.sidebar.checkbox(
        "선택한 모든 후보일에 영업하는 곳만 보기",
        value=True,
        help="체크 시 선택하신 모든 후보일에 휴무가 없는 식당만 추천합니다.",
    )

    st.sidebar.markdown("---")

    # [3] 메뉴 카테고리 필터
    st.sidebar.subheader("🍴 3. 메뉴 카테고리")
    cuisine_choice = st.sidebar.radio(
        "선호 메뉴",
        ["전체", "한식", "중식", "일식", "양식"],
        horizontal=True,
    )

    st.sidebar.markdown("---")

    # [4] 1인 예산 및 인원수
    st.sidebar.subheader("💵 4. 예산 및 인원수")
    target_budget = st.sidebar.slider(
        "1인 목표 예산 (원)",
        min_value=10000,
        max_value=150000,
        value=45000,
        step=5000,
        format="%d원",
    )
    target_headcount = st.sidebar.slider(
        "회식 인원수 (명)",
        min_value=2,
        max_value=60,
        value=8,
        step=1,
        format="%d명",
    )

    # [5] 우선순위 가중치 커스텀
    with st.sidebar.expander("🎛️ 우선순위 가중치 커스텀", expanded=False):
        st.caption("원하는 기준의 비중을 높이면 추천 순위에 즉시 반영됩니다.")
        w_price = st.slider("1. 가격대 적합도", 0.0, 1.0, 0.35, 0.05)
        w_room = st.slider("2. 룸 / 단체석 확보", 0.0, 1.0, 0.30, 0.05)
        w_access = st.sidebar.slider if False else st.slider("3. 기준 위치 접근성(거리)", 0.0, 1.0, 0.20, 0.05)
        w_rating = st.slider("4. 평점 및 리뷰 신뢰도", 0.0, 1.0, 0.15, 0.05)

    weights = {
        "price": w_price,
        "room": w_room,
        "access": w_access,
        "rating": w_rating,
    }

    # ==========================
    # 메인 헤더 배너
    # ==========================
    st.markdown(
        f"""
    <div class="header-box">
        <h1>🏢 대한민국 맞춤형 회식장소 추천 서비스 (전국 확장판)</h1>
        <p>전국 주요 비즈니스 권역 및 지하철역 기준 다차원(예산·인원·룸·거리·평점) 스코어링 기반 최적의 회식 장소를 추천합니다. (현재 기준: <b>{current_hub_name}</b>)</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # ==========================
    # 데이터 필터링 & 동적 거리 계산 & 스코어링
    # ==========================
    df = raw_df.copy()

    # 1. 권역 필터 (전체가 아닐 경우)
    if filter_region_key != "전체":
        df = df[df["region"] == filter_region_key]

    # 2. 메뉴 카테고리 필터
    if cuisine_choice != "전체":
        df = df[df["cuisine_type"] == cuisine_choice]

    # 3. 실시간 하버사인 동적 거리 계산 (m)
    df["distance_m_from_hub"] = df.apply(
        lambda r: calculate_haversine_distance(
            current_hub_lat, current_hub_lng, r["lat"], r["lng"]
        ),
        axis=1,
    )

    # 4. 반경 필터링 (선택적: 해당 반경 내 식당 우선 또는 포함)
    if filter_region_key == "전체" and loc_mode == "🔍 지하철역/지명 직접 검색":
        df = df[df["distance_m_from_hub"] <= (search_radius_m * 1.5)]

    # 5. 다중 후보일 휴무 판정
    def evaluate_multi_dates_open(closed_str: str, date_objs: list) -> Tuple[str, str]:
        if not closed_str or closed_str.strip() == "":
            return "정보없음", "휴무 정보 없음"
        closed_list = [d.strip() for d in str(closed_str).split(",")]

        conflict_labels = []
        for d_obj, w_code in date_objs:
            if w_code in closed_list:
                conflict_labels.append(f"{d_obj.month}/{d_obj.day}({w_code})")

        if conflict_labels:
            return "일부휴무", f"⚠️ {', '.join(conflict_labels)} 휴무"
        return "영업", "✅ 모든 후보일 영업"

    df_status_res = df["closed_days"].apply(
        lambda cd: evaluate_multi_dates_open(cd, selected_date_objs)
    )
    df["open_status"] = [s[0] for s in df_status_res]
    df["open_desc"] = [s[1] for s in df_status_res]

    # 사용자가 '모든 후보일에 영업하는 곳만 보기'를 선택했을 경우 일부 휴무 식당 필터링
    if filter_strict_open:
        df = df[df["open_status"] != "일부휴무"]

    # 6. 다차원 적합도 스코어링 계산
    df["match_score"] = df.apply(
        lambda row: score_row(row, target_budget, target_headcount, weights),
        axis=1,
    )

    # 점수 내림차순 정렬
    df = df.sort_values(by="match_score", ascending=False).reset_index(drop=True)

    # ==========================
    # 상단 요약 카드 (Metrics)
    # ==========================
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(label="📋 추천 후보 식당", value=f"{len(df)} 곳")
    with m2:
        top_name = df.iloc[0]["name"] if not df.empty else "추천 결과 없음"
        st.metric(label="🥇 1위 추천 장소", value=top_name)
    with m3:
        st.metric(
            label="👥 설정 인원 / 1인 예산",
            value=f"{target_headcount}명 / {target_budget:,}원",
        )
    with m4:
        st.metric(
            label="📍 기준 위치 / 후보일수",
            value=f"{current_hub_name[:6]}.. / {len(selected_date_objs)}개 일자",
        )

    st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

    # ==========================
    # 3대 탭 인터페이스
    # ==========================
    tab1, tab2, tab3 = st.tabs(
        ["🏆 맞춤 추천 순위 (카드 뷰)", "🗺️ 위치 지도 보기", "📊 전체 데이터 표"]
    )

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
                        reg_tag = row.get("region", "전국")
                        cuisine_tag = row.get("cuisine_type", "기타")
                        cat_tag = row.get("category", "")
                        score_val = safe_float(row.get("match_score"), 0.0)
                        status_val = row.get("open_status", "영업")

                        status_html = ""
                        if status_val == "정보없음":
                            status_html = '<span class="warn-badge">⚠️ 휴무일 확인 필요</span>'
                        elif status_val == "영업":
                            status_html = '<span class="open-badge">✅ 모든 후보일 영업</span>'
                        elif status_val == "일부휴무":
                            desc_txt = row.get("open_desc", "일부 후보일 휴무")
                            status_html = f'<span class="warn-badge">{desc_txt}</span>'

                        st.markdown(
                            f'<span class="region-badge">📍 {reg_tag}</span>'
                            f'<span class="custom-badge">{cuisine_tag}</span>'
                            f'<span class="custom-badge">{cat_tag}</span>'
                            f'<span class="score-badge">적합도 {score_val:.1f}점</span>'
                            f'{status_html}',
                            unsafe_allow_html=True,
                        )
                    with b_col2:
                        st.markdown(
                            f'<div style="text-align:right;"><span class="rank-badge">추천 {rank}위</span></div>',
                            unsafe_allow_html=True,
                        )

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
                            f"📍 **주소:** {address_val} *(기준 위치에서 약 **{dist_val:.0f}m**)*  \n"
                            f"💵 **1인 예상 예산:** **{price_val:,}원** &nbsp;|&nbsp; 👥 **공간:** {room_txt} *(최대 {max_seats_val}명 단체 가능)*  \n"
                            f"⭐ **평점:** {rating_val:.1f}점 &nbsp;|&nbsp; 📝 **리뷰:** {review_val:,}건 &nbsp;|&nbsp; 📞 **전화:** `{phone_val}`"
                        )
                    with c_info2:
                        place_name = str(row.get("name", "식당"))
                        encoded_query = urllib.parse.quote(place_name)
                        kakao_search_url = f"https://map.kakao.com/link/search/{encoded_query}"
                        st.link_button("🗺️ 카카오맵 상세", url=kakao_search_url, use_container_width=True)

    # --- TAB 2: 인터랙티브 지도 보기 (좌표, 주소, 툴팁) ---
    with tab2:
        st.subheader(f"📍 {current_hub_name} 주변 회식 후보지 인터랙티브 지도")
        st.caption("지도 위의 점에 마우스를 올리면 **식당명, 도로명 주소, 위도/경도 좌표, 예상 가격**이 툴팁으로 표시됩니다.")

        valid_geo_df = df.dropna(subset=["lat", "lng"]).copy()
        if not valid_geo_df.empty:
            valid_geo_df["lat_str"] = valid_geo_df["lat"].apply(lambda v: f"{v:.5f}")
            valid_geo_df["lng_str"] = valid_geo_df["lng"].apply(lambda v: f"{v:.5f}")
            valid_geo_df["price_str"] = valid_geo_df["price_per_person"].apply(lambda v: f"{v:,}원")
            valid_geo_df["rating_str"] = valid_geo_df["rating"].apply(lambda v: f"{v:.1f}점")

            # 선택된 위치 중심 좌표 및 줌 레벨 결정
            center_lat = current_hub_lat if filter_region_key != "전체" else valid_geo_df["lat"].mean()
            center_lng = current_hub_lng if filter_region_key != "전체" else valid_geo_df["lng"].mean()
            zoom_level = 13.5 if filter_region_key != "전체" else 10.5

            layer = pdk.Layer(
                "ScatterplotLayer",
                data=valid_geo_df,
                get_position=["lng", "lat"],
                get_radius=80,
                get_fill_color=[11, 79, 158, 200],  # GBSA Blue
                pickable=True,
                auto_highlight=True,
            )

            view_state = pdk.ViewState(
                latitude=center_lat,
                longitude=center_lng,
                zoom=zoom_level,
                pitch=25,
            )

            tooltip_html = {
                "html": """
                <div style="font-family: sans-serif; font-size: 13px; line-height: 1.5; color: #1e293b; padding: 4px;">
                    <b style="font-size: 15px; color: #0B4F9E;">🍴 {name}</b> ({region})<br/>
                    <b>📍 도로명:</b> {address_road}<br/>
                    <b>🧭 좌표:</b> 위도 {lat_str}, 경도 {lng_str}<br/>
                    <b>💵 1인 예산:</b> {price_str} &nbsp;|&nbsp; <b>⭐ 평점:</b> {rating_str}
                </div>
                """,
                "style": {
                    "backgroundColor": "#ffffff",
                    "color": "#1e293b",
                    "border": "1px solid #cbd5e1",
                    "boxShadow": "0 4px 12px rgba(0,0,0,0.15)",
                    "borderRadius": "8px",
                    "padding": "10px",
                },
            }

            st.pydeck_chart(
                pdk.Deck(
                    layers=[layer],
                    initial_view_state=view_state,
                    tooltip=tooltip_html,
                    map_style="mapbox://styles/mapbox/light-v10",
                ),
                use_container_width=True,
            )

            # 지도 하단 좌표 및 주소 안내 표
            with st.expander("🧭 식당별 정확한 도로명 주소 및 위도/경도 좌표 목록", expanded=False):
                geo_display_df = valid_geo_df[
                    ["region", "name", "address_road", "lat", "lng", "distance_m_from_hub", "price_per_person", "rating"]
                ].rename(
                    columns={
                        "region": "권역",
                        "name": "식당명",
                        "address_road": "도로명 주소",
                        "lat": "위도 (Latitude)",
                        "lng": "경도 (Longitude)",
                        "distance_m_from_hub": "기준위치 거리 (m)",
                        "price_per_person": "1인 예산 (원)",
                        "rating": "평점",
                    }
                )
                st.dataframe(
                    geo_display_df.style.format(
                        {
                            "위도 (Latitude)": "{:.5f}",
                            "경도 (Longitude)": "{:.5f}",
                            "기준위치 거리 (m)": "{:,.0f} m",
                            "1인 예산 (원)": "{:,}원",
                            "평점": "{:.1f}점",
                        }
                    ),
                    use_container_width=True,
                )
        else:
            st.info("지도에 표시할 위치 정보가 없습니다.")

    # --- TAB 3: 전체 비교 데이터 표 ---
    with tab3:
        st.subheader("📊 조건별 전체 식당 비교 데이터")
        display_df = df[
            [
                "match_score",
                "region",
                "name",
                "cuisine_type",
                "category",
                "price_per_person",
                "has_private_room",
                "group_seating_max",
                "distance_m_from_hub",
                "rating",
                "review_count",
                "open_status",
                "address_road",
                "phone",
            ]
        ].rename(
            columns={
                "match_score": "적합도 점수",
                "region": "권역",
                "name": "식당명",
                "cuisine_type": "메뉴 대분류",
                "category": "상세 카테고리",
                "price_per_person": "1인 예상가격",
                "has_private_room": "단독룸",
                "group_seating_max": "최대단체석",
                "distance_m_from_hub": "거리(m)",
                "rating": "평점",
                "review_count": "리뷰수",
                "open_status": "영업상태",
                "address_road": "도로명 주소",
                "phone": "전화번호",
            }
        )
        st.dataframe(
            display_df.style.format(
                {
                    "적합도 점수": "{:.1f}점",
                    "1인 예상가격": "{:,}원",
                    "거리(m)": "{:,.0f} m",
                    "평점": "{:.1f}점",
                    "리뷰수": "{:,}개",
                }
            ),
            use_container_width=True,
            height=450,
        )


if __name__ == "__main__":
    main()
